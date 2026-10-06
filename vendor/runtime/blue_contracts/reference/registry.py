"""Exact catalogue, contextual headers and deferred executable bodies."""
from pathlib import Path
from algorithms import blue as L
from .model import ContractError,require,token,integer,segments,LIMITS
from .catalogue import PARENTS,publish_catalogue
ROLES={'Contract':'abstract','Marker':'abstract','Channel':'abstract','External Channel':'external','Composite External Channels':'composite','All External Channels':'all','Triggered Event Channel':'triggered','Embedded Node Channel':'embedded_event','Document Update Channel':'update','Lifecycle Event Channel':'lifecycle','Process Embedded':'embedding','Handler':'abstract','Operation':'abstract','Sequential Workflow':'workflow','Sequential Workflow Operation':'operation','Operation Request':'request','Compute':'compute','Compute Definition':'compute_definition','Update Document':'patch_step','Trigger Event':'emit_step','Terminate Processing':'terminate_step','Channel Event Checkpoint':'checkpoint','Processing Initialized Marker':'initialized','Processing Terminated Marker':'terminated','Document Processing Initiated':'initiated','Document Processing Terminated':'ended','Document Update':'updated','Embedded Event Delivery':'embedded_delivery','Json Patch Entry':'patch_record','Contract Execution Result':'execution_result','Type Generalization Rule':'generalization_rule','Type Generalization Policy':'generalization'}
EXTERNAL={'external','composite','all','extension_external'}
INTERNAL={'triggered','embedded_event','update','lifecycle','extension_channel'}
EXECUTABLE={'workflow','operation','extension_handler'}
MARKERS={'initialized':'initialized','terminated':'terminated','checkpoint':'checkpoint'}
DATA_ROLES={'request','initiated','ended','updated','embedded_delivery','patch_record','execution_result','generalization_rule'}
LITERAL_FIELDS={'do','expr','constants','functions','event','changeset','request'}
ALLOWED={'external':{'event'},'composite':{'channels'},'all':set(),'triggered':{'event'},'embedded_event':{'sourcePath','event'},'update':{'path','event'},'lifecycle':{'event'},'embedding':{'paths','collectionPaths'},'workflow':{'channel','event','steps'},'operation':{'channel','request','steps'},'compute':{'expr','do','constants','functions','entry','definition'},'compute_definition':{'constants','functions'},'patch_step':{'changeset'},'emit_step':{'event'},'terminate_step':{'cause','reason'},'generalization':{'defaultMode','rules'}}
BODY_FIELDS={'workflow':{'steps'},'operation':{'steps'},'compute':{'expr','do','constants','functions','entry','definition'},'compute_definition':{'constants','functions'},'patch_step':{'changeset'},'emit_step':{'event'},'terminate_step':{'cause','reason'}}

