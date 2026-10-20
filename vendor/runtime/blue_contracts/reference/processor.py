"""One event, one isolated rooted transition and one atomic result.

The continuation machine defines graph/lifecycle behavior; it is not a callback
asking a host to invent missing semantics.
"""
from collections import deque
from copy import deepcopy
import json
from blue_host import HostIncomplete, HOST_FAILURES, incomplete, host_boundary
from algorithms import blue as L
from blue_bex import Engine as Bex,Context,GasExhausted,BexError
from blue_bex.values import UNDEFINED
from .model import Outcome,Meter,ContractError,NeedResources,require,closed,integer,segments,pointer,prefix,digest,LIMITS,trampoline
from .language import Bridge
from .registry import Registry,EXTERNAL,EXECUTABLE,MARKERS
from .graph import Graph,Archive,prepare_bundle,components
from .channels import refresh_lifetimes,signature,checkpoint,event_observation,recognize_call,select_seeds

class Processor:
    def __init__(self, language=None, *, gas_limit=10000000, local_limits=None, local_driver=False):
        self.blue=Bridge(language); self.registry=Registry(self.blue)
        self.archive=Archive(); self.bex=Bex()
        from .receiving import CompletionStore
        self._completion_store=CompletionStore()
        self._completion_reader=None
        self.local_driver=bool(local_driver)
        integer(gas_limit, 0, 10000000)
        self.gas_limit=gas_limit; self.local_limits=deepcopy(local_limits or {})
    def typed(self,type_name,**fields):return self.registry.typed(type_name,**fields)
    def install_runtime(self,binding,implementation):self.registry.install(binding,implementation)
    @host_boundary
    def admit(self,members,root='root',*,bindings=None,gas_limit=None,local_limits=None):
        s=prepare_bundle(self.registry,members,root,bindings,archive=self.archive);g=Graph(s,self.registry,self.archive);refresh_lifetimes(g)
        return Run(self,s,None,None,self.gas_limit if gas_limit is None else gas_limit,admission=True,local_limits=self.local_limits if local_limits is None else local_limits).attempt()
    @host_boundary
    def create(self,document,*,gas_limit=None):
        result=self.admit({'root':document},gas_limit=gas_limit);require(result.commits,'ADMISSION_FAILED',status=result.status,diagnostic=result.diagnostic);return result.snapshot
    @host_boundary
    def validate(self,snapshot,*,require_initialized=True):
        require(snapshot.release==self.registry.specification,'INCOMPATIBLE_RELEASE');require(snapshot.root in snapshot.documents,'MISSING_ROOT');integer(snapshot.revision);integer(snapshot.generation)
        require(digest('runtime-bindings',snapshot.runtimes)==digest('runtime-bindings',self.registry.runtime_bindings),'INCOMPATIBLE_RUNTIME_BINDINGS')
        g=Graph(snapshot,self.registry,self.archive);g.verify_edges()
        for key,doc in sorted(snapshot.documents.items()):
            h=self.blue.head(doc.body);require(h.kind in ('object','none') and h.items is None and h.value is L.ABSENT,'PROCESSING_DOCUMENT_NOT_OBJECT')
            for reserved in MARKERS:
                marker=self.registry.marker(doc.body,reserved)
                if marker is None:continue
                value=self.blue.literal(marker)
                if reserved=='initialized':
                    closed(value,{'type','document'});closed(value['document'],{'blueId'});self.blue.open(L.Ref(value['document']['blueId']))
                elif reserved=='terminated':
                    closed(value,{'type','cause'},{'reason'});require(type(value['cause']) is str and ('reason' not in value or type(value['reason']) is str),'INVALID_TERMINATION')
                else:
                    closed(value,{'type','entries'});require(type(value['entries']) is dict,'INVALID_CHECKPOINT')
                    for channel,row in sorted(value['entries'].items()):
                        require(channel in doc.channel_lives,'INVALID_CHECKPOINT_CHANNEL');closed(row,{'timestamp','event'});integer(row['timestamp']);closed(row['event'],{'blueId'});self.blue.open(L.Ref(row['event']['blueId']))
        for key in sorted(g.reachable(active=True)):
            doc=snapshot.documents[key];cs=self.registry.contracts(doc.body);actual={k:signature(cs,k) for k,c in cs.items() if c['_role'] in EXTERNAL}
            require(set(actual)==set(doc.channel_lives),'INVALID_CHANNEL_LIFETIMES')
            for k,sig in sorted(actual.items()):
                life=doc.channel_lives[k];require(life.signature==sig and life.generation==doc.channel_serials.get(k),'INVALID_CHANNEL_LIFETIME')
                checkpoint(self.registry,doc,k)
            if require_initialized:require(self.registry.marker(doc.body,'initialized') is not None,'UNINITIALIZED_SNAPSHOT')
        return True
    @host_boundary
    def initialize(self, document):
        """Explicit lifecycle action. It supplies no external event or time."""
        from .model import Snapshot
        if isinstance(document, Snapshot):
            return Run(self,document,None,None,self.gas_limit,admission=True,local_limits=self.local_limits).attempt()
        return self.admit({'root':document})

    @host_boundary
    def process(self, document, event, eventTimestamp):
        """Process the complete original event. Exactly three input arguments.

        A Snapshot is the SDK's verified selected document/graph representation.
        A fresh Source object is admitted and initialized within this attempt.
        Gas policy, exact content and installed runtimes are processor configuration.
        """
        from .model import Snapshot
        integer(eventTimestamp)
        if not isinstance(document, Snapshot):
            document=prepare_bundle(self.registry,{'root':document},'root',archive=self.archive)
            refresh_lifetimes(Graph(document,self.registry,self.archive))
        original=self.blue.node(event) if isinstance(event,(L.Node,L.Ref)) else self.blue.source(event)
        return Run(self,document,original,eventTimestamp,self.gas_limit,local_limits=self.local_limits).attempt()

    @host_boundary
    def begin(self, document, event, eventTimestamp):
        """Open an atomic chunked invocation; no chunk publishes state."""
        from .chunks import Attempt
        from .model import Snapshot
        integer(eventTimestamp)
        if not isinstance(document,Snapshot):
            document=prepare_bundle(self.registry,{'root':document},'root',archive=self.archive)
            refresh_lifetimes(Graph(document,self.registry,self.archive))
        original=self.blue.node(event) if isinstance(event,(L.Node,L.Ref)) else self.blue.source(event)
        return Attempt(Run(self,document,original,eventTimestamp,self.gas_limit,local_limits=self.local_limits))
    @host_boundary
    def next_chunk(self,attempt):return attempt.next_chunk()
    @host_boundary
    def prepare_invocation(self, document, event, eventTimestamp, *, evidence):
        """Verify frozen external-runtime evidence for a chunked invocation.

        This is configuration of the installed runtime. process itself remains
        the three-input document/event/timestamp operation.
        """
        from .chunks import Attempt
        integer(eventTimestamp)
        self.validate(document)
        original=self.blue.node(event) if isinstance(event,(L.Node,L.Ref)) else self.blue.source(event)
        return Attempt(Run(self,document,original,eventTimestamp,self.gas_limit,
                           local_limits=self.local_limits,admission_evidence=evidence))
    @host_boundary
    def execute_chunk(self,token):
        from .chunks import execute
        return execute(self,token)
    @host_boundary
    def accept_chunk(self,attempt,token,completion):return attempt.accept_chunk(token,completion)
    @host_boundary
    def finish(self,attempt):return attempt.finish()
    @host_boundary
    def complete_local(self,attempt):
        require(attempt.run.engine is self,'WRONG_CHUNK_EXECUTOR')
        return attempt.finish_local()
    def capture_source_outcome(self, outcome, owned_members=None):
        return self._completion_store.capture(outcome, owned_members or [outcome.snapshot.root])
    @host_boundary
    def begin_receiving_application(self, document, source_completions):
        from .receiving import begin_receiving
        return begin_receiving(self, document, source_completions)
    @host_boundary
    def begin_live_application(self, document, source_completions, *, evidence):
        """Complete a LIVE cause with retained children and frozen own seeds.

        Historical application uses begin_receiving_application instead. Both
        paths require locally established completion capabilities; the public
        three-input process API is unchanged.
        """
        from .receiving import begin_receiving
        return begin_receiving(self, document, source_completions, live=True, evidence=evidence)
    def install_completion_reader(self, reader):
        """Configure a trusted local publication store, never request evidence.

        The adapter must authenticate its own protected committed records and
        exact runtime binding. Foreign serialized results require replay first.
        Like install_runtime, this is privileged host configuration.
        """
        require(self._completion_reader is None,'COMPLETION_READER_ALREADY_INSTALLED')
        require(callable(getattr(reader,'read_completed',None)),'INVALID_COMPLETION_READER')
        self._completion_reader=reader
    def load_source_completion(self, reference, owned_members):
        require(self._completion_reader is not None,'NO_LOCAL_COMPLETION_READER')
        before,outcome,event,timestamp=self._completion_reader.read_completed(self,reference)
        require(outcome.commits and outcome.input_identity==before.identity,'INVALID_STORED_COMPLETION')
        self.validate(before);self.validate(outcome.snapshot)
        self._completion_store.remember(before,outcome,event,timestamp)
        return self.capture_source_outcome(outcome,owned_members)

    def emitted(self, result):
        return [self.blue.project(L.Ref(e['event']),preserve_cyclic=True) for e in result.public_events]

    def read(self,snapshot,path='',*,document=None):return self.blue.read(snapshot.documents[document or snapshot.root].body,path)

    def observe_execution(self, kind, **record):
        """Optional host diagnostics; records are detached from runtime state."""
        observer = getattr(self, 'execution_observer', None)
        if observer is not None:observer(kind, deepcopy(record))

