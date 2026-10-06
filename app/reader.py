"""Read-only transport verifier with lazy Blue references.

Received objects are staged using Language.publish_raw, never admitted as executable
documents. Blue structural identity, protocol field checks and provider signatures
establish page evidence. App-message semantic admission is a later feeder step.
A checkpoint may name a head that appears only on a subsequent page.
"""
import copy,json
from .catalogue import Exact
from reference import check,hexbytes,validate_endpoint,MAX_TIME
from algorithms import blue as B

class ReaderExact(Exact):
    def put(self,obj):
        if isinstance(obj,dict) and set(obj)=={'blueId'}:
            B.final_id(obj['blueId']);return obj['blueId']
        source=json.dumps(obj,sort_keys=True,separators=(',',':'))
        if source in self._identified:return self._identified[source]
        bid=self.language.publish_raw(source,format='json')
        self.objects[bid]=copy.deepcopy(obj);self._identified[source]=bid;return bid
    def identity(self,value):return self.put(value)
    def require_kind(self,value,name):
        obj=super().require_kind(value,name)
        required={
            'Signed Timeline':('provider','url','publicRead'),
            'Timeline Entry':('timeline','timestamp','actor','message'),
            'Provider Attestation':('provider','object','signature'),
            'Timeline Attestation':('timeline','guarantee','signature'),
            'Timeline Completeness Guarantee':('timeline','completeBefore'),
            'Timeline Read Response':('request','checkpoint'),
            'Timeline Entries Page':('timeline','checkpoint','entries','hasMore'),
            'Timeline Read Cursor':('timeline','checkpoint'),
            'Read Timeline Request':('timeline','limit'),
        }.get(name,())
        check(all(k in obj for k in required),'MISSING_PROTOCOL_FIELD')
        if name=='Signed Timeline':
            check(type(obj['publicRead']) is bool,'INVALID_PUBLIC_READ');validate_endpoint(obj['url'])
        elif name=='Timeline Entry':
            check(type(obj['timestamp']) is int and 0<=obj['timestamp']<=MAX_TIME,'INVALID_TIMESTAMP')
            check(self.kind(obj['actor'],'Principal Actor') or self.kind(obj['actor'],'Agent Actor'),'INVALID_ACTOR')
        elif name=='Timeline Entries Page':
            check(isinstance(obj['entries'],list) and type(obj['hasMore']) is bool,'INVALID_PAGE')
        elif name in ('Provider Attestation','Timeline Attestation'):hexbytes(obj['signature'],64)
        return obj
