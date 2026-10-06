"""Versioned local Stack recovery and a transaction boundary over SQLiteJournal.

The database is trusted local storage. Values are a closed JSON schema, never
pickle. All observable state is staged behind the host lock until the journal
CAS commits; a conflict reloads the winner. Outbox delivery is at least once.
"""
from dataclasses import fields,is_dataclass
from enum import Enum
from decimal import Decimal
import hashlib,json,hmac
from .storage import SQLiteJournal,Conflict,CorruptStore
from .stack import Stack
from blue_coordination import model
from blue_coordination.closure import GraphState,Receipt
from blue_coordination.feeder import DriverResult,HostStep
from blue_runtime.support.language import ExactValue,MISSING,BlueAccess
from blue_runtime.support.errors import Eligibility
from blue_language import Language,MemoryProvider
from blue_contracts.catalogue import compact
from blue_bex.values import UNDEFINED

TYPES={c.__name__:c for c in vars(model).values() if isinstance(c,type) and is_dataclass(c)}
TYPES.update({c.__name__:c for c in (GraphState,Receipt,DriverResult,HostStep,ExactValue)})
HOST_FIELDS=('receipts','saved_originals','published','terminals','_issued','_base_admissions','_authored_ids','required_retained','histories')
PROVIDER_FIELDS=('_timelines','_actors','_entries','_frontiers','_unavailable')


def encode(value):
    if value is MISSING:return {'$missing':True}
    if value is UNDEFINED:return {'$undefined':True}
    if isinstance(value,Eligibility):return {'$eligibility':value.value}
    if type(value) in (type(None),str,bool,int,float):return value
    if isinstance(value,Decimal):return {'$decimal':str(value)}
    if is_dataclass(value):
        if type(value).__name__ not in TYPES:raise TypeError('unregistered snapshot record')
        return {'$record':type(value).__name__,'fields':{f.name:encode(getattr(value,f.name)) for f in fields(value)}}
    if type(value) is dict:return {'$map':[[encode(k),encode(v)] for k,v in value.items()]}
    if type(value) in (set,frozenset,tuple,list):return {'$'+type(value).__name__:[encode(x) for x in value]}
    raise TypeError('unsupported snapshot value '+type(value).__name__)


def decode(value):
    if type(value) in (type(None),str,bool,int,float):return value
    if type(value) is not dict:raise CorruptStore('invalid snapshot value')
    if set(value)=={'$record','fields'}:
        cls=TYPES.get(value['$record'])
        if cls is None or set(value['fields'])!={f.name for f in fields(cls)}:raise CorruptStore('unknown record/schema')
        return cls(**{k:decode(v) for k,v in value['fields'].items()})
    if len(value)!=1:raise CorruptStore('invalid snapshot tag')
    key,data=next(iter(value.items()))
    if key=='$missing' and data is True:return MISSING
    if key=='$undefined' and data is True:return UNDEFINED
    if key=='$decimal':return Decimal(data)
    if key=='$eligibility':return Eligibility(data)
    if key=='$map':
        pairs=[(decode(k),decode(v)) for k,v in data];out=dict(pairs)
        if len(out)!=len(pairs):raise CorruptStore('duplicate snapshot key')
        return out
    constructors={'$tuple':tuple,'$list':list,'$set':set,'$frozenset':frozenset}
    if key in constructors:return constructors[key](decode(x) for x in data)
    raise CorruptStore('unknown snapshot tag')


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


