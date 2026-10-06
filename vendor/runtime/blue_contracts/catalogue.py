"""Exact, explicitly local type catalogue and borrowed Language boundary.

No generated Java production identifier is reinterpreted. Alias normalization is
an authoring operation; execution dispatch uses exact type identifiers only.
"""
from __future__ import annotations
import json
from pathlib import Path
from blue_runtime_bootstrap import activate
activate()
from blue_language import Language
from algorithms import blue as L
from blue_runtime.support.language import BlueAccess, ExactValue
from blue_runtime.support.registry import RuntimeRegistry
from blue_bex.values import clone, blue_value, UNDEFINED, BoundaryError, text

COORDINATION = {
 'Coordination/Timeline':'timeline','MyOS/MyOS Timeline':'timeline',
 'Coordination/Actor':'actor','MyOS/Principal Actor':'actor',
 'Coordination/Source':'source','Coordination/Timeline Entry':'timeline_entry',
 'Coordination/Timeline Channel':'timeline_channel',
 'Coordination/Composite Timeline Channel':'composite_channel',
 'Coordination/All Timelines Channel':'all_timelines_channel',
 'Coordination/Operation Request':'operation_request',
 'Coordination/Operation':'operation',
 'Coordination/Sequential Workflow Operation':'operation',
 'Coordination/Sequential Workflow':'workflow','Coordination/Compute':'compute',
 'Coordination/Trigger Event':'trigger_event','Coordination/Update Document':'update_document',
 'Coordination/Terminate Processing':'terminate_step',
 'Coordination/Event':'event','Coordination/Actor Policy':'actor_policy',
 'Coordination/Authority':'authority','Coordination/Mandate Authority':'mandate_authority',
 'Coordination/Mandate':'mandate','Coordination/Operation Mandate':'operation_mandate',
 'Reference/Completeness Evidence':'completeness_evidence',
 'Reference/Mandate Resolution Evidence':'mandate_evidence'}
CONTRACTS = {
 'Process Embedded':'process_embedded','Embedded Node Channel':'embedded_channel',
 'Triggered Event Channel':'triggered_channel','Document Update Channel':'update_channel',
 'Lifecycle Event Channel':'lifecycle_channel','Channel Event Checkpoint':'checkpoint',
 'Processing Initialized Marker':'initialized','Processing Terminated Marker':'terminated',
 'Document Processing Initiated':'initiated_event','Document Processing Terminated':'terminated_event',
 'Document Processing Fatal Error':'fatal_event','Document Update':'update_event',
 'Type Generalization Policy':'generalization_policy'}


def compact(value):
    """Only remove *builtin* scalar/list shells; retain all custom type heads."""
    if type(value) is list:return [compact(x) for x in value]
    if type(value) is not dict:return value
    if set(value)=={'type','value'} and value['type'] in ({'blueId':L.CORE[x]} for x in ('Text','Integer','Double','Boolean')):
        payload=value['value']
        return L.parse_integer(payload) if value['type']=={'blueId':L.CORE['Integer']} and type(payload) is str else payload
    if set(value) in ({'items'},{'type','items'}) and ('type' not in value or value['type']=={'blueId':L.CORE['List']}):
        return [compact(x) for x in value['items']]
    return {k:compact(v) for k,v in value.items()}

