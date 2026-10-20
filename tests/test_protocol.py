"""Qualify the exact MyOS access-events publication and its real update program."""
import copy
import hashlib
import json
import unittest

from app.catalogue import Catalogue, PhysicalCache, VENDOR, now


class ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scope = PhysicalCache(65536).scope()
        cls.scope.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.scope.__exit__(None, None, None)

    def test_vendored_file_integrity_and_exact_myos_publication(self):
        manifest = json.loads((VENDOR / 'manifest.json').read_text())
        actual = {p.relative_to(VENDOR).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in VENDOR.rglob('*') if p.is_file() and p != VENDOR / 'manifest.json'
                  and '__pycache__' not in p.parts and p.suffix != '.pyc'}
        self.assertEqual(actual, manifest)
        c = Catalogue('https://protocol.example', 'Test', b'\x11' * 32)
        self.assertEqual(c.types()['protocol']['blueId'], '4gmSjwn3DCYBVeDieXxuXgsPvvz2dU6ovFXnnuyv2RjA')
        for name, bid in {
            'Timeline Access': '3WukTexA1Nex951RDHoA6S6QfNgFmdiBpigfRUzi9YMh',
            'Update Timeline Access': '8Dd12DcFEA1kiGauJwvVHEwJAMKRPKDGDDxgxWgsdyRG',
            'Timeline Access Updated': 'Ff1CegGgBpYqfdpiZTaETSzodJXf7rh5FNZNJE7KBcdx',
            'Timeline Channel': 'GCd3gAEibsaZi1vdhFhTSfRch1HPruFcE1pgm9eAMKwy',
        }.items():
            self.assertEqual(c.e.aliases['Coordination/' + name], bid)

    def test_updates_emit_once_including_noop_and_restore_but_not_invalid_or_retried(self):
        c = Catalogue('https://protocol.example', 'Test', b'\x11' * 32)
        timeline = c.create_timeline('Private', False, 'timeline')
        tid = c.e.identity(timeline)
        access = c.create_access('Read', [tid], ['22' * 32], 'grant')
        aid = access['blueId']
        run = c.p._runs[aid]
        expected = c.e.identity(c.e.typed('Timeline Access Updated'))
        self.assertEqual(len(run.outcomes), 1)
        self.assertEqual([row['event'] for row in run.outcomes[0].public_events], [expected])
        self.assertIsNotNone(run.p.read(run.state, '/contracts/checkpoint/entries/provider'))
        for key, keys in [('add', ['22' * 32, '33' * 32]),
                          ('unchanged', ['22' * 32, '33' * 32]), ('revoke', [])]:
            c.update_access(aid, [tid], keys, key)
            self.assertEqual([row['event'] for row in run.outcomes[-1].public_events], [expected])
            self.assertEqual(run.permissions()['allowedKeys'], keys)
        occurrences = [outcome.public_events[0] for outcome in run.outcomes]
        self.assertEqual(len({json.dumps(row, sort_keys=True) for row in occurrences}), 4)
        before = copy.deepcopy(c.p.snapshot())
        c.update_access(aid, [tid], [], 'revoke')
        self.assertEqual(len(run.outcomes), 4)
        self.assertEqual(c.p.state['access'], before['access'])
        for timeline_id, timeline_state in before['timelines'].items():
            self.assertEqual(c.p.state['timelines'][timeline_id]['entries'], timeline_state['entries'])
        before = copy.deepcopy(c.p.snapshot())
        with self.assertRaisesRegex(ValueError, 'DUPLICATE'):
            c.update_access(aid, [tid], ['22' * 32, '22' * 32], 'bad')
        self.assertEqual(c.p.snapshot(), before)
        restored = Catalogue(c.endpoint, 'Ignored', b'\x11' * 32, c.snapshot())
        restored_run = restored.p.access_execution(restored.e.get({'blueId': aid}), now())
        self.assertEqual([o.public_events for o in restored_run.outcomes],
                         [o.public_events for o in run.outcomes])
        self.assertFalse(restored.p.can_read(timeline, key='22' * 32))
