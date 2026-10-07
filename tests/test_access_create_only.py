import copy,json,unittest
from unittest.mock import patch
from app.catalogue import Catalogue,PhysicalCache
from app.storage import StateStore
from app.handler import owner_route
from test_provider import MemoryTable,MemoryS3

class CreateOnlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.scope=PhysicalCache(65536).scope();cls.scope.__enter__()
    @classmethod
    def tearDownClass(cls):cls.scope.__exit__(None,None,None)
    def setUp(self):
        self.c=Catalogue('https://provider.example','Example',b'\x11'*32)
        self.tid=self.c.e.identity(self.c.create_timeline('Private',False,'create'))
    def create(self,c,key,create_only=True):
        return owner_route(c,'POST','/owner/access',{'name':'Readers','allowedTimelines':[self.tid],
            'allowedKeys':['22'*32],'idempotencyKey':key,'createOnly':create_only},{})
    def test_collision_never_changes_existing_permissions_or_publications(self):
        c=self.c;aid=self.create(c,'first')['blueId']
        for state in ('current','changed','revoked','archived'):
            with self.subTest(state=state):
                if state!='current':c.update_access(aid,[self.tid] if state=='changed' else [],['33'*32] if state=='changed' else [],state,archived=state=='archived')
                before=copy.deepcopy(c.p.state);ui=copy.deepcopy(c.ui)
                with self.assertRaisesRegex(ValueError,'ACCESS_ALREADY_EXISTS'):self.create(c,'new-'+state)
                self.assertEqual(c.p.state,before);self.assertEqual(c.ui,ui)
        # A caller's own retry does not restore revoked permissions or metadata.
        self.assertEqual(self.create(c,'first')['blueId'],aid)
        self.assertEqual(c.p.state['access'][aid]['keys'],[]);self.assertTrue(c.ui['access'][aid]['archived'])
        self.assertEqual(self.create(c,'legacy',False)['blueId'],aid)
        self.assertEqual(c.p.state['access'][aid]['keys'],['22'*32]);self.assertFalse(c.ui['access'][aid]['archived'])
    def test_flag_must_be_boolean(self):
        for value in ('true',1,None):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'INVALID_REQUEST'):self.create(self.c,'invalid',value)
    def test_cas_retry_checks_competing_arrangement_and_cold_replay(self):
        table,s3=MemoryTable(),MemoryS3();store=StateStore(table,s3,'data',self.c.endpoint,'Example',b'\x11'*32)
        self.tid=store.execute(lambda c:c.e.identity(c.create_timeline('Private',False,'create')),write=True)
        competitor=StateStore(table,s3,'data',self.c.endpoint,'Example',b'\x11'*32)
        # Build a separately committed winner, then make the first writer observe
        # the older pointer until its CAS loses to that winner.
        original=copy.deepcopy(table.items['STATE'])
        winner=competitor.execute(lambda c:self.create(c,'winner'),write=True)
        winning_pointer=copy.deepcopy(table.items['STATE']);table.items['STATE']=original
        table.conflict=lambda db:db.items.__setitem__('STATE',winning_pointer)
        with self.assertRaisesRegex(ValueError,'ACCESS_ALREADY_EXISTS'):
            store.execute(lambda c:self.create(c,'loser'),write=True)
        self.assertEqual(table.items['STATE'],winning_pointer)
        cold=StateStore(table,s3,'data',self.c.endpoint,'Example',b'\x11'*32)
        retry=cold.execute(lambda c:self.create(c,'winner'),write=True)
        self.assertEqual(winner,retry)
        self.assertEqual(cold.execute(lambda c:len(c.p.state['timelines'][c.e.identity(c.control)]['entries'])),1)
