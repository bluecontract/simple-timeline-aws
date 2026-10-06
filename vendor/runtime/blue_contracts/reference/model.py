"""Closed records, portable commitments, errors, limits and a shared live meter."""
from __future__ import annotations
from dataclasses import dataclass, field
from copy import deepcopy
import hashlib, json, unicodedata
from pathlib import Path
from typing import Any
from blue_bex import GasExhausted
from blue_bex.gas import DEFAULT as BEX_GAS

SAFE=(1<<53)-1
DEFAULT_LIMIT=100000
LIMITS = {}  # No universal structural ceilings; retained compatibility export.
GAS_PROFILE=json.loads((Path(__file__).resolve().parents[1]/'GAS_MANIFEST.json').read_text())
TARIFF=GAS_PROFILE['weights']

class ContractError(Exception):
    def __init__(self,code,**context):
        self.code=code;self.context=deepcopy(context)
        super().__init__(code+(': '+str(context) if context else ''))
class NeedResources(ContractError):
    def __init__(self,*ids):super().__init__('NEEDS_RESOURCES',required=sorted(set(ids)))
def require(condition,code,**context):
    if not condition:raise ContractError(code,**context)
def token(value):
    require(type(value) is str and bool(value) and '\0' not in value and unicodedata.normalize('NFC',value)==value,'INVALID_TOKEN')
    return value
def integer(value,minimum=0,maximum=SAFE):
    require(type(value) is int and value>=minimum and (maximum is None or value<=maximum),'INVALID_INTEGER',minimum=minimum,maximum=maximum);return value
def closed(value,required,optional=frozenset()):
    require(type(value) is dict and set(required)<=set(value)<=set(required)|set(optional),'INVALID_RECORD')
    return value

def canonical(value):
    """Canonical platform bytes; deliberately not the BlueId algorithm."""
    if value is None:return b'null'
    if type(value) is bool:return b'true' if value else b'false'
    if type(value) is int:
        from decimal import Decimal
        return str(Decimal(value)).encode('ascii')
    if type(value) is str:
        value.encode('utf-8');return json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    if type(value) in (list,tuple):return b'['+b','.join(canonical(v) for v in value)+b']'
    require(type(value) is dict and all(type(k) is str for k in value),'INVALID_RECORD')
    return b'{'+b','.join(canonical(k)+b':'+canonical(value[k]) for k in sorted(value))+b'}'
def digest(kind,value):return 'sha256:'+hashlib.sha256(canonical({'kind':kind,'value':value})).hexdigest()
def segments(path):
    require(type(path) is str and unicodedata.normalize('NFC',path)==path,'INVALID_POINTER')
    if path=='':return ()
    require(path.startswith('/'),'INVALID_POINTER');parts=[]
    for raw in path[1:].split('/'):
        out='';i=0
        while i<len(raw):
            if raw[i]=='~':
                require(i+1<len(raw) and raw[i+1] in '01','INVALID_POINTER');out+='~' if raw[i+1]=='0' else '/';i+=2
            else:out+=raw[i];i+=1
        parts.append(out)
    return tuple(parts)
def pointer(parts):return ''.join('/'+p.replace('~','~0').replace('/','~1') for p in parts)
def prefix(a,b):
    x,y=segments(a),segments(b);return y[:len(x)]==x

@dataclass(frozen=True)
class ChannelLife:
    generation:int
    signature:str
    def wire(self):return dict(generation=self.generation,signature=self.signature)
@dataclass(frozen=True)
class Edge:
    source:str
    path:str
    target:str
    generation:int
    @property
    def key(self):return self.source,self.path
    @property
    def occurrence(self):return self.source,self.path,self.target,self.generation
    def wire(self):return dict(source=self.source,path=self.path,target=self.target,generation=self.generation)
@dataclass
class Document:
    key:str
    body:Any
    blue_id:str=''
    channel_lives:dict=field(default_factory=dict)
    channel_serials:dict=field(default_factory=dict)
    edge_serials:dict=field(default_factory=dict)
    birth:str|None=None
    def metadata(self):return dict(key=self.key,blueId=self.blue_id,channels={k:v.wire() for k,v in sorted(self.channel_lives.items())},channelSerials=dict(sorted(self.channel_serials.items())),edgeSerials=dict(sorted(self.edge_serials.items())),birth=self.birth)
