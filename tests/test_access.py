"""Dedicated access histories, durable retries and independent public verification."""
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from app.catalogue import Catalogue, PhysicalCache, now
from app.security import OwnerSessions
from app.storage import StateStore
from access_runtime import AccessExecution, control_timeline
from test_provider import MemoryS3, MemoryTable


class AccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scope = PhysicalCache(65536).scope()
        cls.scope.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.scope.__exit__(None, None, None)

    def setUp(self):
        self.seed = b'\x11' * 32
        self.c = Catalogue('https://provider.example', 'Example', self.seed)
        self.timeline = self.c.create_timeline('Private', False, 'timeline')
        self.tid = self.c.e.identity(self.timeline)

    def grant(self, key, c=None):
        return (c or self.c).create_access('Readers', [self.tid], ['22' * 32], key)

    def control(self, access, c=None):
        return control_timeline((c or self.c).e, access['access'])

    def history(self, control, c=None):
        c = c or self.c
        q = c.p.request('Read Timeline Request', timeline=control, limit=50)
        response = c.protocol('/timelines/read', c.export(q))
        c.p.verifier.read_response(q, response)
        return response['object']['page']['entries']

    def test_identical_grants_have_distinct_protected_public_histories(self):
        c = self.c
        a, b = self.grant('first'), self.grant('second')
        ca, cb = self.control(a), self.control(b)
        self.assertNotEqual(a['blueId'], b['blueId'])
        self.assertNotEqual(c.e.identity(ca), c.e.identity(cb))
        self.assertNotEqual(c.e.identity(ca), c.e.identity(c.control))
        for access, control in ((a, ca), (b, cb)):
            cid = c.e.identity(control)
            self.assertTrue(c.p.is_public(control))
            self.assertEqual(c.p.state['timelines'][cid]['owner'], '__provider__')
            self.assertTrue(c.ui['timelines'][cid]['system'])
            entries = self.history(control)
            self.assertEqual(len(entries), 2)
            self.assertEqual(c.e.identity(entries[0]['message']), access['blueId'])
            self.assertEqual(entries[1]['message']['operation'], 'update')
            descriptor = c.p.verifier.attestation(c.descriptor(access['blueId']))
            self.assertEqual(c.e.identity(descriptor['controlTimeline']), cid)
            with self.assertRaisesRegex(ValueError, 'ACCESS_DENIED'):
                c.append(cid, 'forged operation', 'append')
            with self.assertRaisesRegex(ValueError, 'ACCESS_DENIED'):
                c.archive_timeline(cid, 'archive')
            with self.assertRaisesRegex(ValueError, 'ACCESS_DENIED'):
                c.create_access('Invalid', [cid], [], 'nested')
        c.update_access(a['blueId'], [], [], 'revoke', archived=True)
        self.assertEqual(len(self.history(ca)), 3)
        self.assertEqual(len(self.history(cb)), 2)
        self.assertEqual(c.p.state['access'][b['blueId']]['keys'], ['22' * 32])
        self.assertTrue(c.p.can_read(self.timeline, key='22' * 32))
        self.assertEqual(c.entries(c.e.identity(c.control))['total'], 0)
        c.update_access(b['blueId'], [], [], 'revoke-second', archived=True)
        self.assertFalse(c.p.can_read(self.timeline, key='22' * 32))
        self.assertEqual(len(self.history(cb)), 3)

    def test_retry_conflict_and_restart_preserve_channel_and_revocation(self):
        c = self.c
        a = self.grant('first')
        c.update_access(a['blueId'], [], [], 'revoke', archived=True)
        restored = Catalogue(c.endpoint, 'Ignored', self.seed, c.snapshot())
        controls = set(restored.p.state['timelines'])
        self.assertEqual(self.grant('first', restored), a)
        self.assertTrue(restored.ui['access'][a['blueId']]['archived'])
        self.assertEqual(restored.p.state['access'][a['blueId']]['keys'], [])
        self.assertEqual(len(self.history(self.control(a), restored)), 3)
        before = restored.p.snapshot()
        with self.assertRaisesRegex(ValueError, 'IDEMPOTENCY_CONFLICT'):
            restored.create_access('Changed', [self.tid], ['33' * 32], 'first')
        self.assertEqual(restored.p.snapshot(), before)
        self.assertEqual(set(restored.p.state['timelines']), controls)
        b = self.grant('new', restored)
        self.assertNotEqual(self.control(a)['url'], self.control(b, restored)['url'])

    def test_failed_creation_does_not_leave_orphan_history(self):
        c = self.c
        before = c.p.snapshot()
        with patch.object(c.p, 'access_execution', side_effect=ValueError('EXECUTION_FAILED')):
            with self.assertRaisesRegex(ValueError, 'EXECUTION_FAILED'):
                self.grant('failed')
        self.assertEqual(c.p.snapshot(), before)
        self.assertEqual(len(c.list_timelines()), 2)
        self.assertEqual(c.list_access(), [])
        self.grant('failed')
        self.assertEqual(len(c.list_timelines()), 3)

    def test_legacy_documents_keep_their_original_shared_history(self):
        c = self.c
        # Construct the persisted format produced before dedicated histories.
        legacy, publication = c.p.create_access('owner', [self.timeline], ['22' * 32],
                                                'legacy', c.control, 100)
        aid = c._remember_access(legacy, 'Legacy')
        snapshot = copy.deepcopy(c.snapshot())
        restored = Catalogue(c.endpoint, 'Ignored', self.seed, snapshot)
        retry = restored.create_access('Legacy', [self.tid], ['22' * 32], 'legacy')
        self.assertEqual(retry['blueId'], aid)
        self.assertEqual(restored.e.identity(retry['publication']), c.e.identity(publication))
        self.assertEqual(restored.e.identity(self.control(retry, restored)),
                         restored.e.identity(restored.control))
        restored.update_access(aid, [], [], 'revoke', archived=True)
        self.assertEqual(len(self.history(restored.control, restored)), 2)
        fresh = self.grant('fresh', restored)
        self.assertNotEqual(self.control(fresh, restored)['url'], restored.control['url'])
        self.assertEqual(restored.object(aid), c.object(aid))

    def test_failed_initial_update_rolls_back_grant_and_public_history(self):
        before = self.c.p.snapshot()
        with patch.object(self.c.p, 'update_access', side_effect=ValueError('UPDATE_FAILED')):
            with self.assertRaisesRegex(ValueError, 'UPDATE_FAILED'):
                self.grant('failed-initial-update')
        self.assertEqual(self.c.p.snapshot(), before)
        self.assertEqual(self.c.list_access(), [])
        self.assertEqual(self.c.p._runs, {})
        access = self.grant('failed-initial-update')
        self.assertEqual(len(self.history(self.control(access))), 2)

    def test_compare_and_swap_and_lost_response_create_only_one_history(self):
        table, s3 = MemoryTable(), MemoryS3()
        store = StateStore(table, s3, 'data', self.c.endpoint, 'Example', self.seed)
        store.execute(lambda c: c.create_timeline('Private', False, 'timeline'), write=True)
        tid = next(t['blueId'] for t in store.cached.list_timelines() if not t['system'])
        previous = copy.deepcopy(table.items['STATE'])
        table.conflict = lambda db: db.items.__setitem__('STATE', dict(previous, revision='concurrent'))
        create = lambda c: c.create_access('Readers', [tid], ['22' * 32], 'grant')
        first = store.execute(create, write=True)
        cold = StateStore(table, s3, 'data', self.c.endpoint, 'Example', self.seed)
        self.assertEqual(cold.execute(create, write=True), first)
        self.assertEqual(len(cold.cached.list_access()), 1)
        self.assertEqual(len(cold.cached.list_timelines()), 3)
        self.assertEqual(len(self.history(self.control(first, cold.cached), cold.cached)), 2)

    def test_scoped_http_discovery_and_independent_reader(self):
        import app.handler as http
        from scripts import read_timeline
        table, s3 = MemoryTable(), MemoryS3()
        store = StateStore(table, s3, 'data', self.c.endpoint, 'Example', self.seed)
        auth = OwnerSessions(table, {'passwordHash': 'unused'})
        a = store.execute(lambda c: c.create_access('Readers', [], [], 'first'), write=True)
        store.execute(lambda c: c.update_access(a['blueId'], [], [], 'update'), write=True)
        calls = []

        def call(base, path, body=None):
            self.assertEqual(base, self.c.endpoint)
            calls.append(path)
            url = urlsplit(path)
            event = {'rawPath': url.path, 'headers': {},
                     'queryStringParameters': {k: v[0] for k, v in parse_qs(url.query).items()},
                     'requestContext': {'http': {'method': 'POST' if body else 'GET',
                                                 'sourceIp': '127.0.0.1'}}}
            if body is not None:
                event['body'] = json.dumps(body)
            with patch.object(http, 'services', return_value=(store, auth)):
                response = http.handler(event, None)
            self.assertEqual(response['statusCode'], 200, response['body'])
            return json.loads(response['body'])

        with tempfile.TemporaryDirectory() as directory:
            access_file = Path(directory) / 'access.json'
            access_file.write_text(json.dumps(a['access']))
            args = ['read_timeline.py', self.c.endpoint, '--provider', store.cached.p.pid,
                    '--access-file', str(access_file), '--limit', '1']
            with patch('sys.argv', args), patch.object(read_timeline, 'call', side_effect=call), \
                 patch('sys.stdout', new_callable=io.StringIO) as output:
                read_timeline.main()
            result = json.loads(output.getvalue())
            self.assertTrue(result['verified'])
            self.assertEqual(len(result['entries']), 3)
            self.assertIn('/provider?access=' + a['blueId'], calls)
            self.assertEqual(calls.count('/timelines/read'), 3)
            c = store.cached
            descriptor = c.descriptor(a['blueId'])
            control = self.control(a, c)
            entries = self.history(control, c)
            checkpoint = c.p.seal(control, now())
            run = AccessExecution(c.e, a['access'], descriptor, checkpoint, entries)
            run.replay()
            self.assertEqual(run.permissions()['allowedKeys'], [])
            for invalid in ('unknown', c.e.identity(c.control)):
                with self.assertRaisesRegex(ValueError, 'NOT_FOUND'):
                    c.descriptor(invalid)

            # A valid signature on the default descriptor is insufficient when
            # it designates a different channel from the selected access file.
            def wrong_descriptor(base, path, body=None):
                return c.descriptor() if path.startswith('/provider?') else call(base, path, body)
            with patch('sys.argv', args), patch.object(read_timeline, 'call', side_effect=wrong_descriptor):
                with self.assertRaisesRegex(ValueError, 'INVALID_CONTROL_TIMELINE'):
                    read_timeline.main()
