"""Release publication checks without AWS credentials or network access."""
from contextlib import ExitStack
from pathlib import Path
import hashlib
import io
import json
import tempfile
import unittest
import urllib.error
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError

from scripts import build_release, deploy


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'build').mkdir()
        self.readme = self.root / 'README.md'
        self.readme.write_text(
            '# Provider\n<!-- DEPLOY_BUTTON -->\nExisting button\n'
            '<!-- /DEPLOY_BUTTON -->\nKeep this documentation.\n')
        self.original = self.readme.read_bytes()
        self.blob = b'pinned public provider archive'
        digest = hashlib.sha256(self.blob).hexdigest()
        base = f'https://example-releases.s3.eu-west-1.amazonaws.com/releases/{digest}'
        self.release = dict(sha256=digest, artifactUrl=base+'/provider.zip',
                            templateUrl=base+'/template.json')
        template = {'Resources': {'InstallProvider': {'Properties': {
            'ArtifactUrl': self.release['artifactUrl'], 'ArtifactSha256': digest}}}}
        self.files = {'provider.zip': self.blob,
                      'template.json': json.dumps(template).encode()}
        for name, data in self.files.items():
            (self.root / 'build' / name).write_bytes(data)
        (self.root / 'build/release.json').write_text(json.dumps(self.release))
        self.aws = MagicMock()
        self.sts, self.s3, self.cfn = MagicMock(), MagicMock(), MagicMock()
        self.s3.exceptions.ClientError = ClientError
        self.cfn.exceptions.ClientError = ClientError
        self.sts.get_caller_identity.return_value = {'Account': '123456789012'}
        self.cfn.create_stack.return_value = {'StackId': 'created-stack'}
        self.aws.client.side_effect = {
            'sts': self.sts, 's3': self.s3, 'cloudformation': self.cfn}.__getitem__

    def run_publish(self, downloads=None, *, publish_only=True):
        argv = ['deploy.py', '--account', '123456789012', '--region', 'eu-west-1',
                '--release-bucket', 'example-releases', '--update-readme']
        if publish_only:
            argv.append('--publish-only')
        if downloads is None:
            downloads = [io.BytesIO(self.files['template.json']), io.BytesIO(self.blob)]
        with ExitStack() as stack:
            stack.enter_context(patch.object(deploy, 'ROOT', self.root))
            stack.enter_context(patch.object(deploy, 'session', return_value=self.aws))
            stack.enter_context(patch('sys.argv', argv))
            stack.enter_context(patch('sys.stdout', new_callable=io.StringIO))
            download = stack.enter_context(
                patch.object(deploy.urllib.request, 'urlopen', side_effect=downloads))
            deploy.main()
        return download

    def test_build_does_not_advertise_unpublished_release(self):
        with patch.object(build_release, 'ROOT', self.root), \
             patch.object(build_release, 'BUILD', self.root/'build'), \
             patch.object(build_release, 'make_template', return_value={}), \
             patch('sys.argv', ['build_release.py', '--release-base',
                                'https://unpublished.example/releases', '--skip-deps']), \
             patch('sys.stdout', new_callable=io.StringIO):
            build_release.main()
        self.assertEqual(self.readme.read_bytes(), self.original)
        self.assertIn('unpublished.example',
                      json.loads((self.root/'build/release.json').read_text())['templateUrl'])

    def test_publish_only_verifies_both_files_before_advertising_without_a_stack(self):
        def validated(**kwargs):
            self.assertEqual(self.readme.read_bytes(), self.original)
        self.cfn.validate_template.side_effect = validated
        download = self.run_publish()
        self.assertEqual([c.args[0] for c in download.call_args_list],
                         [self.release['templateUrl'], self.release['artifactUrl']])
        self.assertEqual(self.s3.put_object.call_count, 2)
        self.cfn.validate_template.assert_called_once_with(TemplateURL=self.release['templateUrl'])
        self.cfn.describe_stacks.assert_not_called()
        self.cfn.create_stack.assert_not_called()
        self.cfn.update_stack.assert_not_called()
        self.assertFalse((self.root/'.local').exists())
        self.assertIn('region=eu-west-1', self.readme.read_text())
        self.assertIn(deploy.urllib.parse.quote(self.release['templateUrl'], safe=''),
                      self.readme.read_text())
        self.assertTrue(self.readme.read_text().endswith('Keep this documentation.\n'))

    def test_missing_or_private_public_download_keeps_existing_button(self):
        for url in (self.release['templateUrl'], self.release['artifactUrl']):
            for status in (403, 404):
                with self.subTest(url=url, status=status):
                    error = urllib.error.HTTPError(url, status, 'Unavailable', {}, None)
                    downloads = [error] if url == self.release['templateUrl'] else [
                        io.BytesIO(self.files['template.json']), error]
                    with self.assertRaisesRegex(SystemExit, 'Public download failed'):
                        self.run_publish(downloads)
                    self.assertEqual(self.readme.read_bytes(), self.original)
        self.cfn.validate_template.assert_not_called()

    def test_missing_bucket_is_recreated_for_release_files(self):
        self.s3.head_bucket.side_effect = ClientError(
            {'Error': {'Code': '404', 'Message': 'Not found'}}, 'HeadBucket')
        self.run_publish()
        self.s3.head_bucket.assert_called_once_with(
            Bucket='example-releases', ExpectedBucketOwner='123456789012')
        self.s3.create_bucket.assert_called_once_with(
            Bucket='example-releases', CreateBucketConfiguration={'LocationConstraint': 'eu-west-1'})
        policy = json.loads(self.s3.put_bucket_policy.call_args.kwargs['Policy'])
        self.assertEqual(policy['Statement'][0]['Resource'],
                         'arn:aws:s3:::example-releases/releases/*')

    def test_normal_deployment_starts_only_after_public_release_verification(self):
        self.cfn.describe_stacks.side_effect = ClientError(
            {'Error': {'Code': 'ValidationError', 'Message': 'Stack does not exist'}},
            'DescribeStacks')
        def validated(**kwargs):
            self.cfn.create_stack.assert_not_called()
        self.cfn.validate_template.side_effect = validated
        self.run_publish(publish_only=False)
        self.cfn.create_stack.assert_called_once()
        self.assertEqual(self.cfn.create_stack.call_args.kwargs['TemplateURL'],
                         self.release['templateUrl'])
        self.assertTrue((self.root/'.local/console-password.txt').is_file())
        self.cfn.update_stack.assert_not_called()

    def test_changed_public_bytes_do_not_update_button(self):
        for downloads in ([io.BytesIO(b'wrong template')],
                          [io.BytesIO(self.files['template.json']), io.BytesIO(b'wrong archive')]):
            with self.assertRaisesRegex(SystemExit, 'differs from the local release'):
                self.run_publish(downloads)
            self.assertEqual(self.readme.read_bytes(), self.original)

    def test_invalid_cloudformation_template_does_not_update_button(self):
        self.cfn.validate_template.side_effect = ValueError('Invalid CloudFormation template')
        with self.assertRaisesRegex(ValueError, 'Invalid CloudFormation'):
            self.run_publish()
        self.assertEqual(self.readme.read_bytes(), self.original)

    def test_local_archive_or_template_mismatch_fails_before_upload(self):
        cases = [('provider.zip', b'changed archive'),
                 ('template.json', json.dumps({'Resources': {'InstallProvider': {
                     'Properties': {'ArtifactUrl': 'https://wrong.example/provider.zip',
                                    'ArtifactSha256': self.release['sha256']}}}}).encode())]
        for name, data in cases:
            with self.subTest(name=name):
                (self.root/'build'/name).write_bytes(data)
                with self.assertRaisesRegex(SystemExit, 'does not match'):
                    self.run_publish()
                (self.root/'build'/name).write_bytes(self.files[name])
        self.s3.put_object.assert_not_called()
        self.assertEqual(self.readme.read_bytes(), self.original)

    def test_account_mismatch_fails_before_publication(self):
        self.sts.get_caller_identity.return_value = {'Account': 'other'}
        with self.assertRaisesRegex(SystemExit, 'Credential account does not match'):
            self.run_publish()
        self.s3.put_object.assert_not_called()
        self.assertEqual(self.readme.read_bytes(), self.original)


if __name__ == '__main__':
    unittest.main()
