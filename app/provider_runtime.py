"""Hosted authorization over semantic Blue values, independent of wire spelling."""
import json
from reference import ModelProvider,check,ref

class Provider(ModelProvider):
    def is_public(self,timeline):
        result=self.e.language.query(json.dumps(ref(self.e.identity(timeline))),'/publicRead')
        value=result.get('value',{})
        check(result['outcome']=='Established' and value.get('kind')=='Boolean'
              and type(value.get('value')) is bool,'INVALID_PUBLIC_READ')
        return value['value']

    def can_read(self,timeline,key=None,owner=None):
        tid=self.e.identity(timeline)
        if self.is_public(timeline) or owner==self.state['timelines'][tid]['owner']:
            return True
        return any(tid in saved['timelines'] and key in saved['keys']
                   for saved in self.state['access'].values())
