"""Opt-in ordinary-processor reuse; the executable reference remains unchanged.

Evidence is private to a scope, bridge and captured resolver. Strict-closure
coverage is distinct from Language's recipe/requirements/goal validation keys.
Finite host limits, cyclic proofs and custom language adapters use the reference.
The automatic engine keeps its own StoreLanguage admission/retention protocol.
"""
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import fields
from weakref import WeakKeyDictionary
import sys

from algorithms import blue as L
from blue_contracts.reference.language import Bridge
from blue_contracts.reference import storage
from blue_language.api import Language
from blue_language.prepared import PreparedLanguage

_SOURCE, _CERTIFY, _RETAIN = Bridge.source, Bridge.certify, Bridge.retain
_EXPORT_SNAPSHOT = storage.export_snapshot
_ACTIVE = ContextVar('blue_core_reuse', default=None)


class CoreReuse:
    """A local optimization capability, never serialized or accepted as input."""
    def __init__(self, capacity=8192):
        if type(capacity) is not int or capacity < 0:raise ValueError('nonnegative capacity required')
        self.capacity=capacity;self.sessions=WeakKeyDictionary();self.metrics={}

    def count(self, name, n=1):self.metrics[name]=self.metrics.get(name,0)+n
    def clear(self):self.sessions.clear()

    @contextmanager
    def scope(self):
        token=_ACTIVE.set(self)
        try:yield self
        finally:_ACTIVE.reset(token)

    def session(self, blue):
        if not self.capacity or type(blue.language) not in (Language,PreparedLanguage):return None
        # The host may replace Language.limits after this bridge captured its
        # resolver. Source admission must use those current limits as well.
        if any(getattr(limits,f.name) is not None
               for limits in (blue.context.limits,blue.language.limits)
               for f in fields(L.Limits)):return None
        session=self.sessions.get(blue)
        if session is None:
            session=Session(self);self.sessions[blue]=session
        session.bind(blue.context)
        return session


@contextmanager
def core_reuse_scope(*, enabled=True, capacity=8192):
    cache=CoreReuse(capacity if enabled else 0)
    with cache.scope():yield cache


def _session(blue):
    active=_ACTIVE.get()
    return active.session(blue) if active is not None else None


class Session:
    def __init__(self, owner):
        self.owner=owner;self.context=None;self.closed=set();self.retained=set()
        self.policy=Language._policy();self.inventory={}

    def bind(self, context):
        if self.context is not context:
            self.context=context;self.closed.clear();self.retained.clear();self.inventory={}

    def check_inventory(self, provider):
        current=provider.snapshot()
        if any(k not in current or not _same_response(v,current[k]) for k,v in self.inventory.items()):
            self.retained.clear();self.inventory={};self.owner.count('retentionInvalidations')

    def remember_inventory(self, provider):
        current=provider.snapshot()
        if not all(type(k) is str and _text_record(row) for k,row in current.items()):
            self.retained.clear();self.inventory={};return
        size=sum(sys.getsizeof(k)+sum(sys.getsizeof(v) for v in row.values())+256
                 for k,row in current.items())
        if len(current)>self.owner.capacity or size>16*1024*1024:
            self.retained.clear();self.inventory={};self.owner.count('inventoryEvictions')
        else:self.inventory=current

    def trim(self):
        if len(self.closed)+len(self.retained)>2*self.owner.capacity:
            self.closed.clear();self.retained.clear();self.owner.count('evidenceEvictions')

    def certify(self, node, goal):
        c=self.context
        L.require(goal in ('definition','value'),'InvalidOperation','validation goal')
        pending=[(node,c.diagnostic_path)];seen=set();types={};key_types={}
        while pending:
            value,path=pending.pop()
            with L.error_scope(c,path,'dependency-verification'):
                identity=L.identity(value);c.step()
                if identity in seen:continue
                seen.add(identity)
                # No partial coverage for a cyclic set or a pinned alternate body.
                if '#' in identity or isinstance(value,L.Ref) and value.body is not None:
                    self.owner.count('referenceAdmissions');return L.strict_certify(node,c,goal)
                body=L.open_exact(value,c)
                if path==c.diagnostic_path and c.diagnostic_root is node:c.diagnostic_root=body
                if identity in self.closed and identity in self.retained:
                    self.owner.count('closedSubtreesReused');continue
                self.owner.count('admissionBodiesVisited')
                children=[]
                for key,child in body.fields:
                    if key in L.TYPES:
                        L.require(isinstance(child,L.Ref),'InvalidNodeShape','type position')
                        at=L.pointer(path,key);types.setdefault(child.id,at);children.append((child,at))
                        if key=='keyType':key_types.setdefault(child.id,at)
                    elif key=='items':children.extend((item,L.pointer(L.pointer(path,key),i)) for i,item in enumerate(child))
                    elif key not in L.LITERALS|{'mergePolicy'}:children.append((child,L.pointer(path,key)))
                pending.extend(reversed(children))
        for identity in sorted(types):
            if identity not in L.CORE_NAME:
                with L.error_scope(c,types[identity],'type-definition'):L.certify(L.Ref(identity),c,'definition')
        for identity in sorted(key_types):
            with L.error_scope(c,key_types[identity],'type-definition'):
                L.require(L.domain_core(identity,c) in ('Text','Integer','Double','Boolean'),'TypeCompatibilityViolation','keyType')
        with L.error_scope(c,c.diagnostic_path,'validation'):L.certify(node,c,goal)
        # Closure is structural/type coverage only. L.certify above still checks
        # every new effective requirement and requested goal using its own keys.
        self.closed.update(seen);self.trim()
        return tuple(sorted(seen))

    def retain(self, nodes):
        c=self.context;records={};seen=set()
        for root in nodes:
            pending=[root]
            while pending:
                node=pending.pop();identity=L.identity(node);c.step()
                if '#' in identity or isinstance(node,L.Ref) and node.body is not None:
                    # Owning proofs and all derived prefixes use reference collection.
                    records.update(L.admitted_records(root,c));break
                if identity in seen or identity in self.retained:continue
                seen.add(identity);body=L.open_exact(node,c);self.owner.count('retentionBodiesVisited')
                if identity not in L.CORE_NAME:records[identity]={'text':L.export_exact(body,c),'mode':'exact'}
                for key,value in body.fields:
                    if key=='items':
                        payload=c.remember(L.list_node(value));pid=L.identity(payload)
                        records[pid]={'text':L.export_exact(payload,c),'mode':'exact'};pending.extend(reversed(value))
                    elif key not in L.LITERALS|{'mergePolicy'}:pending.append(value)
            # Prefixes depend on the root's effective context, not only child IDs.
            _prefixes(root,c,records)
        return records,seen


