"""Explicit trusted runtime bindings with read-only inputs and staged effects."""
from dataclasses import dataclass,asdict
from copy import deepcopy
from types import MappingProxyType
from blue_host import HostIncomplete, HOST_FAILURES, incomplete, host_boundary
from algorithms import blue as L
from blue_bex import GasExhausted
from .model import require,closed,token,integer,segments,digest,ContractError


def frozen(value):
    if type(value) is dict:return MappingProxyType({k:frozen(v) for k,v in value.items()})
    if type(value) in (list,tuple):return tuple(frozen(v) for v in value)
    return value


def data_copy(value):
    """Copy verified data returned from a read-only context, never capabilities."""
    if isinstance(value, (dict, MappingProxyType)):
        return {k: data_copy(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [data_copy(v) for v in value]
    require(value is None or type(value) in (str, int, float, bool), 'INVALID_VERIFIED_ADMISSION')
    return value


@dataclass(frozen=True)
class RuntimeBinding:
    type_id:str
    semantics_id:str
    role:str
    header_fields:tuple
    body_fields:tuple
    namespace:str
    tariff:tuple
    inherits_to_subtypes:bool=False
    peer_fields:tuple=()
    meter_mode:str='live'

    def __post_init__(self):
        L.final_id(self.type_id);L.final_id(self.semantics_id);token(self.namespace)
        require(self.namespace not in ('bex','contracts'),'RESERVED_GAS_NAMESPACE')
        require(self.role in ('external-channel','processor-channel','handler','marker','step'),'INVALID_RUNTIME_ROLE')
        require(type(self.inherits_to_subtypes) is bool,'INVALID_RUNTIME_BINDING')
        require(self.meter_mode in ('live','ledger'),'INVALID_RUNTIME_METER_MODE')
        for value in (self.header_fields,self.body_fields,self.tariff,self.peer_fields):require(type(value) is tuple,'MUTABLE_RUNTIME_BINDING')
        fields=self.header_fields+self.body_fields
        require(len(fields)==len(set(fields)),'AMBIGUOUS_RUNTIME_FIELDS')
        for name in fields:token(name);require(not name.startswith('_') and name not in ('type','specification','name','description','order'),'INVALID_RUNTIME_FIELD')
        require(set(self.peer_fields)<=set(self.header_fields),'INVALID_PEER_FIELDS')
        require(len(dict(self.tariff))==len(self.tariff),'DUPLICATE_RUNTIME_COUNTER')
        for name,weight in self.tariff:token(name);integer(weight)

    def wire(self):
        def lists(value):
            if type(value) is dict:return {k:lists(v) for k,v in value.items()}
            if type(value) in (list,tuple):return [lists(v) for v in value]
            return value
        return lists(asdict(self))


class RuntimeMeter:
    """A runtime cannot change ownership, tariffs, or the parent allowance."""
    def __init__(self,parent,binding,owner):
        self.__parent=parent;self.__binding=binding;self.__owner=owner
        self.__start=parent.used;self.__rows=[];self.__rejected=None;self.__finished=False;self.__merged=False
        shared=parent.limit-parent.used
        local=parent.local_limits.get(owner,parent.limit)-parent.local_used.get(owner,0)
        self.__allowance=min(shared,local) if owner in parent.local_limits else shared

    @property
    def remaining(self):
        return self.__allowance-sum(row[2] for row in self.__rows)

    def charge(self,counter,units=1):
        require(not self.__finished and self.__rejected is None,'CLOSED_RUNTIME_LEDGER')
        integer(units,maximum=None);weights=dict(self.__binding.tariff);require(counter in weights,'UNDECLARED_RUNTIME_COUNTER',counter=counter)
        amount=weights[counter]*units
        if self.__binding.meter_mode=='live':
            self.__parent.owner=self.__owner;self.__parent.debit(self.__binding.namespace,counter,units,amount)
        elif amount>self.remaining:
            self.__rejected=(counter,units,amount);raise GasExhausted(counter)
        self.__rows.append((counter,units,amount))

    def finish(self):
        require(self.__binding.meter_mode=='ledger','DOUBLE_GAS_DEBIT')
        self.__finished=True;return self

    def merge(self,returned=None,*,failed=False):
        require(not self.__merged,'DOUBLE_GAS_DEBIT');self.__merged=True
        if self.__binding.meter_mode=='live':require(returned is None,'DOUBLE_GAS_DEBIT');return
        require(failed or returned is self and self.__finished,'INVALID_RUNTIME_LEDGER')
        require(self.__parent.used==self.__start,'RUNTIME_LEDGER_ALLOWANCE_CHANGED')
        self.__parent.owner=self.__owner
        for counter,units,amount in self.__rows:self.__parent.debit(self.__binding.namespace,counter,units,amount)
        if self.__rejected:
            counter,units,amount=self.__rejected
            self.__parent.debit(self.__binding.namespace,counter,units,amount)
            raise ContractError('RUNTIME_LEDGER_REJECTION_MISMATCH')
        self.__finished=True


@dataclass(frozen=True)
class RuntimeContext:
    event:object
    header:object
    body:object
    steps:object
    processing_event:str|None
    timestamp:int|None
    read:object
    gas:RuntimeMeter
    call:object=None


class Runtime:
    """An installed implementation is trusted deterministic code, not a sandbox."""
    def __init__(self,binding,implementation):
        self.binding=binding;self.implementation=implementation
        self.role={'external-channel':'extension_external','processor-channel':'extension_channel','handler':'extension_handler','marker':'extension_marker','step':'extension_step'}[binding.role]
        if binding.role in ('handler','step'):require(callable(getattr(implementation,'execute',None)),'MISSING_RUNTIME_EXECUTOR')
        if binding.role=='external-channel':
            require(callable(getattr(implementation,'accept',None)),'MISSING_RUNTIME_CHANNEL_FUNCTION',function='accept')
            require(binding.meter_mode=='live','EXTERNAL_RUNTIME_REQUIRES_LIVE_METER')
        if binding.role=='processor-channel':
            families=getattr(implementation,'families',())
            require(type(families) is tuple and families and set(families)<={'TRIGGERED','EMBEDDED','UPDATE','INITIALIZATION','TERMINATION'},'INVALID_RUNTIME_EVENT_FAMILIES')
            for name in ('accept_internal','channelize_internal'):require(callable(getattr(implementation,name,None)),'MISSING_RUNTIME_CHANNEL_FUNCTION',function=name)

    def header(self,declaration):
        return frozen({k:deepcopy(declaration[k]) for k in self.binding.header_fields if k in declaration})

    def peers(self,declaration,contracts):
        names=set()
        for field in self.binding.peer_fields:
            values=declaration.get(field,[]);require(type(values) is list and all(type(x) is str for x in values),'INVALID_PEER_DECLARATION')
            names.update(values)
        def lookup(name):
            require(name in names,'UNDECLARED_PEER_LOOKUP',peer=name)
            value=contracts.get(name)
            if value is None:return frozen({'status':'absent'})
            if value['_role'] not in {'external','all','composite','triggered','embedded_event','update','lifecycle','extension_external','extension_channel'}:return frozen({'status':'non-channel'})
            return frozen({'status':'present','header':{k:v for k,v in value.items() if not k.startswith('_')}})
        return lookup

    def accept_external(self, declaration, contracts, registry, event, timestamp, checkpoint, meter, owner,
                        *, document=None, channel=None, generation=None, evidence=None):
        from .channels import event_observation
        runtime_meter = RuntimeMeter(meter, self.binding, owner)
        context = ExternalChannelContext(
            self.header(declaration), frozen(event_observation(registry, event)),
            timestamp, frozen(checkpoint), self.peers(declaration, contracts), runtime_meter,
            owner, document, channel, generation, frozen(evidence))
        try:
            accepted = self.implementation.accept(context)
            require(type(accepted) is bool, 'INVALID_RUNTIME_ACCEPTANCE')
        except (GasExhausted, ContractError):
            runtime_meter.merge(failed=True)
            raise
        except HOST_FAILURES as exc:raise incomplete(exc) from exc
        except Exception as exc:
            runtime_meter.merge(failed=True)
            raise ContractError('RUNTIME_FAILURE', exception=type(exc).__name__) from exc
        runtime_meter.merge()
        return accepted


@dataclass(frozen=True)
class ExternalChannelContext:
    header: object
    event: object
    timestamp: int
    checkpoint: object
    peers: object
    gas: RuntimeMeter
    member: str | None = None
    document: str | None = None
    channel: str | None = None
    generation: int | None = None
    evidence: object = None


@dataclass(frozen=True)
class AdmissionContext:
    """Exact invocation facts passed to an installed evidence verifier.

    The verifier, not the submitting client, establishes channel decisions.
    Its result is private to this invocation and exposed read-only to accept().
    A serialized invocation retains the original evidence and verifies it again.
    """
    snapshot: str
    event: str
    timestamp: int
    runtime: object
    members: object
    evidence: object


def prepare_admissions(run):
    """Verify configured evidence without introducing a fourth process input."""
    from .channels import checkpoint
    supplied = run.admission_evidence
    require(type(supplied) is dict, 'INVALID_ADMISSION_EVIDENCE')
    runtimes = {}
    for member in sorted(run.graph.reachable(active=True)):
        doc = run.input.documents[member]
        for key, declaration in sorted(run.reg.contracts(doc.body).items()):
            if declaration['_role'] != 'extension_external':
                continue
            runtime = declaration['_extension']
            if not callable(getattr(runtime.implementation, 'verify_admission', None)):
                continue
            binding = runtime.binding.type_id
            _, rows = runtimes.setdefault(binding, (runtime, []))
            rows.append(dict(member=member, document=doc.blue_id, channel=key,
                             declaration=run.blue.identity(run.blue.exact(declaration['_recipe'])),
                             generation=doc.channel_lives[key].generation,
                             header={k: declaration[k] for k in runtime.binding.header_fields if k in declaration},
                             checkpoint=checkpoint(run.reg, doc, key)))
    require(set(supplied) <= set(runtimes), 'UNUSED_ADMISSION_EVIDENCE')
    result = {}
    for binding, (runtime, rows) in sorted(runtimes.items()):
        context = AdmissionContext(run.input.identity, run.event_id, run.timestamp,
                                   frozen(runtime.binding.wire()), frozen(rows), frozen(supplied.get(binding)))
        try:
            verified = runtime.implementation.verify_admission(context)
            require(type(verified) is dict, 'INVALID_VERIFIED_ADMISSION')
            # Retain a private data copy; accept_external freezes each read.
            result[binding] = data_copy(verified)
        except ContractError:
            raise
        except HOST_FAILURES as exc:raise incomplete(exc) from exc
        except Exception as exc:
            raise ContractError('INVALID_ADMISSION_EVIDENCE', exception=type(exc).__name__) from exc
    run.external_admissions = result


def validate_result(value):
    closed(value,set(),{'patches','events','termination','runtimeLedger'})
    patches=value.get('patches',[]);events=value.get('events',[])
    require(type(patches) is list and type(events) is list,'INVALID_EXECUTION_RESULT')
    for patch in patches:
        require(type(patch) is dict and patch.get('op') in ('add','replace','remove'),'INVALID_PATCH')
        closed(patch,{'op','path'} if patch['op']=='remove' else {'op','path','val'})
        require(segments(patch['path']) and all(segments(patch['path'])),'INVALID_PATCH_PATH')
    if 'termination' in value:
        termination=closed(value['termination'],{'cause'},{'reason'})
        require(type(termination['cause']) is str and ('reason' not in termination or type(termination['reason']) is str),'INVALID_TERMINATION')
    return {'patches':patches,'events':events,**{k:v for k,v in value.items() if k not in ('patches','events')}}
