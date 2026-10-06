"""Bridge to pinned Language operations. No separate BlueId algorithm."""
from __future__ import annotations
from copy import deepcopy, copy
import weakref
from collections.abc import Mapping, Sequence
from blue_host import HostIncomplete, HOST_FAILURES, incomplete, host_boundary
from algorithms import blue as L
from blue_language import Language
from blue_bex.values import UNDEFINED,blue_value,HostValue,pointer_get,kind
from .model import ContractError,NeedResources,require,segments,LIMITS

def compact(raw):
    if isinstance(raw,list):return [compact(v) for v in raw]
    if not isinstance(raw,dict):return raw
    if set(raw)=={'type','value'} and raw['type'] in ({'blueId':L.CORE[n]} for n in ('Text','Integer','Double','Boolean')):
        if raw['type']=={'blueId':L.CORE['Integer']} and type(raw['value']) is str:return L.parse_integer(raw['value'])
        return raw['value']
    if set(raw) in ({'items'},{'items','type'}) and raw.get('type',{'blueId':L.CORE['List']})=={'blueId':L.CORE['List']}:
        return [compact(v) for v in raw['items']]
    return {k:compact(v) for k,v in raw.items()}


class ExactValue(HostValue):
    """Immutable effective value over one captured exact-resolution context.

    Reading a collection never projects its descendants. Exact serialization
    retains references; it is not a lossy dictionary standing in for the value.
    """
    __slots__ = ('_blue', '_recipe', '_logical', '_depth')

    def __init__(self, blue, recipe, logical, depth=0):
        object.__setattr__(self, '_blue', blue)
        object.__setattr__(self, '_recipe', recipe)
        object.__setattr__(self, '_logical', logical)
        object.__setattr__(self, '_depth', depth)

    def __setattr__(self, name, value):
        raise TypeError('Exact values are immutable')

    def __repr__(self): return '<ExactValue>'
    def comparison_key(self): return (id(self._blue.context),self._recipe.key())
    def blue_output(self):
        return self._blue.raw(self._blue.exact(self._recipe))
    def output_view(self):
        return wire_view(self._blue.exact(self._recipe))
    def accounting_view(self):
        # A complete captured node, not its effective/display projection. A
        # composed recipe may construct a new exact value and must establish it
        # under the invocation ledger before it can supply a transfer token.
        node = (self._logical.exact(self._recipe, self._blue) if self._logical
                else self._blue.exact(self._recipe))
        identity = self._blue.known_identity(node)
        if identity is None:
            if self._logical is None:
                return wire_view(node)  # No evidence: no cheap transfer claim.
            identity = self._logical.establish(node)
        return {'blueId': identity}

    def _head(self):
        if self._logical:
            for part in self._recipe.parts:self._logical.open(part)
        return self._blue.head(self._recipe)

    def _child(self, key):
        h = self._head()
        if self._logical:
            self._logical.meter.contracts('listItemRead' if h.items is not None else 'objectMemberRead')
        child = self._blue.child(self._recipe, key)
        return self._blue.view(child, logical=self._logical,depth=self._depth+1)


class ExactObject(ExactValue, Mapping):
    def value_kind(self): return 'object'
    def __iter__(self):
        h = self._head()
        for key in sorted(h.fields):
            if L.present_recipe(L.child_recipe(h, key), self._blue.context):yield key
        n = self._blue.open(self._blue.exact(self._recipe)) if self._recipe.parts else None
        for key in ('name', 'description'):
            if n is not None and n.has(key):yield key
        if h.contracts is not None:yield 'contracts'
        if h.type_id and h.type_id not in L.CORE_NAME:yield 'type'
    def __len__(self): return sum(1 for _ in self)
    def __getitem__(self, key):
        h = self._head()
        if key == 'type' and h.type_id and h.type_id not in L.CORE_NAME:return {'blueId': h.type_id}
        if key == 'contracts' and h.contracts is not None:
            return self._blue.view(self._blue.child(self._recipe,key), logical=self._logical,depth=self._depth+1)
        if key in ('name', 'description'):
            n = self._blue.open(self._blue.exact(self._recipe))
            if n.has(key):return n.get(key)
        if key not in h.fields:raise KeyError(key)
        result = self._child(key)
        if result is UNDEFINED:raise KeyError(key)
        return result