@dataclass
class Snapshot:
    root:str
    documents:dict
    edges:dict=field(default_factory=dict)
    generation:int=0
    revision:int=0
    release:str=''
    runtimes:tuple=()
    def copy(self):return deepcopy(self)
    def wire(self):return dict(root=self.root,documents=[d.metadata() for _,d in sorted(self.documents.items())],edges=[e.wire() for _,e in sorted(self.edges.items())],generation=self.generation,revision=self.revision,release=self.release,runtimes=list(self.runtimes))
    @property
    def identity(self):return digest('contracts.snapshot/completion-1',self.wire())
class Meter:
    def __init__(self,limit=DEFAULT_LIMIT,local_limits=None,known_members=None):
        integer(limit,0,DEFAULT_LIMIT);self.limit=limit;self.used=0;self.trace=[];self.rejected=None;self.owner='';self.schedule=dict(BEX_GAS)
        require(local_limits is None or type(local_limits) is dict,'INVALID_LOCAL_LIMITS')
        self.local_limits=dict(local_limits or {});self.local_used={};self.runtime_schedules={}
        for member,ceiling in self.local_limits.items():
            token(member);integer(ceiling,0,limit)
            require(known_members is None or member in known_members,'UNKNOWN_CAP_TARGET',member=member)
    def policy(self):return {'shared':self.limit,'local':dict(sorted(self.local_limits.items())),'profile':GAS_PROFILE['profile']}
    def debit(self,namespace,counter,units,amount):
        if self.rejected is not None:raise GasExhausted(self.rejected['counter'])
        integer(units,maximum=None);integer(amount,maximum=None)
        row=dict(ordinal=len(self.trace),namespace=namespace,counter=counter,units=units,amount=amount,owner=self.owner)
        shared=self.limit-self.used;local=self.local_limits[self.owner]-self.local_used.get(self.owner,0) if self.owner in self.local_limits else None
        if amount>shared or local is not None and amount>local:
            local_first=local is not None and local<shared
            self.rejected=dict(row,remaining=local if local_first else shared,cap='LOCAL' if local_first else 'SHARED',sharedRemaining=shared,localRemaining=local)
            raise GasExhausted(counter)
        self.trace.append(row);self.used+=amount
        if self.owner:self.local_used[self.owner]=self.local_used.get(self.owner,0)+amount
    def charge(self,counter,units=1,*,amount=None):self.debit('bex',counter,units,self.schedule[counter]*units if amount is None else amount)
    def contracts(self,counter,units=1):
        integer(units,maximum=None)
        if units:self.debit('contracts',counter,units,TARIFF[counter]*units)
@dataclass
class Outcome:
    status:str
    snapshot:Snapshot
    input_identity:str
    invocation:str
    public_events:list=field(default_factory=list)
    event_trace:list=field(default_factory=list)
    work_trace:list=field(default_factory=list)
    changes:list=field(default_factory=list)
    checkpoints:list=field(default_factory=list)
    gas:int=0
    gas_trace:list=field(default_factory=list)
    rejected:Any=None
    diagnostic:Any=None
    completions:list=field(default_factory=list)
    rounds:list=field(default_factory=list)
    units:list=field(default_factory=list)
    @property
    def document(self):
        return self.snapshot
    @property
    def emitted_events(self):
        """Exact emitted values, in FIFO creation order, for this selected root."""
        return tuple({'blueId': row['event']} for row in self.public_events)
    def __iter__(self):
        yield self.document
        yield self.emitted_events
        yield self.gas
    @property
    def commits(self):return self.status=='APPLIED'
    def observations(self):return dict(status=self.status,input=self.input_identity,output=self.snapshot.identity,invocation=self.invocation,publicEvents=self.public_events,events=self.event_trace,work=self.work_trace,changes=self.changes,checkpoints=self.checkpoints,gas=self.gas,gasTrace=self.gas_trace,rejected=self.rejected,diagnostic=self.diagnostic,completions=self.completions,rounds=self.rounds,units=self.units)
    @property
    def receipt(self):return digest('contracts.result/completion-1',self.observations())
def trampoline(generator):
    stack=[generator]
    try:
        while stack:
            try:
                child=next(stack[-1])
                if child is not None:stack.append(child)
            except StopIteration:stack.pop()
    finally:
        for pending in reversed(stack):pending.close()
