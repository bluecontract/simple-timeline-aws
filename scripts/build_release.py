"""Build a pinned Linux Lambda archive and portable CloudFormation template."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,zipfile,urllib.parse
ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build';BUILD.mkdir(exist_ok=True)

def ref(v):return {'Ref':v}
def sub(v):return {'Fn::Sub':v}
def arn(v):return {'Fn::GetAtt':[v,'Arn']}

def make_template(artifact_url,digest):
    r={}
    for name in ('StateBucket','AssetsBucket'):
        r[name]={'Type':'AWS::S3::Bucket','DeletionPolicy':'Retain','UpdateReplacePolicy':'Retain','Properties':{'PublicAccessBlockConfiguration':{'BlockPublicAcls':True,'BlockPublicPolicy':True,'IgnorePublicAcls':True,'RestrictPublicBuckets':True},'BucketEncryption':{'ServerSideEncryptionConfiguration':[{'ServerSideEncryptionByDefault':{'SSEAlgorithm':'AES256'}}]},'VersioningConfiguration':{'Status':'Enabled'}}}
    r['StateTable']={'Type':'AWS::DynamoDB::Table','DeletionPolicy':'Retain','UpdateReplacePolicy':'Retain','Properties':{'BillingMode':'PAY_PER_REQUEST','AttributeDefinitions':[{'AttributeName':'pk','AttributeType':'S'}],'KeySchema':[{'AttributeName':'pk','KeyType':'HASH'}],'SSESpecification':{'SSEEnabled':True},'PointInTimeRecoverySpecification':{'PointInTimeRecoveryEnabled':True},'TimeToLiveSpecification':{'AttributeName':'expiresAt','Enabled':True}}}
    r['ProviderSecret']={'Type':'AWS::SecretsManager::Secret','DeletionPolicy':'Retain','UpdateReplacePolicy':'Retain','Properties':{'Description':'Timeline provider signing seed and salted owner password hash'}}
    trust={'Version':'2012-10-17','Statement':[{'Effect':'Allow','Principal':{'Service':'lambda.amazonaws.com'},'Action':'sts:AssumeRole'}]}
    def role(name,statements):
        r[name]={'Type':'AWS::IAM::Role','Properties':{'AssumeRolePolicyDocument':trust,'ManagedPolicyArns':[sub('arn:${AWS::Partition}:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole')],'Policies':[{'PolicyName':'TimelineResources','PolicyDocument':{'Version':'2012-10-17','Statement':statements}}]}}
    role('BootstrapRole',[{'Effect':'Allow','Action':['s3:PutObject'],'Resource':sub('${AssetsBucket.Arn}/*')},{'Effect':'Allow','Action':['secretsmanager:GetSecretValue','secretsmanager:PutSecretValue'],'Resource':ref('ProviderSecret')}])
    role('ProviderRole',[{'Effect':'Allow','Action':['s3:GetObject','s3:PutObject'],'Resource':sub('${StateBucket.Arn}/snapshots/*')},{'Effect':'Allow','Action':['dynamodb:GetItem','dynamodb:PutItem','dynamodb:UpdateItem','dynamodb:DeleteItem'],'Resource':arn('StateTable')},{'Effect':'Allow','Action':'secretsmanager:GetSecretValue','Resource':ref('ProviderSecret')}])
    r['BootstrapFunction']={'Type':'AWS::Lambda::Function','Properties':{'Runtime':'python3.13','Handler':'index.handler','Role':arn('BootstrapRole'),'Timeout':120,'MemorySize':512,'Code':{'ZipFile':(ROOT/'infra/bootstrap.py').read_text()}}}
    key='provider/'+digest+'.zip'
    r['InstallProvider']={'Type':'Custom::TimelineInstall','Properties':{'ServiceToken':arn('BootstrapFunction'),'ServiceTimeout':180,'ArtifactUrl':artifact_url,'ArtifactSha256':digest,'AssetBucket':ref('AssetsBucket'),'AssetKey':key,'SecretArn':ref('ProviderSecret'),'AdminPassword':ref('AdminPassword')}}
    r['HttpApi']={'Type':'AWS::ApiGatewayV2::Api','DeletionPolicy':'Retain','UpdateReplacePolicy':'Retain','Properties':{'Name':sub('${AWS::StackName}-api'),'ProtocolType':'HTTP'}}
    endpoint=sub('https://${HttpApi}.execute-api.${AWS::Region}.${AWS::URLSuffix}')
    r['InstallProvider']['Properties'].update(ProviderName=ref('ProviderName'),ProviderCompany=ref('ProviderCompany'),ProviderWebsite=ref('ProviderWebsite'),Endpoint=endpoint)
    r['ProviderFunction']={'Type':'AWS::Lambda::Function','DependsOn':'InstallProvider','Properties':{'Runtime':'python3.13','Architectures':['x86_64'],'Handler':'app.handler.handler','Role':arn('ProviderRole'),'Timeout':29,'MemorySize':2048,'EphemeralStorage':{'Size':1024},'Code':{'S3Bucket':ref('AssetsBucket'),'S3Key':key},'Environment':{'Variables':{'STATE_BUCKET':ref('StateBucket'),'TABLE_NAME':ref('StateTable'),'SECRET_ARN':ref('ProviderSecret'),'ENDPOINT':endpoint,'PROVIDER_NAME':ref('ProviderName'),'PROVIDER_COMPANY':ref('ProviderCompany'),'PROVIDER_WEBSITE':ref('ProviderWebsite'),'RELEASE_SHA256':digest,'PYTHONDONTWRITEBYTECODE':'1'}}}}
    for fn in ('ProviderFunction','BootstrapFunction'):
        r[fn+'Logs']={'Type':'AWS::Logs::LogGroup','Properties':{'LogGroupName':sub('/aws/lambda/${'+fn+'}'),'RetentionInDays':14}}
    r['HttpIntegration']={'Type':'AWS::ApiGatewayV2::Integration','Properties':{'ApiId':ref('HttpApi'),'IntegrationType':'AWS_PROXY','IntegrationUri':arn('ProviderFunction'),'PayloadFormatVersion':'2.0','TimeoutInMillis':29000}}
    for name,route in [('ProxyRoute','ANY /{proxy+}'),('RootRoute','ANY /')]:
        r[name]={'Type':'AWS::ApiGatewayV2::Route','Properties':{'ApiId':ref('HttpApi'),'RouteKey':route,'Target':sub('integrations/${HttpIntegration}')}}
    r['DefaultStage']={'Type':'AWS::ApiGatewayV2::Stage','Properties':{'ApiId':ref('HttpApi'),'StageName':'$default','AutoDeploy':True,'DefaultRouteSettings':{'ThrottlingBurstLimit':20,'ThrottlingRateLimit':10}}}
    r['InvokePermission']={'Type':'AWS::Lambda::Permission','Properties':{'FunctionName':ref('ProviderFunction'),'Action':'lambda:InvokeFunction','Principal':'apigateway.amazonaws.com','SourceArn':sub('arn:${AWS::Partition}:execute-api:${AWS::Region}:${AWS::AccountId}:${HttpApi}/*')}}
    return {'AWSTemplateFormatVersion':'2010-09-09','Description':'Blue timeline provider: signed timelines, public access documents and owner console. Private durable storage is retained on stack deletion.','Parameters':{'AdminPassword':{'Type':'String','NoEcho':True,'MinLength':16,'MaxLength':128,'Description':'Owner console password (16–128 characters). Save it securely.'},'ProviderName':{'Type':'String','Default':'My Timeline Provider','MinLength':1,'MaxLength':120,'Description':'Public provider name, fixed when this provider is initialized.'},'ProviderCompany':{'Type':'String','Default':'','MaxLength':200,'Description':'Company operating the provider. Fixed at creation; leave empty for a personal provider.'},'ProviderWebsite':{'Type':'String','Default':'','MaxLength':2048,'AllowedPattern':r'^$|https://[^\s]+$','Description':'Public company website (HTTPS), fixed at creation. Informational only; the API endpoint is generated by this stack.'}},'Metadata':{'AWS::CloudFormation::Interface':{'ParameterGroups':[{'Label':{'default':'Provider identity'},'Parameters':['ProviderName','ProviderCompany','ProviderWebsite']},{'Label':{'default':'Console access'},'Parameters':['AdminPassword']}],'ParameterLabels':{'ProviderName':{'default':'Provider name'},'ProviderCompany':{'default':'Company name'},'ProviderWebsite':{'default':'Website URL'},'AdminPassword':{'default':'Console password'}}}},'Resources':r,'Outputs':{'ConsoleUrl':{'Value':sub('https://${HttpApi}.execute-api.${AWS::Region}.${AWS::URLSuffix}/console')},'ApiEndpoint':{'Value':endpoint},'FunctionName':{'Value':ref('ProviderFunction')},'StateBucket':{'Value':ref('StateBucket')},'StateTable':{'Value':ref('StateTable')}}}

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--release-base',required=True);p.add_argument('--skip-deps',action='store_true');a=p.parse_args()
    deps=BUILD/'linux-deps';deps.mkdir(exist_ok=True)
    if not a.skip_deps:
        subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check','--only-binary=:all:','--platform','manylinux_2_28_x86_64','--platform','manylinux2014_x86_64','--implementation','cp','--python-version','3.13','--target',str(deps),'cryptography==46.0.4'],check=True)
    files={}
    for base in ['app','static','vendor','infra']:
        for path in (ROOT/base).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':files[path.relative_to(ROOT).as_posix()]=path
    # Template and installer changes must also create a new immutable release URL.
    files['release/build_release.py']=Path(__file__)
    for path in deps.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':files[path.relative_to(deps).as_posix()]=path
    target=BUILD/'provider.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,path in sorted(files.items()):
            info=zipfile.ZipInfo(name,(2026,10,6,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,path.read_bytes())
    digest=hashlib.sha256(target.read_bytes()).hexdigest();url=a.release_base.rstrip('/')+'/'+digest+'/provider.zip'
    template=make_template(url,digest);(BUILD/'template.json').write_text(json.dumps(template,indent=2)+'\n')
    (BUILD/'release.json').write_text(json.dumps({'sha256':digest,'artifactUrl':url,'templateUrl':a.release_base.rstrip('/')+'/'+digest+'/template.json','files':len(files),'bytes':target.stat().st_size},indent=2)+'\n')
    readme=ROOT/'README.md'
    if readme.exists():
        text=readme.read_text();start=text.index('<!-- DEPLOY_BUTTON -->');end=text.index('<!-- /DEPLOY_BUTTON -->',start)
        template_url=a.release_base.rstrip('/')+'/'+digest+'/template.json'
        button='[![Deploy to AWS](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)](https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/create/review?stackName=simple-timeline-provider&templateURL='+urllib.parse.quote(template_url,safe='')+')'
        readme.write_text(text[:start]+'<!-- DEPLOY_BUTTON -->\n'+button+'\n'+text[end:])
    print(json.dumps({'sha256':digest,'files':len(files),'bytes':target.stat().st_size}))
if __name__=='__main__':main()
