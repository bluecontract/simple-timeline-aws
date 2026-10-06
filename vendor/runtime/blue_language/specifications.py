"""Read governing metadata along a selected type chain; not a support assertion.
Does not activate protocols, execute code, or scan unrelated provider records.
"""
from algorithms import blue as B

def declared_requirements(node, context):
    result=[]; seen=set(); current=node
    while current is not None:
        identity=B.identity(current)
        B.require(identity not in seen, 'TypeCycle', identity)
        seen.add(identity)
        body=B.open_exact(current,context)
        link=body.get(B.SPECIFICATION)
        if link is not B.ABSENT:
            B.require(isinstance(link,B.Ref), 'InvalidNodeShape', 'specification position')
            result.append({'definedOn':identity,'specification':link.id})
        parent=body.get('type')
        current=parent if isinstance(parent,B.Ref) and parent.id not in B.CORE_NAME else None
    return tuple(result)
