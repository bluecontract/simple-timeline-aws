"""API Gateway HTTP API entry point; owner console and the Coordination protocol."""
import base64,json,logging,os,re,time
from pathlib import Path
from urllib.parse import unquote
import boto3
from .catalogue import ref,check,ProtocolError
from .storage import StateStore,Busy
from .security import OwnerSessions

ROOT=Path(__file__).resolve().parents[1]
SERVICES=None
SECRET_REFRESH=0
LOG=logging.getLogger(__name__)
PUBLIC_PATHS={'/provider','/types','/timelines/read','/timelines/entry','/timelines/content','/access/get'}
PROTOCOL_PATHS=PUBLIC_PATHS-{'/provider','/types'}|{'/timelines/create','/timelines/append','/access/create','/access/update'}

def services():
    global SERVICES,SECRET_REFRESH
    if SERVICES is None or time.monotonic()-SECRET_REFRESH>60:
        secret=json.loads(boto3.client('secretsmanager').get_secret_value(SecretId=os.environ['SECRET_ARN'])['SecretString'])
        identity=secret.get('providerIdentity')
        if identity is not None:
            configured={'ProviderName':os.environ.get('PROVIDER_NAME','Timeline Provider'),'ProviderCompany':os.environ.get('PROVIDER_COMPANY',''),'ProviderWebsite':os.environ.get('PROVIDER_WEBSITE',''),'Endpoint':os.environ['ENDPOINT']}
            check(configured==identity,'IMMUTABLE_PROVIDER_IDENTITY')
        table=boto3.resource('dynamodb').Table(os.environ['TABLE_NAME'])
        SECRET_REFRESH=time.monotonic()
        seed=bytes.fromhex(secret['seed'])
        store=SERVICES[0] if SERVICES is not None and SERVICES[0].seed==seed else StateStore(table,boto3.client('s3'),os.environ['STATE_BUCKET'],os.environ['ENDPOINT'],os.environ.get('PROVIDER_NAME','Timeline Provider'),seed,os.environ.get('PROVIDER_COMPANY',''),os.environ.get('PROVIDER_WEBSITE',''))
        SERVICES=(store,OwnerSessions(table,secret))
    return SERVICES

def response(status,value=None,mime='application/json; charset=utf-8',cookies=None,public=False):
    binary=isinstance(value,bytes)
    body=base64.b64encode(value).decode() if binary else json.dumps(value,ensure_ascii=False,separators=(',',':')) if mime.startswith('application/json') else value or ''
    if len(body.encode())>5_500_000:return response(413,{'error':'LIMIT_EXCEEDED'})
    headers={'content-type':mime,'cache-control':'no-store','x-content-type-options':'nosniff','referrer-policy':'no-referrer','x-frame-options':'DENY',
             'content-security-policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
             'strict-transport-security':'max-age=31536000'}
    if public:headers['access-control-allow-origin']='*'
    result={'statusCode':status,'headers':headers,'body':body,'isBase64Encoded':binary}
    if cookies:result['cookies']=cookies
    return result

def json_body(event):
    raw=event.get('body') or '{}'
    if event.get('isBase64Encoded'):raw=base64.b64decode(raw,validate=True).decode()
    check(len(raw.encode())<=131072,'LIMIT_EXCEEDED')
    value=json.loads(raw);check(isinstance(value,dict),'INVALID_REQUEST');return value

def owner_route(c,method,path,body,query):
    if method=='GET':
        if path=='/owner/workspace':return {'overview':c.summary(),'timelines':c.list_timelines(),'access':c.list_access()}
        if path=='/owner/overview':return c.summary()
        if path=='/owner/timelines':return {'items':c.list_timelines()}
        if path=='/owner/access':return {'items':c.list_access()}
        if path.startswith('/owner/objects/'):return c.object(path.rsplit('/',1)[-1])
        m=re.fullmatch('/owner/timelines/([^/]+)/entries',path)
        if m:return c.entries(m[1],int(query.get('offset','0')))
    key=body.get('idempotencyKey')
    if method=='POST' and path=='/owner/timelines':
        t=c.create_timeline(body.get('name'),body.get('publicRead',False),key)
        return {'blueId':c.e.identity(t),'timeline':c.export(t)}
    m=re.fullmatch('/owner/timelines/([^/]+)(/entries)?',path)
    if m and method=='POST' and m[2]:
        check('message' in body,'INVALID_REQUEST')
        entry=c.append(m[1],body['message'],key,body.get('expectedLastEntry'))
        return {'blueId':c.e.identity(entry),'entry':c.export(entry)}
    if m and method=='DELETE' and not m[2]:return c.archive_timeline(m[1],key)
    if method=='POST' and path=='/owner/access':return c.create_access(body.get('name'),body.get('allowedTimelines'),body.get('allowedKeys'),key,create_only=body.get('createOnly',False))
    m=re.fullmatch('/owner/access/([^/]+)',path)
    if m and method=='PUT':return c.update_access(m[1],body.get('allowedTimelines'),body.get('allowedKeys'),key)
    if m and method=='DELETE':return c.update_access(m[1],[],[],key,archived=True)
    raise ValueError('NOT_FOUND')

