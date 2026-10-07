"""Blue identity, protocol values and real Timeline Access execution."""
from pathlib import Path
import copy,hashlib,json,os,sys,time,uuid
ROOT=Path(__file__).resolve().parents[1]
VENDOR=ROOT/'vendor'
os.environ['BLUE_PACKAGES_DIR']=str(VENDOR/'packages')
sys.path.insert(0,str(VENDOR/'runtime'))
sys.path.insert(0,str(VENDOR/'packages/blue-coordination/tools'))
from reference import Exact,Verifier,ref,check,hexbytes
from .provider_runtime import Provider as ModelProvider
from .provider import initial_details,resolved_details
from examples import import_inline,inline_response,inline_entry
from .wire import wire
from blue_language.physical import PhysicalCache

MAX_PAGE=50
MAX_CONTENT=32768
ADMISSION_RUNTIME=hashlib.sha256(json.dumps(json.loads((VENDOR/'manifest.json').read_text()),sort_keys=True,separators=(',',':')).encode()).hexdigest()
LEGACY_ADMISSION_RUNTIME='6e3a466972a34523adc5cd6d55971095ee362c51c0d3ed581452cf3e806cd186'

def now():return time.time_ns()//1000

class ProtocolError(Exception):
    def __init__(self,status,payload):
        self.status,self.payload=status,payload

