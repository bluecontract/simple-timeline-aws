"""Generic selected-document processor and hosted Coordination workflows.

This executable candidate implements the explicit profile in SPECIFICATION.md.
It is NOT a substitute for the full pinned Java blue-contracts-core implementation.
"""
from __future__ import annotations
from collections import defaultdict, deque
from dataclasses import dataclass
import json
import math
from blue_bex import Engine, Context, Gas, GasExhausted, BexError, BoundaryError
from blue_bex.values import (UNDEFINED, clone, pointer_get, segments, escape, blue_value)
from .patch import ContractError, CapabilityError, boundary, apply, join_scope
from .catalogue import Catalogue, compact

@dataclass(frozen=True, init=False)
class ProcessingResult:
    """Own result snapshots; consumers cannot mutate a published result in place."""
    _document: dict
    _events: tuple
    gas_used: int
    changed: bool
    terminated: bool

    def __init__(self, document, events, gas_used, changed, terminated):
        object.__setattr__(self, '_document', clone(document))
        object.__setattr__(self, '_events', clone(tuple(events)))
        object.__setattr__(self, 'gas_used', gas_used)
        object.__setattr__(self, 'changed', changed)
        object.__setattr__(self, 'terminated', terminated)

    @property
    def document(self): return clone(self._document)

    @property
    def events(self): return clone(self._events)

class Processor:
    def __init__(self,catalogue:Catalogue,*,bex=None):
        self.catalogue=catalogue;self.bex=bex if bex is not None else Engine()

    def process(self,document,event,*,channels=(),operation=None,gas=None,gas_limit=100000,
                managed_paths=(),read_document=None,initialize_only=False,managed_children=False):
        self.catalogue.validate(document)
        run=Run(self,document,event,gas if gas is not None else Gas(gas_limit),managed_paths,read_document)
        run.managed_children=managed_children
        run.preflight('/')
        run.scope('/',tuple(channels),operation,initialize_only=initialize_only)
        return ProcessingResult(run.document,tuple(run.emitted['/']),run.gas.used-run.start_gas,
                                run.document!=document,'/'in run.terminated)