class ExactList(ExactValue, Sequence):
    def value_kind(self): return 'list'
    def __len__(self): return len(self._head().items)
    def __getitem__(self, index):
        if isinstance(index, slice):return [self[i] for i in range(*index.indices(len(self)))]
        if not 0 <= index < len(self):raise IndexError(index)
        return self._child(index)

class WireObject(HostValue, Mapping):
    """A finite exact output manifest; references stay one-field objects."""
    def __init__(self,node):self.node=node
    def value_kind(self):return 'object'
    def __len__(self):return 1 if isinstance(self.node,L.Ref) else len(self.node.fields)
    def __iter__(self):return iter(('blueId',) if isinstance(self.node,L.Ref) else self.node.keys())
    def __getitem__(self,key):
        if isinstance(self.node,L.Ref):
            if key!='blueId':raise KeyError(key)
            return self.node.id
        value=self.node.get(key)
        if value is L.ABSENT:raise KeyError(key)
        if key in L.LITERALS|{'mergePolicy'}:return value
        return WireList(value) if key=='items' else wire_view(value)
    def blue_output(self):return L.export_tree(self.node)


class WireList(HostValue, Sequence):
    def __init__(self,items):self.items=items
    def value_kind(self):return 'list'
    def __len__(self):return len(self.items)
    def __getitem__(self,index):return wire_view(self.items[index])
    def blue_output(self):return [L.export_tree(v) for v in self.items]


def wire_view(node):
    if isinstance(node,L.Node) and node.keys()==('items',):return WireList(node.get('items'))
    return WireObject(node)