class Registry:
    def __init__(self,bridge):
        self.blue=bridge;self.types={};self.by_id={};self.extensions={};document=Path(__file__).resolve().parents[1]/'COMPLETE_SPECIFICATION.md'
        require(document.is_file(),'MISSING_SPECIFICATION');self.specification=self.blue.identity(self.blue.source(document.read_text(encoding='utf-8')))
        def admit(raw):return self.blue.identity(self.blue.source(raw,goal='definition'))
        self.types=publish_catalogue(admit,self.specification,L.CORE)
        self.by_id={tid:ROLES[name] for name,tid in self.types.items()}
        aliases={alias:tid for name,tid in self.types.items() for alias in (name,'Contracts/'+name)}
        for alias,tid in aliases.items():
            require(self.blue.language.aliases.get(alias,tid)==tid,'CORE_ALIAS_CONFLICT',alias=alias)
        self.blue.language.aliases.update(aliases)
        self.blue.refresh()
    def typed(self,type_name,**fields):return {'type':{'blueId':self.types[type_name]},**fields}
    @property
    def runtime_bindings(self):return tuple(self.extensions[k].binding.wire() for k in sorted(self.extensions))
    def install(self,binding,implementation):
        from .runtime import Runtime
        self.blue.certify(L.Ref(binding.type_id),'definition');self.blue.certify(L.Ref(binding.semantics_id))
        require(binding.type_id not in self.by_id,'STANDARD_RUNTIME_REBIND')
        parent={'external-channel':'Channel','processor-channel':'Channel','handler':'Handler','marker':'Marker','step':'Contract'}[binding.role]
        require(self.types[parent] in L.ancestry(binding.type_id,self.blue.context),'INVALID_RUNTIME_CATEGORY',category=parent)
        previous=self.extensions.get(binding.type_id)
        if previous is not None:
            require(previous.binding==binding and previous.implementation is implementation,'RUNTIME_BINDING_CONFLICT');return
        self.extensions[binding.type_id]=Runtime(binding,implementation)
    def binding(self,r):
        h=self.blue.head(r);tid=h.type_id
        if tid is None:return None
        try:
            for ancestor in L.ancestry(tid,self.blue.context):
                if ancestor in self.extensions:
                    extension=self.extensions[ancestor]
                    if tid==ancestor or extension.binding.inherits_to_subtypes:return extension
                if ancestor in self.by_id:return self.by_id[ancestor]
        except L.Failure as e:self.blue.translate(e)
        return None
    def role(self,r):
        binding=self.binding(r)
        return binding if isinstance(binding,str) or binding is None else binding.role
    def configured(self,r,key):
        """Authored syntax may be empty; catalogue declaration holes are absent.

        Stop at installed catalogue definitions. Custom inherited contributions
        still count, including type-only patterns and explicit empty objects.
        """
        recipe=r if isinstance(r,L.Recipe) else L.recipe(r)
        for part in recipe.parts:
            seen=set();node=part
            while node is not None:
                tid=self.blue.identity(node)
                if tid in seen or tid in self.by_id:break
                seen.add(tid);body=self.blue.open(node)
                if body.has(key):return True
                parent=body.get('type');node=parent if isinstance(parent,L.Ref) else None
        return False
    def declaration(self,r,*,demand=True):
        h=self.blue.head(r);binding=self.binding(r);role=self.role(r);require(role is not None,'UNSUPPORTED_CONTRACT_TYPE',type=h.type_id)
        out={'type':{'blueId':h.type_id},'_role':role,'_recipe':r}
        extension=None if isinstance(binding,str) else binding
        body_fields=set(extension.binding.body_fields) if extension else BODY_FIELDS.get(role,set())
        allowed=(set(extension.binding.header_fields)|body_fields) if extension else ALLOWED.get(role)
        if allowed is not None:require(set(h.fields)<=allowed|{'specification','order'},'UNKNOWN_RUNTIME_FIELD',role=role,fields=sorted(set(h.fields)-allowed-{'specification','order'}))
        for k in sorted(h.fields):
            if k=='specification' or k=='steps' and role in ('workflow','operation'):continue
            if not demand and k in body_fields:continue
            ch=L.child_recipe(h,k)
            if k=='definition':
                if self.configured(r,k):out[k]=ch
            elif k in LITERAL_FIELDS or k in body_fields:
                if self.configured(r,k):out[k]=self.blue.bex_data(ch)
            elif L.present_recipe(ch,self.blue.context):out[k]=self.blue.project(ch)
        n=self.blue.open(self.blue.exact(r))
        for label in ('name','description'):
            if n.has(label):out[label]=n.get(label)
        if 'order' in out:integer(out['order'],-(1<<31),(1<<31)-1)
        if extension:out['_extension']=extension
        if role=='embedding':
            for k in ('paths','collectionPaths'):
                xs=out.get(k,[]);require(type(xs) is list and all(type(p) is str for p in xs),'INVALID_EMBEDDED_PATHS');require(len(xs)==len(set(xs)),'DUPLICATE_EMBEDDED_PATH')
                for p in xs:require(segments(p) and all(segments(p)) and segments(p)[0]!='contracts','INVALID_EMBEDDED_PATH')
        if role in ('embedded_event','update'):
            field='sourcePath' if role=='embedded_event' else 'path'
            if field in out:segments(out[field])
        if role=='terminate_step' and demand:
            require(type(out.get('cause')) is str,'INVALID_TERMINATION_CAUSE')
            if 'reason' in out:require(type(out['reason']) is str,'INVALID_TERMINATION_REASON')
        if role in EXECUTABLE:
            token(out.get('channel'))
            if role!='extension_handler':
                require(self.configured(r,'steps'),'MISSING_STEPS')
                if demand:out['steps']=[self.declaration(s) for s in self.steps(out)]
        return out
    def steps(self,handler):
        r=handler['_recipe'];h=self.blue.head(r);sh=self.blue.head(L.child_recipe(h,'steps'))
        require(sh.items is not None,'INVALID_STEPS')
        return (L.child_recipe(sh,i) for i in range(len(sh.items)))
    def contracts(self,body):
        h=self.blue.head(body)
        if h.contracts is None:return {}
        ch=self.blue.head(h.contracts);require(ch.kind in ('object','none'),'INVALID_CONTRACT_MAP');result={}
        for k in sorted(ch.fields):
            token(k);r=L.child_recipe(ch,k);role=self.role(r)
            if k in MARKERS:require(role==MARKERS[k],'INVALID_PROCESSOR_STATE',key=k);continue
            require(role not in set(MARKERS.values()),'MISPLACED_PROCESSOR_STATE',key=k);d=self.declaration(r,demand=False);require(d['_role'] in EXTERNAL|INTERNAL|EXECUTABLE|{'embedding','generalization','extension_marker','compute_definition'},'INVALID_CONTRACT_ROLE',role=d['_role'])
            if d['_role']=='embedding':require(k=='embedded','EMBEDDING_KEY')
            if d['_role']=='generalization':require(k=='generalization','GENERALIZATION_KEY');self.policy(body)
            result[k]=d
        for k,d in result.items():
            if d['_role'] in EXECUTABLE:require(d['channel'] in result and result[d['channel']]['_role'] in EXTERNAL|INTERNAL,'INVALID_HANDLER_CHANNEL',handler=k)
        return result
    def policy(self,body):
        from .policy import GeneralizationPolicy,GeneralizationRule,GeneralizationError
        h=self.blue.head(body)
        if h.contracts is None:return GeneralizationPolicy(),None
        r=self.blue.child(h.contracts,'generalization')
        if r is None:return GeneralizationPolicy(),None
        require(self.role(r)=='generalization','INVALID_GENERALIZATION_POLICY')
        d=self.declaration(r);rules=[];rh=self.blue.head(r);sequence=self.blue.child(r,'rules')
        try:
            sh=self.blue.head(sequence) if sequence is not None else None
            if sh is not None:
                require(sh.items is not None or not self.configured(r,'rules'),'INVALID_GENERALIZATION_RULES')
            for i in range(len(sh.items or ()) if sh is not None else 0):
                item=L.child_recipe(sh,i);ih=self.blue.head(item)
                require(set(ih.fields)<={'specification','path','mode','mustRemainSubtypeOf'},'INVALID_GENERALIZATION_RULE')
                path=self.blue.child(item,'path');mode=self.blue.child(item,'mode');floor=self.blue.child(item,'mustRemainSubtypeOf')
                if floor is not None:
                    floor=self.blue.identity(self.blue.exact(floor));self.blue.certify(L.Ref(floor),'definition')
                rules.append(GeneralizationRule(self.blue.project(path),self.blue.project(mode),floor))
            policy=GeneralizationPolicy(tuple(rules),d.get('defaultMode','reject'))
        except GeneralizationError as exc:raise ContractError('INVALID_GENERALIZATION_POLICY',detail=str(exc)) from exc
        return policy,self.blue.identity(self.blue.exact(r))
    @staticmethod
    def ordered(cs):return sorted(cs.items(),key=lambda kv:(kv[1].get('order',0),kv[0],kv[1]['type']['blueId']))
    def marker(self,body,key):
        n=self.blue.open(body);cs=n.get('contracts')
        if cs is L.ABSENT:return None
        cs=self.blue.open(cs);value=cs.get(key)
        if value is L.ABSENT:return None
        require(self.role(value)==MARKERS[key],'INVALID_PROCESSOR_STATE',key=key);return value


# Build mandatory authoring content independently of caller operation limits.
# The cached data is immutable release content; executable roles still belong
# to the Processor's own Registry, never to a repository upload.
from functools import lru_cache

@lru_cache(maxsize=1)
def core_catalogue():
    from .language import Bridge
    blue=Bridge()
    Registry(blue)
    return dict(blue.language.aliases),blue.language.provider.snapshot()
