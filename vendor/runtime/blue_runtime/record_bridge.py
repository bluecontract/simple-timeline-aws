"""Host projection for identity-valued fields of standard runtime records.

Admitted Blue DAGs may retain children inline or by reference without changing
identity. The pinned processors parse reference-shaped fields in these records.
This boundary projects those fields, checks the unchanged commitment, and leaves
all role, closed-record, signature and checkpoint validation to the processors.
"""
from copy import deepcopy
from decimal import Decimal
from algorithms import blue as L
from blue_contracts.reference.language import Bridge
from blue_contracts.reference.model import require,pointer
from .identity_cache import IdentityCache


class RecordBridge(Bridge):
    def __init__(self,language,types):
        super().__init__(language)
        self.initialized=types['Processing Initialized Marker']
        self.checkpoint=types['Channel Event Checkpoint']
        self.identity_cache=IdentityCache()

    def identity(self,node):
        try:return self.identity_cache.identity(node)
        except L.Failure as error:self.translate(error)

    def retain(self,nodes):
        retain=getattr(self.language,'retained_records',None)
        if retain is None:return super().retain(nodes)
        try:
            for node in nodes:retain(node,self.context)
        except L.Failure as error:self.translate(error)

    def certify(self,node,goal='value'):
        certify=getattr(self.language,'certify_context',None)
        if certify is None:return super().certify(node,goal)
        try:certify(node,self.context,goal)
        except L.Failure as error:self.translate(error)

    def normalize_input(self,value,*,aliases=True):
        """Carry the host YAML parser's decimal tokens into Language unchanged.

        Do not pre-round through float: Language owns decimal-to-binary64
        conversion. Handle explicit scalar `value` too, which Bridge treats as
        an opaque payload instead of traversing recursively.
        """
        def token(number):
            require(number.is_finite(),'LANGUAGE_InvalidScalar')
            text=str(number)
            return L.NumberToken(text if any(c in text for c in '.eE') else text+'.0')
        if isinstance(value,Decimal):return token(value)
        if type(value) is dict and isinstance(value.get('value'),Decimal):
            value={**value,'value':token(value['value'])}
        return super().normalize_input(value,aliases=aliases)

    def begin_request(self):
        """A host request gets a fresh step budget while keeping resolver caches.

        Call only at a public host operation boundary, never inside a Contracts
        transition or a traversal. The per-request Language cap is unchanged.
        """
        self.context.work=0

    def literal(self,r):
        value=super().literal(r)
        if type(value) is not dict:return value
        typ=value.get('type');paths=[]
        if typ=={'blueId':self.initialized}:paths=[('document',)]
        elif typ=={'blueId':self.checkpoint} and type(value.get('entries')) is dict:
            paths=[('entries',name,'event') for name in value['entries']]
        else:return value
        value=deepcopy(value);projected=False
        for path in paths:
            at=value
            for part in path[:-1]:
                if type(at) is not dict:break
                at=at.get(part)
            if type(at) is not dict:continue
            field=at.get(path[-1])
            if type(field) is dict and set(field)!={'blueId'}:
                child=self.exact(self.select(self.exact(r),pointer(path)))
                at[path[-1]]={'blueId':self.identity(child)};projected=True
        if projected:
            identity=self.identity(self.exact(r))
            require(self.identity(self.node(value))==identity,'RECORD_IDENTITY_MISMATCH')
        return value


def install_record_bridge(processor):
    processor.blue=RecordBridge(processor.blue.language,processor.registry.types)
    processor.registry.blue=processor.blue
    return processor