from .completion import CompletionMachine

class Run(CompletionMachine):
    def __init__(self,engine,state,event,timestamp,gas_limit,admission=False,local_limits=None,admission_evidence=None):
        self.engine=engine;self.blue=engine.blue;self.reg=engine.registry
        self.input=state;self.state=state.copy();self.event=event;self.timestamp=timestamp
        self.event_id=self.blue.identity(event) if event is not None else None
        self.call=None;self.call_record=None;self.seeds=()
        self.admission_evidence=deepcopy(admission_evidence or {});self.external_admissions={}
        self.admission=admission;self.meter=Meter(gas_limit,local_limits,state.documents)
        self.views=engine.archive.bindings()
        self.invocation=digest('contracts.invocation/completion-1',dict(input=state.identity,event=self.event_id,
            timestamp=timestamp,gas=self.meter.policy(),release=engine.registry.specification))
        self.graph=Graph(self.state,self.reg,engine.archive.restrict(self.views),self.meter,self.invocation)
        if self.event_id:self.graph.logical.carried_roots.add(self.event_id)
        self.queue=deque();self.events=[];self.work=[];self.public=[];self.writes=[]
        self.initializing=set();self.initialized={};self.terminating=set();self.termination={}
        self.settlements=[];self.effect_count=0
        self.opened=set();self.headers=set();self.activation={k:0 for k in state.documents}
        self.setup_completion();self.graph.changes=self.changes
    def runtime_node(self,value,**kwargs):
        if self.frame is not None:self.meter.owner=self.frame.key
        return self.blue.node(value,logical=self.graph.logical,**kwargs)
    def runtime_matches(self,value,pattern):
        if self.frame is not None:self.meter.owner=self.frame.key
        return self.blue.matches(value,pattern,logical=self.graph.logical)
    @property
    def cause_order(self):
        # An immutable cause token, NOT an external ordering relation.
        return self.event_id
    def fail_result(self,status,diagnostic):
        return Outcome(status,self.input.copy(),self.input.identity,self.invocation,event_trace=deepcopy(self.events),work_trace=deepcopy(self.work),gas=self.meter.used,rejected=deepcopy(self.meter.rejected),diagnostic=diagnostic)
    def attempt(self):
        from .chunks import Attempt
        attempt=Attempt(self)
        if self.engine.local_driver:return attempt.finish_local()
        while (token:=attempt.next_chunk()) is not None:
            attempt.accept_chunk(token,attempt.execute_chunk(token))
        return attempt.finish()
    def guard(self,action):
        try:return action()
        except HOST_FAILURES as e:raise incomplete(e) from e
        except GasExhausted:return self.fail_result('GAS_LIMIT_EXCEEDED',{'code':'GAS_LIMIT_EXCEEDED'})
        except NeedResources as e:return Outcome('NEEDS_RESOURCES',self.input.copy(),self.input.identity,self.invocation,diagnostic={'code':e.code,**e.context})
        except ContractError as e:return self.fail_result('FAILED',{'code':e.code,**e.context})
        except L.Failure as e:
            if e.category=='OperationLimitExceeded':raise HostIncomplete(e.detail) from e
            if e.category=='ProviderUnavailable':return Outcome('NEEDS_RESOURCES',self.input.copy(),self.input.identity,self.invocation,diagnostic={'code':'NEEDS_RESOURCES','required':sorted(set(self.blue.context.demands))})
            return self.fail_result('FAILED',{'code':'LANGUAGE_'+e.category,'detail':e.detail})
        except BexError as e:return self.fail_result('FAILED',{'code':'BEX_'+getattr(e,'code',type(e).__name__)})
    def begin_work(self):
        self.meter.contracts('processInvocation');self.meter.contracts('closureInvocation')
        self.preflight();self.engine.validate(self.input,require_initialized=False)
        if not self.admission:
            from .runtime import prepare_admissions
            prepare_admissions(self)
            self.call,self.call_record=recognize_call(self.reg,self.event)
            self.seeds=select_seeds(self)
        self.meter.owner=''
        if self.graph.terminated(self.state.root):return self.fail_result('TERMINATED',None)
        self.phase=self.new_phase('INITIALIZE')
    def ready(self):
        while self.phase is not None:
            unit=self.next_unit(self.phase)
            if unit is not None:return unit
            self.phase=self.new_phase('PROCESS') if self.phase.name=='INITIALIZE' and not self.admission else None
        return None
    def finish_work(self):
        self.graph.finalize();self.preflight()
        self.state.revision=integer(self.input.revision+1)
        if self.topology_changed:self.state.generation=integer(self.input.generation+1)
        self.engine.validate(self.state)
        for event in self.events:
            if event['document']==self.state.root:
                self.meter.owner=self.state.root;self.meter.contracts('rootEventRecorded');self.public.append(deepcopy(event))
        result=Outcome('APPLIED',self.state,self.input.identity,self.invocation,public_events=deepcopy(self.public),event_trace=deepcopy(self.events),work_trace=deepcopy(self.work),changes=deepcopy(self.changes),checkpoints=deepcopy(self.writes),gas=self.meter.used,completions=deepcopy(self.turns),rounds=deepcopy(self.rounds),units=deepcopy(self.units))
        self.blue.retain([d.body for _,d in sorted(self.state.documents.items())]);self.engine.archive.add(self.state)
        self.engine._completion_store.remember(self.input,result,self.event_id,self.timestamp)
        return result
    def preflight(self,*,members=None):
        for key in sorted(self.graph.reachable(active=True) if members is None else members):
            self.meter.owner=key
            if key not in self.opened:
                self.meter.contracts('scopeOpened');self.meter.contracts('managedDocumentOpened');self.opened.add(key)
            cs=self.reg.contracts(self.state.documents[key].body)
            fresh=[]
            for name,c in sorted(cs.items()):
                identity=(key,name,self.blue.identity(self.blue.exact(c['_recipe'])))
                if identity not in self.headers:fresh.append((identity,c))
            if fresh:self.graph.logical.headers(self.state.documents[key].body,cs)
            for identity,c in fresh:
                self.meter.contracts('contractHeaderRecognized');self.headers.add(identity)
                for field in sorted(k for k in c if not k.startswith('_')):self.meter.contracts('objectMemberRead')
            for edge in sorted(self.state.edges.values(),key=lambda e:e.key):
                if edge.source==key and edge.occurrence not in self.graph.verified_bindings:
                    self.meter.contracts('managedOccurrenceBindingVerified');self.graph.verified_bindings.add(edge.occurrence)
        self.meter.owner=''
    def ordered(self,cs):return self.graph.logical.ordered(cs)
    @staticmethod
    def program(step):return {k:deepcopy(step[k]) for k in ('expr','do','constants','functions') if k in step}
    def compute_definition(self,key,step):
        from .compute import resolve_definition
        return resolve_definition(self,key,step)
    def context(self,key,payload,contract,steps,call=None,*,overlay_program=None):
        def overlays(value):
            if type(value) is list:return any(overlays(x) for x in value)
            if type(value) is dict:return '$resultValue' in value or any(overlays(x) for k,x in value.items() if k!='$literal')
            return False
        body=self.state.documents[key].body
        view=self.blue.view(body,logical=self.graph.logical) if overlays(self.program(contract) if overlay_program is None else overlay_program) else body
        event=event_observation(self.reg,payload,logical=self.graph.logical)
        binding={'processingEvent':event_observation(self.reg,self.event,logical=self.graph.logical) if self.event is not None else UNDEFINED,
                 'timestamp':self.timestamp if self.timestamp is not None else UNDEFINED,
                 'call':event_observation(self.reg,call,logical=self.graph.logical) if call is not None else UNDEFINED}
        return Context(document=view,resolved_document=deepcopy(view),event=event,current_contract={k:(self.blue.view(v,logical=self.graph.logical) if k=='definition' else deepcopy(v)) for k,v in contract.items() if not k.startswith('_')},steps=steps,bindings=binding,scope='/',read_document=lambda p,v,d:self.graph.logical.read(d,'' if p=='/' else p) if isinstance(d,(L.Node,L.Ref)) else self.blue.read_bex(d,p),matcher=self.runtime_matches,node_blue_id=self.graph.logical.node_blue_id)
    def evaluate(self,key,payload,contract,steps,expr,call=None):
        self.meter.owner=key;result=self.engine.bex.execute({'expr':expr},self.context(key,payload,contract,steps,call),gas=self.meter);require(not result.changeset and not result.events,'EFFECTFUL_EXPRESSION');return result.value
    def work_record(self,key,channel,payload,kind):
        self.meter.owner=key;self.meter.contracts('closureWorkOccurrenceEnqueued');self.meter.contracts('closureWorkOccurrenceDequeued');row=dict(ordinal=len(self.work),document=key,channel=channel,kind=kind,payload=self.blue.identity(payload));row['identity']=digest('contracts.work/completion-1',{'invocation':self.invocation,**row});self.work.append(row)
        counter={'UPDATE':'documentUpdateDelivered','TRIGGERED':'triggeredEventDelivered','EMBEDDED':'embeddedEventDelivered','INITIALIZATION':'lifecycleDelivered','TERMINATION':'lifecycleDelivered'}.get(kind)
        if counter:self.meter.contracts(counter)
    def custom_internal(self,key,kind,node,cs,route=(),allow_terminating=False):
        from .runtime import frozen
        for channel,d in self.ordered(cs):
            if d['_role']!='extension_channel':continue
            if not self.continuation_live(key,self.activation.get(key,0),allow_terminating):return
            extension=d['_extension'];implementation=extension.implementation
            if kind not in implementation.families:continue
            self.meter.owner=key;self.meter.contracts('channelCandidateTested')
            header=extension.header(d);event=frozen(self.blue.bex_data(node));peers=extension.peers(d,cs)
            try:
                accepted=implementation.accept_internal(header,kind,event,peers)
                require(type(accepted) is bool,'INVALID_RUNTIME_ACCEPTANCE')
                if accepted:
                    self.meter.contracts('channelAccepted')
                    value=implementation.channelize_internal(header,kind,event,peers)
            except HOST_FAILURES as exc:raise incomplete(exc) from exc
            except (GasExhausted,ContractError):raise
            except Exception as exc:
                raise ContractError('RUNTIME_FAILURE',exception=type(exc).__name__) from exc
            if accepted:
                yield self.dispatch(key,channel,self.runtime_node(value),kind,allow_terminating=allow_terminating)
    def dispatch(self,key,channel,payload,kind,operation=None,allow_terminating=False,call=None):
        frame=self.frame;ticket=frame.ticket;writer=frame.writer
        if kind!='EMBEDDED':frame.ticket=None
        try:
            yield self.dispatch_local(key,channel,payload,kind,operation,allow_terminating,call)
        finally:frame.ticket=ticket;frame.writer=writer
    def dispatch_local(self,key,channel,payload,kind,operation=None,allow_terminating=False,call=None):
        if not self.live(key) and not (allow_terminating and key in self.terminating):return
        self.work_record(key,channel,payload,kind);cs=self.reg.contracts(self.state.documents[key].body);require(channel in cs,'MISSING_HANDLER_CHANNEL');frozen=[]
        for hkey,h in self.ordered(cs):
            if h['_role'] not in EXECUTABLE or h['channel']!=channel:continue
            if h['_role']=='operation' and (kind!='EXTERNAL' or operation is None or hkey!=operation):continue
            frozen.append((hkey,{k:v if k in ('_recipe','_extension') else deepcopy(v) for k,v in h.items()}))
        event=payload
        generation=self.activation.get(key,0)
        for hkey,h in frozen:
            if not self.continuation_live(key,generation,allow_terminating):break
            self.meter.owner=key;self.meter.contracts('handlerCandidateTested')
            if 'event' in h and not self.runtime_matches(event,h['event']):continue
            declaration=self.blue.exact(h['_recipe']);self.blue.remember(declaration)
            self.frame.writer=dict(handler=hkey,declaration=self.blue.identity(declaration),channel=channel,
                kind=kind,event=self.blue.identity(event),call=self.blue.identity(call) if call is not None else None)
            self.meter.contracts('handlerCall');steps={}
            if h['_role']=='extension_handler':
                yield self.execute_extension(key,payload,h,steps,generation,allow_terminating,call)
                continue
            for i,recipe in enumerate(self.reg.steps(h)):
                if not self.continuation_live(key,generation,allow_terminating):break
                self.meter.owner=key;step=self.reg.declaration(recipe);name=step.get('name',str(i));role=step['_role']
                require(name not in steps,'DUPLICATE_STEP_NAME')
                configured={k:v for k,v in step.items() if not k.startswith('_')}
                if role=='compute':
                    definition=self.compute_definition(key,step)
                    program=self.program(step)
                    # Overlay detection includes imported function bodies.
                    overlay_program={**program,'functions':{**(definition or {}).get('functions',{}),**step.get('functions',{})}}
                    result=self.engine.bex.execute(program,self.context(key,payload,step,steps,call,overlay_program=overlay_program),gas=self.meter,entry=step.get('entry'),definition=definition);value=result.value
                    if type(value) is dict:changes=value.get('changeset',result.changeset);events=value.get('events',result.events)
                    else:changes=result.changeset;events=result.events
                    self.validate_effects(changes,events);steps[name]=deepcopy(value)
                    for p in changes:
                        if not self.continuation_live(key,generation,allow_terminating):break
                        yield self.patch(key,p)
                    for e in events:
                        if not self.continuation_live(key,generation,allow_terminating):break
                        self.emit(key,self.runtime_node(e))
                elif role=='patch_step':
                    require('changeset' in step,'MISSING_CHANGESET')
                    changes=self.evaluate(key,payload,step,steps,step['changeset'],call);self.validate_effects(changes,[]);steps[name]={'changeset':deepcopy(changes)}
                    for p in changes:
                        if not self.continuation_live(key,generation,allow_terminating):break
                        yield self.patch(key,p)
                elif role=='emit_step':
                    require('event' in step,'MISSING_EVENT')
                    event_value=self.evaluate(key,payload,step,steps,step['event'],call);self.emit(key,self.runtime_node(event_value));steps[name]=deepcopy(event_value)
                elif role=='terminate_step':
                    cause=step['cause'];reason=step.get('reason');require(type(cause) is str and (reason is None or type(reason) is str),'INVALID_TERMINATION');yield self.terminate(key,cause,reason);break
                elif role=='extension_step':
                    yield self.execute_extension(key,payload,step,steps,generation,allow_terminating,call)
                    steps[name]={}
                else:raise ContractError('UNSUPPORTED_STEP')
    def execute_extension(self,key,payload,declaration,steps,generation,allow_terminating=False,call=None):
        from .runtime import RuntimeMeter,RuntimeContext,frozen,validate_result
        extension=declaration['_extension'];binding=extension.binding
        selected=self.reg.declaration(declaration['_recipe']);body=self.state.documents[key].body
        meter=RuntimeMeter(self.meter,binding,key)
        context=RuntimeContext(frozen(event_observation(self.reg,payload)),extension.header(selected),
            frozen({k:deepcopy(selected[k]) for k in binding.body_fields if k in selected}),frozen(deepcopy(steps)),
            self.event_id,self.timestamp,lambda path:frozen(self.blue.read(body,path)),meter,
            frozen(event_observation(self.reg,call)) if call is not None else None)
        try:raw=extension.implementation.execute(context)
        except HOST_FAILURES as exc:raise incomplete(exc) from exc
        except (GasExhausted,ContractError):
            meter.merge(failed=True);raise
        except Exception as exc:
            meter.merge(failed=True)
            raise ContractError('RUNTIME_FAILURE',exception=type(exc).__name__) from exc
        # Merge admitted runtime work even when the returned effect shape is
        # invalid. Effects remain staged until the entire result is checked.
        meter.merge(raw.get('runtimeLedger') if type(raw) is dict else None)
        result=validate_result(raw)
        self.validate_effects(result['patches'],result['events'])
        def alive():return self.continuation_live(key,generation,allow_terminating)
        for patch in result['patches']:
            if not alive():return
            yield self.patch(key,patch)
        for event in result['events']:
            if not alive():return
            self.emit(key,self.runtime_node(event))
        if 'termination' in result and alive():
            end=result['termination'];yield self.terminate(key,end['cause'],end.get('reason'))
    def validate_effects(self,patches,events):
        require(type(patches) is list and type(events) is list,'INVALID_EFFECT_RESULT')
        for p in patches:
            require(type(p) is dict and p.get('op') in ('add','replace','remove'),'INVALID_PATCH');closed(p,{'op','path'} if p['op']=='remove' else {'op','path','val'});require(bool(segments(p['path'])),'INVALID_PATCH_PATH')
            if p['op']!='remove':self.runtime_node(p['val'],certify=False)
        for e in events:self.runtime_node(e)
    def protected(self,body):
        return self.reg.policy(body)[1],{k:self.blue.identity(v) if (v:=self.reg.marker(body,k)) is not None else None for k in MARKERS}
    def patch(self,key,patch):
        self.effect_count+=1;self.meter.owner=key;path=patch['path'];doc=self.state.documents[key]
        # Normalize list append to the concrete index. An inserted position
        # has no before value; a removed position has no after value even when
        # a following list item shifts into the same numerical index.
        parts=segments(path);parent=self.blue.select(doc.body,pointer(parts[:-1]))
        list_parent=parent is not None and self.blue.head(parent).items is not None
        if list_parent and parts[-1]=='-' and patch['op']=='add':
            path=pointer(parts[:-1]+(str(len(self.blue.head(parent).items)),))
        self.meter.contracts('patchBoundaryChecked')
        for _ in segments(path):self.meter.contracts('pointerSegmentTraversed')
        self.meter.contracts('patchRemove' if patch['op']=='remove' else 'patchAddOrReplace')
        for (source,p),edge in self.state.edges.items():
            if source==key:require(not(prefix(p,path) and p!=path),'MANAGED_BOUNDARY_VIOLATION',path=path)
        before_r=None if list_parent and patch['op']=='add' else self.blue.select(doc.body,path);before=self.blue.exact(before_r) if before_r is not None else None;protection=self.protected(doc.body)
        value=self.runtime_node(patch['val'],certify=False) if patch['op']!='remove' else None;next_body=self.blue.set_at(doc.body,path,value,op=patch['op'])
        self.graph.logical.establish(next_body,doc.body)
        requested_body=next_body
        from .generalization import repair
        next_body,generated=repair(self.blue,doc.body,next_body,path,self.reg.policy(doc.body)[0],self.meter,validate=lambda candidate:self.graph.logical.validate(candidate,doc.body),establish=lambda candidate:self.graph.logical.establish(candidate,doc.body))
        require(self.protected(next_body)==protection,'PROTECTED_STATE_MUTATION',path=path)
        for write in generated:
            self.meter.contracts('patchBoundaryChecked')
            for _ in segments(write['path']):self.meter.contracts('pointerSegmentTraversed')
            self.meter.contracts('patchAddOrReplace')
        if generated:self.graph.logical.establish(next_body,requested_body)
        self.blue.remember(doc.body);self.blue.remember(next_body)
        self.frame.writes.append(dict(writer=deepcopy(self.frame.writer),op=patch['op'],path=path,
            before=self.blue.identity(doc.body),after=self.blue.identity(next_body)))
        reachable=self.graph.reachable()
        doc.body=next_body
        self.graph.reconcile(self.cause_order,owner=key,replaced=(path,))
        for member in reachable ^ self.graph.reachable():self.activation[member]=self.activation.get(member,0)+1
        self.allocation=max(self.allocation,self.graph.allocation)
        refresh_lifetimes(self.graph,self.cause_order,members={key}|set(self.graph.added))
        self.graph.finalize_local(key);self.preflight(members={key}|set(self.graph.added))
        self.creation_barrier()
        self.graph.finalize_local(key)
        after_r=None if patch['op']=='remove' else self.blue.select(doc.body,path)
        after=self.blue.exact(after_r) if after_r is not None else None
        before_id=self.blue.identity(before) if before is not None else None;after_id=self.blue.identity(after) if after is not None else None
        if before_id==after_id:return
        # A contextual selection (especially after generated type writes) can
        # materialize a new exact subtree which is not a stored root. Retain
        # both immutable observations before an update refers to their IDs.
        if before is not None:self.blue.remember(before)
        if after is not None:self.blue.remember(after)
        payload={'op':'add' if before is None else 'remove' if after is None else 'replace','path':path,'beforePresent':before is not None,'afterPresent':after is not None}
        if before is not None:payload['before']={'blueId':before_id}
        if after is not None:payload['after']={'blueId':after_id}
        for write in generated:
            change={'op':'replace','path':write['path'],'beforePresent':True,'afterPresent':True,'before':{'blueId':self.blue.identity(write['before'])},'after':{'blueId':self.blue.identity(write['after'])}}
            yield self.update(key,change,())
        yield self.update(key,payload,())
    def update(self,key,payload,route):
        if not self.graph.route_live(route) or not self.live(key):return
        generation=self.activation.get(key,0)
        node=self.runtime_node(self.reg.typed('Document Update',**payload));cs=self.reg.contracts(self.state.documents[key].body)
        channels=[k for k,c in self.ordered(cs) if c['_role']=='update' and prefix(c.get('path',''),payload['path']) and ('event' not in c or self.runtime_matches(node,c['event']))]
        for k in channels:
            if not self.graph.route_live(route) or self.activation.get(key,0)!=generation:break
            yield self.dispatch(key,k,node,'UPDATE')
        if self.activation.get(key,0)==generation:yield self.custom_internal(key,'UPDATE',node,cs,route)
    def terminate(self,key,cause,reason):
        if key in self.terminating or self.graph.terminated(key):return
        self.meter.owner=key;self.meter.contracts('terminationRequested')
        self.terminating.add(key);self.termination[key]=(cause,reason);raw=self.reg.typed('Document Processing Terminated',cause=cause)
        if reason is not None:raw['reason']=reason
        node=self.runtime_node(raw);cs=self.reg.contracts(self.state.documents[key].body)
        for k,c in self.ordered(cs):
            if c['_role']=='lifecycle' and ('event' not in c or self.runtime_matches(node,c['event'])):yield self.dispatch(key,k,node,'TERMINATION',allow_terminating=True)
        yield self.custom_internal(key,'TERMINATION',node,cs,allow_terminating=True)
    def direct_marker(self,key,name,value):
        doc=self.state.documents[key];root=self.blue.open(doc.body);cs=root.get('contracts');cs=L.node({}) if cs is L.ABSENT else self.blue.open(cs);fields=dict(cs.fields)
        if value is None:fields.pop(name,None)
        else:fields[name]=self.runtime_node(value,certify=False)
        candidate=L.changed(root,contracts=L.node(fields))
        self.graph.logical.establish(candidate,doc.body)
        doc.body=candidate
