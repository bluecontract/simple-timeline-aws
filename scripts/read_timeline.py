"""Fetch and verify a public or Ed25519-authorized private timeline, following pages."""
import argparse,json,sys,urllib.parse,urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.catalogue import PhysicalCache,ref,wire,import_inline
from app.reader import ReaderExact as Exact
from reference import Verifier,check
from access_runtime import control_timeline
from algorithms.blue import Failure
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

def call(base,path,body=None):
    req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=45) as response:return json.load(response)

def main():
    p=argparse.ArgumentParser();p.add_argument('endpoint');p.add_argument('--provider',required=True,help='Expected provider BlueId from a trusted source')
    target=p.add_mutually_exclusive_group(required=True);target.add_argument('--timeline-file',type=Path,help='Exact timeline JSON copied from the console');target.add_argument('--public-access',action='store_true',help='Read the legacy provider control timeline');target.add_argument('--access-file',type=Path,help='Initial Timeline Access JSON whose public history should be verified')
    p.add_argument('--key-file',type=Path,help='32-byte Ed25519 seed in lowercase hex');p.add_argument('--after-timestamp',type=int);p.add_argument('--after-entry-file',type=Path)
    p.add_argument('--limit',type=int,default=50);p.add_argument('--show-exchanges',action='store_true');a=p.parse_args()
    check(a.endpoint.startswith('https://'),'HTTPS_REQUIRED')
    with PhysicalCache(65536).scope():
        e=Exact();types=call(a.endpoint,'/types');definition=types['providerType']
        check(e.define('Remote/Provider',definition['definition'])==definition['blueId'],'PROVIDER_TYPE_MISMATCH')
        access=json.loads(a.access_file.read_text()) if a.access_file else None
        path='/provider'
        if access is not None:
            import_inline(e,access);e.require_kind(access,'Timeline Access')
            path+='?'+urllib.parse.urlencode({'access':e.identity(access)})
        discovery=call(a.endpoint,path);import_inline(e,discovery);provider=discovery['provider'];check(e.identity(provider)==a.provider,'WRONG_PROVIDER')
        verify=Verifier(e,provider);descriptor=verify.attestation(discovery)
        if access is not None:
            timeline=control_timeline(e,access)
            check(e.identity(descriptor['controlTimeline'])==e.identity(timeline),'INVALID_CONTROL_TIMELINE')
            verify.timeline(timeline)
        else:timeline=descriptor['controlTimeline'] if a.public_access else json.loads(a.timeline_file.read_text())
        import_inline(e,timeline)
        fields={'timeline':ref(e.identity(timeline)),'limit':a.limit}
        if a.after_timestamp is not None:fields['afterTimestamp']=a.after_timestamp
        if a.after_entry_file:
            prior=json.loads(a.after_entry_file.read_text());import_inline(e,prior);fields['afterEntry']=ref(e.identity(prior))
        key=Ed25519PrivateKey.from_private_bytes(bytes.fromhex(a.key_file.read_text().strip())) if a.key_file else None
        entries=[]
        resolving=set()
        def hydrate(value):
            # Content fetched here is not accepted as evidence until its provider
            # attestation is checked. Public access history has public closure.
            for _ in range(256):
                try:import_inline(e,value);return
                except Failure as exc:
                    if exc.category!='ProviderUnavailable' or key:raise
                    bid=exc.detail
                    if bid in resolving:raise ValueError('CYCLIC_OR_MISSING_CONTENT') from exc
                    resolving.add(bid)
                    query={'type':ref(e.aliases['Coordination/Resolve Timeline Content Request']),
                           'timeline':fields['timeline'],'content':ref(bid)}
                    fetched=call(a.endpoint,'/timelines/content',query)
                    hydrate(fetched['object']['content'])
                    e.put(fetched['object']['content'])
                    import_inline(e,query)
                    hydrate(fetched)
                    body=verify.attestation(fetched)
                    check(e.identity(body['request'])==e.identity(query),'WRONG_REQUEST')
                    check(e.identity(body['content'])==bid,'WRONG_CONTENT')
                    resolving.remove(bid)
            raise ValueError('CONTENT_CLOSURE_LIMIT')
        while True:
            q=e.typed('Read Timeline Request',**fields);body=q
            if key:
                from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
                body=e.typed('Signed Reader Request',request=q,publicKey=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw).hex(),signature=key.sign(('blue.coordination.reader-request\n'+e.identity(q)).encode()).hex())
            body=wire(e,body);r=call(a.endpoint,'/timelines/read',body);hydrate(r)
            response=verify.read_response(q,r)
            if a.show_exchanges:print(json.dumps({'request':body,'response':r},indent=2))
            if not a.limit:break
            page,ids=verify.page(q,r);entries.extend(page['entries'])
            if not page['hasMore']:break
            fields={'timeline':fields['timeline'],'limit':a.limit,'cursor':e.get(page['nextCursor'])}
        checkpoint=e.get(response['checkpoint']);guarantee=e.get(checkpoint['guarantee'])
        print(json.dumps({'verified':True,'completeBefore':guarantee['completeBefore'],'entries':entries},indent=2))
if __name__=='__main__':main()
