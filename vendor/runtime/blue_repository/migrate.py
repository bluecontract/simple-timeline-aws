"""Identity-preserving import followed by an explicitly re-identified migration.

Only dynamic typed templates INSIDE Compute expression/program slots are changed.
A template is not an instance of its eventual result type before evaluation.
BEX object construction delays that result's type edge until evaluation finishes.
All dependent references are re-addressed; the published profile is untouched.
"""
from __future__ import annotations
import copy
import json
from collections import defaultdict
from typing import Any
from algorithms import blue as B
from blue_language import Language
from .api import Repository, RepositoryError, canonical


def references(value: Any) -> set[str]:
    if isinstance(value, list):
        return set().union(*(references(x) for x in value)) if value else set()
    if not isinstance(value, dict): return set()
    if set(value) == {'blueId'}: return {value['blueId']}
    return set().union(*(references(x) for x in value.values())) if value else set()


def remap(value: Any, ids: dict[str, str]) -> Any:
    if isinstance(value, list): return [remap(x, ids) for x in value]
    if not isinstance(value, dict): return value
    if set(value) == {'blueId'}: return {'blueId': ids.get(value['blueId'], value['blueId'])}
    return {key: remap(val, ids) for key, val in value.items()}


def migrate_repository(published: Repository) -> tuple[Repository, dict]:
    """Rebuild a compatible profile, producing a reviewable old/new-ID ledger."""
    records = published.records
    bodies = {tid: (copy.deepcopy(row['body']) if 'proof' in row else json.loads(row['text']))
              for tid, row in records.items()}
    compute = published.aliases['Coordination/Compute']
    changes = []

    def has_expression(value):
        if isinstance(value, list): return any(has_expression(x) for x in value)
        if not isinstance(value, dict): return False
        if any(key.startswith('$') and key not in {'$previous', '$previousItems', '$empty', '$pos', '$replace'} for key in value):
            return True
        return any(has_expression(v) for k,v in value.items() if k not in {'type','schema','blue'})

    def program(value, path, owner):
        if isinstance(value, list): return [program(x,path+'/'+str(i),owner) for i,x in enumerate(value)]
        if not isinstance(value,dict): return value
        # These are literal/static islands, not executable recursive programs.
        if set(value)=={'$literal'}: return copy.deepcopy(value)
        out={k:(copy.deepcopy(v) if k in {'type','itemType','valueType','keyType','schema','blue'}
                else program(v,path+'/'+k,owner)) for k,v in value.items()}
        if (isinstance(value.get('type'),dict) and set(value['type'])=={'blueId'}
                and value['type']['blueId'] not in B.CORE_NAME
                and any(has_expression(v) for k,v in value.items() if k!='type')):
            changes.append({'owner':owner,'path':path,'action':'typed-template-to-object-construction',
                            'resultType':value['type']['blueId']})
            return {'$objectFromEntries':[{'key':{'type':{'blueId':B.CORE['Text']},'value':k},'val':v}
                                          for k,v in out.items()]}
        return out

    def walk(value,path,owner):
        if isinstance(value,list): return [walk(v,path+'/'+str(i),owner) for i,v in enumerate(value)]
        if not isinstance(value,dict): return value
        is_compute=value.get('type')=={'blueId':compute}
        return {k:program(v,path+'/'+k,owner) if is_compute and k in {'do','expr','functions'}
                else walk(v,path+'/'+k,owner) for k,v in value.items()}

    transformed={tid:walk(body,'',tid) for tid,body in bodies.items()}
    groups=defaultdict(list)
    for tid in bodies: groups[tid.split('#')[0] if '#' in tid else tid].append(tid)
    group_for={tid:group for group,members in groups.items() for tid in members}
    dependencies={group:{group_for[ref] for tid in members for ref in references(transformed[tid])
                         if ref in group_for and group_for[ref]!=group}
                  for group,members in groups.items()}
    context=Language()._context(); mapping={}; rebuilt={}; active=set(); done=set()

    def build(group):
        if group in done:return
        if group in active:raise RepositoryError('unrepresented cross-group dependency cycle: '+group)
        active.add(group)
        for dep in sorted(dependencies[group]):build(dep)
        members=groups[group]
        if '#' in members[0]:
            members=sorted(members,key=lambda tid:int(tid.split('#')[1]))
            local={tid:'this#'+str(i) for i,tid in enumerate(members)}
            raw=[remap(transformed[tid],{**mapping,**local}) for tid in members]
            result=B.finalize_set(raw,context)
            mapping.update(zip(members,result['ids']))
            proof={'members':[B.export_tree(n) for n in result['canonical']]}
            for i,body in enumerate(result['bodies']):
                rebuilt[result['master']+'#'+str(i)]={'proof':proof,'body':B.export_tree(body)}
        else:
            tid=members[0]
            node=B.normalize(B.parse(canonical(remap(transformed[tid],mapping))),context)
            new=B.identity(node); mapping[tid]=new
            rebuilt[new]={'text':B.export_exact(node,context),'mode':'exact','format':'json'}
        active.remove(group);done.add(group)

    for group in sorted(groups):build(group)
    ledger=[{'name':name,'before':tid,'after':mapping[tid]}
            for name,tid in sorted(published.aliases.items()) if tid!=mapping[tid]]
    report={'format':'blue-python-repository-migration/1','source':published.identity,
            'templateRewrites':changes,'changedAliases':ledger,
            'changedRecords':[{'before':tid,'after':new} for tid,new in sorted(mapping.items()) if tid!=new],
            'boundary':'Admission compatibility only; runtime/Java/gas equivalence requires separate execution tests.'}
    compatible=Repository.from_payload('blue-compatible',
        {name:mapping[tid] for name,tid in published.aliases.items()},rebuilt,
        metadata={'profile':'compatible','origin':published.identity,'migration':report})
    return compatible,report