class Catalogue:
    def __init__(self,language=None):
        self.language=language if language is not None else Language(core_contracts=False)
        self.blue=BlueAccess(self.language);self.types={};self.specs={};self._contract_cache={}
        base=Path(__file__).resolve().with_name('resources')/'specifications'
        for layer in ('bex','contracts','coordination'):
            path=Path(__file__).with_name('LEGACY_SPECIFICATION.md') if layer=='contracts' else base/layer/'SPECIFICATION.md'
            if not path.is_file():raise FileNotFoundError('required specification: '+str(path))
            text=path.read_text(encoding='utf-8')
            self.specs[layer]=self.blue.admit_value(text)
        self.registry=RuntimeRegistry(self.blue,self.specs['coordination'].blue_id)
        for layer,roles in (('coordination',COORDINATION),('contracts',CONTRACTS)):
            for name,role in roles.items():
                value=self.blue.admit({'name':name,'specification':{'blueId':self.specs[layer].blue_id}},goal='definition')
                self.types[name]=value
                if layer=='coordination':self.registry.install(value,role)
                else:self.registry.install_extension(value,role,role,specification=self.specs[layer].blue_id)
                previous=self.language.aliases.get(name)
                if previous is not None and previous!=value.blue_id:raise ValueError('alias conflict: '+name)
                self.language.aliases[name]=value.blue_id

    def initialization_value(self,name,before):
        return self.typed(name,documentId=before)

    def checkpoint_value(self,entry_blue_id):
        return {'subject':{'blueId':entry_blue_id}}

    def id(self,name):return self.types[name].blue_id
    def typed(self,name,**fields):return {'type':{'blueId':self.id(name)},**fields}
    def role(self,node):
        if type(node) is not dict:return None
        typ=node.get('type');tid=typ.get('blueId') if type(typ) is dict else None
        binding=self.registry.lookup(tid,required=False)
        return binding.role if binding else None

    def normalize_types(self,node):
        """Resolve authoring aliases even inside symbolic cyclic-set input."""
        if type(node) is int and abs(node)>L.SAFE:
            rendered=text(node)
            return {'type':{'blueId':L.CORE['Integer']},'value':rendered}
        if type(node) is list:return [self.normalize_types(x) for x in node]
        if type(node) is not dict:return node
        out={}
        for k,v in node.items():
            if k=='value':
                out[k]=v;continue
            if k in L.TYPES and type(v) is str:
                tid=L.CORE.get(v,self.language.aliases.get(v))
                if tid is None:raise BoundaryError('unknown type alias '+v)
                out[k]={'blueId':tid}
            else:out[k]=self.normalize_types(v)
        if type(out.get('value')) is int and abs(out['value'])>L.SAFE:
            typ=out.get('type',{'blueId':L.CORE['Integer']})
            if typ not in ({'blueId':L.CORE['Integer']},{'blueId':L.CORE['Double']}):
                raise BoundaryError('custom typed large scalar requires explicit canonical Source value text')
            out['type']=typ;out['value']=text(out['value'])
        return out

    def admit(self,value,*,goal='definition'):
        exact=self.blue.admit_value(blue_value(self.normalize_types(value)),goal=goal)
        return exact,compact(self.blue.tree(exact))

    def validate(self,value,*,goal='definition'):
        # Semantic admission, including referenced definitions; never raw hash.
        return self.blue.admit_value(self.normalize_types(blue_value(value)),goal=goal)

    def read_plain(self,value):
        if value is UNDEFINED:return value
        exact=self.validate(value)
        return self.blue.view(exact).plain(types=True)

    def matches(self,value,pattern):
        # BlueAccess.matches accepts the candidate before checking specialization.
        candidate=self.blue.admit_value(self.normalize_types(blue_value(value)),goal='value')
        pat=self.blue.admit_value(self.normalize_types(pattern),goal='definition')
        return self.blue.matches(pat,candidate)

    def effective_contracts(self,document):
        # Contract recognition depends on the exact contract subtree and enclosing
        # type, not unrelated mutable fields. Cache an already validated view.
        # This is not a document-validity cache: Processor/admission still validate
        # the full document and every tentative mutation separately.
        key=json.dumps({'contracts':document.get('contracts',{}),'type':document.get('type')},
                       sort_keys=True,ensure_ascii=False,separators=(',',':'))
        if key in self._contract_cache:return clone(self._contract_cache[key])
        exact=self.validate(document)
        from blue_runtime.support.language import MISSING
        contracts=self.blue.view(exact).field('contracts')
        out={} if contracts is MISSING else self._contract_plain(contracts,contract_entries=True)
        self._contract_cache[key]=clone(out)
        return out

    def _literal_source(self,view):
        h=view.head
        if h.items is not None:
            return [compact(v.source()) for v in view.items()]
        raw=compact(view.source())
        if isinstance(raw,dict) and view.recipe.parts:
            latest=L.open_exact(view.recipe.parts[-1],view.context)
            # Container-level labels supplied only by its declaration are not
            # members of a BEX user dictionary/program. Keep authored labels.
            for key in L.LABELS:
                if not latest.has(key):raw.pop(key,None)
        return raw

    def _contract_plain(self,view,active=frozenset(),*,contract_entries=False):
        """Effective executable view, retaining Language labels such as step name.

        Language's business observation helper intentionally omits labels. That
        is unsuitable here: Coordination uses a step's name as the $steps key.
        """
        key=view.recipe.key()
        if key in active:raise BoundaryError('recursive executable contract tree')
        h=view.head
        if h.value is not L.ABSENT:return h.value
        if h.items is not None:return [self._contract_plain(v,active|{key}) for v in view.items()]
        binding=self.registry.lookup(h.type_id,required=False) if h.type_id else None
        role=binding.role if binding else None
        literal_fields={'compute':{'do','expr','constants','functions'},
            'trigger_event':{'event'},'update_document':{'changeset'},
            'workflow':{'event'},'operation':{'event','request'},
            'embedded_channel':{'event'},'embedded_collection_channel':{'event'},
            'triggered_channel':{'event'},'update_channel':{'event'},
            'lifecycle_channel':{'event'}}.get(role,set())
        # Runtime declarations use effective fields; embedded executable/data
        # programs retain their admitted Source structure. Flattening the type
        # of every literal would inject inherited fields (even an entire spec!)
        # into effects and charge for data the author never constructed.
        def configured(k,v):
            # Contract entries can legitimately contain only a runtime type.
            # They are declarations to execute, not optional business values.
            if contract_entries:return True
            if L.present_recipe(v.recipe,v.context):return True
            if k in {'request','event'} and k in literal_fields:
                # A request/event matcher is a definition, not a sample value.
                raw=L.recipe_exact_value(v.recipe,v.context)
                body=L.open_exact(raw,v.context)
                return bool(set(body.keys())-L.LABELS)
            return False
        out={k:(self._literal_source(v) if k in literal_fields else self._contract_plain(v,active|{key}))
             for k,v in view.fields().items() if configured(k,v)}
        out.update(clone(h.labels))
        if h.type_id:out['type']={'blueId':h.type_id}
        if h.contracts is not None:
            from blue_runtime.support.language import View
            out['contracts']=self._contract_plain(View(view.access,h.contracts,view.context),active|{key},contract_entries=True)
        return out
