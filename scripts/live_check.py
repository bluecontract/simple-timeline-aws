"""Exercise a deployed provider; revoke/archive the test objects on completion."""
import http.cookiejar,json,os,sys,urllib.error,urllib.request,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.catalogue import PhysicalCache,ref,wire,import_inline
from app.reader import ReaderExact as Exact
from reference import Verifier,check
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat

def main():
    deployment=json.loads((ROOT/'.local/deployment.json').read_text());base=deployment['ApiEndpoint']
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    anonymous=urllib.request.build_opener()
    def call(path,body=None,method=None,owner=False):
        headers={'Content-Type':'application/json','Origin':base}
        req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,method=method,headers=headers)
        try:
            with (opener if owner else anonymous).open(req,timeout=60) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as exc:return exc.code,json.load(exc)
    def ok(path,body=None,method=None,owner=False):
        code,result=call(path,body,method,owner);check(code==200,f'HTTP_{code}:{path}:{result}');return result
    def command(path,body=None,method='POST'):
        return ok(path,{**(body or {}),'idempotencyKey':uuid.uuid4().hex},method,True)
    with PhysicalCache(65536).scope():
        e=Exact();types=ok('/types');e.define('Remote/Provider',types['providerType']['definition'])
        discovery=ok('/provider');import_inline(e,discovery);provider=discovery['provider'];verifier=Verifier(e,provider);descriptor=verifier.attestation(discovery)
        check(call('/owner/timelines')[0]==401,'OWNER_BOUNDARY')
        ok('/owner/login',{'password':(ROOT/'.local/console-password.txt').read_text().strip()},owner=True)
        private=command('/owner/timelines',{'name':'Verification · private','publicRead':False});public=command('/owner/timelines',{'name':'Verification · public','publicRead':True})
        for item in [private,public]:import_inline(e,item['timeline'])
        tids=[private['blueId'],public['blueId']];aid=None
        try:
            first=command('/owner/timelines/'+tids[0]+'/entries',{'message':'Hello'});second=command('/owner/timelines/'+tids[0]+'/entries',{'message':'Hello 2'})
            check(first['entry']['timestamp']<second['entry']['timestamp'],'TIMESTAMP_ORDER')
            check(second['entry']['prevEntry']['blueId']==first['blueId'],'CHAIN_LINK')
            reader=Ed25519PrivateKey.generate();reader_public=reader.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw).hex()
            access=command('/owner/access',{'name':'Verification grant','allowedTimelines':[tids[0]],'allowedKeys':[reader_public]});aid=access['blueId'];import_inline(e,access['access'])
            def read(fields,sign=False):
                q=e.typed('Read Timeline Request',**fields);body=q
                if sign:body=e.typed('Signed Reader Request',request=q,publicKey=reader_public,signature=reader.sign(('blue.coordination.reader-request\n'+e.identity(q)).encode()).hex())
                result=ok('/timelines/read',wire(e,body));import_inline(e,result);page,_=verifier.page(q,result);return page,body
            check(call('/timelines/read',wire(e,e.typed('Read Timeline Request',timeline=ref(tids[0]),limit=1)))[0]==401,'PRIVATE_BOUNDARY')
            page,signed=read({'timeline':ref(tids[0]),'limit':1},True);check(page['hasMore'],'PAGINATION')
            page2,_=read({'timeline':ref(tids[0]),'limit':1,'cursor':e.get(page['nextCursor'])},True);check(not page2['hasMore'],'FINAL_PAGE')
            check(e.get(page['entries'][0])['message']=='Hello','FIRST_CONTENT');check(e.get(page2['entries'][0])['message']=='Hello 2','SECOND_CONTENT')
            # Exact entry response must carry reusable provider acceptance evidence.
            q=e.typed('Fetch Timeline Entry Request',timeline=ref(tids[0]),entry=ref(second['blueId']))
            signedq=e.typed('Signed Reader Request',request=q,publicKey=reader_public,signature=reader.sign(('blue.coordination.reader-request\n'+e.identity(q)).encode()).hex())
            result=ok('/timelines/entry',wire(e,signedq));import_inline(e,result);body=verifier.attestation(result);check(e.identity(verifier.attestation(body['entryAttestation']))==second['blueId'],'ENTRY_ATTESTATION')
            command('/owner/access/'+aid,{'allowedTimelines':[],'allowedKeys':[]},'PUT')
            code,denied=call('/timelines/read',wire(e,signed));check(code==403,'REVOKED_READ');import_inline(e,denied);check(verifier.attestation(denied)['code']=='ACCESS_DENIED','SIGNED_REVOCATION_FAILURE')
            command('/owner/timelines/'+tids[1]+'/entries',{'message':'Public verification'})
            publicpage,_=read({'timeline':ref(tids[1]),'limit':50});check(not publicpage['hasMore'],'PUBLIC_READ')
            history,_=read({'timeline':ref(e.identity(descriptor['controlTimeline'])),'limit':50});check(len(history['entries'])>=2,'ACCESS_HISTORY')
            result={'verified':True,'providerBlueId':e.identity(provider),'api':base,'checks':['owner boundary','private boundary','unique timestamps','predecessor link','signed pagination','entry attestation','published access update','revocation','anonymous public read','public access history']}
            (ROOT/'.local/live-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
        finally:
            if aid:command('/owner/access/'+aid,method='DELETE')
            for tid in tids:command('/owner/timelines/'+tid,method='DELETE')
        ok('/owner/logout',{},owner=True)
if __name__=='__main__':main()
