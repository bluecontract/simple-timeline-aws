"""Deterministic documents shared by collapse tests, guides and benchmarks."""
def tree(fanout=0,grandchildren=0,operations=1,products=0,distinct=False):
    def make(name,depth):
        channel='input_'+name
        doc={'name':name,'counter':0,'contracts':{
            channel:{'type':'Coordination/Timeline Channel','timeline':{'timelineId':'benchmark'},'actor':{'actorId':name}}}}
        for index in range(operations):
            doc['contracts']['op'+str(index)]={'type':'Contracts/Sequential Workflow Operation','channel':channel,
                'steps':[{'type':'Contracts/Compute','do':[{'$appendChange':{'op':'replace','path':'/counter','val':{'$add':[{'$document':'/counter'},index+1 if distinct else 1]}}}]}]}
        width=fanout if depth==0 else grandchildren if depth==1 else 0
        if width:
            doc['children']={str(i):make(name+'_'+str(i),depth+1) for i in range(width)}
            doc['contracts']['embedded']={'type':'Contracts/Process Embedded','collectionPaths':['/children']}
        if products:doc['products']={str(i):{'sku':name+'-'+str(i),'title':'Product '+str(i),'quantity':i+1} for i in range(products)}
        return doc
    return make('root',0)