class DurableStack:
    """Use execute(command_id, operation, *args, **kwargs) for durable mutations.

    Retrying a command ID returns the stored result. Reusing it with different
    operands conflicts. Read state through .stack, never mutate it directly.
    """
    def __init__(self,path,*,catalogue=None,stack=None):
        self.stack=stack if stack is not None else Stack(catalogue=catalogue)
        self.commands={};self.generation=0;self.metadata={}
        self.journal=SQLiteJournal(path,validate_snapshot=self.validate_snapshot)
        try:
            loaded=self.journal.load('workspace')
            if loaded:self.generation,snapshot=loaded;self.restore(snapshot,verify_replay=True)
        except BaseException:
            self.journal.close()
            raise

    def snapshot(self):
        s=self.stack;groups=[];seen={}
        for root,state in s.host.roots.items():
            if id(state) not in seen:seen[id(state)]=len(groups);groups.append({'roots':[],'state':state})
            groups[seen[id(state)]]['roots'].append(root)
        payload={'format':'blue-python-stack-snapshot/1','profile':s.host.profile,
            'records':s.catalogue.language.provider.snapshot(),'groups':encode(groups),
            'host':encode({k:getattr(s.host,k) for k in HOST_FIELDS}),
            'provider':encode({k:getattr(s.provider,k) for k in PROVIDER_FIELDS}),
            'routes':encode(s._entry_roots),'commands':encode(self.commands),'metadata':encode(self.metadata)}
        return {**payload,'seal':s.host._seal({'snapshot':digest(payload)})}

    def validate_snapshot(self,snapshot):
        if set(snapshot)!={'format','profile','records','groups','host','provider','routes','commands','metadata','seal'}:
            raise CorruptStore('snapshot schema mismatch')
        if snapshot['format']!='blue-python-stack-snapshot/1' or snapshot['profile']!=self.stack.host.profile:
            raise CorruptStore('snapshot execution profile changed; explicit migration is required')
        payload={k:v for k,v in snapshot.items() if k!='seal'}
        if not hmac.compare_digest(snapshot['seal'],self.stack.host._seal({'snapshot':digest(payload)})):
            raise CorruptStore('snapshot seal mismatch')
        # Reopen every current member through Language, including owning-set
        # proofs. A digest of arbitrary JSON is not managed content evidence.
        language=Language(MemoryProvider(snapshot['records']));blue=BlueAccess(language)
        for group in decode(snapshot['groups']):
            state=group['state']
            if not set(group['roots'])<=set(state.documents):raise CorruptStore('missing selected root')
            if any(set(getattr(state,k))!=set(state.documents) for k in ('ids','edges','epochs','initials','bases')):
                raise CorruptStore('incomplete managed graph')
            for n,tid in state.ids.items():
                if compact(blue.tree(blue.get(tid,goal='definition')))!=state.documents[n]:raise CorruptStore('managed member/proof mismatch')
                if type(state.epochs[n]) is not int or state.epochs[n]<0:raise CorruptStore('invalid epoch')
                if not set(state.edges[n].values())<=set(state.documents):raise CorruptStore('missing managed dependency')
        host=decode(snapshot['host']);provider=decode(snapshot['provider'])
        if set(host)!=set(HOST_FIELDS) or set(provider)!=set(PROVIDER_FIELDS):raise CorruptStore('host/provider schema mismatch')
        decode(snapshot['commands']);decode(snapshot['routes']);decode(snapshot['metadata'])

    def restore(self,snapshot,*,verify_replay=False):
        self.validate_snapshot(snapshot);s=self.stack
        s.catalogue.language.provider._records=snapshot['records'].copy()
        s.catalogue.blue._verified.clear();s.catalogue.blue._values.clear();s.catalogue.blue._admitted_inputs.clear()
        s.host.roots={};s.host._cohorts={}
        for group in decode(snapshot['groups']):
            state=group['state'];roots=set(group['roots']);s.host._cohorts[id(state)]=roots
            for root in roots:s.host.roots[root]=state
        for k,v in decode(snapshot['host']).items():setattr(s.host,k,v)
        for k,v in decode(snapshot['provider']).items():setattr(s.provider,k,v)
        s.providers.clear();s.providers.update({tid:s.provider for tid in s.provider._timelines})
        s._entry_roots=decode(snapshot['routes']);self.commands=decode(snapshot['commands'])
        self.metadata=decode(snapshot['metadata'])
        # Verify retained transitions and authoritative complete prefixes using
        # their real adapters; checkpoint/receipt relations survive recovery.
        for rows in s.host.histories.values():s.host._verify_history(rows)
        for tid in s.providers:
            previous=None
            for stored in s.provider.history(tid):
                parsed=model.Entry.read(stored.exact,s.catalogue.blue,s.catalogue.registry)
                if parsed!=stored or parsed.previous_blue_id!=previous:raise CorruptStore('timeline predecessor/entry mismatch')
                if parsed.actor.blue_id not in s.provider._actors[tid]:raise CorruptStore('unregistered recovered actor')
                previous=parsed.blue_id
            if tid not in s.provider._unavailable:s.provider.verify(s.provider.acquire(tid))
        for root in s.host.roots:s.host.load_root(root)
        if verify_replay:
            for invocation in s.host.receipts:
                if not s.host.replay_saved(invocation)['verified']:raise CorruptStore('saved original cannot reproduce receipt')

    def execute(self,command_id,operation,*args,**kwargs):
        allowed={'admit_graph','call','close_before','drain'}
        if operation not in allowed:raise ValueError('unsupported durable operation')
        return self.transaction(command_id,(operation,args,kwargs),lambda:getattr(self.stack,operation)(*args,**kwargs))

    def transaction(self,command_id,operands,action):
        """Trusted host adapter callback; executes behind both publication locks."""
        if not isinstance(command_id,str) or not command_id:raise ValueError('command ID required')
        request=digest(encode(operands))
        with self.stack.host._lock,self.stack.provider._lock:
            if command_id in self.commands:
                previous=self.commands[command_id]
                if previous['request']!=request:raise Conflict('command retry has different operands')
                return decode(encode(previous['result']))
            before=self.snapshot();event_count=len(self.stack.host.published)
            try:
                result=action()
                self.commands[command_id]={'request':request,'result':result}
                after=self.snapshot()
                events=encode(self.stack.host.published[event_count:])['$list']
                commit=self.journal.commit('workspace',self.generation,command_id,after,events)
                self.generation=commit.generation
                return result
            except BaseException:
                latest=self.journal.load('workspace')
                if latest:self.generation,snapshot=latest;self.restore(snapshot)
                else:self.restore(before)
                raise

    def close(self):self.journal.close()