class Run:
    def __init__(self,processor,document,event,gas,managed_paths,reader):
        self.processor=processor;self.cat=processor.catalogue
        self.document=clone(document);self.event=clone(event);self.gas=gas;self.start_gas=gas.used
        self.managed_paths=tuple(managed_paths);self.reader=reader
        self.managed_children=False
        self.emitted=defaultdict(list);self.fifo=defaultdict(deque)
        self.terminated=set();self.terminating=set();self.active_scopes=[];self.cascade_depth=0

    def charge(self,name,amount):self.gas.charge('contracts.'+name,amount=amount)
    def subtree(self,s):return pointer_get(self.document,s)
    def contracts(self,s):
        node=self.subtree(s)
        if type(node) is not dict:raise ContractError('scope must be object')
        raw=self.cat.effective_contracts(node)
        if type(raw) is not dict:raise ContractError('contracts must be object')
        return raw
    def inactive(self,s):return s in self.terminated or self.subtree(s) is UNDEFINED
    def ordered(self,items):
        for k,v in items:
            if type(v.get('order',0)) is not int:raise ContractError('contract order must be Integer')
        return sorted(items,key=lambda p:(p[1].get('order',0),p[0]))

    def embedded(self,s):
        paths=[]
        for key,c in self.ordered(list(self.contracts(s).items())):
            if self.cat.role(c)!='process_embedded':continue
            for p in c.get('paths',[]):
                if type(p) is not str:raise ContractError('embedded path must be Text')
                path=join_scope(s,p)
                if path==s:raise ContractError('embedded self-root path is invalid')
                paths.append(path)
            for p in c.get('collectionPaths',[]):
                base=join_scope(s,p);collection=self.subtree(base)
                if collection is UNDEFINED:continue
                if type(collection) is not dict:raise ContractError('embedded collection must be an object')
                paths.extend(base.rstrip('/')+'/'+escape(k) for k in sorted(collection))
        if len(paths)!=len(set(paths)):raise ContractError('duplicate embedded occurrence path')
        return paths

    def preflight(self,s,seen=None):
        seen=set() if seen is None else seen
        if s in seen:return
        seen.add(s)
        if len(seen)>1024:raise CapabilityError('portable inline-scope bound exceeded')
        cs=self.contracts(s)
        used={c.get('channel') for c in cs.values() if type(c) is dict and 'channel'in c}
        for key,c in cs.items():
            if type(c) is not dict:raise CapabilityError('contract entry must be object')
            role=self.cat.role(c)
            if role is None and (c.get('mustUnderstand') is True or key in used):raise CapabilityError('unknown required exact contract type')
            if role=='generalization_policy':raise CapabilityError('nearest-valid generalization adapter is not implemented')
            if role in {'initialized','terminated','checkpoint'} and key not in {'initialized','terminated','checkpoint'}:
                raise CapabilityError('required runtime marker at noncanonical key')
        for p in self.embedded(s):
            if not self.managed_children and p not in self.managed_paths and self.subtree(p) is not UNDEFINED:self.preflight(p,seen)

    def scope(self,s,channels,operation,*,initialize_only=False):
        self.charge('scopeEntry',50+10*len(self.active_scopes))
        if self.subtree(s) is UNDEFINED:return
        if self.cat.role(self.contracts(s).get('terminated'))=='terminated':self.terminated.add(s);return
        self.active_scopes.append(s);processed=[];bridged=set()
        def discover_children():
            if self.managed_children:return False
            added=False
            while True:
                todo=[p for p in self.embedded(s) if p not in processed and p not in self.managed_paths]
                if not todo:break
                child=todo[0];processed.append(child);added=True
                if len(processed)>1024:raise CapabilityError('inline occurrence work bound exceeded')
                if self.subtree(child) is not UNDEFINED:
                    self.preflight(child)
                    self.scope(child,(),None,initialize_only=initialize_only)
                if self.inactive(s):break
            return added
        try:
            discover_children()
            if self.inactive(s):return
            if 'initialized'not in self.contracts(s):self.initialize(s)
            if self.inactive(s):return
            if not initialize_only:
                for key in channels:
                    c=self.contracts(s).get(key)
                    if c is None:raise ContractError('selected channel missing')
                    self.handlers(s,key,self.event,operation)
                    if self.inactive(s):break
            # Discover newly inserted inline scopes in this same local PROCESS.
            # Independently managed children remain exclusively the host's job.
            discover_children()
            while not self.inactive(s):
                for child in processed:
                    if child in bridged:continue
                    bridged.add(child)
                    for event in tuple(self.emitted[child]):
                        rel='/'+'/'.join(escape(x) for x in segments(child)[len(segments(s)):])
                        matching=self.matching_channels(s,'embedded_channel',event,source_path=rel)
                        if matching:self.charge('bridge',10)
                        for key,_ in matching:self.handlers(s,key,event,None)
                self.drain(s)
                if not discover_children():break
        finally:self.active_scopes.pop()

    def initialize(self,s):
        self.charge('initialize',1000)
        prior=self.cat.validate(self.subtree(s)).blue_id
        self.lifecycle(s,self.cat.initialization_value('Document Processing Initiated',prior))
        if not self.inactive(s):
            self.patch(s,{'op':'add','path':join_scope(s,'/contracts/initialized'),
                        'val':self.cat.initialization_value('Processing Initialized Marker',prior)},internal=True)

    def matching_channels(self,s,role,event,*,source_path=None,changed_path=None):
        result=[]
        for key,c in self.ordered(list(self.contracts(s).items())):
            if self.cat.role(c)!=role:continue
            if source_path is not None and c.get('sourcePath')!=source_path:continue
            if changed_path is not None:
                expected=join_scope(s,c.get('path','/'))
                if not (changed_path==expected or changed_path.startswith(expected.rstrip('/')+'/')):continue
            if 'event'in c and not self.cat.matches(event,c['event']):continue
            result.append((key,c))
        return result

    def handlers(self,s,channel,event,operation):
        cs=self.contracts(s);handlers=[]
        for key,h in cs.items():
            role=self.cat.role(h)
            if h.get('channel')!=channel or role not in {'workflow','operation'}:continue
            if role=='operation' and key!=operation:continue
            if role=='workflow' and operation is not None:continue
            if 'event'in h and not self.cat.matches(event,h['event']):continue
            handlers.append((key,h))
        for key,h in self.ordered(handlers):
            if self.inactive(s):return
            self.charge('handler',50)
            steps=h.get('steps',[])
            if type(steps) is not list:raise ContractError('workflow steps must be list')
            results={}
            for i,step in enumerate(steps):
                if self.inactive(s):break
                role=self.cat.role(step)
                if role=='compute':
                    limit=step.get('gasLimit',100000)
                    if type(limit) is not int or limit<=0:raise ContractError('Compute gasLimit must be positive')
                    meter=Gas(limit,parent=self.gas,owner=self.gas.owner)
                    # A BEX invocation sees a stable selected snapshot. Patches are
                    # applied only after all returned effects have been validated.
                    # The selected Contracts scope IS the BEX document. Absolute
                    # pointers are local to it, not capabilities to the parent.
                    snapshot=clone(self.document)
                    def scoped_reader(path,view,local_document):
                        if self.reader is None:return pointer_get(local_document,path)
                        selected=(local_document if s=='/' else apply(snapshot,
                            {'op':'replace','path':s,'val':local_document}))
                        return self.reader(join_scope(s,path),view,selected)
                    context=Context(document=clone(self.subtree(s)),event=clone(event),
                        current_contract=clone(h),steps=clone(results),bindings={'event':clone(event)},
                        scope='/',read_document=scoped_reader,matcher=self.cat.matches)
                    result=self.processor.bex.execute(step,context,gas=meter)
                    returned=result.value if type(result.value) is dict else {}
                    patches=returned.get('changeset',UNDEFINED)
                    if patches is None or patches is UNDEFINED:patches=result.changeset
                    events=returned.get('events',UNDEFINED)
                    if events is None or events is UNDEFINED:events=result.events
                    if not step.get('emitEvents',True):events=[]
                    termination=returned.get('termination',None)
                    # BEX returns scope-local patches; remap only at the Contracts
                    # boundary, after normal BEX effect construction.
                    if type(patches) is list:
                        patches=clone(patches)
                        for patch in patches:
                            if type(patch) is not dict:raise ContractError('effect patch must be object')
                            patch['path']=join_scope(s,patch.get('path'))
                    self.effects(s,patches,events,termination)
                    if step.get('returnResult',True):results[step.get('name',str(i))]=clone(result.value)
                elif role=='trigger_event':
                    if 'event'not in step:raise ContractError('Trigger Event event is required')
                    self.effects(s,[],[step['event']],None)
                elif role=='update_document':
                    patches=clone(step.get('changeset',[]))
                    if type(patches) is not list:raise ContractError('Update Document must have static changeset list')
                    for p in patches:
                        if type(p) is not dict:raise ContractError('static patch must be object')
                        p['path']=join_scope(s,p.get('path'))
                    self.effects(s,patches,[],None)
                elif role=='terminate_step':self.terminate(s,step.get('cause','graceful'),step.get('reason'))
                else:raise CapabilityError('unsupported exact workflow-step runtime')

    def effects(self,s,patches,events,termination):
        if type(patches) is not list or type(events) is not list:raise ContractError('Compute effects must be lists')
        checked_p=[];checked_e=[]
        for p in patches:
            if type(p) is not dict or set(p)-{'op','path','val'} or not {'op','path'}<=p.keys():raise ContractError('invalid effect patch')
            if p['op']not in {'add','replace','remove'}:raise ContractError('unsupported effect operation')
            segments(p['path']);q=clone(p)
            if p['op']=='remove':
                if 'val'in p:raise ContractError('remove val must be absent')
            else:
                if 'val'not in p:raise ContractError('patch val missing')
                _,q['val']=self.cat.admit(blue_value(p['val']),goal='value')
            checked_p.append(q)
        for event in events:
            _,normalized=self.cat.admit(blue_value(event),goal='value');checked_e.append(normalized)
        if termination is not None:
            if type(termination) is not dict or set(termination)-{'cause','reason'} or termination.get('cause')not in {'graceful','fatal'}:raise ContractError('invalid termination result')
            if 'reason'in termination and type(termination['reason']) is not str:raise ContractError('termination reason must be Text')
        for p in checked_p:
            if self.inactive(s):return
            self.patch(s,p)
        for e in checked_e:
            if self.inactive(s):return
            self.emit(s,e)
        if termination is not None and not self.inactive(s):self.terminate(s,termination['cause'],termination.get('reason'))

    def byte_size(self,value):
        # Reuses Language's canonical JSON emitter, NOT its content hash. See
        # profile limitations for selected-view tariffs and checked-node counts.
        from algorithms import blue as L
        return len(L.canonical_text(self.cat.normalize_types(value)).encode('utf-8'))

    def patch(self,s,p,*,internal=False):
        if not internal:self.charge('boundary',2)
        managed=self.managed_paths
        if self.managed_children:managed=tuple(set(managed)|set(self.embedded('/')))
        boundary(s,p['path'],managed,internal=internal)
        before=clone(pointer_get(self.document,p['path']))
        candidate=apply(self.document,p)
        self.charge('patch',10 if p['op']=='remove' else 20+math.ceil(self.byte_size(p['val'])/100))
        self.charge('typeCheck',5*(len(segments(p['path']))+1))
        self.cat.validate(candidate)  # No type erasure fallback; rejection stays rejection.
        self.document=candidate
        after=clone(pointer_get(self.document,p['path']))
        payload=self.cat.typed('Document Update',op=p['op'],path=p['path'],
            **({'before':before} if before is not UNDEFINED else {}),
            **({'after':after} if after is not UNDEFINED else {}))
        self.cascade_depth+=1
        if self.cascade_depth>128:raise CapabilityError('portable cascade depth limit exceeded')
        try:
            for receiver in reversed(self.active_scopes):
                if self.inactive(receiver):continue
                matches=self.matching_channels(receiver,'update_channel',payload,changed_path=p['path'])
                if matches:self.charge('cascade',10)
                for key,_ in matches:self.handlers(receiver,key,payload,None)
        finally:self.cascade_depth-=1
        # Topology changing inside a local PROCESS is discovered on the next
        # traversal/recompile; the managed closure owns graph-level admission.

    def emit(self,s,event):
        if self.inactive(s):return
        self.cat.validate(event,goal='value');self.charge('emit',20+math.ceil(self.byte_size(event)/100))
        self.emitted[s].append(clone(event));self.fifo[s].append(clone(event))

    def drain(self,s):
        if not any(self.cat.role(c)=='triggered_channel' for c in self.contracts(s).values()):return
        while self.fifo[s] and not self.inactive(s):
            event=self.fifo[s].popleft();self.charge('fifo',10)
            for key,_ in self.matching_channels(s,'triggered_channel',event):self.handlers(s,key,event,None)

    def lifecycle(self,s,event):
        self.charge('lifecycle',30);self.emitted[s].append(clone(event))
        for key,_ in self.matching_channels(s,'lifecycle_channel',event):self.handlers(s,key,event,None)

    def terminate(self,s,cause,reason):
        if s in self.terminating or s in self.terminated:return
        if cause not in {'graceful','fatal'}:raise ContractError('invalid termination cause')
        self.terminating.add(s);self.charge('terminationMarker',20)
        if cause=='fatal':self.charge('fatal',100)
        fields={'cause':cause,**({'reason':reason} if reason is not None else {})}
        self.document=apply(self.document,{'op':'add','path':join_scope(s,'/contracts/terminated'),
                                         'val':self.cat.typed('Processing Terminated Marker',**fields)})
        self.lifecycle(s,self.cat.typed('Document Processing Terminated',**fields))
        self.terminated.add(s);self.fifo[s].clear();self.terminating.remove(s)
        if cause=='fatal':raise ContractError('contract requested fatal termination')
