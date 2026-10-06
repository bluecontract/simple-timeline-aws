"""Publish a public code/template release and create or update an independent stack.

Credentials come from the normal AWS SDK chain, or the explicitly selected local
properties file. Secret values are never printed or written into release assets.
"""
from pathlib import Path
import argparse,json,os,secrets,time
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

def main():
    p=argparse.ArgumentParser();p.add_argument('--credentials');p.add_argument('--region',default='us-east-1');p.add_argument('--account',required=True);p.add_argument('--stack',default='simple-timeline-provider');p.add_argument('--release-bucket',required=True);p.add_argument('--provider-name');p.add_argument('--provider-company');p.add_argument('--provider-website');p.add_argument('--status',action='store_true');a=p.parse_args()
    aws=session(a.credentials,a.region);identity=aws.client('sts').get_caller_identity()
    if identity['Account']!=a.account:raise SystemExit('Credential account does not match --account')
    cfn=aws.client('cloudformation');local=ROOT/'.local';local.mkdir(exist_ok=True);os.chmod(local,0o700)
    if a.status:
        stack=cfn.describe_stacks(StackName=a.stack)['Stacks'][0];status=stack['StackStatus'];outputs={x['OutputKey']:x['OutputValue'] for x in stack.get('Outputs',[])}
        print(json.dumps({'status':status,'outputs':outputs},indent=2))
        if status in ('CREATE_COMPLETE','UPDATE_COMPLETE'):
            dest=local/'deployment.json';dest.write_text(json.dumps({'account':a.account,'region':a.region,'stack':a.stack,**outputs},indent=2)+'\n');os.chmod(dest,0o600)
            history=local/'deployments';history.mkdir(exist_ok=True);saved=history/(a.stack+'.json');saved.write_text(dest.read_text());os.chmod(saved,0o600)
        elif status.endswith('FAILED') or 'ROLLBACK' in status:
            events=cfn.describe_stack_events(StackName=a.stack)['StackEvents']
            print(json.dumps([{'resource':e['LogicalResourceId'],'status':e['ResourceStatus'],'reason':e.get('ResourceStatusReason')} for e in events if 'FAILED' in e['ResourceStatus']],indent=2))
        return
    try:
        existing=cfn.describe_stacks(StackName=a.stack)['Stacks'][0]
        if not any(t['Key']=='Project' and t['Value']=='simple-timeline-aws' for t in existing.get('Tags',[])):
            raise SystemExit('Refusing to update an unrelated existing stack')
    except cfn.exceptions.ClientError as exc:
        if 'does not exist' not in str(exc):raise
        existing=None
    try:profile_params=identity_parameters(existing,a.provider_name,a.provider_company,a.provider_website)
    except ValueError as exc:raise SystemExit(str(exc)) from None
    release=json.loads((ROOT/'build/release.json').read_text());sha=release['sha256'];s3=aws.client('s3')
    expected=f'https://{a.release_bucket}.s3.{a.region}.amazonaws.com/releases/{sha}/provider.zip'
    if release['artifactUrl']!=expected:raise SystemExit('Rebuild release with the selected bucket and region')
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
    for filename,mime in [('provider.zip','application/zip'),('template.json','application/json')]:
        s3.put_object(Bucket=a.release_bucket,Key=f'releases/{sha}/{filename}',Body=(ROOT/'build'/filename).read_bytes(),ContentType=mime,CacheControl='public,max-age=31536000,immutable')
    cfn.validate_template(TemplateURL=release['templateUrl'])
    passwordfile=local/'console-password.txt'
    if not passwordfile.exists():
        descriptor=os.open(passwordfile,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(descriptor,'w') as f:f.write(secrets.token_urlsafe(27)+'\n')
    password=passwordfile.read_text().strip()
    params=[{'ParameterKey':'AdminPassword','ParameterValue':password},*profile_params]
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
