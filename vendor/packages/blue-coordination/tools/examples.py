"""Generate the reproducible, fully signed HTTP example (public test keys only)."""
import json
from reference import Exact, ModelProvider, ref, api_urls
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from blue_language.physical import PhysicalCache
import package as publisher

READER_SEED = b'\x22' * 32  # PUBLIC fixture, never a deployment credential.

def wire(e, value):
    if isinstance(value, list):
        return [wire(e, item) for item in value]
    if isinstance(value, dict):
        return {k: ref(e.language.aliases[v]) if k in ('type', 'itemType', 'keyType', 'valueType') and isinstance(v, str) and v in e.language.aliases else wire(e, v) for k, v in value.items()}
    return value


def import_inline(e, value):
    """Register transmitted bodies in dependency order, independent of JSON key order."""
    from algorithms.blue import Failure
    pending = []
    def collect(node):
        if isinstance(node, list):
            for child in node:
                collect(child)
        elif isinstance(node, dict) and set(node) != {'blueId'}:
            for key, child in node.items():
                if key not in ('type', 'itemType', 'keyType', 'valueType'):
                    collect(child)
            pending.append(node)
    collect(value)
    while pending:
        retry, last_error = [], None
        for node in pending:
            try:
                e.put(node)
            except Failure as exc:
                if exc.category != 'ProviderUnavailable':
                    raise
                retry.append(node)
                last_error = exc
        if len(retry) == len(pending):
            raise last_error
        pending = retry


def inline_checkpoint(e, value):
    result = e.get(value)
    result['guarantee'] = e.get(result['guarantee'])
    return result


def inline_entry(e, value):
    result = e.get(value)
    result['actor'] = e.get(result['actor'])
    result['message'] = e.get(result['message'])
    return result


def inline_response(e, envelope):
    result = e.get(envelope)
    body = e.get(result['object'])
    body['checkpoint'] = inline_checkpoint(e, body['checkpoint'])
    if 'page' in body:
        page = e.get(body['page'])
        page['entries'] = [inline_entry(e, x) for x in page['entries']]
        if 'predecessor' in page:
            page['predecessor'] = inline_entry(e, page['predecessor'])
        if 'nextCursor' in page:
            page['nextCursor'] = e.get(page['nextCursor'])
        body['page'] = page
    result['object'] = body
    assert e.identity(result) == e.identity(envelope)
    return wire(e, result)


