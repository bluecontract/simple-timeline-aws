"""CloudFormation custom resource: install pinned code and initialize provider secrets."""
import hashlib,hmac,json,os,urllib.request
import boto3

IDENTITY_FIELDS=('ProviderName','ProviderCompany','ProviderWebsite','Endpoint')

class ImmutableProviderIdentity(ValueError):pass

def freeze_identity(secret,properties):
    # Old templates may be replayed during rollback of the first guard upgrade.
    # They contain no identity fields and must leave an existing lock untouched.
    if not any(k in properties for k in IDENTITY_FIELDS):return dict(secret)
    if not all(k in properties for k in IDENTITY_FIELDS):raise ValueError('Incomplete provider identity')
    identity={k:properties[k] for k in IDENTITY_FIELDS}
    if 'providerIdentity' in secret and secret['providerIdentity']!=identity:
        raise ImmutableProviderIdentity()
    return dict(secret,providerIdentity=identity)

def handler(event,context):
    status='SUCCESS';reason='Initialization complete';data={}
    try:
        if event['RequestType']!='Delete':
            p=event['ResourceProperties']
            client=boto3.client('secretsmanager')
            try:secret=json.loads(client.get_secret_value(SecretId=p['SecretArn'])['SecretString'])
            except client.exceptions.ResourceNotFoundException:secret={}
            except client.exceptions.InvalidRequestException:secret={}
            original=dict(secret)
            secret=freeze_identity(secret,p)
            with urllib.request.urlopen(p['ArtifactUrl'],timeout=30) as r:blob=r.read(60*1024*1024)
            if hashlib.sha256(blob).hexdigest()!=p['ArtifactSha256']:raise ValueError('Release checksum mismatch')
            boto3.client('s3').put_object(Bucket=p['AssetBucket'],Key=p['AssetKey'],Body=blob,ServerSideEncryption='AES256')
            secret.setdefault('seed',os.urandom(32).hex())
            password=p['AdminPassword']
            matches=False
            if secret.get('salt') and secret.get('passwordHash'):
                candidate=hashlib.scrypt(password.encode(),salt=bytes.fromhex(secret['salt']),n=16384,r=8,p=1,dklen=32).hex()
                matches=hmac.compare_digest(candidate,secret['passwordHash'])
            if not matches:
                salt=os.urandom(16).hex()
                secret.update(salt=salt,passwordHash=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1,dklen=32).hex())
            if secret!=original:client.put_secret_value(SecretId=p['SecretArn'],SecretString=json.dumps(secret))
    except ImmutableProviderIdentity:
        status='FAILED';reason='Provider identity is immutable: name, company, website and endpoint must keep their creation values.'
    except Exception:
        status='FAILED';reason='Provider initialization failed; verify the pinned release URL and stack permissions.'
    body={'Status':status,'Reason':reason,'PhysicalResourceId':event.get('PhysicalResourceId',event['LogicalResourceId']), 'StackId':event['StackId'],'RequestId':event['RequestId'],'LogicalResourceId':event['LogicalResourceId'],'NoEcho':True,'Data':data}
    encoded=json.dumps(body).encode()
    request=urllib.request.Request(event['ResponseURL'],data=encoded,headers={'Content-Type':'','Content-Length':str(len(encoded))},method='PUT')
    with urllib.request.urlopen(request,timeout=20):pass
