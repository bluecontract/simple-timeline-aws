"""Explicit trusted runtime bindings for the supplied Contracts guide."""
from blue_contracts import RuntimeBinding

def install_extensions(p):
    class TickChannel:
        def accept(self,context):
            context.gas.charge('accept')
            return context.event.get('kind')=='tick'
    class DoubleStep:
        def execute(self,context):
            context.gas.charge('execute')
            value=context.read('/count')*2
            return {'patches':[{'op':'replace','path':'/count','val':value}],
                    'events':[{'kind':'doubled','count':value}]}
    for alias,parent,role,tariff,impl in [
        ('Tick Channel','Channel','external-channel',(('accept',1),),TickChannel()),
        ('Double Step','Contract','step',(('execute',2),),DoubleStep())]:
        tid=p.blue.identity(p.blue.source({'name':alias,'type':{'blueId':p.registry.types[parent]}},goal='definition'))
        sid=p.blue.identity(p.blue.source('Tutorial '+alias+' runtime v1: see tools/scenarios.py.'))
        p.install_runtime(RuntimeBinding(tid,sid,role,(),(),'tutorial-'+role,tariff),impl)
        p.blue.language.aliases['Tutorial/'+alias]=tid
    p.blue.refresh()