def handler(event,context):
    path=unquote(event.get('rawPath','/'));method=event.get('requestContext',{}).get('http',{}).get('method','GET')
    headers={k.lower():v for k,v in event.get('headers',{}).items()}
    if event.get('cookies'):headers['cookie']='; '.join(event['cookies'])
    public=path in PUBLIC_PATHS or path.startswith('/packages/')
    try:
        if method=='OPTIONS' and public:
            r=response(204,'',mime='text/plain',public=True);r['headers'].update({'access-control-allow-methods':'GET,POST,OPTIONS','access-control-allow-headers':'Content-Type'});return r
        if method=='GET' and path in ('/','/console','/console/'):
            return response(200,(ROOT/'static/index.html').read_text(),mime='text/html; charset=utf-8')
        static={'/assets/app.js':('app.js','text/javascript; charset=utf-8'),'/assets/app.css':('app.css','text/css; charset=utf-8')}
        if method=='GET' and path in static:
            f,mime=static[path];return response(200,(ROOT/'static'/f).read_text(),mime=mime)
        if method=='GET' and path=='/health':return response(200,{'status':'ok'})
        if method=='GET' and path=='/packages/coordination.bluepkg':return response(200,(ROOT/'vendor/packages/blue-coordination/dist/package.bluepkg').read_bytes(),mime='application/zip',public=True)
        store,auth=services();owner=auth.authenticated(headers)
        if method=='GET' and path=='/owner/session':return response(200,{'authenticated':owner})
        if path=='/owner/login' and method=='POST':
            check(auth.origin(headers,store.endpoint),'INVALID_ORIGIN')
            body=json_body(event);cookie=auth.login(body.get('password'),event['requestContext']['http'].get('sourceIp','unknown'))
            return response(200,{'authenticated':True},cookies=[cookie])
        if path=='/owner/logout' and method=='POST':
            check(auth.origin(headers,store.endpoint),'INVALID_ORIGIN')
            return response(200,{'authenticated':False},cookies=[auth.logout(headers)])
        if path.startswith('/owner/'):
            check(owner,'UNAUTHENTICATED')
            if method!='GET':check(auth.origin(headers,store.endpoint),'INVALID_ORIGIN')
            body=json_body(event) if method!='GET' else {};query=event.get('queryStringParameters') or {}
            if method=='GET':
                try:return response(200,store.read_owner(path,query))
                except LookupError:
                    # Rare package-object inspection can still resolve through
                    # the runtime; normal console records are in the snapshot.
                    pass
            return response(200,store.execute(lambda c:owner_route(c,method,path,body,query),write=method!='GET'))
        if method=='GET' and path in ('/provider','/types'):
            return response(200,store.execute(lambda c:c.descriptor() if path=='/provider' else c.types()),public=True)
        if method=='POST' and path in PROTOCOL_PATHS:
            if path not in PUBLIC_PATHS:
                check(owner,'UNAUTHENTICATED');check(auth.origin(headers,store.endpoint),'INVALID_ORIGIN')
            body=json_body(event)
            # Reads that issue completeness guarantees also commit the seal before returning.
            return response(200,store.execute(lambda c:c.protocol(path,body,owner),write=True),public=public)
        raise ValueError('NOT_FOUND')
    except ProtocolError as exc:return response(exc.status,exc.payload,public=public)
    except Busy:return response(503,{'error':'BUSY','retryable':True},public=public)
    except PermissionError as exc:return response(401,{'error':str(exc)},public=public)
    except (ValueError,KeyError,TypeError,RecursionError) as exc:
        code=str(exc).strip("'").split(':',1)[0]
        if not re.fullmatch('[A-Z_]+',code):code='INVALID_REQUEST'
        status=401 if code=='UNAUTHENTICATED' else 403 if code in ('ACCESS_DENIED','INVALID_SIGNATURE','INVALID_ORIGIN','OWNER_OPERATION') else 404 if code=='NOT_FOUND' else 409 if code in ('IDEMPOTENCY_CONFLICT','HEAD_CONFLICT','ACCESS_ALREADY_EXISTS') else 413 if code=='LIMIT_EXCEEDED' else 400
        return response(status,{'error':code,'retryable':False},public=public)
    except Exception as exc:
        from algorithms.blue import Failure
        if isinstance(exc,Failure):return response(400,{'error':'INVALID_BLUE_DOCUMENT','retryable':False},public=public)
        LOG.exception('Request failed: %s %s',method,path)
        return response(500,{'error':'INTERNAL_ERROR','retryable':True},public=public)
