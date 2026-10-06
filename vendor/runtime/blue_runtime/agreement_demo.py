"""Current-runtime Agreement/Order workflow with actual repository business types.

The repository's older executable Agreement and Order are not silently rebound.
This explicitly authored demo uses its Product, Order Line and Payment/Amount
contracts for business data and the selected event release for execution.
"""
def channel(name):return {'type':'Coordination/Timeline Channel','timeline':{'timelineId':'agreement'},'actor':{'actorId':name}}
def operation(channel,actions,request=None):
    return {'type':'Contracts/Sequential Workflow Operation','channel':channel,'request':request or {},
            'steps':[{'type':'Contracts/Compute','do':actions}]}
def order(index,products=20):
    key='order'+str(index);input_name='input_'+key
    return {'name':key,'status':'open','lines':[
        {'type':'Commerce/Order Line','lineId':key+'-line'+str(i),
         'product':{'type':'Commerce/Product','sku':'SKU-'+str(i),'title':'Product '+str(i)},
         'quantity':i+1,'unitPrice':{'type':'Payment/Amount','minorUnits':100+i,'currency':'EUR'}} for i in range(products)],
        'contracts':{input_name:channel(key),'fulfill':operation(input_name,[
            {'$appendChange':{'op':'replace','path':'/status','val':'fulfilled'}},
            {'$appendEvent':{'kind':'OrderFulfilled','order':key}}])}}
def agreement(orders=20,products=20):
    return {'name':'Repository agreement demo','description':'Current Contracts workflows with verified Commerce data types.',
        'orders':{'order'+str(i):order(i,products) for i in range(orders)},
        'contracts':{'input':channel('buyer'),'embedded':{'type':'Contracts/Process Embedded','collectionPaths':['/orders']},
            'orderEvents':{'type':'Contracts/Embedded Node Channel','event':{'kind':'OrderFulfilled'}},
            'reportFulfillment':{'type':'Contracts/Sequential Workflow','channel':'orderEvents',
                'steps':[{'type':'Contracts/Trigger Event','event':{'$event':'/event'}}]},
            'addOrder':operation('input',[
                {'$appendChange':{'op':'add','path':'/orders/added','val':{'$binding':'call/request/order'}}},
                {'$appendEvent':{'kind':'OrderAdded','slot':'added'}}],{'order':{}})}}
