"""Owner-only presentation of a committed snapshot, without contract execution.

This is a read model, never an input to authorization or signed protocol responses.
StateStore checks the S3 snapshot hash and the current DynamoDB pointer first.
"""
import copy,re
from .provider import resolved_details,inline_provider

FORMAT='simple-timeline-console/1'

class ConsoleView:
    def __init__(self,snapshot):
        self.snapshot=snapshot
        self.view=snapshot['console']
        if self.view['format']!=FORMAT:raise ValueError('INCOMPATIBLE_CONSOLE_VIEW')
        self.workspace=copy.deepcopy(self.view['workspace'])
        provider=snapshot['objects'][snapshot['provider']]
        self.workspace['overview']['providerDetails']=resolved_details(snapshot['definition'],provider)

    def wire(self,value):
        if isinstance(value,list):return [self.wire(x) for x in value]
        if isinstance(value,dict):
            return {k:{'blueId':self.view['aliases'][v]} if k in ('type','itemType','keyType','valueType') and isinstance(v,str) and v in self.view['aliases'] else self.wire(v) for k,v in value.items()}
        return value

    def get(self,value):
        if isinstance(value,dict) and set(value)=={'blueId'}:
            bid=value['blueId']
            if bid not in self.snapshot['objects']:raise LookupError(bid)
            value=self.snapshot['objects'][bid]
        return copy.deepcopy(value)

    def read(self,path,query):
        workspace=self.workspace
        if path=='/owner/workspace':return copy.deepcopy(workspace)
        if path=='/owner/overview':return copy.deepcopy(workspace['overview'])
        if path=='/owner/timelines':return {'items':copy.deepcopy(workspace['timelines'])}
        if path=='/owner/access':return {'items':copy.deepcopy(workspace['access'])}
        if path.startswith('/owner/objects/'):
            bid=path.rsplit('/',1)[-1]
            value=self.snapshot['definition'] if bid==self.view['providerType'] else self.get({'blueId':bid})
            return self.wire(inline_provider(value,self.snapshot['provider'],self.get({'blueId':self.snapshot['provider']})))
        match=re.fullmatch('/owner/timelines/([^/]+)/entries',path)
        if match:
            timeline=self.snapshot['providerState']['timelines'].get(match[1])
            if timeline is None:raise ValueError('NOT_FOUND')
            offset=int(query.get('offset','0'))
            if offset<0:raise ValueError('INVALID_REQUEST')
            ids=timeline['entries'];items=[]
            for bid in list(reversed(ids))[offset:offset+50]:
                entry=self.get({'blueId':bid})
                entry['actor']=self.get(entry['actor'])
                entry['message']=self.get(entry['message'])
                items.append({'blueId':bid,'entry':self.wire(entry)})
            return {'items':items,'hasMore':offset+50<len(ids),'total':len(ids),'offset':offset}
        raise ValueError('NOT_FOUND')
