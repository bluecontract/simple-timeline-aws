"""Exact-reference storage projection for already admitted processing snapshots.

No semantic admission or runtime role is inferred here. Complete owning-set
proofs remain intact for cyclic members. Unknown deferred bodies stay opaque.
"""
from algorithms import blue as L
from blue_contracts.reference.model import pointer,require

def collapse_snapshot(processor,snapshot,*,data_paths=()):
    blue=processor.blue;result=snapshot.copy();fragments={};cuts=0;cyclic=0
    for key,doc in sorted(result.documents.items()):
        if '#' in doc.blue_id:cyclic+=1;continue
        body=blue.open(doc.body);paths=set(data_paths)
        for edge in result.edges.values():
            if edge.source==key:paths.add(edge.path)
        contracts=body.get('contracts')
        if isinstance(contracts,L.Node):
            for name,declaration in contracts.fields:
                if name not in ('initialized','checkpoint','terminated') and isinstance(declaration,L.Node):
                    paths.add(pointer(('contracts',name)))
        # Only cut physically present children. A missing deferred reference is
        # never opened merely to optimize its representation.
        selected=[]
        for path in sorted(paths):
            node=body
            for part in L.path_parts(path):
                if not isinstance(node,L.Node):break
                if node.has('items') and part.isdigit():
                    values=node.get('items');node=values[int(part)] if int(part)<len(values) else L.ABSENT
                else:node=node.get(part)
            if isinstance(node,L.Node):selected.append(path)
        if not selected:continue
        projected,records=L.split_fragments(body,selected,blue.context)
        require(L.identity(projected)==doc.blue_id,'COMPACT_IDENTITY_MISMATCH')
        fragments.update(records);doc.body=projected;cuts+=len(selected)
    for node in fragments.values():blue.remember(node)
    blue.refresh()
    require(result.identity==snapshot.identity,'COMPACT_SNAPSHOT_MISMATCH')
    processor.validate(result)
    return result,dict(fragments=len(fragments),cuts=cuts,cyclicDocumentsKept=cyclic)
