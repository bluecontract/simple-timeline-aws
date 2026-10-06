"""Demanded, deterministic shared Compute definitions in the current frame."""
from algorithms import blue as L
from .model import require, segments


def resolve_definition(attempt,key,step):
    if 'definition' not in step:return None
    blue=attempt.blue;logical=attempt.graph.logical
    operand=step['definition'];head=blue.head(operand)
    if head.value is not L.ABSENT:
        name=head.value
        require(type(name) is str and bool(name),'INVALID_COMPUTE_DEFINITION')
        path=name if name.startswith('/') else '/contracts/'+name.replace('~','~0').replace('/','~1')
        selected=L.recipe(attempt.state.documents[key].body)
        for part in segments(path):
            for node in selected.parts:logical.open(node)
            logical.meter.contracts('objectMemberRead')
            selected=blue.child(selected,part)
            require(selected is not None,'MISSING_COMPUTE_DEFINITION',path=path)
        operand=selected
    # Traverse only this selected executable definition. The existing finite
    # manifest counters charge reads before extraction; no user code runs here.
    seen=set()
    def visit(recipe):
        if recipe.key() in seen:
            require(False,'CYCLIC_COMPUTE_DEFINITION')
        seen.add(recipe.key())
        for node in recipe.parts:logical.open(node)
        h=blue.head(recipe)
        if h.value is not L.ABSENT:
            if type(h.value) is str:logical.meter.charge('textWork',(len(h.value)+63)//64)
        elif h.items is not None:
            logical.meter.contracts('listItemRead',len(h.items))
            for i in range(len(h.items)):visit(L.child_recipe(h,i))
        else:
            logical.meter.contracts('objectMemberRead',len(h.fields))
            for field in sorted(h.fields):
                # Static exact type references are retained by bex_data.
                if field not in L.TYPES:visit(L.child_recipe(h,field))
        seen.remove(recipe.key())
    head=blue.head(operand)
    require(head.value is L.ABSENT and head.items is None,'INVALID_COMPUTE_DEFINITION')
    require(set(head.fields)<={'constants','functions','specification','order'},'INVALID_COMPUTE_DEFINITION')
    out={}
    for field in ('constants','functions'):
        child=blue.child(operand,field)
        if child is not None:
            visit(child);out[field]=blue.bex_data(child)
            require(type(out[field]) is dict,'INVALID_COMPUTE_DEFINITION',field=field)
    return out
