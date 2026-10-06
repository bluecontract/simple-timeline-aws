"""Explicit re-addressing to the selected Language core; published IDs stay intact.

This is a compatibility edition, not a claim of Java execution equivalence.
Executable repository types still require separately approved runtime bindings.
"""
import json
from collections import defaultdict
from algorithms import blue as B
from blue_language import Language
from .api import Repository,RepositoryError,canonical
from .migrate import references,remap,migrate_repository

CORE_MIGRATION={'8DSFoWG9MqRSUhStqoPLrwVQiYByRh18NWbDEarN8MKF':B.CORE['List'],
                'Efkz9D1ARMM7rU43w3rDNVqat1naS6qXKCqP4eHin3yG':B.CORE['Dictionary']}

def current_profile(published):
    template_profile,templates=migrate_repository(published)
    original=template_profile.records
    bodies={tid:row['body'] if 'proof' in row else json.loads(row['text']) for tid,row in original.items()}
    groups=defaultdict(list)
    for tid in bodies:
        if tid not in CORE_MIGRATION:groups[tid.split('#')[0]].append(tid)
    owner={tid:g for g,members in groups.items() for tid in members}
    deps={g:{owner[ref] for tid in members for ref in references(bodies[tid]) if ref in owner and owner[ref]!=g} for g,members in groups.items()}
    c=Language()._context();mapping=dict(CORE_MIGRATION);records={};done=set();active=set()
    def build(g):
        if g in done:return
        if g in active:raise RepositoryError('unrepresented dependency cycle: '+g)
        active.add(g)
        for dep in sorted(deps[g]):build(dep)
        members=groups[g];c.work=0
        if '#' in members[0]:
            members=sorted(members,key=lambda s:int(s.split('#')[1]));local={tid:'this#'+str(i) for i,tid in enumerate(members)}
            z=B.finalize_set([remap(bodies[tid],{**mapping,**local}) for tid in members],c);mapping.update(zip(members,z['ids']))
            proof={'members':[B.export_tree(n) for n in z['canonical']]}
            for i,body in enumerate(z['bodies']):records[z['master']+'#'+str(i)]={'proof':proof,'body':B.export_tree(body)}
        else:
            tid=members[0];node=B.normalize(B.parse(canonical(remap(bodies[tid],mapping))),c);new=B.identity(node);mapping[tid]=new
            records[new]={'mode':'exact','format':'json','text':B.export_exact(node,c)}
        active.remove(g);done.add(g)
    for g in sorted(groups):build(g)
    aliases={name:mapping[tid] for name,tid in template_profile.aliases.items()}
    ledger=[{'name':name,'before':tid,'after':aliases[name]} for name,tid in published.aliases.items() if tid!=aliases[name]]
    report={'source':published.identity,'coreMigration':CORE_MIGRATION,'templates':templates,'changedAliases':ledger,
            'scope':'Explicit current-Language compatibility migration. Does not install or translate legacy executable runtime roles.'}
    repo=Repository.from_payload('blue-repository-compatible-20260921',aliases,records,metadata={'profile':'compatible','migration':report})
    return repo,report
