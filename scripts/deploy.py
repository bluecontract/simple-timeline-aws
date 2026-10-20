"""Publish a public code/template release and create or update an independent stack.

Credentials come from the normal AWS SDK chain, or the explicitly selected local
properties file. Secret values are never printed or written into release assets.
"""
from pathlib import Path
import argparse,hashlib,json,os,secrets,time
import urllib.error,urllib.parse,urllib.request
import boto3
ROOT=Path(__file__).resolve().parents[1]

def session(properties,region):
    if not properties:return boto3.Session(region_name=region)
    values={}
    for line in Path(properties).read_text().splitlines():
        line=line.strip()
        if not line or line.startswith(('#','!')):continue
        if '=' in line:k,v=line.split('=',1);values[k.strip()]=v.strip()
    return boto3.Session(aws_access_key_id=values['access'],aws_secret_access_key=values['secret'],aws_session_token=values.get('token'),region_name=region)

def identity_parameters(existing,name=None,company=None,website=None):
    previous={x['ParameterKey']:x.get('ParameterValue') for x in existing.get('Parameters',[])} if existing else {}
    result=[]
    for key,value,default in [('ProviderName',name,'My Timeline Provider'),('ProviderCompany',company,''),('ProviderWebsite',website,'')]:
        if existing and value is not None and value!=previous.get(key,default):
            raise ValueError(f'{key} is immutable after provider creation')
        result.append({'ParameterKey':key,'UsePreviousValue':True} if key in previous else {'ParameterKey':key,'ParameterValue':value if value is not None else default})
    return result

def verify_release(release):
    archive=(ROOT/'build/provider.zip').read_bytes()
    template=(ROOT/'build/template.json').read_bytes()
    if hashlib.sha256(archive).hexdigest()!=release['sha256']:
        raise SystemExit('Local archive does not match release.json')
    install=json.loads(template).get('Resources',{}).get('InstallProvider',{}).get('Properties',{})
    if install.get('ArtifactUrl')!=release['artifactUrl'] or install.get('ArtifactSha256')!=release['sha256']:
        raise SystemExit('Local template does not match release.json')
    return [('provider.zip','application/zip',archive),('template.json','application/json',template)]

def verify_public_release(release,files):
    bodies={name:body for name,mime,body in files}
    for name,url in [('template.json',release['templateUrl']),('provider.zip',release['artifactUrl'])]:
        expected=bodies[name]
        try:
            with urllib.request.urlopen(url,timeout=60) as response:
                actual=response.read(len(expected)+1)
        except (OSError,urllib.error.URLError) as exc:
            raise SystemExit(f'Public download failed for {name}: {exc}') from None
        if actual!=expected:
            raise SystemExit(f'Public {name} differs from the local release')

def update_readme(release,region):
    readme=ROOT/'README.md'
    text=readme.read_text();start=text.index('<!-- DEPLOY_BUTTON -->');end=text.index('<!-- /DEPLOY_BUTTON -->',start)
    url=('https://console.aws.amazon.com/cloudformation/home?region='+urllib.parse.quote(region,safe='')+
         '#/stacks/create/review?stackName=simple-timeline-provider&templateURL='+
         urllib.parse.quote(release['templateUrl'],safe=''))
    button='[![Deploy to AWS](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)]('+url+')'
    readme.write_text(text[:start]+'<!-- DEPLOY_BUTTON -->\n'+button+'\n'+text[end:])