def _prefixes(root,c,records):
    def visit(value):
        if isinstance(value,list):
            for item in value:visit(item)
        elif isinstance(value,dict):
            if set(value)=={'$previous'}:
                identity=value['$previous']['blueId']
                records[identity]={'text':L.export_exact(L.payload_body(identity,c),c),'mode':'exact'}
            else:
                for item in value.values():visit(item)
    visit(L.canonical_wire(root,c))


def certify(blue,node,goal='value'):
    session=_session(blue)
    if session is None:return _CERTIFY(blue,node,goal)
    try:session.certify(node,goal)
    except L.Failure as error:blue.translate(error)


def retain(blue,nodes):
    session=_session(blue)
    if session is None:return _RETAIN(blue,nodes)
    try:
        session.check_inventory(blue.language.provider)
        records,seen=session.retain(nodes)
        blue.language.provider.merge_responses(records)
        blue.context.provider.update(deepcopy(records))
        session.retained.update(seen);session.trim()
        session.remember_inventory(blue.language.provider)
    except L.Failure as error:blue.translate(error)


def _text_record(row):
    return type(row) is dict and all(type(k) is str and type(v) is str for k,v in row.items())


def _same_response(left,right):
    if not _text_record(left) or not _text_record(right):return False
    if left==right:return True
    # These two defaults are specified by exact opening. Different bytes,
    # source envelopes, incomplete manifests and proofs never match this way.
    allowed={'text','format','mode'}
    return (type(left) is dict and type(right) is dict and 'text' in left and 'text' in right
            and set(left)<=allowed and set(right)<=allowed
            and {'format':'json','mode':'exact',**left}=={'format':'json','mode':'exact',**right})