class Catalogue:
    def __init__(self,endpoint,provider_name,seed,snapshot=None,provider_company='',provider_website=''):
        self.e=Exact()
        details=initial_details(provider_name,provider_company,provider_website) if not snapshot else None
        definition=snapshot['definition'] if snapshot else {
            'name':'Standalone Timeline Provider','type':'Coordination/Timeline Provider',
            'displayName':{'type':'Text'},'companyName':{'type':'Text'},'website':{'type':'Text'}}
        self.definition=definition
        self.provider_type=self.e.define('Standalone/Timeline Provider',definition)
        if snapshot:
            check(snapshot['format']=='simple-timeline-state/1','INCOMPATIBLE_STATE')
            check(snapshot.get('admissionRuntime',LEGACY_ADMISSION_RUNTIME)==ADMISSION_RUNTIME,'INCOMPATIBLE_ADMISSION_RUNTIME')
            # These are our own previously admitted objects from the hash-checked
            # committed snapshot, not remote request content. Rehash their Blue
            # structure once, then reuse the original admission on later lookups.
            # Strictly re-admitting every nested object makes cold restoration
            # quadratic in accumulated read responses and access history.
            pending=[]
            for bid,obj in snapshot['objects'].items():
                source=json.dumps(obj,sort_keys=True,separators=(',',':'))
                raw_id=self.e.language.publish_raw(source,format='json')
                if raw_id!=bid:pending.append((bid,obj,source))
                else:
                    self.e.objects[bid]=copy.deepcopy(obj)
                    self.e._identified[source]=bid
            # Source creation may have omitted exact inherited duplicates. Such
            # objects need the canonical admission path to reproduce their ID.
            for bid,obj,source in pending:
                document=self.e.language.create(source,format='json')
                check(document.blue_id==bid,'CORRUPT_STATE')
                self.e.language.publish_document(document)
                self.e.objects[bid]=copy.deepcopy(obj)
                self.e._identified[source]=bid
        model_endpoint=self.e.text_field(ref(snapshot['provider']),'endpoint') if snapshot else endpoint
        self.p=ModelProvider(self.e,seed=seed,endpoint=model_endpoint,provider_type='Standalone/Timeline Provider',
                             snapshot=snapshot['providerState'] if snapshot else None)
        provider=self.e.get(ref(snapshot['provider'])) if snapshot else dict(self.p.provider,**details,endpoint=endpoint)
        check(self.e.text_field(provider,'publicKey')==self.p.key,'PROVIDER_IDENTITY_CHANGED')
        self.p.provider=provider
        self.p.pid=self.e.identity(provider)
        self.p.verifier=Verifier(self.e,provider)
        self.endpoint=self.e.text_field(provider,'endpoint')
        check(self.endpoint==endpoint,'PROVIDER_ENDPOINT_CHANGED')
        self.provider_details=resolved_details(definition,provider)
        if snapshot:
            check(snapshot['provider']==self.p.pid,'PROVIDER_IDENTITY_CHANGED')
            self.ui=copy.deepcopy(snapshot['ui'])
            self.control=self.e.get(ref(snapshot['control']))
        else:
            self.ui={'timelines':{},'access':{}}
            self.control=self.p.create('__provider__','access',True)
            self.ui['timelines'][self.e.identity(self.control)]={'name':'Access publications','archived':False,'system':True}
            self.p.set_actor('owner',self.e.typed('Principal Actor',displayName='Owner'))

    def snapshot(self):
        # Prepare the owner read model at the same commit boundary as the state.
        # Opening the console must not replay/admit the entire provider history.
        from .console import FORMAT
        console={'format':FORMAT,'providerType':self.provider_type,
                 'aliases':dict(self.e.language.aliases),
                 'workspace':{'overview':self.summary(),'timelines':self.list_timelines(),'access':self.list_access()}}
        return {'format':'simple-timeline-state/1','admissionRuntime':ADMISSION_RUNTIME,'definition':self.definition,'provider':self.p.pid,
                'control':self.e.identity(self.control),'objects':self.e.objects,
                'providerState':self.p.snapshot(),'ui':self.ui,'console':console}

    def descriptor(self):
        att=self.p.discovery(self.control,self.endpoint)
        obj=self.e.get(att['object']);obj['maxPageSize']=MAX_PAGE
        return wire(self.e,dict(self.p.attest(obj),provider=self.p.provider,object=obj))

    def types(self):
        return {'types':self.e.aliases,'providerType':{'blueId':self.provider_type,'definition':wire(self.e,self.definition)},
                'package':'/packages/coordination.bluepkg'}

    def export(self,value):return wire(self.e,value)

    def object(self,bid):
        if bid==self.provider_type:return self.export(self.definition)
        if bid in self.e.objects:return self.export(self.e.get(ref(bid)))
        try:return json.loads(self.e.language.load(bid).exact_text)
        except Exception:raise ValueError('NOT_FOUND') from None

    def summary(self):
        return {'provider':self.export(self.p.provider),'providerBlueId':self.p.pid,'endpoint':self.endpoint,
                'providerDetails':self.provider_details,
                'controlTimeline':self.e.identity(self.control),'timelineCount':len(self.ui['timelines']),
                'entryCount':sum(len(x['entries']) for x in self.p.state['timelines'].values()),
                'accessCount':len(self.ui['access']),'maxPageSize':MAX_PAGE}

    def timeline(self,bid):
        check(bid in self.p.state['timelines'],'NOT_FOUND')
        return self.e.get(ref(bid))

    def list_timelines(self):
        rows=[]
        for bid,meta in self.ui['timelines'].items():
            entries=self.p.state['timelines'][bid]['entries']
            rows.append({'blueId':bid,**meta,'timeline':self.export(self.timeline(bid)),
                         'entryCount':len(entries),'lastTimestamp':self.e.get(ref(entries[-1]))['timestamp'] if entries else None})
        return rows

    def entries(self,bid,offset=0,limit=50):
        self.timeline(bid);check(type(offset) is int and offset>=0 and 1<=limit<=MAX_PAGE,'INVALID_REQUEST')
        ids=self.p.state['timelines'][bid]['entries'];selected=list(reversed(ids))[offset:offset+limit]
        return {'items':[{'blueId':x,'entry':self.export(inline_entry(self.e,ref(x)))} for x in selected],
                'hasMore':offset+limit<len(ids),'total':len(ids),'offset':offset}

    def _mutation_key(self,key):
        check(isinstance(key,str) and 1<=len(key)<=128,'INVALID_IDEMPOTENCY_KEY')
        return key

    def create_timeline(self,name,public,key):
        check(isinstance(name,str) and 0<len(name.strip())<=120 and type(public) is bool,'INVALID_REQUEST')
        slot='owner/create/'+self._mutation_key(key);fingerprint=[name,public]
        previous=self.p.state['requests'].get(slot)
        if previous:
            check(previous['fingerprint']==fingerprint,'IDEMPOTENCY_CONFLICT');return self.timeline(previous['timeline'])
        timeline=self.p.create('owner',uuid.uuid4().hex,public)
        bid=self.e.identity(timeline);self.ui['timelines'][bid]={'name':name.strip(),'archived':False,'system':False}
        self.p.state['requests'][slot]={'fingerprint':fingerprint,'timeline':bid}
        return timeline

    def append(self,bid,message,key,expected=None):
        timeline=self.timeline(bid);meta=self.ui['timelines'][bid]
        check(not meta['archived'] and not meta['system'],'TIMELINE_ARCHIVED' if meta['archived'] else 'ACCESS_DENIED')
        check(len(json.dumps(message,ensure_ascii=False).encode())<=MAX_CONTENT,'LIMIT_EXCEEDED')
        self._mutation_key(key)
        import_inline(self.e,message)
        return self.p.append('owner',timeline,message,key,now(),expected=expected)

    def _access_targets(self,timelines,keys):
        check(isinstance(timelines,list) and isinstance(keys,list) and len(timelines)<=100 and len(keys)<=100,'INVALID_REQUEST')
        values=[]
        for bid in timelines:
            t=self.timeline(bid);meta=self.ui['timelines'][bid]
            check(not meta['system'] and not meta['archived'],'ACCESS_DENIED');values.append(t)
        for key in keys:hexbytes(key,32)
        return values

    def _remember_access(self,access,name=None,archived=False):
        aid=self.e.identity(access);run=self.p.access_execution(access,now())
        self.ui['access'][aid]={'name':name or self.ui['access'].get(aid,{}).get('name','Timeline access'),
                                'archived':archived,'current':self.e.identity(run.current())}
        return aid

    def create_access(self,name,timelines,keys,key):
        check(isinstance(name,str) and 0<len(name.strip())<=120,'INVALID_REQUEST')
        values=self._access_targets(timelines,keys);self._mutation_key(key)
        replay='owner/access-create/'+key in self.p.state['requests']
        access,entry=self.p.create_access('owner',values,keys,key,self.control,now())
        aid=self.e.identity(access);saved=self.p.state['access'][aid]
        if not replay and (saved['timelines']!=timelines or saved['keys']!=keys):
            entry=self.p.update_access('owner',access,values,keys,hashlib.sha256(('create/'+key).encode()).hexdigest(),now())
        archived=self.ui['access'].get(aid,{}).get('archived',False) if replay else False
        aid=self._remember_access(access,name.strip(),archived=archived)
        return {'blueId':aid,'access':self.export(access),'publication':self.export(inline_entry(self.e,entry))}

    def update_access(self,aid,timelines,keys,key,archived=False):
        check(aid in self.ui['access'],'NOT_FOUND');self._mutation_key(key)
        values=self._access_targets(timelines,keys);access=self.e.get(ref(aid))
        replay='owner/access-update/'+key in self.p.state['requests']
        entry=self.p.update_access('owner',access,values,keys,key,now())
        self._remember_access(access,archived=self.ui['access'][aid]['archived'] if replay else archived)
        return {'blueId':aid,'current':self.object(self.ui['access'][aid]['current']),
                'publication':self.export(inline_entry(self.e,entry))}

    def list_access(self):
        return [{'blueId':aid,**meta,'allowedTimelines':self.p.state['access'][aid]['timelines'],
                 'allowedKeys':self.p.state['access'][aid]['keys'],'access':self.object(aid),
                 'currentDocument':self.object(meta['current'])} for aid,meta in self.ui['access'].items()]

    def archive_timeline(self,bid,key):
        self.timeline(bid);self._mutation_key(key);meta=self.ui['timelines'][bid]
        check(not meta['system'],'ACCESS_DENIED')
        if meta['archived']:return {'archived':True}
        for aid,record in list(self.p.state['access'].items()):
            if bid in record['timelines']:
                self.update_access(aid,[x for x in record['timelines'] if x!=bid],record['keys'],hashlib.sha256((key+'/'+aid).encode()).hexdigest())
        meta['archived']=True
        return {'archived':True}

    def read(self,request,key=None,owner=False):
        check(type(request.get('limit')) is int and 0<=request['limit']<=MAX_PAGE,'LIMIT_EXCEEDED')
        response=self.p.read(request,now(),key=key,owner='owner' if owner else None)
        return self.export(inline_response(self.e,response))

    def _reachable(self,bid):
        """Only follow content edges of accepted entries on the authorized timeline."""
        self.timeline(bid);todo=[bid,*self.p.state['timelines'][bid]['entries']];seen=set()
        def references(value):
            if isinstance(value,dict):
                if set(value)=={'blueId'}:todo.append(value['blueId'])
                else:
                    for x in value.values():references(x)
            elif isinstance(value,list):
                for x in value:references(x)
        while todo:
            current=todo.pop()
            if current in seen:continue
            seen.add(current)
            if current in self.e.objects:references(self.e.objects[current])
        return seen

    def protocol(self,path,body,owner=False):
        try:return self._protocol(path,body,owner)
        except (ValueError,KeyError) as exc:
            code=str(exc).strip("'").split(':',1)[0]
            status=401 if code=='UNAUTHENTICATED' else 403 if code in ('ACCESS_DENIED','INVALID_SIGNATURE','OWNER_OPERATION') else 404 if code=='NOT_FOUND' else 409 if code in ('IDEMPOTENCY_CONFLICT','HEAD_CONFLICT') else 413 if code in ('LIMIT_EXCEEDED','PAGE_LIMIT') else 503 if code=='BOUND_UNAVAILABLE' else 400
            request=body.get('request') if self.e.kind(body,'Signed Reader Request') else body
            try:
                request=self.e.require_kind(request,'Provider Request')
                if code=='INVALID_SIGNATURE':code='UNAUTHENTICATED'
                elif code=='OWNER_OPERATION':code='ACCESS_DENIED'
                elif status==400:code='INVALID_REQUEST'
                response=self.p.request('Provider Failure',request=ref(self.e.identity(request)),code=code,retryable=status==503)
                payload=self.export(dict(self.p.attest(response),object=response))
            except Exception:raise exc
            raise ProtocolError(status,payload) from None

    def _protocol(self,path,body,owner=False):
        import_inline(self.e,body)
        key=None;request=body
        if self.e.kind(body,'Signed Reader Request'):request,key=self.p.authenticate_reader(body)
        names={'/timelines/read':'Read Timeline Request','/timelines/entry':'Fetch Timeline Entry Request',
               '/timelines/content':'Resolve Timeline Content Request','/access/get':'Get Timeline Access Request',
               '/timelines/create':'Create Timeline Request','/timelines/append':'Append Entry Request',
               '/access/create':'Create Timeline Access Request','/access/update':'Update Timeline Access Request'}
        check(path in names,'NOT_FOUND');request=self.e.require_kind(request,names[path])
        mutations={'/timelines/create','/timelines/append','/access/create','/access/update'}
        if path in mutations:
            check(owner,'UNAUTHENTICATED');idempotency=request['idempotencyKey']
            if path=='/timelines/create':
                result=self.create_timeline('Timeline',request['publicRead'],idempotency)
                response=self.p.request('Timeline Created Response',request=ref(self.e.identity(request)),timeline=result)
            elif path=='/timelines/append':
                bid=self.e.identity(request['timeline']);expected=self.e.identity(request['expectedLastEntry']) if 'expectedLastEntry' in request else None
                entry=self.append(bid,self.e.get(request['message']),idempotency,expected)
                response=self.p.request('Append Entry Response',request=ref(self.e.identity(request)),entry=inline_entry(self.e,entry),entryAttestation=self.p.attest(entry))
            else:
                tids=[self.e.identity(x) for x in request['allowedTimelines']]
                if path=='/access/create':aid=self.create_access('Timeline access',tids,request['allowedKeys'],idempotency)['blueId']
                else:aid=self.e.identity(request['access']);self.update_access(aid,tids,request['allowedKeys'],idempotency)
                q=self.p.request('Get Timeline Access Request',access=ref(aid));response=self.e.get(self.p.get_access(q,now())['object'])
                response['request']=ref(self.e.identity(request))
            return self.export(dict(self.p.attest(response),object=response))
        if path=='/access/get':
            response=self.p.get_access(request,now());return self.export(dict(response,object=self.e.get(response['object'])))
        timeline=self.e.require_kind(request['timeline'],'Signed Timeline');bid=self.e.identity(timeline)
        self.p.verifier.timeline(timeline);self.timeline(bid)
        if not self.p.is_public(timeline) and key is None and not owner:raise ValueError('UNAUTHENTICATED')
        check(self.p.can_read(timeline,key,owner='owner' if owner else None),'ACCESS_DENIED')
        if path=='/timelines/read':return self.read(request,key,owner)
        if path=='/timelines/entry':
            eid=self.e.identity(request['entry']);check(eid in self.p.state['timelines'][bid]['entries'],'NOT_FOUND')
            response=self.p.request('Timeline Entry Response',request=ref(self.e.identity(request)),entry=inline_entry(self.e,ref(eid)),entryAttestation=self.p.attest(ref(eid)))
        else:
            cid=self.e.identity(request['content']);check(cid in self._reachable(bid),'ACCESS_DENIED')
            response=self.p.request('Timeline Content Response',request=ref(self.e.identity(request)),content=self.e.get(ref(cid)))
        return self.export(dict(self.p.attest(response),object=response))
