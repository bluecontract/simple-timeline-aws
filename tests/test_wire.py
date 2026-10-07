import copy,json,unittest
from app.catalogue import Catalogue,PhysicalCache,ref,wire
from app.console import ConsoleView
from algorithms.blue import CORE,Failure

class WireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scope=PhysicalCache(65536).scope();cls.scope.__enter__()
    @classmethod
    def tearDownClass(cls):cls.scope.__exit__(None,None,None)
    def setUp(self):self.c=Catalogue('https://provider.example','Example',b'\x11'*32)

    def test_native_and_package_type_positions_leave_text_and_references_unchanged(self):
        c=self.c
        values=[{'type':name} for name in CORE]
        values += [{'type':'List','itemType':'Text'}, {'type':'Dictionary','keyType':'Text','valueType':'Integer'},
                   {'type':{'name':'Inline','type':'Text'},'value':'Text'},
                   {'type':'Coordination/Principal Actor','displayName':'Text'},ref(CORE['Text'])]
        before=copy.deepcopy(values);out=wire(c.e,values)
        for i,name in enumerate(CORE):self.assertEqual(out[i]['type'],ref(CORE[name]))
        self.assertEqual(out[6],{'type':ref(CORE['List']),'itemType':ref(CORE['Text'])})
        self.assertEqual(out[7],{'type':ref(CORE['Dictionary']),'keyType':ref(CORE['Text']),'valueType':ref(CORE['Integer'])})
        self.assertEqual(out[8],{'type':{'name':'Inline','type':ref(CORE['Text'])},'value':'Text'})
        self.assertEqual(out[9]['displayName'],'Text');self.assertEqual(out[10],values[10]);self.assertEqual(values,before)
        for i,(original,exported) in enumerate(zip(values[:-1],out[:-1])):
            if i<8:
                self.assertEqual(c.e.language.admit_definition(json.dumps(original)).blue_id,
                                 c.e.language.admit_definition(json.dumps(exported),mode='exact').blue_id)
            else:self.assertEqual(c.e.identity(original),c.e.identity(exported))

    def test_unknown_and_conflicting_native_aliases_fail(self):
        with self.assertRaisesRegex(ValueError,'UNKNOWN_TYPE_ALIAS'):wire(self.c.e,{'type':'Missing/Type'})
        self.c.e.language.aliases['Text']=CORE['Integer']
        with self.assertRaisesRegex(ValueError,'NATIVE_TYPE_ALIAS_CONFLICT'):wire(self.c.e,{'type':'Text'})

    def test_catalogue_restore_and_console_keep_identities_signatures_and_owner(self):
        c=self.c
        owner=c.e.typed('Principal Actor',displayName='Persisted custom owner');c.p.set_actor('owner',ref(c.e.identity(owner)))
        timeline=c.create_timeline('Private',False,'create');tid=c.e.identity(timeline)
        message={'payload':{'type':'Text','value':'Text'}}
        entry=c.append(tid,message,'append');eid=c.e.identity(entry)
        access=c.create_access('Readers',[tid],['22'*32],'grant')
        q=c.p.request('Read Timeline Request',timeline=ref(tid),limit=50)
        read=c.read(q,owner=True);descriptor=c.descriptor()
        snapshot=copy.deepcopy(c.snapshot())
        snapshot['console']['workspace']['overview']['ownerActor']=c.export(owner)
        restored=Catalogue(c.endpoint,'Ignored',b'\x11'*32,snapshot)
        self.assertEqual(restored.provider_type,'C4xm8EiPv6GW4H4SKkG4RcAfFV6BU8FZ641jBspJ4NmT')
        self.assertEqual(restored.p.pid,c.p.pid);self.assertEqual(restored.e.identity(restored.timeline(tid)),tid)
        self.assertEqual(restored.e.identity(restored.append(tid,message,'append')),eid)
        self.assertEqual(restored.create_access('Readers',[tid],['22'*32],'grant')['blueId'],access['blueId'])
        self.assertEqual(restored.e.identity(restored.p.state['actors']['owner']),c.e.identity(owner))
        console=ConsoleView(snapshot)
        self.assertNotIn('ownerActor',console.read('/owner/overview',{}))
        self.assertNotIn('ownerActor',console.read('/owner/workspace',{})['overview'])
        self.assertEqual(snapshot['console']['workspace']['overview']['ownerActor'],c.export(owner))
        self.assertEqual(c.e.identity(snapshot['providerState']['actors']['owner']),c.e.identity(owner))
        self.assertEqual(console.read('/owner/timelines/'+tid+'/entries',{})['items'][0]['entry']['message']['payload']['type'],ref(CORE['Text']))
        self.assertEqual(console.read('/owner/objects/'+c.provider_type,{}),c.types()['providerType']['definition'])
        self.assertEqual(c.types()['providerType']['definition']['displayName']['type'],ref(CORE['Text']))
        from examples import wire as legacy_wire
        with self.assertRaises(Failure):
            c.e.language.admit_definition(json.dumps(legacy_wire(c.e,c.definition)),mode='exact')
        self.assertEqual(c.e.language.admit_definition(json.dumps(c.types()['providerType']['definition']),mode='exact').blue_id,c.provider_type)
        self.assertEqual(c.e.identity(owner),c.e.identity(entry['actor']))
        access_request=c.p.request('Get Timeline Access Request',access=ref(access['blueId']))
        access_response=c.protocol('/access/get',c.export(access_request))
        restored.e.put(access_request)
        restored.p.verifier.attestation(access_response)
        operation={'type':'Contracts/Operation Request','document':access['access'],'channel':'provider','operation':'update',
                   'input':c.e.typed('Timeline Access Update',allowedTimelines=[ref(tid)],allowedKeys=['22'*32])}
        for payload in [descriptor,read,access_response,operation]:
            exported=c.export(payload)
            self.assertEqual(c.e.language.raw_identify(json.dumps(exported),mode='exact'),c.e.identity(payload))
        self.assertEqual(read['object']['page']['entries'][0]['message']['payload']['type'],ref(CORE['Text']))
        self.assertEqual(restored.e.identity(read),c.e.identity(read))
        restored.p.verifier.read_response(q,read);restored.p.verifier.attestation(descriptor)
        for obj in [c.p.provider,entry,access['access'],descriptor,read,message]:
            self.assertEqual(c.e.identity(obj),restored.e.identity(restored.export(obj)))
