"""Parameterized publication recipes; no invented or reused immutable IDs.

The caller supplies the actual Language definition-admission operation and the
exact BlueId of this revision's complete specification Text. Returned IDs must
come from that operation, not a structural-hash-only fallback.
"""
from typing import Callable, Mapping

PARENTS = {
    'Contract': None,
    'Marker': 'Contract',
    'Channel': 'Contract',
    'Handler': 'Contract',
    'Operation': 'Handler',
    'External Channel': 'Channel',
    'Composite External Channels': 'Channel',
    'All External Channels': 'Channel',
    'Triggered Event Channel': 'Channel',
    'Embedded Node Channel': 'Channel',
    'Document Update Channel': 'Channel',
    'Lifecycle Event Channel': 'Channel',
    'Sequential Workflow': 'Handler',
    'Sequential Workflow Operation': 'Operation',
    'Compute': 'Contract',
    'Compute Definition': 'Marker',
    'Update Document': 'Contract',
    'Trigger Event': 'Contract',
    'Terminate Processing': 'Contract',
    'Process Embedded': 'Marker',
    'Processing Initialized Marker': 'Marker',
    'Processing Terminated Marker': 'Marker',
    'Channel Event Checkpoint': 'Marker',
    'Operation Request': None,
    'Document Processing Initiated': None,
    'Document Processing Terminated': None,
    'Document Update': None,
    'Embedded Event Delivery': None,
    'Json Patch Entry': None,
    'Contract Execution Result': None,
    'Type Generalization Rule': None,
    'Type Generalization Policy': 'Marker',
}


def publish_catalogue(admit_definition: Callable[[dict], str], specification_id: str,
                      core_ids: Mapping[str,str]) -> dict[str,str]:
    if not specification_id:
        raise ValueError('SPECIFICATION_ID_REQUIRED')
    for name in ('Text','Integer','Boolean','List','Dictionary'):
        if not core_ids.get(name):raise ValueError('MISSING_CORE_TYPE:'+name)
    result: dict[str,str] = {}
    def field(name):return {'type':{'blueId':core_ids[name]}}
    # An unrestricted runtime operand has no Language declaration constraint.
    # A description-only child would become an inherited contribution and
    # change exact source/event/program identities. The closed field rules in
    # the specification and runtime validators own these slot requirements.
    def any_value(description):return None
    def seq(item=None):
        value=field('List')
        if item is not None:value['itemType']={'blueId':result[item]}
        return value
    for name,parent in PARENTS.items():
        body={'name':name,'specification':{'blueId':specification_id}}
        if parent is not None:body['type']={'blueId':result[parent]}
        if name=='Contract':body['order']=field('Integer')
        elif name in ('Handler','Operation'):body['channel']=field('Text')
        elif name=='External Channel':body['event']=any_value('Optional actual-original-event filter.')
        elif name=='Composite External Channels':body['channels']=seq()
        elif name in ('Triggered Event Channel','Lifecycle Event Channel'):body['event']=any_value('Optional Language event definition.')
        elif name=='Embedded Node Channel':body.update(sourcePath=field('Text'),event=any_value('Optional event definition.'))
        elif name=='Document Update Channel':body.update(path=field('Text'),event=any_value('Optional event definition.'))
        elif name=='Sequential Workflow':body.update(steps=seq(),event=any_value('Optional event definition.'))
        elif name=='Sequential Workflow Operation':body.update(steps=seq(),request=any_value('Optional request definition, including unvalued typed definitions.'))
        elif name=='Compute':
            for key in ('expr','do','constants','functions','entry','definition'):body[key]=any_value('BEX program slot; executable validation occurs at demand.')
        elif name=='Compute Definition':
            for key in ('constants','functions'):body[key]=any_value('Reusable BEX declaration.')
        elif name=='Update Document':body['changeset']=any_value('Required effect-free BEX changeset expression.')
        elif name=='Trigger Event':body['event']=any_value('Required BEX event expression; empty objects are present values.')
        elif name in ('Terminate Processing','Processing Terminated Marker','Document Processing Terminated'):body.update(cause=field('Text'),reason=field('Text'))
        elif name=='Process Embedded':body.update(paths=seq(),collectionPaths=seq())
        elif name in ('Processing Initialized Marker','Document Processing Initiated'):body['document']=any_value('Exact pre-initialization document.')
        elif name=='Channel Event Checkpoint':
            entries=field('Dictionary');entries['valueType']={'timestamp':field('Integer'),'event':any_value('Pure reference to the original external event.')};body['entries']=entries
        elif name=='Operation Request':body.update(operation=field('Text'),channel=field('Text'),document=any_value('Optional exact document precondition.'),requireExactDocumentVersion=field('Boolean'),request=any_value('Optional exact request value.'))
        elif name=='Document Update':body.update(op=field('Text'),path=field('Text'),beforePresent=field('Boolean'),afterPresent=field('Boolean'),before=any_value('Exact before value when present.'),after=any_value('Exact after value when present.'))
        elif name=='Embedded Event Delivery':body.update(sourcePath=field('Text'),event=any_value('Exact immutable nested event.'))
        elif name=='Json Patch Entry':body.update(op=field('Text'),path=field('Text'),val=any_value('Required for add/replace, forbidden for remove.'))
        elif name=='Contract Execution Result':body.update(patches=seq('Json Patch Entry'),events=seq(),termination=any_value('Optional graceful termination.'),runtimeLedger=any_value('Optional bounded child ledger, only without live debit.'))
        elif name=='Type Generalization Rule':body.update(path=field('Text'),mode=field('Text'),mustRemainSubtypeOf=any_value('Optional exact ancestor-floor type.'))
        elif name=='Type Generalization Policy':body.update(defaultMode=field('Text'),rules=seq('Type Generalization Rule'))
        if name=='Channel Event Checkpoint':
            body['entries']['valueType']={k:v for k,v in body['entries']['valueType'].items() if v is not None}
        body={k:v for k,v in body.items() if v is not None}
        value=admit_definition(body)
        if not isinstance(value,str) or not value:raise ValueError('ADMISSION_DID_NOT_RETURN_BLUEID')
        result[name]=value
    return result