def generate():
    e = Exact()
    definitions = []
    text_field = {'type':'Text','schema':{'required':True,'minLength':1}}
    for alias, body in [
        ('Example/ACME Timeline Provider', {'name':'ACME Timeline Provider','type':'Coordination/Timeline Provider',
            'companyName':'ACME Timeline Services Sp. z o.o.','registeredOffice':'Example Street 10, Warsaw, Poland',
            'website':'https://acme.example',
            'endpoint':'https://timeline.acme.example'}),
        ('Example/Polish Citizen', {'name':'Polish Citizen','type':'Coordination/Principal Actor',
            'givenName':text_field,'familyName':text_field,'citizenNumber':text_field}),
        ('Example/ACME Access Service', {'name':'ACME Access Service','type':'Coordination/Agent Actor','serviceName':text_field})]:
        definitions.append({'alias':alias,'blueId':e.define(alias,body),'body':body})
    citizen={'type':'Example/Polish Citizen','givenName':'Anna','familyName':'Example','citizenNumber':'DEMO-42'}
    service={'type':'Example/ACME Access Service','serviceName':'ACME timeline access'}
    endpoint='https://timeline.acme.example'
    p=ModelProvider(e,endpoint=None,provider_type='Example/ACME Timeline Provider')
    p.set_actor('alice',citizen);p.set_actor('__provider__',service)
    key=Ed25519PrivateKey.from_private_bytes(READER_SEED).public_key().public_bytes(Encoding.Raw,PublicFormat.Raw).hex()
    other=Ed25519PrivateKey.from_private_bytes(b'\x33'*32).public_key().public_bytes(Encoding.Raw,PublicFormat.Raw).hex()
    t0=1791288000000000;now=t0+3000000
    timeline=p.create('alice','1234');second_timeline=p.create('alice','5345')
    control=p.create('__provider__','access',public=True)
    access,publication=p.create_access('alice',[timeline],[key],'create-access',control,t0-1000000)
    first=p.append('alice',timeline,'Hello','hello',t0)
    second=p.append('alice',timeline,'Hello 2','hello2',t0+2000000)
    before=p.access_execution(access,t0+2100000).current()
    update=p.update_access('alice',access,[timeline,second_timeline],[key,other],'add-timeline-and-key',t0+2500000)
    execution=p.access_execution(access,now)
    after=execution.current()
    permission_fields={name:after[name]['items'] for name in ('allowedTimelines','allowedKeys')}
    descriptor=p.discovery(control,endpoint)
    cases={}
    def read(name,target,signed=False,**fields):
        q=p.request('Read Timeline Request',timeline=ref(e.identity(target)),**fields)
        if signed:
            envelope=p.sign_reader(q,READER_SEED);p.authenticate_reader(envelope)
            request=dict(envelope,request=q);response=p.read(q,now,key=key)
        else:request=q;response=p.public_read(q,now)
        body=p.verifier.read_response(q,response)
        page,ids=p.verifier.page(q,response) if fields['limit']>0 else (None,[])
        cases[name]={'method':'POST','url':api_urls(e,target)['read'],'request':wire(e,request),
            'response':inline_response(e,response),'entries':ids}
        return page
    read('publicControl',control,limit=100)
    read('publicCheckpoint',control,limit=0)
    read('privateBoth',timeline,signed=True,limit=100)
    read('privateAfterFirst',timeline,signed=True,limit=100,afterEntry=ref(e.identity(first)))
    page=read('firstPage',timeline,signed=True,limit=1)
    read('nextPage',timeline,signed=True,limit=1,cursor=e.get(page['nextCursor']))
    q=p.request('Get Timeline Access Request',access=ref(e.identity(access)))
    att=p.get_access(q,now);body=e.get(att['object'])
    for name in ('publication','lastEntry'):
        proof=e.get(body[name]);body[name]=dict(proof,object=inline_entry(e,proof['object']))
    cases['accessDiscovery']={'method':'POST','url':endpoint+'/access/get','request':wire(e,q),
        'response':wire(e,dict(att,provider=p.provider,object=body))}
    out={'format':'coordination-examples','warning':'Fictional company/person data and PUBLIC test signing keys; not a deployed service.',
        'definitions':definitions,'types':e.aliases,'provider':wire(e,p.provider),
        'timelines':[wire(e,dict(t,provider=p.provider)) for t in (timeline,second_timeline,control)],
        'actors':{'human':wire(e,citizen),'agent':wire(e,service)},
        'entries':[wire(e,inline_entry(e,x)) for x in (first,second)],
        'timelineAccess':wire(e,access),'beforeUpdate':wire(e,before),'afterUpdate':wire(e,after),
        'updateOperation':wire(e,e.get(update['message'])),
        'discovery':{'method':'GET','url':endpoint+'/provider','response':wire(e,descriptor)},'cases':cases,
        'expected':{'firstEntry':e.identity(first),'secondEntry':e.identity(second),'controlTimeline':e.identity(control),
            'access':e.identity(access),'beforeUpdate':e.identity(before),'afterUpdate':e.identity(after),
            'completeBefore':now,'keys':[key,other], 'executionStatus':execution.outcomes[-1].status}}
    (publisher.ROOT/'examples/protocol.json').write_text(json.dumps(out,indent=2)+'\n')
    reverse={v:k for k,v in e.language.aliases.items()}
    reverse.update({v:k for k,v in e.language.aliases.items() if k.startswith('Contracts/')})
    reverse.update({v:k for k,v in e.aliases.items()})
    def friendly(value):
        if isinstance(value,list):return [friendly(x) for x in value]
        if isinstance(value,dict):
            return {k:reverse.get(v.get('blueId'),v) if k in ('type','itemType') and isinstance(v,dict) else friendly(v) for k,v in value.items()}
        return value
    def block(value):return '```json\n'+json.dumps(friendly(value),indent=2)+'\n```\n'
    text=f'''# ACME timelines and an executable Timeline Access document

All company/person data are fictional. The Ed25519 signatures are real but use
public test keys. [protocol.json](../examples/protocol.json) contains complete
requests, signed responses, exact Blue references and the executed before/after
documents. Type aliases below resolve to those exact types; there is no separate
protocolVersion, providerId, accessId, timelineId or grantId.

## Provider and actor types

ACME specializes Timeline Provider with domain details. Its exact type carries
those inherited values, including the common API base. The
instance supplies only its verification key. Clients resolve the inherited fields
through Blue; their omission from the instance JSON does not make them absent.

{block(definitions[0]['body'])}
{block(out['provider'])}

Actors describe the publishing entity separately from the timeline's provider.
Principal Actor is human; Agent Actor is non-human. Domain identity data belong in
subtypes, such as Polish Citizen and ACME Access Service.

{block(out['actors']['human'])}
{block(out['actors']['agent'])}

## Timelines and Hello entries

A timeline uses its canonical URL to distinguish its history. It has a provider,
but no additional arbitrary timeline ID. Its provider supplies the API base,
so POST to `{api_urls(e,timeline)['read']}` reads its history. The same URL serves
ACME's public control history. The exact timeline in the request selects the source.

{block(out['timelines'][0])}
{block(out['entries'][0])}
{block(out['entries'][1])}

The entries are immutable. Hello 2 names Hello as its immediate predecessor.
Only one entry is allowed per microsecond per timeline. Simultaneous publications
must get different increasing timestamps, wait, or fail.

## The initial access document

The allowed timeline list holds Blue references, so it does not repeat provider
details. Each allowed key may read every allowed timeline. The provider is declared
once in contracts.provider. Resolve the API locations from that channel and its
provider to fetch the public history; no extra lookup identifier is needed.

{block(out['timelineAccess'])}

The document's initial BlueId is `{out['expected']['access']}`. Its public channel
means the Signed Timeline with that provider, that URL and publicRead=true, carrying
no additional API location. The signed provider descriptor confirms that this is ACME's reserved control timeline.
ACME publishes the complete initial document there to confirm its initial grants.
Anyone can verify this publication. A self-authored copy alone does not grant access.

contracts.update has type Update Timeline Access, a real Contracts Sequential
Workflow Operation. The type supplies BEX validation and an Update Document step
that replaces both lists atomically. It rejects duplicate values and foreign
providers. This is executable Blue content, not prose interpreted by a custom ACL
state machine. The specification contains the exact operation rules; the exported
type contains its actual program.

## One operation updates timelines and keys

Here ACME adds its second timeline and another reader key with one operation.
Every update targets the original published document. Both lists are replaced
atomically in accepted timeline order; a later accepted replacement determines the
lists. There is no version precondition or revision number.

{block(out['updateOperation'])}

This operation is the message of a public control entry and also its identical
operation field. Feed that complete entry to Contracts at its timestamp. The
pinned processor returns `{out['expected']['executionStatus']}` and the resulting
document has these permission fields:

{block(permission_fields)}

Omitting a key or timeline from a later replacement removes its corresponding
permissions in this document. Independent grants can still provide access. Owner
credentials authorize asking ACME to make the change; reader signatures cannot.

## Fetch that public channel's complete history

Resolve the inline channel's inherited provider URLs. Verify the signed GET
`{api_urls(e,control)['descriptor']}` descriptor against that provider, then send
this bare request to the shared read URL:

`POST {cases['publicControl']['url']}`

{block(cases['publicControl']['request'])}

No reader key, signature, login, nonce, request label or client timestamp is needed.
This is the complete signed response, with the initial publication and update:

<details><summary>Public response: two entries and a completeness checkpoint</summary>

{block(cases['publicControl']['response'])}
</details>

It contains the checkpoint, page and real provider signatures. Verify and execute
the applicable entries to calculate the access document's current state.

For more than 100 entries, send the returned nextCursor as cursor, with the same
timeline and limit. Repeat until hasMore=false. The fixed checkpoint prevents
concurrent appends from changing the page sequence. Public history stays readable
after every private reader key has been revoked.

## Private reads: both Hello entries, then only Hello 2

Private requests use an Ed25519 Signed Reader Request. Sign the exact bytes
UTF8("blue.coordination.reader-request\\n" + BlueId(innerRequest)). The target
already identifies the provider. Both requests use
`POST {cases['privateBoth']['url']}`. These are the complete signed requests:

{block(cases['privateBoth']['request'])}
{block(cases['privateAfterFirst']['request'])}

The first returns Hello and Hello 2; the second returns only Hello 2, with predecessor
evidence for Hello. Their full signed responses and a two-page variant are in the
same fixture, along with the individual response for each request.

<details><summary>Private response: Hello and Hello 2</summary>

{block(cases['privateBoth']['response'])}
</details>

Repeating a signature repeats that exact query; every use rechecks
current access. To demand history closed through a particular time, include
minimumCompleteBefore, rather than a client-created timestamp or expiry.

## One API endpoint

ACME's type supplies `endpoint: https://timeline.acme.example`. Every public and
private timeline uses `POST https://timeline.acme.example/timelines/read`.
The target timeline is part of the request. Public reads omit the reader envelope;
private reads carry an authorized key and Ed25519 signature. Every response is
provider-signed. Canonical timeline URLs identify histories and are not API bases.

## Permanent completeness

In this example completeBefore is `{now}`. At hasMore=false, all entries in the
selected range strictly before that bound have been returned across the pages.
No later acceptance can insert an entry below it, including after an empty result.
At or after the boundary, new entries remain possible. A later poll uses afterEntry
with the last known entry. A limit=0 query obtains only the checkpoint and makes no
claim that the caller already possesses its contents.
'''
    (publisher.ROOT/'docs/examples.md').write_text(text)
    print('Generated ACME access example:',len(cases),'exchanges, native',out['expected']['executionStatus'])


if __name__=='__main__':
    with PhysicalCache(65536).scope():generate()
