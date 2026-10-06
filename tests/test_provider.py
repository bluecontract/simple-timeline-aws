import copy,gzip,hashlib,io,json,os,threading,unittest
from unittest.mock import patch
from app.catalogue import Catalogue,ProtocolError,PhysicalCache,ref,wire
from app.storage import StateStore
from app.security import OwnerSessions,password_hash

class Conditional(Exception):
    response={'Error':{'Code':'ConditionalCheckFailedException'}}
class MemoryTable:
    def __init__(self):self.items={};self.lock=threading.Lock();self.conflict=None
    def get_item(self,Key,**kwargs):
        with self.lock:return {'Item':copy.deepcopy(self.items[Key['pk']])} if Key['pk'] in self.items else {}
    def put_item(self,Item,**kwargs):
        with self.lock:
            if self.conflict:
                action=self.conflict;self.conflict=None;action(self);raise Conditional()
            condition=kwargs.get('ConditionExpression');old=self.items.get(Item['pk'])
            if condition=='attribute_not_exists(pk)' and old:raise Conditional()
            if condition=='revision = :r' and (not old or old['revision']!=kwargs['ExpressionAttributeValues'][':r']):raise Conditional()
            self.items[Item['pk']]=copy.deepcopy(Item)
    def delete_item(self,Key):self.items.pop(Key['pk'],None)
    def update_item(self,Key,ExpressionAttributeValues,**kwargs):
        with self.lock:
            item=self.items.setdefault(Key['pk'],{'attempts':0});item['attempts']+=1;item['expiresAt']=ExpressionAttributeValues[':expires'];return {'Attributes':copy.deepcopy(item)}
class MemoryS3:
    def __init__(self):self.objects={}
    def put_object(self,Key,Body,**kwargs):self.objects[Key]=Body
    def get_object(self,Key,**kwargs):return {'Body':io.BytesIO(self.objects[Key])}

class ProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.cache=PhysicalCache(65536);cls.scope=cls.cache.scope();cls.scope.__enter__()
    @classmethod
    def tearDownClass(cls):cls.scope.__exit__(None,None,None)
    def setUp(self):
        self.seed=os.urandom(32);self.c=Catalogue('https://provider.example','Example provider',self.seed)
    def timeline(self,public=False):
        t=self.c.create_timeline('Example',public,'create');return t,self.c.e.identity(t)
    def signed(self,q,seed=b'\x22'*32):
        s=self.c.p.sign_reader(q,seed);s['request']=q;return wire(self.c.e,s)
    def test_order_seal_paging_restart_and_retry(self):
        c=self.c;t,tid=self.timeline(True)
        with patch('app.catalogue.now',return_value=100):
            a=c.append(tid,'Hello','one');b=c.append(tid,'Hello 2','two')
            self.assertEqual((a['timestamp'],b['timestamp']),(100,101))
            self.assertEqual(c.append(tid,'Hello','one'),a)
            q=c.p.request('Read Timeline Request',timeline=ref(tid),limit=1)
            r=c.protocol('/timelines/read',wire(c.e,q));body=c.p.verifier.read_response(q,r);page=c.e.get(body['page'])
            self.assertTrue(page['hasMore']);checkpoint=c.e.get(body['checkpoint']);bound=c.e.get(checkpoint['guarantee'])['completeBefore']
            third=c.append(tid,'Later','three');self.assertGreaterEqual(third['timestamp'],bound)
            nextq=c.p.request('Read Timeline Request',timeline=ref(tid),limit=1,cursor=page['nextCursor'])
            r=c.protocol('/timelines/read',wire(c.e,nextq));p=c.e.get(c.p.verifier.read_response(nextq,r)['page'])
            self.assertFalse(p['hasMore']);self.assertEqual(c.e.identity(p['entries'][0]),c.e.identity(b))
        restored=Catalogue(c.endpoint,'Ignored after creation',self.seed,c.snapshot())
        self.assertEqual(restored.p.pid,c.p.pid);self.assertEqual(restored.e.identity(restored.append(tid,'Hello','one')),c.e.identity(a))
        self.assertGreater(restored.append(tid,'After restart','four')['timestamp'],third['timestamp'])
    def test_access_native_replay_revocation_and_public_history(self):
        c=self.c;t,tid=self.timeline();c.append(tid,'Private','one')
        q=c.p.request('Read Timeline Request',timeline=ref(tid),limit=1);s=self.signed(q);key=s['publicKey']
        with self.assertRaises(ProtocolError):c.protocol('/timelines/read',s)
        a=c.create_access('Conversation',[tid],[key],'grant');aid=a['blueId']
        r=c.protocol('/timelines/read',s);c.p.verifier.read_response(q,r)
        c.update_access(aid,[],[],'revoke')
        with self.assertRaises(ProtocolError) as denied:c.protocol('/timelines/read',s)
        self.assertEqual(denied.exception.status,403);self.assertEqual(c.p.verifier.attestation(denied.exception.payload)['code'],'ACCESS_DENIED')
        pub=c.p.request('Read Timeline Request',timeline=ref(c.e.identity(c.control)),limit=50)
        history=c.protocol('/timelines/read',wire(c.e,pub));entries=history['object']['page']['entries']
        self.assertEqual(len(entries),2);self.assertEqual(entries[1]['message']['operation'],'update')
        restored=Catalogue(c.endpoint,'Test',self.seed,c.snapshot())
        restored.update_access(aid,[tid],[key],'restore');restored.protocol('/timelines/read',s)
        self.assertEqual(restored.list_access()[0]['allowedKeys'],[key])
    def test_invalid_signatures_and_private_content_isolation(self):
        c=self.c;t,tid=self.timeline();private=c.append(tid,'secret','one')
        public=c.create_timeline('Public',True,'pub');pid=c.e.identity(public)
        q=c.p.request('Resolve Timeline Content Request',timeline=ref(pid),content=private['message'])
        with self.assertRaises(ProtocolError) as denied:c.protocol('/timelines/content',wire(c.e,q))
        self.assertEqual(denied.exception.status,403)
        pubq=c.p.request('Read Timeline Request',timeline=ref(pid),limit=50);s=self.signed(pubq);s['signature']='00'*64
        with self.assertRaises(ProtocolError) as denied:c.protocol('/timelines/read',s)
        self.assertEqual(denied.exception.status,403)
    def test_owner_ingest_response_attestation(self):
        c=self.c;t,tid=self.timeline()
        q=c.p.request('Append Entry Request',timeline=ref(tid),message='Hello',idempotencyKey='api-one')
        with self.assertRaises(ProtocolError):c.protocol('/timelines/append',wire(c.e,q))
        r=c.protocol('/timelines/append',wire(c.e,q),owner=True);body=c.p.verifier.attestation(r)
        self.assertEqual(c.p.verifier.attestation(body['entryAttestation'])['message'],body['entry']['message'] if isinstance(body['entry']['message'],dict) else ref(c.e.identity(body['entry']['message'])))
    def test_archive_revokes_but_preserves_history(self):
        c=self.c;t,tid=self.timeline();c.append(tid,'Preserve me','one');a=c.create_access('Read',[tid],['22'*32],'grant')
        c.archive_timeline(tid,'archive');self.assertEqual(c.list_access()[0]['allowedTimelines'],[])
        self.assertEqual(c.entries(tid)['total'],1)
        with self.assertRaises(ValueError):c.append(tid,'No','after')
    def test_state_compare_and_swap_and_lost_response(self):
        table,s3=MemoryTable(),MemoryS3();store=StateStore(table,s3,'data','https://provider.example','Example',self.seed)
        result=store.execute(lambda c:c.create_timeline('Durable',True,'create'),write=True)
        tid=store.cached.e.identity(result)
        original=copy.deepcopy(table.items['STATE'])
        table.conflict=lambda db:db.items.__setitem__('STATE',dict(original,revision='concurrent'))
        first=store.execute(lambda c:c.append(tid,'Once','lost-response'),write=True)
        cold=StateStore(table,s3,'data','https://provider.example','Example',self.seed)
        retry=cold.execute(lambda c:c.append(tid,'Once','lost-response'),write=True)
        self.assertEqual(first,retry);self.assertEqual(cold.execute(lambda c:c.entries(tid))['total'],1)
    def test_restoration_rejects_changed_runtime_and_object_identity(self):
        c=self.c;t,tid=self.timeline();entry=c.append(tid,'Original','one');snapshot=c.snapshot()
        changed=copy.deepcopy(snapshot);changed['admissionRuntime']='wrong-runtime'
        with self.assertRaisesRegex(ValueError,'INCOMPATIBLE_ADMISSION_RUNTIME'):
            Catalogue(c.endpoint,'Test',self.seed,changed)
        changed=copy.deepcopy(snapshot);changed['objects'][c.e.identity(entry)]['timestamp']+=1
        with self.assertRaisesRegex(ValueError,'CORRUPT_STATE'):
            Catalogue(c.endpoint,'Test',self.seed,changed)
    def test_console_reads_committed_state_without_runtime_and_sees_other_writer(self):
        table,s3=MemoryTable(),MemoryS3()
        writer=StateStore(table,s3,'data','https://provider.example','Example',self.seed)
        t=writer.execute(lambda c:c.create_timeline('Read model',False,'create'),write=True)
        tid=writer.cached.e.identity(t)
        entry=writer.execute(lambda c:c.append(tid,{'hello':'world'},'append'),write=True)
        bid=writer.cached.e.identity(entry)
        access=writer.execute(lambda c:c.create_access('Readers',[tid],['22'*32],'grant'),write=True)
        expected=writer.execute(lambda c:{'overview':c.summary(),'timelines':c.list_timelines(),'access':c.list_access()})
        expected_entries=writer.execute(lambda c:c.entries(tid))
        cold=StateStore(table,s3,'data','https://provider.example','Example',self.seed)
        with patch('app.storage.Catalogue',side_effect=AssertionError('Console must not load the runtime')):
            self.assertEqual(cold.read_owner('/owner/workspace',{}),expected)
            self.assertEqual(cold.read_owner('/owner/timelines/'+tid+'/entries',{}),expected_entries)
            self.assertEqual(cold.read_owner('/owner/objects/'+bid,{}),writer.cached.object(bid))
        writer.execute(lambda c:c.update_access(access['blueId'],[],[],'revoke',archived=True),write=True)
        with patch('app.storage.Catalogue',side_effect=AssertionError('Console must not load the runtime')):
            current=cold.read_owner('/owner/access',{})['items'][0]
            self.assertEqual(current['allowedKeys'],[])
            self.assertTrue(current['archived'])
        pointer=table.items['STATE'];s3.objects[pointer['key']]+=b'corruption'
        fresh=StateStore(table,s3,'data','https://provider.example','Example',self.seed)
        with self.assertRaisesRegex(RuntimeError,'Snapshot integrity failure'):
            fresh.read_owner('/owner/workspace',{})
    def test_console_migrates_old_snapshot_once(self):
        table,s3=MemoryTable(),MemoryS3()
        snapshot=self.c.snapshot();snapshot.pop('console')
        packed=gzip.compress(json.dumps(snapshot).encode())
        s3.objects['legacy']=packed
        table.items['STATE']={'pk':'STATE','key':'legacy','revision':'legacy','sha256':hashlib.sha256(packed).hexdigest()}
        cold=StateStore(table,s3,'data',self.c.endpoint,'Example',self.seed)
        migrated=cold.read_owner('/owner/workspace',{})
        self.assertEqual(migrated['overview']['providerBlueId'],self.c.p.pid)
        self.assertNotEqual(table.items['STATE']['revision'],'legacy')
        cold=StateStore(table,s3,'data',self.c.endpoint,'Example',self.seed)
        with patch('app.storage.Catalogue',side_effect=AssertionError('Already migrated')):
            self.assertEqual(cold.read_owner('/owner/workspace',{}),migrated)
    def test_secret_refresh_preserves_state_cache_and_rotates_authentication(self):
        import app.handler as http
        table,s3=MemoryTable(),MemoryS3()
        store=StateStore(table,s3,'data','https://provider.example','Example',self.seed)
        old=OwnerSessions(table,{'passwordHash':'old'})
        secret={'seed':self.seed.hex(),'passwordHash':'new'}
        with patch.object(http,'SERVICES',(store,old)),patch.object(http,'SECRET_REFRESH',0),patch.dict(os.environ,{'SECRET_ARN':'secret','TABLE_NAME':'table'}),patch.object(http.boto3,'client') as client,patch.object(http.boto3,'resource') as resource:
            client.return_value.get_secret_value.return_value={'SecretString':json.dumps(secret)}
            resource.return_value.Table.return_value=table
            restored,auth=http.services()
            self.assertIs(restored,store)
            self.assertEqual(auth.secret['passwordHash'],'new')
    def test_provider_profile_and_endpoint_are_part_of_identity(self):
        c=Catalogue('https://unique.example','John Doe',self.seed,provider_company='ACME Company',provider_website='https://acme.example')
        self.assertEqual(c.p.provider['displayName'],'John Doe')
        self.assertEqual(c.p.provider['companyName'],'ACME Company')
        self.assertEqual(c.p.provider['website'],'https://acme.example')
        self.assertEqual(c.p.provider['endpoint'],'https://unique.example')
        self.assertNotEqual(c.e.identity(dict(c.p.provider,endpoint='https://other.example')),c.p.pid)
        from app.console import ConsoleView
        timeline=c.create_timeline('Example',True,'profile-test');tid=c.e.identity(timeline)
        shown=ConsoleView(c.snapshot()).read('/owner/objects/'+tid,{})
        self.assertEqual(shown['provider']['endpoint'],c.endpoint)
        self.assertEqual(shown['provider']['companyName'],'ACME Company')
        self.assertEqual(c.e.identity(shown),tid)
        snapshot=c.snapshot()
        restored=Catalogue(c.endpoint,'Ignored new label',self.seed,snapshot,provider_company='Ignored company',provider_website='https://ignored.example')
        self.assertEqual(restored.p.pid,c.p.pid)
        self.assertEqual(restored.provider_details,c.provider_details)
        with self.assertRaisesRegex(ValueError,'PROVIDER_ENDPOINT_CHANGED'):
            Catalogue('https://other.example','John Doe',self.seed,snapshot)
    def test_legacy_provider_keeps_exact_identity_and_resolves_inherited_endpoint(self):
        from reference import Exact,ModelProvider
        from app.catalogue import ADMISSION_RUNTIME
        e=Exact();definition={'name':'Standalone Timeline Provider','type':'Coordination/Timeline Provider','companyName':'Legacy company','endpoint':'https://legacy.example'}
        e.define('Standalone/Timeline Provider',definition)
        p=ModelProvider(e,seed=self.seed,endpoint=None,provider_type='Standalone/Timeline Provider')
        control=p.create('__provider__','access',True);tid=e.identity(control)
        snapshot={'format':'simple-timeline-state/1','admissionRuntime':ADMISSION_RUNTIME,'definition':definition,'provider':p.pid,'control':tid,'objects':e.objects,'providerState':p.snapshot(),'ui':{'timelines':{tid:{'name':'Access publications','archived':False,'system':True}},'access':{}}}
        c=Catalogue('https://legacy.example','New setup label',self.seed,snapshot)
        self.assertEqual(c.p.provider,p.provider)
        self.assertEqual(c.p.pid,p.pid)
        self.assertEqual(c.provider_details['endpoint'],'https://legacy.example')
        self.assertEqual(c.provider_details['companyName'],'Legacy company')
    def test_stack_requests_provider_details_and_retains_endpoint(self):
        from scripts.build_release import make_template
        template=make_template('https://release.example/provider.zip','0'*64)
        self.assertTrue({'ProviderName','ProviderCompany','ProviderWebsite'}<=set(template['Parameters']))
        env=template['Resources']['ProviderFunction']['Properties']['Environment']['Variables']
        self.assertEqual(env['PROVIDER_COMPANY'],{'Ref':'ProviderCompany'})
        self.assertEqual(env['PROVIDER_WEBSITE'],{'Ref':'ProviderWebsite'})
        install=template['Resources']['InstallProvider']['Properties']
        self.assertEqual(install['Endpoint'],env['ENDPOINT'])
        for field in ('ProviderName','ProviderCompany','ProviderWebsite'):
            self.assertEqual(install[field],{'Ref':field})
        self.assertEqual(template['Resources']['HttpApi']['DeletionPolicy'],'Retain')
        self.assertEqual(template['Resources']['HttpApi']['UpdateReplacePolicy'],'Retain')
    def test_independent_reader_does_not_preload_checkpoint_head(self):
        from app.reader import ReaderExact
        from reference import Verifier
        c=self.c;t,tid=self.timeline(True);first=c.append(tid,'Hello','first');last=c.append(tid,'Hello 2','last')
        r=ReaderExact();self.assertEqual(r.define('Remote/Provider',c.export(c.definition)),c.provider_type)
        from examples import import_inline
        import_inline(r,c.descriptor());import_inline(r,c.export(t))
        q=r.typed('Read Timeline Request',timeline=ref(tid),limit=1)
        response=c.protocol('/timelines/read',wire(r,q));import_inline(r,response)
        verifier=Verifier(r,c.export(c.p.provider));page,ids=verifier.page(q,response)
        self.assertTrue(page['hasMore']);self.assertEqual(ids,[c.e.identity(first)]);self.assertNotIn(c.e.identity(last),r.objects)
        q2=r.typed('Read Timeline Request',timeline=ref(tid),limit=1,cursor=page['nextCursor'])
        response2=c.protocol('/timelines/read',wire(r,q2));import_inline(r,response2);page2,ids=verifier.page(q2,response2)
        self.assertFalse(page2['hasMore']);self.assertEqual(ids,[c.e.identity(last)])
    def test_recreate_access_and_historical_retries(self):
        c=self.c;t,tid=self.timeline();a=c.create_access('Reader',[tid],['22'*32],'first');aid=a['blueId']
        c.update_access(aid,[],[],'delete',archived=True)
        c.create_access('Reader',[tid],['22'*32],'first')
        self.assertTrue(c.ui['access'][aid]['archived']);self.assertEqual(c.list_access()[0]['allowedKeys'],[])
        c.create_access('Reader',[tid],['22'*32],'second')
        self.assertFalse(c.ui['access'][aid]['archived']);self.assertEqual(c.list_access()[0]['allowedKeys'],['22'*32])
        c.update_access(aid,[],[],'delete',archived=True)
        self.assertEqual(c.list_access()[0]['allowedKeys'],['22'*32])
    def test_http_owner_boundary_and_public_read(self):
        import app.handler as http
        table,s3=MemoryTable(),MemoryS3();store=StateStore(table,s3,'data','https://provider.example','Example',self.seed)
        salt='11'*16;auth=OwnerSessions(table,{'salt':salt,'passwordHash':password_hash('correct password',salt)})
        def call(path,method='GET',body=None,cookie=None,origin=True):
            event={'rawPath':path,'requestContext':{'http':{'method':method,'sourceIp':'127.0.0.1'}},'headers':{}}
            if origin:event['headers']['origin']=store.endpoint
            if cookie:event['headers']['cookie']=cookie
            if body is not None:event['body']=json.dumps(body)
            with patch.object(http,'services',return_value=(store,auth)):return http.handler(event,None)
        self.assertEqual(call('/owner/timelines')['statusCode'],401)
        self.assertEqual(call('/owner/login','POST',{'password':'correct password'},origin=False)['statusCode'],403)
        login=call('/owner/login','POST',{'password':'correct password'});self.assertEqual(login['statusCode'],200)
        cookie=login['cookies'][0].split(';')[0]
        workspace=call('/owner/workspace',cookie=cookie);self.assertEqual(workspace['statusCode'],200);self.assertEqual(json.loads(workspace['body'])['overview']['timelineCount'],1)
        created=call('/owner/timelines','POST',{'name':'Public','publicRead':True,'idempotencyKey':'http-create'},cookie)
        self.assertEqual(created['statusCode'],200);tid=json.loads(created['body'])['blueId']
        denied=call('/owner/timelines/'+tid+'/entries','POST',{'message':'Denied','idempotencyKey':'deny'})
        self.assertEqual(denied['statusCode'],401)
        self.assertEqual(call('/owner/timelines/'+tid+'/entries','POST',{'message':'Hello','idempotencyKey':'http-entry'},cookie)['statusCode'],200)
        q=store.execute(lambda c:c.export(c.p.request('Read Timeline Request',timeline=ref(tid),limit=50)))
        read=call('/timelines/read','POST',q,origin=False);self.assertEqual(read['statusCode'],200)
        self.assertEqual(json.loads(read['body'])['object']['page']['entries'][0]['message'],'Hello')
    def test_password_sessions_and_rate_limit(self):
        table=MemoryTable();salt='11'*16;auth=OwnerSessions(table,{'salt':salt,'passwordHash':password_hash('correct password',salt)})
        with self.assertRaises(PermissionError):auth.login('wrong','127.0.0.1')
        cookie=auth.login('correct password','127.0.0.1');headers={'cookie':cookie.split(';')[0]}
        self.assertTrue(auth.authenticated(headers));auth.logout(headers);self.assertFalse(auth.authenticated(headers))
        for i in range(18):
            with self.assertRaises(PermissionError):auth.login('wrong','127.0.0.1')
        with self.assertRaisesRegex(PermissionError,'Too many'):auth.login('correct password','127.0.0.1')

if __name__=='__main__':unittest.main()