class Bridge:
    def __init__(self,language=None):
        self.language=language if language is not None else Language(core_contracts=False);self.context=self.language.processing_context()
        self._identity_witnesses={}
    def note_identity(self,node,identity=None):
        # An invocation-local handle indexes evidence issued by admission,
        # verified opening or prepaid construction. Cache presence is not proof.
        if isinstance(node,L.Node):
            key=id(node);rows=self._identity_witnesses
            ref=weakref.ref(node,lambda dead:rows.pop(key,None) if rows.get(key,(None,))[0] is dead else None)
            rows[key]=(ref,identity)
        return node
    def known_identity(self,node):
        if isinstance(node,L.Ref):return node.id
        row=self._identity_witnesses.get(id(node))
        if row is None or row[0]() is not node:return None
        if row[1] is None:
            self.note_identity(node,L.identity(node));row=self._identity_witnesses[id(node)]
        return row[1]
    def has_identity_evidence(self,node):
        if isinstance(node,L.Ref):return True
        row=self._identity_witnesses.get(id(node))
        return row is not None and row[0]() is node

    def selected_child(self,parent,child):
        """Carry exact provenance through Language's effective-head recipes.

        Head caches may return different immutable handles for the same exact
        contributions. Selecting their existing child parts derives evidence
        from the witnessed parent and verified type resolution, not those
        handles. This neither composes the parts nor validates their context.
        Literal metadata and the items sequence slot never enter this path.
        """
        if child is not None and all(self.has_identity_evidence(n) for n in parent.parts):
            for part in child.parts:
                if isinstance(part,L.Node) and not self.has_identity_evidence(part):
                    self.note_identity(part)
        return child
    def witnessed_children(self,node):
        if not isinstance(node,L.Node):return
        for key,value in node.fields:
            if key in L.LITERALS|{'mergePolicy'}:continue
            for child in value if key=='items' else (value,):
                if isinstance(child,L.Node) and id(child) not in self._identity_witnesses:self.note_identity(child)

    def refresh(self):self.context=self.language.processing_context()
    def translate(self,error):
        if isinstance(error,HOST_FAILURES):raise incomplete(error) from error
        if isinstance(error,L.Failure):
            if error.category=='OperationLimitExceeded':raise HostIncomplete(error.detail) from error
            if error.category=='ProviderUnavailable':raise NeedResources(*self.context.demands) from error
            raise ContractError('LANGUAGE_'+error.category,detail=error.detail) from error
        raise error
    def raw(self,node):return L.export_tree(node)
    def text(self,node):return L.wire_text(self.raw(node))
    def normalize_input(self,value,*,aliases=True):
        if type(value) is int and abs(value)>L.SAFE:return {'type':{'blueId':L.CORE['Integer']},'value':L.integer_text(value)}
        if type(value) is list:return [self.normalize_input(v,aliases=aliases) for v in value]
        if type(value) is not dict:return value
        out={}
        for k,v in value.items():
            if k=='value':out[k]=L.integer_text(v) if type(v) is int and abs(v)>L.SAFE else v
            elif k in L.TYPES and type(v) is str:
                require(aliases,'UNRESOLVED_RUNTIME_TYPE',alias=v)
                tid=self.language.aliases.get(v,L.CORE.get(v));require(tid is not None,'UNKNOWN_ALIAS',alias=v)
                out[k]={'blueId':tid}
            else:out[k]=self.normalize_input(v,aliases=aliases)
        return out
    def source(self,value,*,goal='value'):
        try:
            d=self.language.create(L.wire_text(self.normalize_input(value)),goal=goal,mode='source')
            self.language.publish_document(d);self.refresh();body=self.open(L.Ref(d.blue_id))
            return L.Ref(d.blue_id,body) if '#' in d.blue_id else body
        except L.Failure as e:
            if e.category=='ProviderUnavailable':
                # Source admission uses its own Language operation context;
                # self.context may have no demands from that failed operation.
                try:missing=L.final_id(e.detail)
                except L.Failure:self.translate(e)
                raise NeedResources(missing) from e
            self.translate(e)
    def node(self,value,*,goal='value',certify=True,logical=None):
        if logical is not None:return logical.node(value,goal=goal,certify=certify)
        try:
            if isinstance(value,ExactValue):value=value._blue.exact(value._recipe)
            n=value if isinstance(value,(L.Node,L.Ref)) else L.normalize(self.normalize_input(blue_value(value),aliases=False),self.context,'exact')
            if certify:self.certify(n,goal)
            self.remember(n);return n
        except L.Failure as e:self.translate(e)
    def remember(self,node):
        try:
            self.context.remember(node)
            if not isinstance(node,L.Ref):
                tid=L.identity(node);self.context.bodies[tid]=node;self.language.provider.set_exact(tid,self.text(node));self.note_identity(node,tid)
        except L.Failure as e:self.translate(e)
    def retain(self,nodes):
        """Retain complete admitted dependencies before rebuilding a resolver.

        Content retention does not publish any process head or checkpoint.
        """
        try:
            records={}
            for node in nodes:records.update(L.admitted_records(node,self.context))
            self.language.provider.merge_responses(records)
        except L.Failure as e:self.translate(e)
    def open(self,node):
        try:
            result=L.open_exact(node,self.context)
            if isinstance(node,L.Ref):self.note_identity(result,node.id if '#' not in node.id else None)
            if self.known_identity(result) is not None:self.witnessed_children(result)
            return result
        except L.Failure as e:self.translate(e)
    def identity(self,node):
        try:return L.identity(node)
        except L.Failure as e:self.translate(e)
    def certify(self,node,goal='value'):
        try:L.strict_certify(node,self.context,goal)
        except L.Failure as e:self.translate(e)
    def head(self,r):
        try:return L.head(r if isinstance(r,L.Recipe) else L.recipe(r),self.context)
        except L.Failure as e:self.translate(e)
    def exact(self,r):
        if not isinstance(r,L.Recipe):return r
        try:return L.recipe_exact_value(r,self.context)
        except L.Failure as e:self.translate(e)
    def child(self,r,k):
        r=r if isinstance(r,L.Recipe) else L.recipe(r)
        h=self.head(r)
        if k=='contracts':return self.selected_child(r,h.contracts)
        if k in L.TYPES:
            tid=getattr(h,{'type':'type_id','itemType':'item_type','keyType':'key_type','valueType':'value_type'}[k])
            return L.recipe(L.Ref(tid)) if tid is not None else None
        if k in L.LITERALS:
            value=h.value if k=='value' else h.labels.get(k,L.ABSENT)
            if value is L.ABSENT:return None
            return L.recipe(L.normalize(self.normalize_input(value),self.context,'exact'))
        if k in ('schema','mergePolicy'):
            node=self.open(self.exact(r));value=node.get(k)
            if value is L.ABSENT:return None
            return L.recipe(L.scalar('Text',value) if k=='mergePolicy' else value)
        if h.items is not None:
            if k=='-':return None
            if isinstance(k,str):
                require(k=='0' or k.isascii() and k.isdigit() and not k.startswith('0'),'INVALID_LIST_INDEX');k=int(k)
            return self.selected_child(r,L.child_recipe(h,k)) if 0<=k<len(h.items) else None
        return self.selected_child(r,L.child_recipe(h,k)) if k in h.fields else None
    def select(self,node,path):
        r=L.recipe(node)
        for k in segments(path):
            r=self.child(r,k)
            if r is None:return None
        return r
    def project(self,r,*,definitions=False,seen=frozenset(),depth=0,preserve_cyclic=False):
        if r is None:return UNDEFINED
        r=r if isinstance(r,L.Recipe) else L.recipe(r)
        if preserve_cyclic:
            exact=self.exact(r)
            if isinstance(exact,L.Ref) and '#' in exact.id:return {'blueId':exact.id}
        h=self.head(r)
        if h.value is not L.ABSENT:return h.value
        key=r.key()
        if key in seen:return {'blueId':self.identity(self.exact(r))}
        seen=seen|{key}
        if h.items is not None:return [self.project(L.child_recipe(h,i),definitions=definitions,seen=seen,depth=depth+1,preserve_cyclic=preserve_cyclic) for i in range(len(h.items))]
        out={}
        for k in sorted(h.fields):
            ch=L.child_recipe(h,k)
            if definitions or L.present_recipe(ch,self.context):out[k]=self.project(ch,definitions=definitions,seen=seen,depth=depth+1,preserve_cyclic=preserve_cyclic)
        n=self.open(self.exact(r)) if r.parts else None
        for k in ('name','description'):
            if n is not None and n.has(k):out[k]=n.get(k)
        if h.contracts is not None:out['contracts']=self.literal(h.contracts)
        if h.type_id and h.type_id not in L.CORE_NAME:out['type']={'blueId':h.type_id}
        if not definitions and not out and not L.concrete(h,self.context):return UNDEFINED
        return out
    def view(self, r, *, logical=None, depth=0):
        if r is None:return UNDEFINED
        r = r if isinstance(r, L.Recipe) else L.recipe(r)
        captured = copy(self)  # Capture resolver/context, not a future refresh.
        if logical:
            for part in r.parts:logical.open(part)
        h = captured.head(r)
        if h.value is not L.ABSENT:return h.value
        if h.items is not None:return ExactList(captured, r, logical,depth)
        if not (h.contracts is not None or h.type_id and h.type_id not in L.CORE_NAME or
                h.labels.get('name') is not None or h.labels.get('description') is not None or
                L.concrete(h, captured.context)):return UNDEFINED
        return ExactObject(captured, r, logical,depth)
    def literal(self,r):return compact(self.raw(self.open(self.exact(r))))
    def bex_data(self,r,*,seen=frozenset(),depth=0):
        n=self.exact(r)
        if isinstance(n,L.Ref):
            if '#' in n.id or n.id in seen:return {'blueId':n.id}
            seen=seen|{n.id}
        n=self.open(n);out={}
        for k,v in n.fields:
            if k in L.LITERALS or k=='mergePolicy':out[k]=v
            elif k in L.TYPES:out[k]=self.raw(v)
            elif k=='items':out[k]=[self.bex_data(x,seen=seen,depth=depth+1) for x in v]
            else:out[k]=self.bex_data(v,seen=seen,depth=depth+1)
        return compact(out)
    def read(self,node,path,view='canonical'):
        require(view in ('canonical','resolved'),'INVALID_VIEW');r=self.select(node,path)
        return self.project(r) if r is not None else UNDEFINED
    def read_bex(self,value,path):
        if isinstance(value, HostValue):return pointer_get(value,path)
        at=value
        for k in segments('' if path=='/' else path):
            if isinstance(at,dict) and set(at)=={'blueId'}:at=self.view(L.Ref(at['blueId']))
            if kind(at)=='object':at=at.get(k,UNDEFINED)
            elif kind(at)=='list':
                if not k.isdigit() or k!='0' and k.startswith('0'):return UNDEFINED
                i=int(k);at=at[i] if i<len(at) else UNDEFINED
            else:return UNDEFINED
        return deepcopy(at)
    def matches(self,value,pattern,*,logical=None):
        """Actual-field matching; Language validates types and constraints.

        The presence pass prevents refine_exact from supplying the event with
        fields contributed only by the filter. Invalid evidence is an error,
        not an ordinary false match. No Language operation is modified.
        """
        n=self.node(self.exact(value),logical=logical);p=self.node(self.exact(pattern),goal='definition',logical=logical)
        def present(actual, wanted, seen=frozenset(), depth=0):
            pair=(actual.key(),wanted.key())
            if pair in seen:return True
            seen=seen|{pair}; ah=self.head(actual); ph=self.head(wanted)
            if ph.type_id is not None:
                if ah.type_id is None:return False
                if ph.type_id not in L.ancestry(ah.type_id,self.context):return False
            authored=self.open(self.exact(wanted))
            if ph.items is not None:
                if ah.items is None or len(ah.items)<len(ph.items):return False
                for i in range(len(ph.items)):
                    if not present(L.child_recipe(ah,i),L.child_recipe(ph,i),seen,depth+1):return False
            for key in sorted(ph.fields):
                expected=L.child_recipe(ph,key)
                # Catalogue type-only optional declarations are not explicitly
                # supplied filter fields. Concrete inherited values do count.
                if not authored.has(key) and not L.present_recipe(expected,self.context):continue
                actual_child=self.child(actual,key)
                if actual_child is None or not L.present_recipe(actual_child,self.context):return False
                if not present(actual_child,expected,seen,depth+1):return False
            return True
        if not present(L.recipe(n),L.recipe(p)):return False
        try:
            L.refine_exact(p,n,self.context)
            return True
        except L.Failure as e:
            if e.category in ('TypeCompatibilityViolation','SchemaViolation','FixedValueConflict',
                              'CollectionCompatibilityViolation','InvalidCollectionType','IncompatibleTypes'):
                return False
            self.translate(e)
    def set_at(self,root,path,val=None,*,op='replace'):
        parts=segments(path);require(parts and all(parts),'INVALID_PATCH_PATH',path=path)
        return self._set(root,L.recipe(root),parts,val,op)
    def _set(self,n,r,parts,val,op):
        n=self.open(n);h=self.head(r);key=parts[0];require(isinstance(n,L.Node),'INVALID_PATCH_PARENT');m=dict(n.fields)
        if h.items is not None:
            require(key=='-' and op=='add' and len(parts)==1 or key=='0' or key.isascii() and key.isdigit() and not key.startswith('0'),'INVALID_LIST_INDEX')
            values=[self.exact(L.child_recipe(h,i)) for i in range(len(h.items))];i=len(values) if key=='-' else int(key)
            require(i<=len(values) if op=='add' and len(parts)==1 else i<len(values),'INVALID_LIST_INDEX')
            if len(parts)>1:values[i]=self._set(values[i],L.child_recipe(h,i),parts[1:],val,op)
            elif op=='remove':values.pop(i)
            elif op=='add':values.insert(i,val)
            else:values[i]=val
            m['items']=tuple(values)
        elif key in L.LITERALS:
            require(len(parts)==1,'INVALID_PATCH_PATH')
            if op=='remove':require(key in m,'MISSING_PATCH_TARGET');m.pop(key)
            else:
                v=self.head(val).value;require(v is not L.ABSENT,'INVALID_LITERAL');m[key]=v
        else:
            child=self.child(r,key)
            if len(parts)>1:
                require(child is not None,'MISSING_PATCH_PARENT');m[key]=self._set(self.exact(child),child,parts[1:],val,op)
            elif op=='remove':require(key in m,'MISSING_PATCH_TARGET');m.pop(key)
            else:
                if key in L.TYPES:
                    self.remember(val);m[key]=L.Ref(self.identity(val))
                else:m[key]=val
        try:return L.node(m)
        except L.Failure as e:self.translate(e)
    def substitute(self,root,replacements):
        """Set disjoint symbolic edges together; never hash a partial Local graph."""
        rows=[(segments(path),value) for path,value in replacements]
        def visit(n,r,rows):
            n=self.open(n);h=self.head(r);m=dict(n.fields);grouped={}
            for path,value in rows:
                require(path,'INVALID_SYMBOLIC_PATH');grouped.setdefault(path[0],[]).append((path[1:],value))
            if h.items is not None:
                values=[self.exact(L.child_recipe(h,i)) for i in range(len(h.items))]
                for key,items in sorted(grouped.items()):
                    require(key.isdigit() and (key=='0' or not key.startswith('0')),'INVALID_LIST_INDEX');i=int(key);require(i<len(values),'INVALID_LIST_INDEX')
                    if not items[0][0]:require(len(items)==1,'OVERLAPPING_SYMBOLIC_PATH');values[i]=items[0][1]
                    else:values[i]=visit(values[i],L.child_recipe(h,i),items)
                m['items']=tuple(values)
            else:
                for key,items in sorted(grouped.items()):
                    if not items[0][0]:require(len(items)==1,'OVERLAPPING_SYMBOLIC_PATH');m[key]=items[0][1]
                    else:
                        ch=self.child(r,key);require(ch is not None,'MISSING_SYMBOLIC_PATH');m[key]=visit(self.exact(ch),ch,items)
            return L.node(m)
        return visit(root,L.recipe(root),rows) if rows else root
    def finalize_component(self,keys,bodies,edges):
        position={k:i for i,k in enumerate(keys)};raw=[]
        for k in keys:
            replacements=[(e.path,L.Local(position[e.target])) for e in sorted(edges,key=lambda e:(e.source,e.path)) if e.source==k and e.target in position]
            raw.append(self.raw(self.substitute(bodies[k],replacements)))
        try:
            result=L.finalize_set(raw,self.context);proof={'members':[self.raw(n) for n in result['canonical']]};out={}
            for i,k in enumerate(keys):
                tid=result['ids'][i];n=result['bodies'][int(tid.split('#')[1])];response={'proof':L.wire_text(proof),'body':self.text(n)}
                self.language.provider.set_response(tid,response);self.context.provider[tid]=response;self.context.bodies[tid]=n;self.context.proofs[tid]=proof;out[k]=(tid,n)
            return out
        except L.Failure as e:self.translate(e)
