from __future__ import annotations
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping, Iterable
import copy, json, hashlib, hmac, secrets
from algorithms import blue as B

_ROOT=Path(__file__).resolve().parents[1]

def registry() -> dict[str,Any]:
    return {name:json.loads((_ROOT/'registry'/f'{name}.json').read_text(encoding='utf-8')) for name in B.CORE}

@dataclass
class MemoryProvider:
    """Defensive in-memory provider of exact text, Source envelopes, or set proofs.

No arbitrary URL is fetched and no unverified response is installed in a trusted
cache. A partial manifest remains unavailable to semantic operations.
"""
    _records: dict[str,Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._records=copy.deepcopy(self._records)

    def set_response(self, blue_id: str, response: Mapping[str,Any]) -> None:
        B.final_id(blue_id)
        if not isinstance(response,Mapping):raise TypeError('provider response must be a mapping')
        self._records[blue_id]=copy.deepcopy(dict(response))

    def set_exact(self, blue_id: str, text: str, *, format: str='json') -> None:
        if not isinstance(text,str):raise TypeError('exact content must be text')
        self.set_response(blue_id,{'text':text,'format':format,'mode':'exact'})

    def set_unavailable(self, blue_id: str) -> None:
        self.set_response(blue_id,{'outcome':'Unavailable'})

    def snapshot(self) -> dict[str,Any]:
        return copy.deepcopy(self._records)

    def merge_responses(self, records: Mapping[str,Any]) -> None:
        """Atomically retain provider evidence, not semantic admission evidence.

        Opening/admission still verifies every requested exact identity. Callers
        importing a processing snapshot must verify it before this operation.
        """
        staged=MemoryProvider(self.snapshot())
        for blue_id,response in records.items():staged.set_response(blue_id,response)
        self._records=staged._records

    def dump(self, path: str|Path) -> None:
        Path(path).write_text(json.dumps(self._records,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')

    @classmethod
    def load(cls,path: str|Path) -> 'MemoryProvider':
        raw=json.loads(Path(path).read_text(encoding='utf-8'),object_pairs_hook=B.pairs_no_duplicates)
        if not isinstance(raw,dict):raise ValueError('provider file must contain an object')
        return cls(raw)

@dataclass(frozen=True)
class AdmittedDocument:
    """Immutable capability returned only after strict admission.

    A serialized record is untrusted until imported with an explicitly configured
    trusted signing key. Python object privacy is not a hostile-code sandbox.
    """
    blue_id: str
    exact_text: str
    canonical_text: str
    goal: str
    policy: str
    original_blue_id: str
    removed_fields: tuple[str,...]
    _records_json: str = field(repr=False)
    _ticket: str = field(repr=False,compare=False)

    def dependency_responses(self) -> dict[str,Any]:
        return json.loads(self._records_json)


class Language:
    """Text-first public API. Source/exact/direct roles are explicit keyword args."""
    def __init__(self,provider: MemoryProvider|None=None, *, aliases: Mapping[str,str]|None=None,
                 directive_aliases: Mapping[str,str]|None=None,limits: B.Limits|None=None,
                 repositories: Iterable[Any]=(), core_contracts: bool=True) -> None:
        self.provider=provider if provider is not None else MemoryProvider()
        self.aliases=dict(aliases or {})
        self.directive_aliases=dict(directive_aliases or {})
        self.limits=replace(limits) if limits is not None else B.Limits()
        self.last_demands:tuple[str,...]=()
        self._registry=registry()
        self._issued:dict[str,tuple[AdmittedDocument,dict]]= {}
        self._repositories: dict[str,dict[str,Any]] = {}
        self._core_records: dict[str,dict[str,Any]] = {}
        self._repository_base_aliases: dict[str,str|None] = {}
        self._context() # verify bindings and all six actual registry files
        if core_contracts:
            from blue_contracts.reference.registry import core_catalogue
            core_aliases,core_records=core_catalogue()
            for alias,identity in core_aliases.items():
                B.require(self.aliases.get(alias,identity)==identity,'InvalidSource','core alias conflict: '+alias)
            self._core_records=core_records
            self.aliases.update(core_aliases)
        for repository in repositories: self.enable_repository(repository)

    @property
    def repositories(self) -> dict[str,str]:
        """Enabled repository names and immutable manifest identities."""
        return {name: value['identity'] for name,value in self._repositories.items()}

    def enable_repository(self, repository: Any) -> None:
        """Install an immutable Repository without changing the base provider.

        Configuration is per instance, not global and not thread-safe to mutate
        during an operation. Admission still validates referenced definitions.
        """
        from blue_repository.api import Repository, RepositoryError
        if not isinstance(repository,Repository): raise TypeError('expected Repository')
        name, identity = repository.name, repository.identity
        old=self._repositories.get(name)
        if old is not None:
            if old['identity'] == identity: return
            raise RepositoryError('different repository already enabled under '+name)
        aliases, records=repository.aliases,repository.records
        for alias,tid in aliases.items():
            existing=B.CORE.get(alias,self.aliases.get(alias))
            if existing is not None and existing != tid:
                raise RepositoryError('alias conflict: '+alias)
        # Validate the entire new configuration before mutating any binding.
        current=self.provider.snapshot()
        for mounted in self._repositories.values():current.update(mounted['records'])
        for tid,response in records.items():
            if tid in current and current[tid] != response:
                # Alternate materializations are allowed only after their
                # claimed identity independently verifies; invalid evidence
                # never wins by provider-order accident.
                context=B.initialize(self._registry,{tid:current[tid]},limits=replace(self.limits))
                try:B.open_exact(B.Ref(tid),context)
                except B.Failure as error:raise RepositoryError('conflicting provider evidence: '+tid) from error
        for alias,tid in aliases.items():
            if alias not in self._repository_base_aliases:self._repository_base_aliases[alias]=self.aliases.get(alias)
            self.aliases[alias]=tid
        self._repositories[name]={'identity':identity,'aliases':aliases,'records':records}

    def disable_repository(self, name: str) -> None:
        """Remove name availability; never revoke content already published.

        Published immutable dependencies and previously admitted handles remain
        valid. Disabling a repository is NOT data deletion or access revocation.
        """
        mounted=self._repositories.pop(name,None)
        if mounted is None:raise KeyError(name)
        remaining={alias:tid for repo in self._repositories.values() for alias,tid in repo['aliases'].items()}
        for alias,tid in mounted['aliases'].items():
            if alias in remaining:continue
            before=self._repository_base_aliases.pop(alias,None)
            if self.aliases.get(alias)==tid:
                if before is None:self.aliases.pop(alias,None)
                else:self.aliases[alias]=before

    def processing_context(self) -> B.Context:
        """Fresh isolated resolver including mounted repositories and bindings.

        This public integration port exposes the pinned Language operation
        context. Mutating its evidence does not install it in this Language.
        """
        records=dict(self._core_records)
        for mounted in self._repositories.values():records.update(mounted['records'])
        records.update(self.provider.snapshot())
        c=B.initialize(self._registry,records,self.aliases,replace(self.limits))
        c.directive_aliases=dict(self.directive_aliases)
        # Shipped extension definitions are exact environment inputs, not invented
        # bodies selected from a human name or an unverified ID constant.
        definition=_ROOT/'registry/transforms/SetRootSourceField.json'
        if definition.exists():
            n=B.normalize(B.parse(definition.read_text(encoding='utf-8'),limits=c.limits),c)
            B.require(B.identity(n)==B.SET_SOURCE_FIELD_ID,'RegistryMismatch','Set Root Source Field')
        return c

    def _context(self) -> B.Context:
        return self.processing_context()

    @staticmethod
    def _input(text: str|bytes,c: B.Context,mode: str,format: str) -> B.Node|B.Ref:
        with B.error_scope(c,phase='parsing'): raw=B.parse(text,format,c.limits)
        if mode=='source':return B.prepare_source(raw,c)
        if mode=='canonical': return B.decode_canonical(raw,c)
        B.require(mode in ('exact','direct'),'InvalidOperation','input role')
        return B.normalize(raw,c,mode)

    def _run(self,fn):
        c=self._context()
        try:
            with B.error_scope(c,'','operation'): return fn(c)
        except RecursionError as error:
            raise B.Failure('OperationLimitExceeded','recursion') from error
        finally:self.last_demands=tuple(c.demands)

    def preprocess(self,text: str|bytes, *, format: str='json') -> str:
        """Return preprocessed Source text; list controls may remain instructions."""
        def op(c):
            def wire(x):
                if isinstance(x,(B.Node,B.Ref,B.Local)): return B.export_tree(x)
                if isinstance(x,list): return [wire(v) for v in x]
                if isinstance(x,dict): return {k:wire(v) for k,v in x.items()}
                return x
            value=B.preprocess(B.parse(text,format,c.limits),c)
            return B.wire_text(wire(value))
        return self._run(op)

    @staticmethod
    def _policy() -> str:
        # Bind issued evidence to both executable behavior and its stated contract.
        files=['SPECIFICATION_1.0.md','algorithms/blue.py','blue_language/api.py']
        value=[(name,hashlib.sha256((_ROOT/name).read_bytes()).hexdigest()) for name in files]
        return 'sha256:'+hashlib.sha256(json.dumps(value,separators=(',',':')).encode()).hexdigest()

    @staticmethod
    def _document_payload(doc: AdmittedDocument) -> dict[str,Any]:
        return {'blueId':doc.blue_id,'exactText':doc.exact_text,'canonicalText':doc.canonical_text,
                'goal':doc.goal,'policy':doc.policy,'originalBlueId':doc.original_blue_id,
                'removedFields':list(doc.removed_fields),'records':doc.dependency_responses()}

    def _issue(self,payload: Mapping[str,Any]) -> AdmittedDocument:
        ticket=secrets.token_hex(32)
        doc=AdmittedDocument(payload['blueId'],payload['exactText'],payload['canonicalText'],
              payload['goal'],payload['policy'],payload['originalBlueId'],tuple(payload['removedFields']),
              json.dumps(payload['records'],sort_keys=True,separators=(',',':'),ensure_ascii=False),ticket)
        self._issued[ticket]=(doc,copy.deepcopy(dict(payload)))
        return doc

    def _check_handle(self,doc: AdmittedDocument,goal: str|None=None) -> AdmittedDocument:
        entry=self._issued.get(doc._ticket)
        B.require(entry is not None and entry[0] is doc and entry[1]==self._document_payload(doc),
                  'InvalidValidationEvidence','handle was not issued by this instance or was changed')
        B.require(doc.policy==self._policy(),'InvalidValidationEvidence','policy changed')
        B.require(goal is None or doc.goal==goal,'InvalidValidationEvidence','validation role mismatch')
        self.last_demands=()
        return doc

    def create(self,text: str|bytes|AdmittedDocument, *, goal: str='value',
               mode: str='source',format: str='json') -> AdmittedDocument:
        """Validate all reachable content and declared types before success.

        Source creation removes only exact whole-child duplicates at this root.
        Existing exact/canonical references retain their original addresses.
        """
        if isinstance(text,AdmittedDocument): return self._check_handle(text,goal)
        def op(c):
            c.diagnostic_goal=goal
            n=self._input(text,c,mode,format);c.diagnostic_root=n;before=B.identity(n)
            B.strict_certify(n,c,goal)  # Never clean away an invalid authored override.
            if mode=='source': n,removed=B.omit_root_duplicates(n,c)
            else: removed=()
            if removed: B.strict_certify(n,c,goal)
            exact=B.export_exact(n,c);canonical=B.canonical_export(n,c)
            records=B.admitted_records(n,c)
            return self._issue({'blueId':B.identity(n),'exactText':exact,'canonicalText':canonical,
                    'goal':goal,'policy':self._policy(),'originalBlueId':before,
                    'removedFields':list(removed),'records':records})
        return self._run(op)

    def admit_definition(self,text: str|bytes, *, mode: str='source',format: str='json') -> AdmittedDocument:
        return self.create(text,goal='definition',mode=mode,format=format)

    def identify(self,text: str|bytes|AdmittedDocument, *, goal: str='value',
                 mode: str='source',format: str='json') -> str:
        """Validated canonical identity; use raw_identify for non-certifying hashing."""
        return self.create(text,goal=goal,mode=mode,format=format).blue_id

    def raw_identify(self,text: str|bytes, *, mode: str='source',format: str='json') -> str:
        """Structural calculation only. This never certifies semantic validity."""
        return self._run(lambda c:B.identity(self._input(text,c,mode,format)))

    def raw_canonicalize(self,text: str|bytes, *, mode: str='source',format: str='json') -> str:
        """Lossless full exact export without a validity claim or duplicate removal."""
        return self._run(lambda c:B.export_exact(self._input(text,c,mode,format),c))

    def canonicalize(self,text: str|bytes|AdmittedDocument, *, goal: str='value',
                     mode: str='source',format: str='json',compact: bool=True) -> str:
        doc=self.create(text,goal=goal,mode=mode,format=format)
        return doc.canonical_text if compact else doc.exact_text

    def inspect(self,text: str|bytes, *, goal: str='value',mode: str='source',format: str='json') -> dict[str,Any]:
        d=self.create(text,goal=goal,mode=mode,format=format)
        return {'blueId':d.blue_id,'canonicalText':d.canonical_text,'canonicalMode':'canonical',
                'exactText':d.exact_text,'validated':True,'goal':d.goal,
                'originalBlueId':d.original_blue_id,'removedFields':list(d.removed_fields),
                'dependencies':sorted(d.dependency_responses())}

    def check(self,text: str|bytes, *, goal: str='value',mode: str='source',format: str='json') -> dict[str,Any]:
        """Structured admission result. It never retries a value as a definition."""
        try:
            return {'outcome':'Established',**self.inspect(text,goal=goal,mode=mode,format=format)}
        except B.Failure as error:
            status='Incomplete' if error.category in ('ProviderUnavailable','OperationLimitExceeded') else 'Invalid'
            return {'outcome':status,**error.as_dict(),'requestedBlueIds':list(self.last_demands)}

    def validate(self,text: str|bytes, *, goal: str='value',mode: str='source',format: str='json') -> str:
        return self.create(text,goal=goal,mode=mode,format=format).blue_id

    def query(self,text: str|bytes,path: str='',question: str='value', *, mode: str='source',format: str='json') -> dict[str,Any]:
        return self._run(lambda c:B.outcome(lambda:B.observe(self._input(text,c,mode,format),path,question,c)))

    def resolve(self,text: str|bytes, *, goal: str='value',mode: str='source',format: str='json') -> dict[str,Any]:
        d=self.create(text,goal=goal,mode=mode,format=format)
        demands=self.last_demands
        c=self._context();c.provider.update(d.dependency_responses())
        n=self._input(d.exact_text,c,'exact','json')
        view=describe_view(B.recipe(n),c)
        self.last_demands=demands
        return {'blueId':d.blue_id,'exactText':d.exact_text,'canonicalText':d.canonical_text,'view':view}

    def minimize(self,text: str|bytes, *, goal: str='value',mode: str='source',format: str='json') -> str:
        def op(c):
            c.diagnostic_goal=goal
            n=self._input(text,c,mode,format);c.diagnostic_root=n;B.strict_certify(n,c,goal)
            result=B.minimize(n,c,goal)
            # A successful text-only authoring result must work in the next public
            # call, not only in this temporary warm dependency context.
            fresh=self._context()
            try:
                candidate=self._input(result,fresh,'source','json')
                B.strict_certify(candidate,fresh,goal)
                # Same-view comparison can use original verified input bodies.
                fresh.bodies.update(c.bodies);fresh.proofs.update(c.proofs)
                B.require(B.same_view(n,candidate,fresh),'InternalError','public minimize roundtrip')
                return result
            except B.Failure as error:
                if error.category not in ('ProviderUnavailable','OperationLimitExceeded'): raise
                if mode=='source':
                    # The unchanged original Source is an allowed nonminimal
                    # rendering. Keep its inline definitions and new values.
                    return B.wire_text(B.parse(text,format,c.limits))
                raise B.Failure('MinimizationDependencyRequired',error.detail) from error
        return self._run(op)

    def expand(self,text: str|bytes,paths: Iterable[str]=('',), *, mode: str='exact',format: str='json') -> str:
        return self._run(lambda c:B.wire_text(B.export_tree(B.expand(self._input(text,c,mode,format),list(paths),c))))

    def collapse(self,text: str|bytes,paths: Iterable[str]=('',), *, mode: str='exact',format: str='json') -> str:
        return self._run(lambda c:B.wire_text(B.export_tree(B.collapse(self._input(text,c,mode,format),list(paths),c))))

    def publish(self,text: str|bytes|AdmittedDocument, *, goal: str='value',
                mode: str='source',format: str='json') -> str:
        d=self.create(text,goal=goal,mode=mode,format=format)
        demands=self.last_demands
        result=self.publish_document(d)
        self.last_demands=demands
        return result

    def publish_document(self,doc: AdmittedDocument) -> str:
        self._check_handle(doc)
        # Build one replacement store state; no writes precede successful admission.
        updated=self.provider.snapshot();updated.update(doc.dependency_responses())
        self.provider._records=updated
        return doc.blue_id

    def load(self,blue_id: str, *, goal: str='value') -> AdmittedDocument:
        return self.create(json.dumps({'blueId':B.final_id(blue_id)}),goal=goal,mode='exact')

    def export_validated(self,doc: AdmittedDocument,signing_key: bytes) -> str:
        """Seal reusable evidence. The host explicitly supplies a trusted secret."""
        self._check_handle(doc)
        B.require(isinstance(signing_key,bytes) and len(signing_key)>=32,
                  'InvalidValidationEvidence','at least 32 key bytes required')
        payload=self._document_payload(doc)
        wire=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False)
        signature=hmac.new(signing_key,wire.encode('utf-8'),hashlib.sha256).hexdigest()
        sealed=json.dumps({'payload':payload,'hmacSha256':signature},sort_keys=True,ensure_ascii=False)
        B.require(B.within(len(sealed.encode('utf-8')),self.limits.text_bytes),'OperationLimitExceeded','validation record bytes')
        return sealed

    def import_validated(self,sealed: str,signing_key: bytes, *, goal: str|None=None) -> AdmittedDocument:
        """Trust an explicitly selected issuer/key; never a caller's valid:true flag."""
        B.require(isinstance(signing_key,bytes) and len(signing_key)>=32,'InvalidValidationEvidence','key')
        B.require(isinstance(sealed,str),'InvalidValidationEvidence','record text')
        B.checked_unicode(sealed)
        B.require(B.within(len(sealed.encode('utf-8')),self.limits.text_bytes),'OperationLimitExceeded','validation record bytes')
        try:
            record=json.loads(sealed,object_pairs_hook=B.pairs_no_duplicates)
            B.require(isinstance(record,dict) and set(record)=={'payload','hmacSha256'},'InvalidValidationEvidence','envelope')
            payload=record['payload']
            B.require(isinstance(payload,dict) and set(payload)=={'blueId','exactText','canonicalText','goal','policy','originalBlueId','removedFields','records'},'InvalidValidationEvidence','payload')
            wire=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False)
            signature=hmac.new(signing_key,wire.encode('utf-8'),hashlib.sha256).hexdigest()
            B.require(isinstance(record['hmacSha256'],str) and hmac.compare_digest(signature,record['hmacSha256']),
                      'InvalidValidationEvidence','signature')
            B.require(payload['policy']==self._policy(),'InvalidValidationEvidence','policy mismatch')
            B.require(payload['goal'] in ('definition','value') and (goal is None or goal==payload['goal']),
                      'InvalidValidationEvidence','role mismatch')
            B.final_id(payload['blueId']);B.final_id(payload['originalBlueId'])
            B.require(isinstance(payload['exactText'],str) and isinstance(payload['canonicalText'],str)
                      and isinstance(payload['records'],dict) and isinstance(payload['removedFields'],list),
                      'InvalidValidationEvidence','field types')
        except (ValueError,KeyError,TypeError) as error:
            raise B.Failure('InvalidValidationEvidence','malformed record') from error
        self.last_demands=()
        return self._issue(payload)

    def publish_raw(self,text: str|bytes, *, mode: str='source',format: str='json') -> str:
        """Explicit untrusted content-store import; never semantic admission."""
        def op(c):
            n=self._input(text,c,mode,format);rid=B.identity(n)
            # Publication asserts available content, not merely an ID string.
            if isinstance(n,B.Ref):
                body=B.open_exact(n,c)
                if '#' in rid:
                    # Existing cyclic provider evidence already authenticates it.
                    return rid
                c.remember(body)
            else:
                c.remember(n)
            prepared={key:{'text':B.export_exact(body,c),'mode':'exact'} for key,body in list(c.bodies.items()) if key not in B.CORE.values() and '#'not in key}
            for key,response in prepared.items():self.provider.set_response(key,response)
            return rid
        return self._run(op)

    def verify(self,blue_id: str) -> str:
        return self._run(lambda c:B.export_exact(B.open_exact(B.Ref(B.final_id(blue_id)),c),c))

    def finalize(self,documents: Iterable[str], *, format: str='json',publish: bool=False,goal: str='value') -> dict[str,Any]:
        def op(c):
            z=B.finalize_set([B.parse(s,format,c.limits)for s in documents],c)
            proof=B.wire_text({'members':[B.export_tree(n)for n in z['canonical']]})
            bodies=[B.export_exact(n,c)for n in z['bodies']]
            staged={rid:{'proof':proof,'body':bodies[int(rid.split('#')[1])]} for rid in z['ids']}
            c.provider.update(staged)
            for rid in z['ids']: B.strict_certify(B.Ref(rid),c,goal)
            if publish:
                records={}
                for rid in z['ids']: records.update(B.admitted_records(B.Ref(rid),c))
                updated=self.provider.snapshot();updated.update(records);self.provider._records=updated
            return {'master':z['master'],'blueIds':z['ids'],'proofText':proof,'bodyTexts':bodies}
        return self._run(op)

    def split(self,text: str|bytes,paths: Iterable[str], *, mode: str='exact',format: str='json') -> dict[str,Any]:
        def op(c):
            n=self._input(text,c,mode,format);out,fragments=B.split_fragments(n,list(paths),c)
            return {'blueId':B.identity(n),'rootText':B.export_exact(out,c),
                    'fragments':{key:B.export_exact(value,c)for key,value in fragments.items()},
                    'proofTexts':{key:B.wire_text(c.proofs[key])for key in fragments if '#' in key and key in c.proofs}}
        return self._run(op)


def describe_view(r:B.Recipe,c:B.Context,active:frozenset=frozenset(),depth:int=0) -> dict[str,Any]:
    """Tagged observation of a certified view; never exported as exact Blue content."""
    B.require(B.within(depth+1,c.limits.depth),'OperationLimitExceeded','view export')
    key=r.key()
    if key in active:return {'recursive':True,'contributionIds':list(key[0]),'requirements':list(key[1])}
    h=B.head(r,c);out={'kind':h.kind,'labels':dict(h.labels),'constraints':B.describe_constraints(h.constraints)}
    if h.specification is not None:out['specification']={'blueId':h.specification.id}
    if h.type_id:out['effectiveType']=h.type_id
    if h.value is not B.ABSENT:out['value']=B.literal_output(h.value,h.core)
    active=active|{key}
    if h.fields:out['fields']={k:describe_view(B.child_recipe(h,k),c,active,depth+1)for k in h.fields}
    if h.items is not None:out['items']=[describe_view(B.child_recipe(h,i),c,active,depth+1)for i in range(len(h.items))]
    if h.contracts is not None:out['contracts']=describe_view(h.contracts,c,active,depth+1)
    return out
