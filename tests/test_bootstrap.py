import copy,hashlib,json,unittest
from unittest.mock import MagicMock,patch
from infra import bootstrap
from scripts.deploy import identity_parameters

class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.identity={'ProviderName':'John Doe','ProviderCompany':'ACME Company','ProviderWebsite':'https://acme.example','Endpoint':'https://endpoint.example'}
        self.secret={'seed':'11'*32,'providerIdentity':dict(self.identity),'salt':'22'*16,'passwordHash':hashlib.scrypt(b'old password',salt=bytes.fromhex('22'*16),n=16384,r=8,p=1,dklen=32).hex()}
        self.blob=b'public release code'
        self.properties={**self.identity,'SecretArn':'secret','ArtifactUrl':'https://release.example/code.zip','ArtifactSha256':hashlib.sha256(self.blob).hexdigest(),'AssetBucket':'assets','AssetKey':'code.zip','AdminPassword':'new password'}
        self.event={'RequestType':'Update','ResourceProperties':self.properties,'ResponseURL':'https://response.example','LogicalResourceId':'Install','PhysicalResourceId':'Install','StackId':'stack','RequestId':'request'}

    def test_identity_is_pinned_once_and_every_field_is_immutable(self):
        original=copy.deepcopy(self.secret)
        self.assertEqual(bootstrap.freeze_identity({},self.properties)['providerIdentity'],self.identity)
        self.assertEqual(bootstrap.freeze_identity(self.secret,self.properties),self.secret)
        for field in self.identity:
            with self.subTest(field=field),self.assertRaises(bootstrap.ImmutableProviderIdentity):
                bootstrap.freeze_identity(self.secret,dict(self.properties,**{field:'changed'}))
        self.assertEqual(self.secret,original)
        self.assertEqual(bootstrap.freeze_identity(self.secret,{}),self.secret)

    def test_cloudformation_rejects_identity_change_before_side_effects(self):
        secrets=MagicMock();secrets.get_secret_value.return_value={'SecretString':json.dumps(self.secret)}
        self.event['ResourceProperties']=dict(self.properties,ProviderName='Changed')
        with patch.object(bootstrap.boto3,'client',return_value=secrets) as client,patch.object(bootstrap.urllib.request,'urlopen') as urlopen:
            bootstrap.handler(self.event,None)
        client.assert_called_once_with('secretsmanager')
        secrets.put_secret_value.assert_not_called()
        urlopen.assert_called_once()
        sent=urlopen.call_args.args[0]
        self.assertEqual(sent.full_url,self.event['ResponseURL'])
        response=json.loads(sent.data)
        self.assertEqual(response['Status'],'FAILED')
        self.assertIn('immutable',response['Reason'])

    def test_code_and_password_update_preserve_identity_and_signing_key(self):
        secrets=MagicMock();secrets.get_secret_value.return_value={'SecretString':json.dumps(self.secret)}
        storage=MagicMock();download=MagicMock();download.__enter__.return_value.read.return_value=self.blob
        with patch.object(bootstrap.boto3,'client',side_effect=lambda name:secrets if name=='secretsmanager' else storage),patch.object(bootstrap.urllib.request,'urlopen',side_effect=[download,MagicMock()]) as urlopen:
            bootstrap.handler(self.event,None)
        saved=json.loads(secrets.put_secret_value.call_args.kwargs['SecretString'])
        self.assertEqual(saved['providerIdentity'],self.identity)
        self.assertEqual(saved['seed'],self.secret['seed'])
        expected=hashlib.scrypt(b'new password',salt=bytes.fromhex(saved['salt']),n=16384,r=8,p=1,dklen=32).hex()
        self.assertEqual(saved['passwordHash'],expected)
        self.assertEqual(json.loads(urlopen.call_args.args[0].data)['Status'],'SUCCESS')

    def test_deploy_rejects_changed_identity_parameters(self):
        existing={'Parameters':[{'ParameterKey':k,'ParameterValue':v} for k,v in self.identity.items() if k!='Endpoint']}
        self.assertTrue(all(p.get('UsePreviousValue') for p in identity_parameters(existing)))
        self.assertTrue(all(p.get('UsePreviousValue') for p in identity_parameters(existing,'John Doe','ACME Company','https://acme.example')))
        for field in ('name','company','website'):
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'immutable'):
                identity_parameters(existing,**{field:'Changed'})
        created=identity_parameters(None,'John Doe','ACME Company','https://acme.example')
        self.assertEqual({p['ParameterKey']:p['ParameterValue'] for p in created},{k:v for k,v in self.identity.items() if k!='Endpoint'})

    def test_code_only_deploy_preserves_password_even_without_local_file(self):
        import tempfile
        from pathlib import Path
        from scripts import deploy
        aws=MagicMock();aws.client.return_value.get_caller_identity.return_value={'Account':'123'}
        aws.client.return_value.describe_stacks.return_value={'Stacks':[{'Tags':[{'Key':'Project','Value':'simple-timeline-aws'}],'Parameters':[{'ParameterKey':'AdminPassword','ParameterValue':'****'}]}]}
        aws.client.return_value.update_stack.return_value={'StackId':'stack'}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'build').mkdir()
            release={'sha256':'abc','artifactUrl':'https://artifacts.s3.eu-west-1.amazonaws.com/releases/abc/provider.zip','templateUrl':'https://artifacts/template.json'}
            (root/'build/release.json').write_text(json.dumps(release))
            for name in ('provider.zip','template.json'):(root/'build'/name).write_bytes(b'fixture')
            with patch.object(deploy,'ROOT',root),patch.object(deploy,'session',return_value=aws),patch('sys.argv',['deploy','--account','123','--region','eu-west-1','--release-bucket','artifacts']),patch('builtins.print'):
                deploy.main()
            parameters=aws.client.return_value.update_stack.call_args.kwargs['Parameters']
            self.assertEqual(next(p for p in parameters if p['ParameterKey']=='AdminPassword'),{'ParameterKey':'AdminPassword','UsePreviousValue':True})
            passwordfile=root/'.local/console-password.txt'
            self.assertFalse(passwordfile.exists())
            with patch.object(deploy,'ROOT',root),patch.object(deploy,'session',return_value=aws),patch('sys.argv',['deploy','--account','123','--region','eu-west-1','--release-bucket','artifacts','--rotate-password']),patch('builtins.print'):
                deploy.main()
            parameters=aws.client.return_value.update_stack.call_args.kwargs['Parameters']
            rotated=next(p for p in parameters if p['ParameterKey']=='AdminPassword')
            self.assertEqual(rotated,{'ParameterKey':'AdminPassword','ParameterValue':passwordfile.read_text().strip()})
            self.assertGreater(len(rotated['ParameterValue']),20)
            self.assertEqual(passwordfile.stat().st_mode & 0o777,0o600)
