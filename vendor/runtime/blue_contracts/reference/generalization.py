"""Policy-controlled type changes, validated by the actual Language context."""
from algorithms import blue as L
from .model import ContractError,require,segments,pointer
from .policy import GeneralizationError,choose_type

SEMANTIC_FAILURES={'TypeCompatibilityViolation','SchemaViolation','FixedValueConflict'}


def direct_at(blue,node,parts):
    for key in parts:
        body=blue.open(node)
        if body.has('items'):
            if not key.isdigit() or int(key)>=len(body.get('items')):return None
            node=body.get('items')[int(key)]
        else:
            node=body.get(key)
            if node is L.ABSENT or not isinstance(node,(L.Node,L.Ref)):return None
    return node


def replace_direct(blue,node,parts,value):
    if not parts:return value
    body=blue.open(node);fields=dict(body.fields);key=parts[0]
    if body.has('items'):
        items=list(body.get('items'));i=int(key)
        items[i]=replace_direct(blue,items[i],parts[1:],value);fields['items']=tuple(items)
    else:fields[key]=replace_direct(blue,fields[key],parts[1:],value)
    return L.node(fields)


def repair(blue,before,changed,path,policy,meter,validate=None,establish=None):
    """Return a valid changed root and ordered exact generated type writes.

    Visit the changed subtree bottom-up, then its containing spine. Candidate
    validation keeps contextual requirements and each containing schema. This
    permits two invalid children in one replacement to be repaired separately,
    without treating either child's failure as permission to weaken the other.
    """
    validate=validate or blue.certify
    try:validate(changed);return changed,[]
    except ContractError as failure:
        if failure.code not in {'LANGUAGE_'+name for name in SEMANTIC_FAILURES}:raise
        original=failure
    parts=segments(path)
    paths=[];writes=[]
    def affected(node,prior,at,depth=0):
        if node is None:return
        if prior is not None and blue.identity(node)==blue.identity(prior):return
        if isinstance(node,L.Node):
            old=blue.open(prior) if isinstance(prior,(L.Node,L.Ref)) else None
            for key,value in node.fields:
                if key=='items':
                    previous=old.get('items') if old else L.ABSENT
                    for i,child in enumerate(value):affected(child,previous[i] if isinstance(previous,tuple) and i<len(previous) else None,at+(str(i),),depth+1)
                elif key not in L.LITERALS|L.TYPES|{'schema','mergePolicy','contracts'}:
                    previous=old.get(key) if old else L.ABSENT
                    affected(value,None if previous is L.ABSENT else previous,at+(key,),depth+1)
        paths.append(at)
    affected(direct_at(blue,changed,parts),direct_at(blue,before,parts),parts)
    paths.extend(parts[:size] for size in range(len(parts)-1,-1,-1))
    for at in paths:
        node=direct_at(blue,changed,at)
        if node is None:continue
        body=blue.open(node);typ=body.get('type')
        if not isinstance(typ,L.Ref):continue
        selected=policy.select(pointer(at))
        if selected.mode=='reject':continue
        candidates={}
        def valid(_,tid):
            candidate=replace_direct(blue,changed,at,L.changed(body,type=L.Ref(tid)))
            try:
                if establish:establish(candidate)
                selected=blue.select(candidate,pointer(at))
                L.validate(selected,blue.context,'value')
                for size in range(len(at)-1,-1,-1):
                    enclosing=blue.select(candidate,pointer(at[:size]));head=blue.head(enclosing)
                    L.validate_schema(head,True,'value',size==0,blue.context)
            except L.Failure as exc:
                if exc.category in SEMANTIC_FAILURES:return False
                blue.translate(exc)
            except ContractError as exc:
                if exc.code in {'LANGUAGE_'+name for name in SEMANTIC_FAILURES}:return False
                raise
            candidates[tid]=candidate;return True
        def ancestor(tid):
            parent=blue.open(L.Ref(tid)).get('type')
            if isinstance(parent,L.Ref):meter.contracts('typeEdgeFollowed');return parent.id
            return None
        try:
            tid=choose_type(typ.id,body,pointer(at),policy,immediate_ancestor=ancestor,
                            valid_with_type=valid,is_subtype=lambda a,b:L.check_subtype(a,b,blue.context),
                            charge_candidate=lambda _:meter.contracts('subtypeCandidateTested'))
        except GeneralizationError as exc:raise ContractError(str(exc),path=pointer(at)) from exc
        if tid!=typ.id:
            changed=candidates[tid];writes.append({'path':pointer(at+('type',)),'before':typ,'after':L.Ref(tid)})
    if not writes:raise original
    validate(changed)
    return changed,writes