def source(blue,value,*,goal='value'):
    session=_session(blue)
    if session is None:return _SOURCE(blue,value,goal=goal)
    language=blue.language;old=blue.context
    # Configuration/provider changes invalidate ALL carried evidence, including
    # negative/missing dependencies. Custom mutable/demand providers fall back.
    fresh=language.processing_context()
    if (type(old.provider) is not dict or type(fresh.provider) is not dict or
            any(getattr(fresh.limits,f.name) is not None for f in fields(L.Limits))):
        return _SOURCE(blue,value,goal=goal)
    same=(len(old.validation_cache)<=session.owner.capacity and
          session.policy==Language._policy() and old.aliases==fresh.aliases and old.directive_aliases==fresh.directive_aliases and
          all(k in fresh.provider and _same_response(fresh.provider[k],v) for k,v in old.provider.items()))
    if same:
        # Carry only verified coverage, never hydrate the provider's bodies.
        # Opening stays demand-driven in the new resolver. In particular, an
        # unrelated historical result must not be hashed before the invocation
        # ledger exists, nor replace a provider's exact materialization.
        fresh.validation_cache.update(old.validation_cache)
        closed,retained,inventory=session.closed,session.retained,session.inventory
    else:
        closed,retained,inventory=set(),set(),{};session.policy=Language._policy();session.owner.count('resolverInvalidations')
    blue.context=fresh;session.bind(fresh);session.closed=closed;session.retained=retained;session.inventory=inventory
    try:
        fresh.diagnostic_goal=goal
        with L.error_scope(fresh,'','operation'):
            n=language._input(L.wire_text(blue.normalize_input(value)),fresh,'source','json')
            fresh.diagnostic_root=n;session.certify(n,goal)
            n,removed=L.omit_root_duplicates(n,fresh)
            if removed:session.certify(n,goal)
            # Keep representation validation and canonical prefix side effects.
            L.export_exact(n,fresh);L.canonical_export(n,fresh)
            retain(blue,[n])
            # Reference publication refreshes diagnostic state before processing.
            language.last_demands=()
            fresh.diagnostic_root=None;fresh.diagnostic_goal=None
            fresh.diagnostic_phase='operation';fresh.diagnostic_path=''
            # Enter through the exact reference, as Bridge.source does. This
            # carries verified identity and child-selection evidence to BEX;
            # opening an inline Node alone would change transfer gas.
            body=blue.open(L.Ref(L.identity(n)))
            return L.Ref(L.identity(n),body) if '#' in L.identity(n) else body
    except L.Failure as error:
        language.last_demands=tuple(fresh.demands)
        # Match Bridge.source's original demanded identity on a source miss.
        if error.category=='ProviderUnavailable':
            from blue_contracts.reference.model import NeedResources
            try:missing=L.final_id(error.detail)
            except L.Failure:blue.translate(error)
            raise NeedResources(missing) from error
        blue.translate(error)


class ExportCollection:
    """One export's materialization memo; every returned inventory is complete."""
    def __init__(self):self.rows=OrderedDict();self.bytes=0
    def records(self,root,c):
        records={};seen=set();todo=[root]
        while todo:
            node=todo.pop();identity=L.identity(node);c.step()
            if identity in seen:continue
            seen.add(identity)
            # Actual body handle distinguishes alternate exact materializations.
            body=L.open_exact(node,c);key=(id(c),identity,id(body))
            row=self.rows.get(key)
            if row is None or row[0] is not body:
                direct={};children=[]
                if identity not in L.CORE_NAME:
                    if '#' in identity:L.require(identity in c.proofs,'InvalidCyclicProof','publication proof unavailable')
                    direct[identity]=({'proof':L.wire_text(c.proofs[identity]),'body':L.export_exact(body,c)}
                        if '#' in identity else {'text':L.export_exact(body,c),'mode':'exact'})
                for name,value in body.fields:
                    if name=='items':
                        payload=c.remember(L.list_node(value));pid=L.identity(payload)
                        direct[pid]={'text':L.export_exact(payload,c),'mode':'exact'};children.extend(reversed(value))
                    elif name not in L.LITERALS|{'mergePolicy'}:children.append(value)
                row=(body,direct,children)
                size=sum(len(v.encode('utf-8')) for response in direct.values() for v in response.values())+256+len(children)*16
                if size<=16*1024*1024:
                    self.rows[key]=(*row,size);self.bytes+=size
                    while len(self.rows)>8192 or self.bytes>16*1024*1024:
                        _,removed=self.rows.popitem(last=False);self.bytes-=removed[3]
            records.update(row[1]);todo.extend(row[2])
        _prefixes(root,c,records)
        return records


_EXPORT = ContextVar('blue_complete_export_collection',default=None)

def export_snapshot(engine,snapshot,*,require_initialized=True):
    active=_ACTIVE.get()
    if active is None or not active.capacity or any(getattr(engine.blue.context.limits,f.name) is not None for f in fields(L.Limits)):
        return _EXPORT_SNAPSHOT(engine,snapshot,require_initialized=require_initialized)
    collector=_EXPORT.get() or ExportCollection()
    engine.validate(snapshot,require_initialized=require_initialized);records={}
    for _,doc in sorted(snapshot.documents.items()):records.update(collector.records(doc.body,engine.blue.context))
    for binding in snapshot.runtimes:
        for name in ('type_id','semantics_id'):records.update(collector.records(L.Ref(binding[name]),engine.blue.context))
    return {'snapshot':snapshot.wire(),'identity':snapshot.identity,'content':records}


@contextmanager
def export_collection():
    token=_EXPORT.set(ExportCollection())
    try:yield
    finally:_EXPORT.reset(token)


_EXPORT_INVOCATION=storage.export_invocation

def export_invocation(engine,snapshot,event,eventTimestamp):
    with export_collection():return _EXPORT_INVOCATION(engine,snapshot,event,eventTimestamp)


Bridge.source=source
Bridge.certify=certify
Bridge.retain=retain
storage.export_snapshot=export_snapshot
# Re-exported functions retain their public callable but invoke the scoped storage
# snapshot helper; invocation callers may explicitly use export_collection too.