def main():
    p=argparse.ArgumentParser();p.add_argument('--credentials');p.add_argument('--region',default='us-east-1');p.add_argument('--account',required=True);p.add_argument('--stack',default='simple-timeline-provider');p.add_argument('--release-bucket',required=True);p.add_argument('--provider-name');p.add_argument('--provider-company');p.add_argument('--provider-website');p.add_argument('--status',action='store_true');p.add_argument('--rotate-password',action='store_true',help='Generate and save a new owner password, invalidating existing sessions')
    p.add_argument('--publish-only',action='store_true',help='Publish and verify installer files without creating or updating a stack')
    p.add_argument('--update-readme',action='store_true',help='Point the deploy button to the verified public release')
    a=p.parse_args()
    if a.status and (a.publish_only or a.update_readme):p.error('--status cannot be combined with publication options')
    aws=session(a.credentials,a.region);identity=aws.client('sts').get_caller_identity()
    if identity['Account']!=a.account:raise SystemExit('Credential account does not match --account')
    cfn=aws.client('cloudformation');local=ROOT/'.local'
    if a.status:
        stack=cfn.describe_stacks(StackName=a.stack)['Stacks'][0];status=stack['StackStatus'];outputs={x['OutputKey']:x['OutputValue'] for x in stack.get('Outputs',[])}
        print(json.dumps({'status':status,'outputs':outputs},indent=2))
        if status in ('CREATE_COMPLETE','UPDATE_COMPLETE'):
            local.mkdir(exist_ok=True);os.chmod(local,0o700)
            dest=local/'deployment.json';dest.write_text(json.dumps({'account':a.account,'region':a.region,'stack':a.stack,**outputs},indent=2)+'\n');os.chmod(dest,0o600)
            history=local/'deployments';history.mkdir(exist_ok=True);saved=history/(a.stack+'.json');saved.write_text(dest.read_text());os.chmod(saved,0o600)
        elif status.endswith('FAILED') or 'ROLLBACK' in status:
            events=cfn.describe_stack_events(StackName=a.stack)['StackEvents']
            print(json.dumps([{'resource':e['LogicalResourceId'],'status':e['ResourceStatus'],'reason':e.get('ResourceStatusReason')} for e in events if 'FAILED' in e['ResourceStatus']],indent=2))
        return
    existing=None
    if not a.publish_only:
        try:
            existing=cfn.describe_stacks(StackName=a.stack)['Stacks'][0]
            if not any(t['Key']=='Project' and t['Value']=='simple-timeline-aws' for t in existing.get('Tags',[])):
                raise SystemExit('Refusing to update an unrelated existing stack')
        except cfn.exceptions.ClientError as exc:
            if 'does not exist' not in str(exc):raise
    try:profile_params=identity_parameters(existing,a.provider_name,a.provider_company,a.provider_website)
    except ValueError as exc:raise SystemExit(str(exc)) from None
    release=json.loads((ROOT/'build/release.json').read_text());sha=release['sha256'];s3=aws.client('s3')
    expected=f'https://{a.release_bucket}.s3.{a.region}.amazonaws.com/releases/{sha}/provider.zip'
    if release['artifactUrl']!=expected:raise SystemExit('Rebuild release with the selected bucket and region')
    if release['templateUrl']!=expected.removesuffix('provider.zip')+'template.json':
        raise SystemExit('Template URL does not match the selected release')
    files=verify_release(release)
    try:s3.head_bucket(Bucket=a.release_bucket,ExpectedBucketOwner=a.account)
    except s3.exceptions.ClientError as exc:
        if exc.response['Error']['Code'] not in ('404','NoSuchBucket'):raise
        args={'Bucket':a.release_bucket}
        if a.region!='us-east-1':args['CreateBucketConfiguration']={'LocationConstraint':a.region}
        s3.create_bucket(**args)
        s3.put_bucket_ownership_controls(Bucket=a.release_bucket,OwnershipControls={'Rules':[{'ObjectOwnership':'BucketOwnerEnforced'}]})
    s3.put_public_access_block(Bucket=a.release_bucket,PublicAccessBlockConfiguration={'BlockPublicAcls':True,'IgnorePublicAcls':True,'BlockPublicPolicy':False,'RestrictPublicBuckets':False})
    s3.put_bucket_encryption(Bucket=a.release_bucket,ServerSideEncryptionConfiguration={'Rules':[{'ApplyServerSideEncryptionByDefault':{'SSEAlgorithm':'AES256'}}]})
    # Public artifacts contain code and public Blue specifications only. No data snapshots.
    policy={'Version':'2012-10-17','Statement':[{'Sid':'ReadPublicReleases','Effect':'Allow','Principal':'*','Action':'s3:GetObject','Resource':f'arn:aws:s3:::{a.release_bucket}/releases/*'}]}
    s3.put_bucket_policy(Bucket=a.release_bucket,Policy=json.dumps(policy))
    for filename,mime,body in files:
        s3.put_object(Bucket=a.release_bucket,Key=f'releases/{sha}/{filename}',Body=body,ContentType=mime,CacheControl='public,max-age=31536000,immutable')
    verify_public_release(release,files)
    cfn.validate_template(TemplateURL=release['templateUrl'])
    if a.update_readme:update_readme(release,a.region)
    if a.publish_only:
        print(json.dumps({'operation':'publish','templateUrl':release['templateUrl'],'sha256':sha}))
        return
    local.mkdir(exist_ok=True);os.chmod(local,0o700)
    if existing and not a.rotate_password:
        password_param={'ParameterKey':'AdminPassword','UsePreviousValue':True}
    else:
        passwordfile=local/'console-password.txt'
        if a.rotate_password or not passwordfile.exists():
            descriptor=os.open(passwordfile,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(descriptor,'w') as f:
                os.fchmod(f.fileno(),0o600)
                f.write(secrets.token_urlsafe(27)+'\n')
        password_param={'ParameterKey':'AdminPassword','ParameterValue':passwordfile.read_text().strip()}
    params=[password_param,*profile_params]
    args={'StackName':a.stack,'TemplateURL':release['templateUrl'],'Parameters':params,'Capabilities':['CAPABILITY_IAM'],'Tags':[{'Key':'Project','Value':'simple-timeline-aws'}]}
    if existing:
        try:result=cfn.update_stack(**args)
        except cfn.exceptions.ClientError as exc:
            if 'No updates are to be performed' in str(exc):print('Stack already current');return
            raise
    else:result=cfn.create_stack(**args,EnableTerminationProtection=True,OnFailure='ROLLBACK')
    (local/'release.json').write_text(json.dumps(release,indent=2)+'\n')
    print(json.dumps({'operation':'update' if existing else 'create','stack':a.stack,'stackId':result['StackId'],'templateUrl':release['templateUrl']}))
if __name__=='__main__':main()
