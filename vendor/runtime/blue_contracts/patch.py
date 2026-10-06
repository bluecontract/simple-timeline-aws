"""Contracts mutation, deliberately not BEX's sparse observation overlay."""
from blue_bex.values import clone, segments, index, pointer_get, UNDEFINED, BexError

class ContractError(BexError):code='CONTRACT_FATAL'
class CapabilityError(ContractError):code='UNSUPPORTED_CAPABILITY'

RESERVED={'initialized','terminated','checkpoint','process','managed','runtime'}

def join_scope(scope,path):
    if type(path) is not str or not path.startswith('/'):raise ContractError('scope-relative absolute pointer required')
    segments(path)
    return scope if path=='/' else scope.rstrip('/')+path


def boundary(scope,path,managed_paths=(),*,internal=False):
    parts=segments(path);root=segments(scope)
    if not parts or parts==root:raise ContractError('handler cannot replace selected root or own scope root')
    if parts[:len(root)]!=root:raise ContractError('patch escapes executing scope')
    for p in managed_paths:
        cut=segments(p)
        if len(parts)>len(cut) and parts[:len(cut)]==cut:raise ContractError('patch crosses a managed document boundary')
    if not internal:
        for i in range(len(parts)-1):
            if parts[i]=='contracts' and parts[i+1] in RESERVED:raise ContractError('processor-owned marker is not writable')


def apply(document,patch):
    if type(patch) is not dict or set(patch)-{'op','path','val'} or not {'op','path'}<=patch.keys():raise ContractError('malformed patch')
    op=patch['op'];parts=segments(patch['path'])
    if op not in {'add','replace','remove'}:raise ContractError('unsupported patch operation')
    if not parts:raise ContractError('root patch is forbidden')
    if op=='remove' and 'val'in patch:raise ContractError('remove val must be absent')
    if op!='remove' and 'val'not in patch:raise ContractError('patch val missing')
    out=clone(document);at=out
    for p in parts[:-1]:
        if type(at) is dict:
            if p not in at:
                if op=='remove':raise ContractError('remove path missing')
                at[p]={}
            at=at[p]
        elif type(at) is list:at=at[index(p,len(at))]
        else:raise ContractError('scalar intermediate patch parent')
    p=parts[-1]
    if type(at) is dict:
        if op=='remove':
            if p not in at:raise ContractError('remove member missing')
            del at[p]
        else:at[p]=clone(patch['val'])  # Both add and replace are object UPSERT.
    elif type(at) is list:
        i=index(p,len(at),add=op=='add')
        if op=='add':at.insert(i,clone(patch['val']))
        elif op=='replace':at[i]=clone(patch['val'])
        else:at.pop(i)
    else:raise ContractError('patch parent is scalar')
    return out
