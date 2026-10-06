"""Run-local logical work, independent of physical resolver/cache warmth."""
from algorithms import blue as L

EMPTY_LIST_ID=L.H({'$list':'empty'})


def canonical_size(value):
    """Exact canonical UTF-8 size, without allocating serialized Text."""
    def quoted(text):
        size=2
        for char in text:
            n=ord(char)
            size += (2 if char in '\"\\\b\f\n\r\t' else 6 if n<32 else
                     1 if n<128 else 2 if n<2048 else 3 if n<65536 else 4)
        return size
    pending=[value];size=0
    while pending:
        current=pending.pop()
        if isinstance(current,dict):
            size+=2+max(0,len(current)-1)+len(current)
            for key,item in current.items():size+=quoted(key);pending.append(item)
        elif isinstance(current,(tuple,list)):
            size+=2+max(0,len(current)-1);pending.extend(current)
        elif isinstance(current,str):size+=quoted(current)
        else:size+=len(L.canonical_text(current))
    return size


class LogicalWork:
    def __init__(self,blue,meter):
        self.blue=blue;self.meter=meter;self.manifests=set();self.established=set();self.proofs=set()
        self.carried_roots=set()
        self.bound_identities=set()
        self.exact_values={}
        self.partition=None

    def exact(self,recipe,blue):
        """Captured exact content; prepay synthesis of multi-part recipes.

        Single contributions already have admission/opening evidence. Contextual
        requirements are not part of their exact identity. Refining several
        contributions creates content, even if a physical resolver is warm.
        """
        if len(recipe.parts)==1:return recipe.parts[0]
        from copy import copy
        key=recipe.key()
        if key not in self.exact_values:
            context=copy(blue.context)
            def remember(node):
                identity=self.establish(node)
                if isinstance(node,L.Node):
                    context.bodies[identity]=node
                    blue.note_identity(node,identity)
                return node
            context.remember=remember
            try:node=L.recipe_exact_value(recipe,context)
            except L.Failure as error:blue.translate(error)
            # Carry the prepaid identity explicitly. Native continuation copies
            # can change handles; a physical cache must not decide whether this
            # construction evidence survives transport.
            self.exact_values[key]=(node,blue.known_identity(node))
        node,identity=self.exact_values[key]
        if isinstance(node,L.Node):blue.note_identity(node,identity)
        return node

    def open(self,node):
        identity=self.blue.identity(node)
        if identity not in self.manifests:
            self.meter.contracts('nodeManifestOpened');self.manifests.add(identity)
        return self.blue.open(node)

    def compare(self,left,right):
        self.meter.contracts('scalarComparison')
        if type(left) is str and type(right) is str:
            for offset in range(0,min(len(left),len(right)),64):
                self.meter.contracts('textBlockExamined')
                self.meter.contracts('textBlockExamined')
                a,b=left[offset:offset+64],right[offset:offset+64]
                if a!=b:return (a>b)-(a<b)
            return (len(left)>len(right))-(len(left)<len(right))
        elif type(left) is int and type(right) is int:
            self.meter.contracts('integerLimbOperation',max(1,(abs(left).bit_length()+31)//32)+max(1,(abs(right).bit_length()+31)//32))
        return (left>right)-(left<right)

    def ordered(self,contracts):
        """The prescribed stable bottom-up merge schedule, from key order."""
        rows=sorted(contracts.items());width=1
        def compare(a,b):
            self.meter.contracts('sortComparison')
            for left,right in zip((a[1].get('order',0),a[0],a[1]['type']['blueId']),
                                  (b[1].get('order',0),b[0],b[1]['type']['blueId'])):
                result=self.compare(left,right)
                if result:return result
            return 0
        while width<len(rows):
            output=[]
            for start in range(0,len(rows),2*width):
                left=rows[start:start+width];right=rows[start+width:start+2*width];i=j=0
                while i<len(left) and j<len(right):
                    if compare(left[i],right[j])<=0:output.append(left[i]);i+=1
                    else:output.append(right[j]);j+=1
                output.extend(left[i:]);output.extend(right[j:])
            rows=output;width*=2
        return rows

    def headers(self,body,contracts):
        """Inspect immutable ancestor contributions without compiling bodies."""
        seen=set();node=body
        while node is not None:
            identity=self.blue.identity(node)
            if identity in seen:break
            seen.add(identity);manifest=self.open(node)
            if manifest.has('contracts'):
                contribution=self.open(manifest.get('contracts'))
                self.meter.contracts('objectMemberRead',len(contribution.fields))
            parent=manifest.get('type')
            if parent is L.ABSENT:break
            self.meter.contracts('typeEdgeFollowed');node=parent

    def read(self,node,path):
        from .model import segments,require,LIMITS
        r=L.recipe(node)
        depth=0
        for name in segments(path):
            depth+=1
            for part in r.parts:self.open(part)
            head=self.blue.head(r)
            self.meter.contracts('listItemRead' if head.items is not None else 'objectMemberRead')
            r=self.blue.child(r,name)
            if r is None:break
        return self.blue.view(r,logical=self,depth=depth)

    def establish(self,node,previous=None,*,token=None,scope=None):
        # Input witnesses come from admission/opening, never a resolver cache.
        # Unknown candidates are visited postorder before any identity lookup.
        if isinstance(node,L.Local):return token(node.index)
        if isinstance(node,L.Ref):
            if '#' in node.id:return node.id
            node=self.blue.open(node)
        self._identity_input(node)
        identity,_=self._establish(node,previous,token=token,scope=scope,prerequisite=True)
        return identity

    def _identity_input(self,node):
        self.meter.contracts('identityInputMember',len(node.fields))
        for key,value in node.fields:
            self.meter.contracts('identityInputTextBlock',(len(key)+63)//64)
            if isinstance(value,str):self.meter.contracts('identityInputTextBlock',(len(value)+63)//64)
            elif key=='items':self.meter.contracts('identityInputMember',len(value))
            elif type(value) is int:
                limbs=max(1,(abs(value).bit_length()+31)//32)
                self.meter.contracts('integerLimbOperation',limbs*limbs)

    def _establish(self,node,previous=None,*,token=None,scope=None,prerequisite=False):
        if isinstance(node,L.Local):return token(node.index),True
        if isinstance(previous,L.Node) and self.blue.known_identity(previous) is None:self.blue.note_identity(previous)
        known=self.blue.known_identity(node)
        prior_id=self.blue.identity(previous) if previous is not None else None
        if known is not None:
            if (('ordinary',known) in self.established or known==prior_id or
                known in self.carried_roots or known in self.bound_identities or known in L.CORE_NAME or '#' in known):
                return known,False
        # Opening an admitted inline manifest must propagate the same child
        # witnesses as opening its Ref. Otherwise prior host reads affect reuse.
        node=self.blue.open(node)
        if not prerequisite:self._identity_input(node)
        old=self.blue.open(previous) if previous is not None else None
        pure_list=node.keys()==('items',);parts=[];local=False
        for key,value in node.fields:
            prior=old.get(key) if old is not None else L.ABSENT
            if key in L.LITERALS:
                if type(value) is str and value!=prior:self.meter.contracts('textBlockConstructed',(len(value)+63)//64)
                parts.append((key,True,value))
                continue
            if key=='mergePolicy':
                child,cyclic=self._establish(L.scalar('Text',value),None if prior is L.ABSENT else L.scalar('Text',prior),token=token,scope=scope)
            elif key=='items':
                if not pure_list:
                    child,cyclic=self._establish(L.list_node(value),L.list_node(prior) if isinstance(prior,tuple) else None,token=token,scope=scope)
                else:
                    old_items=prior if isinstance(prior,tuple) else ()
                    cyclic=False;prefix=True
                    # The empty fold is fixed, not a candidate-derived hash.
                    child=EMPTY_LIST_ID
                    for i,item in enumerate(value):
                        before=old_items[i] if i<len(old_items) else None
                        item_id,item_local=self._establish(item,before,token=token,scope=scope)
                        cyclic|=item_local
                        same=before is not None and item_id==L.identity(before,token)
                        prefix=prefix and same
                        if not prefix:self.meter.contracts('listFoldStepRecomputed')
                        child=L.append_id(child,item_id)
            else:child,cyclic=self._establish(value,None if prior is L.ABSENT else prior,token=token,scope=scope)
            local|=cyclic;parts.append((key,False,child))
        self.meter.contracts('nodeIdentityEstablished')
        if pure_list:identity=parts[0][2]
        else:
            self.meter.contracts('objectMemberRebuilt',len(node.fields))
            helper={key:value if literal else {'blueId':value} for key,literal,value in parts}
            size=canonical_size(helper)
            self.meter.contracts('directIdentityHashBlock',(size+9+63)//64)
            identity=L.H(helper)
        ledger_key=('cyclic',scope,identity) if local else ('ordinary',identity)
        self.established.add(ledger_key)
        # Issue evidence only after the complete successful charge/hash prefix.
        # Cyclic token-context hashes are not ordinary exact identity witnesses.
        if not local:self.blue.note_identity(node,identity)
        return identity,local

    def node_blue_id(self,value,meter):
        from .language import ExactValue
        from .model import require
        from blue_bex.values import blue_value
        require(meter is self.meter,'IDENTITY_METER_MISMATCH')
        if isinstance(value,ExactValue):
            node=self.exact(value._recipe,value._blue)
            known=value._blue.known_identity(node)
            if known is not None:return known
            return self.establish(node)
        # Validate output semantics before normalization (null is not an empty
        # node, and source directives/aliases are not runtime identity inputs).
        # Finite output validation is metered before allocating its projection.
        from blue_bex.values import size_parts
        for _ in size_parts(value,lambda counter,units=1:self.meter.charge(counter,units)):pass
        def prepare(item):
            # Exact children carry admission/identity evidence just like an
            # exact root. Do not flatten them into storage-shaped dictionaries.
            if isinstance(item,ExactValue):return item
            from blue_bex.values import UNDEFINED
            if type(item) is dict:
                return {key:prepare(part) for key,part in item.items() if part is not UNDEFINED}
            if type(item) is list:return [prepare(part) for part in item]
            return blue_value(item)
        node=self.node(prepare(value))
        return self.blue.identity(node)

    def node(self,value,*,goal='value',certify=True):
        """Normalize runtime output with guards before copying/encoding/hashing.

        Exact references remain references. Newly built children are normalized
        bottom-up; Language's remember hook cannot run ahead of establishment.
        """
        from copy import copy
        from blue_bex.values import HostValue,kind,UNDEFINED
        from .language import ExactValue
        context=copy(self.blue.context)
        def remember(node):
            identity=self.establish(node)
            if isinstance(node,L.Node):
                context.bodies[identity]=node
                # Constructed evidence is now explicit, after the successful
                # charge prefix. Every raw occurrence still pays normalization.
                self.blue.note_identity(node,identity)
            return node
        context.remember=remember
        def literal(value):
            if type(value) is str:self.meter.contracts('identityInputTextBlock',(len(value)+63)//64)
            elif type(value) is int:
                limbs=max(1,(abs(value).bit_length()+31)//32)
                self.meter.contracts('integerLimbOperation',limbs*limbs)
            return value
        def build(value):
            self.meter.contracts('identityInputMember')
            if isinstance(value,ExactValue):value=self.exact(value._recipe,value._blue)
            if isinstance(value,(L.Node,L.Ref)):
                self.establish(value);return value
            if isinstance(value,HostValue):value=value.output_view()
            if kind(value)=='object':
                count=len(value);self.meter.contracts('identityInputMember',count)
                keys=list(value)
                rounds=(count-1).bit_length() if count else 0
                self.meter.contracts('identityInputMember',count*rounds)
                self.meter.contracts('identityInputTextBlock',sum((len(key)+63)//64 for key in keys)*(rounds+1))
                # Language's UTF-16 canonical order; keys have been prepaid.
                keys=L.ordered(keys)
                raw={}
                for key in keys:
                    part=value[key]
                    if part is UNDEFINED:continue
                    if key in L.LITERALS|{'mergePolicy','blueId'}:
                        raw[key]=literal(part)
                        if key=='value':raw[key]=self.blue.normalize_input({'value':raw[key]},aliases=False)['value']
                    elif key=='items':
                        self.meter.contracts('identityInputMember',len(part))
                        raw[key]=[build(item) for item in part]
                    else:raw[key]=None if part is None else build(part)
                # Preserve runtime rejection of string aliases in type slots.
                for key in L.TYPES & set(raw):
                    if type(value[key]) is str:
                        from .model import require
                        require(False,'UNRESOLVED_RUNTIME_TYPE',alias=value[key])
            elif kind(value)=='list':
                self.meter.contracts('identityInputMember',len(value))
                raw={'items':[build(item) for item in value]}
            else:raw=self.blue.normalize_input(literal(value),aliases=False)
            return L.normalize(raw,context,'exact')
        try:
            node=build(value)
            if certify:
                if goal=='value':self.validate(node)
                else:self.blue.certify(node,goal)
            self.blue.remember(node)
            return node
        except L.Failure as error:self.blue.translate(error)

    def validate(self,node,previous=None):
        """Account changed contextual obligations, then use Language validation.

        Unchanged children under identical requirements retain their admitted
        context. Header changes conservatively revisit descendant obligations.
        """
        pending=set()
        def visit(recipe,old=None,seen=frozenset()):
            if recipe.key() in seen:return
            # Carrying an already admitted invocation subject into an
            # unrestricted reference slot introduces no new obligation. This
            # inventory is derived from bound inputs, never resolver warmth.
            if not recipe.requirements and len(recipe.parts)==1 and self.blue.identity(recipe.parts[0]) in self.carried_roots:return
            h=self.blue.head(recipe);key=(recipe.key(),'value')
            if key in self.proofs or key in pending:self.meter.contracts('validationProofReused');return
            if old is not None and recipe.key()==old.key():return
            seen=seen|{recipe.key()};prior=self.blue.head(old) if old is not None else None
            for part in recipe.parts:self.open(part)
            constraints=h.constraints
            for _ in L.describe_constraints(constraints):self.meter.contracts('schemaPredicateEvaluated')
            if h.value is not L.ABSENT:
                value=h.value
                if type(value) in (int,float):
                    for bound in (constraints.lower,constraints.upper):
                        if bound is not None:self.compare(value,int(bound.value) if bound.value.denominator==1 else float(bound.value))
                    if constraints.multiple is not None:
                        self.meter.contracts('scalarComparison')
                        if type(value) is int:
                            limbs=max(1,(abs(value).bit_length()+31)//32)*max(1,(abs(constraints.multiple.numerator).bit_length()+31)//32)
                            self.meter.contracts('integerLimbOperation',limbs)
                elif type(value) is str and constraints.counts:
                    self.meter.contracts('textBlockExamined',(len(value)+63)//64)
                    for count in constraints.counts.values():self.compare(len(value),count)
                if constraints.enum is not None:
                    for group in constraints.enum:
                        for alternative in group:
                            self.meter.contracts('validationMemberExamined')
                            _,core,other=constraints.enum_values[alternative]
                            if type(other) is type(value) and self.compare(value,other)==0:break
            for field in sorted(h.fields):
                child=L.child_recipe(h,field);before=L.child_recipe(prior,field) if prior and field in prior.fields else None
                if before is not None and child.key()==before.key():continue
                self.meter.contracts('objectMemberRead')
                if h.value_type or h.key_type:self.meter.contracts('validationMemberExamined')
                visit(child,before,seen)
            if h.items is not None:
                for count in constraints.counts.values():self.compare(len(h.items),count)
                for i in range(len(h.items)):
                    child=L.child_recipe(h,i);before=L.child_recipe(prior,i) if prior and prior.items is not None and i<len(prior.items) else None
                    if before is not None and child.key()==before.key() and not h.constraints.unique:continue
                    self.meter.contracts('listItemRead')
                    if h.item_type or h.constraints.unique:self.meter.contracts('validationMemberExamined')
                    visit(child,before,seen)
            if h.contracts is not None:
                previous_contracts=prior.contracts if prior else None
                if previous_contracts is None or h.contracts.key()!=previous_contracts.key():visit(h.contracts,previous_contracts,seen)
            pending.add(key)
        visit(L.recipe(node),L.recipe(previous) if previous is not None else None)
        self.blue.certify(node)
        self.proofs.update(pending)
