"""Verified provider-bundle import; storage availability is not execution authority."""
from collections import defaultdict
from copy import deepcopy
from algorithms import blue as B
from blue_language import Language
from .api import Repository,RepositoryError,canonical,digest
from .import_java import canonical_enums
from .migrate import references

def import_provider_bundle(bundle,dependencies=(),*,name='blue-repository-published-20260921'):
    bundle=deepcopy(bundle)
    if bundle.get('formatVersion')!=1:raise RepositoryError('unsupported provider bundle version')
    claimed=bundle.pop('providerBundleIdentity',None)
    # The carrier's publisher digest uses an external format not defined by
    # Language. Preserve the claim; do not pretend our JSON digest verifies it.
    # Every contained exact ID and complete dependency is verified below, and
    # Repository assigns its own documented integrity commitment.
    if not isinstance(claimed,str):raise RepositoryError('missing publisher bundle identity')
    rows=list(bundle['entries'])+list(dependencies);aliases={};records={};groups=defaultdict(dict);changes=[];c=Language()._context()
    for row in rows:
        tid=row['blueId'];raw=row['content'];B.final_id(tid)
        alias=row.get('qualifiedName')
        if alias:
            if alias in aliases and aliases[alias]!=tid:raise RepositoryError('alias collision: '+alias)
            aliases[alias]=tid
        if '#' in tid:
            master,index=tid.split('#');groups[master][int(index)]=raw;continue
        c.work=0;node=B.normalize(B.parse(canonical(raw)),c)
        if B.identity(node)!=tid:
            raw=canonical_enums(raw,c);node=B.normalize(B.parse(canonical(raw)),c)
            if B.identity(node)!=tid:raise RepositoryError('published identity mismatch: '+tid)
            changes.append(tid)
        response={'mode':'exact','format':'json','text':B.export_exact(node,c)}
        if tid in records and records[tid]!=response:raise RepositoryError('conflicting exact body: '+tid)
        records[tid]=response
    sets=[]
    for master,members in sorted(groups.items()):
        if sorted(members)!=list(range(len(members))):raise RepositoryError('incomplete cyclic owning set: '+master)
        def symbolic(value):
            if type(value) is list:return [symbolic(x) for x in value]
            if type(value) is not dict:return value
            if set(value)=={'blueId'} and value['blueId'].startswith(master+'#'):return {'blueId':'this#'+value['blueId'].split('#')[1]}
            return {k:symbolic(v) for k,v in value.items()}
        c.work=0;result=B.finalize_set([symbolic(members[i]) for i in range(len(members))],c)
        if result['master']!=master:raise RepositoryError('cyclic identity mismatch: '+master)
        proof={'members':[B.export_tree(n) for n in result['canonical']]}
        for i,body in enumerate(result['bodies']):records[master+'#'+str(i)]={'proof':proof,'body':B.export_tree(body)}
        sets.append({'master':master,'members':len(members)})
    allrefs=set().union(*(references(row.get('body',{})) if 'proof' in row else references(__import__('json').loads(row['text'])) for row in records.values()))
    missing=sorted(allrefs-set(records)-set(B.CORE_NAME))
    while missing and all(tid in c.bodies for tid in missing):
        for tid in missing:
            body=c.bodies[tid]
            if B.identity(body)!=tid:raise RepositoryError('invalid normalized inline type: '+tid)
            records[tid]={'mode':'exact','format':'json','text':B.export_exact(body,c)}
            allrefs.update(references(B.export_tree(body)))
        missing=sorted(allrefs-set(records)-set(B.CORE_NAME))
    if missing:raise RepositoryError('missing exact dependencies: '+', '.join(missing))
    report={'providerBundleIdentity':claimed,'publisherDigestVerification':'claim retained; external encoding unspecified','repositoryBlueId':bundle['repositoryBlueId'],'registryPackageIdentities':bundle['registryPackageIdentities'],'aliases':len(aliases),'records':len(records),'cyclicSets':sets,'canonicalEnumCarriers':changes,'scope':'Exact structural verification. Admission and executable runtime bindings are separate.'}
    return Repository.from_payload(name,aliases,records,metadata={'profile':'published','import':report}),report
