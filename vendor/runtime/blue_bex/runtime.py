"""Executable BEX reference candidate. Effects are data until Contracts applies them."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable
from .values import (UNDEFINED, BexError, BoundaryError, ResourceError, ExecutionRejected, clone, kind,
    truthy, number, integer, text, required_text, equal, estimated_size,
    segments, escape, pointer_get, pointer_overlay, blue_value)
from .compiler import Compiler, Program, operator, STATIC, UNARY, ARRAY, QUERY
from .gas import Gas
from blue_host import host_boundary
from .values import HostValue, size_parts, ordered_keys
from decimal import Decimal

@dataclass
class Context:
    document: Any = field(default_factory=dict)
    event: Any = field(default_factory=dict)
    current_contract: Any = field(default_factory=dict)
    steps: dict = field(default_factory=dict)
    bindings: dict = field(default_factory=dict)
    scope: str = '/'
    resolved_document: Any = UNDEFINED
    read_document: Callable[[str,str,Any],Any] | None = None
    matcher: Callable[[Any,Any],bool] | None = None
    intrinsics: dict = field(default_factory=dict)
    node_blue_id: Callable[[Any, Any], str] | None = None

@dataclass(frozen=True)
class Result:
    value: Any
    changeset: list
    events: list
    gas_used: int
    gas_trace: tuple

    def blue_output(self):
        return blue_value(self.value)

class _Return(Exception):
    def __init__(self,value): self.value=value

class Engine:
    def __init__(self, *, intrinsics=None):
        self.intrinsics=dict(intrinsics or {})

    @host_boundary
    def compile(self,source,*,definition=None,entry=None):
        return Compiler(intrinsic_ids=self.intrinsics).compile(source,definition=definition,entry=entry)

    @host_boundary
    def execute(self,program,context=None,*,gas=None,gas_limit=100000,definition=None,entry=None):
        if isinstance(program,Program):
            # Program is a transport value, not an unforgeable admission ticket.
            program=self.compile(program.source,entry=program.selected_entry)
        else:program=self.compile(program,definition=definition,entry=entry)
        run=Invocation(program, context or Context(), gas if gas is not None else Gas(gas_limit),self.intrinsics)
        return run.execute()

class Invocation:
    def __init__(self,program,context,gas,intrinsics):
        self.program=clone(program.source);self.entry=program.selected_entry
        self.context=context;self.gas=gas;self.intrinsics=dict(intrinsics)
        self.constants=self.program.get('constants',{});self.functions=self.program.get('functions',{})
        self.changes=[];self.events=[];self.frames=[{}]
        self.start_gas=gas.used;self.start_trace=len(gas.trace)

    def copy(self,value):
        # Values are immutable during evaluation: operators construct new
        # collections and frame updates replace slots, never mutate a value.
        return value

    @staticmethod
    def limbs(n):return max(1,(abs(n).bit_length()+31)//32)

    def to_integer(self,value):
        if type(value) is int:return value
        if type(value) is str:
            self.gas.charge('textWork',(len(value)+63)//64)
            digits=len(value.lstrip('-'))
        else:
            n=number(value);digits=max(len(n.as_tuple().digits),n.adjusted()+1)
        self.gas.charge('integerWork',max(1,(4*digits+31)//32)**2)
        return integer(value)

    def to_text(self,value):
        if type(value) is int:self.gas.charge('integerWork',self.limbs(value)**2)
        return text(value)

    def sized(self,counter,value,extra=0):
        self.gas.charge(counter,amount=self.gas.schedule[counter]+extra)
        for quantity in size_parts(value,self.gas.charge):
            self.gas.charge(counter,amount=quantity)

    @property
    def frame(self):return self.frames[-1]

    def default(self):
        self.gas.charge('valueMember',len(self.changes)+len(self.events))
        return dict(changeset=list(self.changes),events=list(self.events))

    def execute(self):
        self.gas.charge('functionCall')
        if self.entry is not None:value=self.function(self.entry,{},charge=False)
        else:value=self.body(self.program)
        return Result(clone(value),clone(self.changes),clone(self.events),self.gas.used-self.start_gas,
                      tuple(clone(self.gas.trace[self.start_trace:])))

    def body(self,b):
        try:
            if 'expr' in b:return self.expr(b['expr'])
            self.block(b.get('do',[]));return self.default()
        except _Return as r:return r.value

    def function(self,n,args,*,charge=True):
        if charge:self.gas.charge('functionCall')
        body=self.functions[n]
        for key in sorted(body.get('args',{})):
            if not self.matches(args[key],body['args'][key]):raise BexError('function argument pattern rejected: '+key)
        self.frames.append(dict(args))
        try:return self.body(body)
        finally:self.frames.pop()

    def matches(self,node,pattern):
        if node is UNDEFINED:return False
        try:converted=node if isinstance(node,HostValue) else blue_value(node)
        except BoundaryError:return False
        if self.context.matcher is None:raise BexError('Language matching capability unavailable')
        return bool(self.context.matcher(converted,self.copy(pattern)))

    def textarg(self,v):
        return required_text(v if type(v) is str else self.expr(v))

    def path(self,p):
        p=self.textarg(p)
        if p in ('','/'):return self.context.scope
        if p.startswith('/'):segments(p);return p
        base=self.context.scope.rstrip('/')
        result=base+'/'+p;segments(result);return result

    def read(self,op,b):
        if op in {'$var','$const','$binding','$steps'}:
            if op!='$const':self.gas.charge('stepsRead' if op=='$steps' else 'varRead')
            if type(b) is str:
                key,p=b,''
                if op=='$binding' and '/' in b:key,suffix=b.split('/',1);p='/'+suffix
                if op=='$steps' and '.' in b:key,suffix=b.split('.',1);p='/'+suffix.replace('.','/')
            else:
                key=b.get('step' if op=='$steps' else 'name',UNDEFINED)
                key=self.textarg(key);p=self.textarg(b.get('path',''))
            source=self.frame if op=='$var' else self.constants if op=='$const' else self.context.bindings if op=='$binding' else self.context.steps
            return self.copy(pointer_get(source.get(key,UNDEFINED),p))
        if op in {'$event','$currentContract'}:
            self.gas.charge('eventRead' if op=='$event' else 'currentContractRead')
            p=b.get('path','') if type(b) is dict and operator(b) is None else b
            p=self.textarg(p)
            return self.copy(pointer_get(self.context.event if op=='$event' else self.context.current_contract,p))
        self.gas.charge('documentRead' if op=='$document' else 'resultValueRead')
        if type(b) is dict and operator(b) is None:
            p=self.path(b.get('path',''));view=self.textarg(b.get('view','canonical'))
        else:p=self.path(b);view='canonical'
        doc=self.context.resolved_document if view=='resolved' else self.context.document
        if doc is UNDEFINED:raise BexError('resolved document capability unavailable')
        if op=='$resultValue':
            for patch in self.changes:doc=pointer_overlay(doc,patch['path'],patch.get('val',UNDEFINED),remove=patch['op']=='remove',charge=self.gas.charge)
        result=(self.context.read_document(p,view,doc) if self.context.read_document else pointer_get(doc,p))
        return self.copy(result)

    def expr(self,v):
        self.gas.charge('expressionBase')
        op=operator(v)
        if op is None:
            if type(v) is dict:
                out={}
                for k in sorted(v):
                    x=self.copy(v[k]) if k in STATIC else self.expr(v[k])
                    if x is not UNDEFINED:out[k]=x
                return out
            if type(v) is list:return [self.expr(x) for x in v]
            kind(v);return self.copy(v)
        b=v[op]
        if op=='$literal':return self.copy(b)
        if op=='$null':return None
        if op=='$emptyObject':return {}
        if op=='$emptyList':return []
        if op=='$changeset':
            self.gas.charge('valueMember',len(self.changes));return list(self.changes)
        if op=='$events':
            self.gas.charge('valueMember',len(self.events));return list(self.events)
        if op in {'$document','$event','$currentContract','$resultValue','$binding','$steps','$var','$const'}:return self.read(op,b)
        if op in UNARY:
            x=self.expr(b)
            if op=='$nodeBlueId':
                self.gas.charge('nodeIdentityRequested')
                if self.context.node_blue_id is None:
                    raise BoundaryError('Language identity boundary unavailable')
                identity=self.context.node_blue_id(x,self.gas)
                if type(identity) is not str or not identity:
                    raise BoundaryError('Language identity boundary returned an invalid identity')
                return identity
            if op=='$unwrap':
                while True:
                    self.gas.charge('valueMember')
                    if kind(x)!='object':return self.copy(x)
                    child=x.get('value',UNDEFINED)
                    if child is UNDEFINED:return self.copy(x)
                    x=child
            k=kind(x)
            if op=='$kind':return k
            if op=='$text':return self.to_text(x)
            if op=='$integer':return self.to_integer(x)
            if op=='$number':
                if type(x) is int:self.gas.charge('integerWork',self.limbs(x)**2)
                elif type(x) is str:self.gas.charge('textWork',(len(x)+63)//64)
                return number(x)
            if op=='$boolean':
                if x=='true':return True
                if x=='false':return False
                return truthy(x)
            if op in {'$object','$list'}:
                expected='object' if op=='$object' else 'list'
                if k in {'null','undefined'}:return {} if expected=='object' else []
                if k!=expected:raise BexError('wrong collection kind')
                return x
            if op in {'$not','$empty','$isEmpty'}:return not truthy(x)
            if op=='$truthy':return truthy(x)
            if op=='$exists':return x is not UNDEFINED
            if op=='$keys':
                if k!='object':return []
                self.gas.charge('valueMember',len(x));return sorted(x)
            if op=='$entries':
                if k!='object':return []
                self.gas.charge('valueMember',len(x));return [dict(key=a,val=x[a]) for a in sorted(x)]
            if op=='$size':return len(x) if k in {'object','list'} else 0 if k in {'null','undefined'} else 1
            if op=='$objectFromEntries':
                if k!='list':raise BexError('entries must be a list')
                out={}
                for row in x:
                    self.gas.charge('forEachItem')
                    if kind(row) != 'object':raise BexError('entry must be object')
                    key=required_text(row.get('key',UNDEFINED));val=row.get('val',UNDEFINED)
                    if val is UNDEFINED:out.pop(key,None)
                    else:out[key]=self.copy(val)
                return out
        if op in {'$and','$or','$coalesce','$default'}:
            for a in b:
                x=self.expr(a);t=truthy(x)
                if op=='$and' and not t:return False
                if op=='$or' and t:return True
                if op in {'$coalesce','$default'} and t:return x
            return True if op=='$and' else False if op=='$or' else UNDEFINED
        if op in ARRAY:
            args=[self.expr(a) for a in b]
            if op=='$concat':
                strings=[self.to_text(a) for a in args]
                self.gas.charge('textWork',(sum(map(len,strings))+63)//64)
                return ''.join(strings)
            if op=='$pointerJoin':
                strings=[self.to_text(x) if x is not None and x is not UNDEFINED else required_text(x) for x in args]
                self.gas.charge('textWork',(sum(map(len,strings))+len(strings)+63)//64)
                return '/'+ '/'.join(escape(x) for x in strings)
            if op in {'$startsWith','$sliceAfter'}:
                s,p=map(self.to_text,args)
                self.gas.charge('textWork',(len(s)+len(p)+63)//64)
                return s.startswith(p) if op=='$startsWith' else s[len(p):] if s.startswith(p) else ''
            if op in {'$eq','$ne'}:return equal(*args,charge=self.gas.charge) == (op=='$eq')
            if op in {'$gt','$gte','$lt','$lte'}:
                for v in args:
                    if type(v) is int:self.gas.charge('integerWork',self.limbs(v)**2)
                    elif type(v) is str:self.gas.charge('textWork',(len(v)+63)//64)
                a,z=map(number,args);return {'$gt':a>z,'$gte':a>=z,'$lt':a<z,'$lte':a<=z}[op]
            if op in {'$add','$subtract','$multiply','$divide'}:
                ints=[self.to_integer(a) for a in args];r=ints[0]
                for n in ints[1:]:
                    a,z=self.limbs(r),self.limbs(n)
                    self.gas.charge('integerWork',max(a,z) if op in {'$add','$subtract'} else a*z*(2 if op=='$divide' else 1))
                    if op=='$add':r+=n
                    elif op=='$subtract':r-=n
                    elif op=='$multiply':r*=n
                    else:
                        if n==0 or r%n:raise BexError('division requires nonzero divisor and exact integer result')
                        r//=n
                return r
            if op=='$listConcat':
                if any(kind(x) != 'list' for x in args):raise BexError('listConcat requires lists')
                out=[]
                for x in args:
                    for a in x:self.gas.charge('valueMember');out.append(a)
                return out
            if op=='$merge':
                out={}
                for a in args:
                    if kind(a) != 'object':raise BexError('merge requires objects')
                    for key in ordered_keys(a,self.gas.charge):out[key]=a[key]
                return out
        if op=='$choose':
            if truthy(self.expr(b['cond'])):return self.expr(b['then'])
            return self.expr(b['else']) if 'else' in b else UNDEFINED
        if op=='$is':return self.matches(self.expr(b['node']),b['pattern'])
        if op=='$isKind':return kind(self.expr(b['val'])) in (b['kind'] if type(b['kind']) is list else [b['kind']])
        if op=='$call':return self.function(b['function'],{k:self.expr(b.get('args',{})[k]) for k in sorted(b.get('args',{}))})
        if op=='$intrinsic':
            tid=b['type']['blueId']
            processor=self.intrinsics.get(tid)
            if processor is None:raise BexError('intrinsic exact type is not installed at execution')
            payload={}
            for k in sorted(b):
                if k!='type':
                    x=self.expr(b[k])
                    if x is not UNDEFINED:payload[k]=x
            output=processor(clone(payload),self.gas)
            if output is None:raise BexError('intrinsic returned Python None; explicit BEX values required')
            kind(output);return self.copy(output)
        if op in QUERY:return self.query(op,b)
        if op in {'$join','$split'}:
            if op=='$join':
                arr=self.expr(b['list']);sep=self.textarg(b['separator'])
                if kind(arr) != 'list':raise BexError('join requires list')
                self.gas.charge('valueMember',len(arr))
                strings=[self.to_text(x) for x in arr]
                self.gas.charge('textWork',(sum(map(len,strings))+len(sep)*max(0,len(strings)-1)+63)//64)
                return sep.join(strings)
            s=self.textarg(b['text']);sep=self.textarg(b['separator']);lim=self.to_integer(self.expr(b['limit'])) if 'limit'in b else -1
            if not sep or lim==0 or lim < -1:raise BexError('invalid split separator/limit')
            self.gas.charge('textWork',(len(s)+len(sep)+63)//64)
            self.gas.charge('valueMember',len(s)+1)
            return s.split(sep,lim-1 if lim>0 else -1)
        if op=='$listGet':
            arr=self.expr(b['list']);i=self.to_integer(self.expr(b['index']))
            if kind(arr) != 'list' or i<0:raise BexError('listGet requires a list and nonnegative index')
            return self.copy(arr[i]) if i<len(arr) else self.expr(b['default']) if 'default'in b else UNDEFINED
        if op in {'$get','$hasKey'}:
            obj=self.expr(b['object']);key=self.textarg(b['key'])
            return (kind(obj) == 'object' and obj.get(key,UNDEFINED) is not UNDEFINED) if op=='$hasKey' else self.copy(obj.get(key,UNDEFINED)) if kind(obj) == 'object' else UNDEFINED
        if op=='$objectSet':
            key=self.textarg(b['key']);val=self.expr(b['val']);self.sized('objectSetBase',val)
            obj=self.expr(b['object'])
            if obj is None or obj is UNDEFINED:obj={}
            if kind(obj) != 'object':raise BexError('objectSet requires object')
            out={key:obj[key] for key in ordered_keys(obj,self.gas.charge)}
            if val is UNDEFINED:out.pop(key,None)
            else:out[key]=val
            return out
        if op=='$pointerGet':
            obj=self.expr(b['object']);path=self.textarg(b['path']);parts=segments(path)
            self.gas.charge('pointerGetBase',amount=self.gas.schedule['pointerGetBase']+len(parts));out=pointer_get(obj,path)
            return self.copy(out) if out is not UNDEFINED else self.expr(b['default']) if 'default'in b else UNDEFINED
        if op=='$pointerSet':
            operation=self.textarg(b.get('op','set'));path=self.textarg(b['path'])
            if operation not in {'set','remove'}:raise BexError('pointerSet op must be set/remove')
            val=UNDEFINED if operation=='remove' else self.expr(b['val']) if 'val'in b else UNDEFINED
            obj=self.expr(b['object']);self.sized('pointerSetBase',val,len(segments(path)))
            return pointer_overlay(obj,path,val,remove=operation=='remove',charge=self.gas.charge)
        if op=='$includes':
            arr=self.expr(b['list']);val=self.expr(b['val'])
            if kind(arr) != 'list':raise BexError('includes requires list')
            for x in arr:
                self.gas.charge('forEachItem')
                if equal(x,val,charge=self.gas.charge):return True
            return False
        raise BexError('unimplemented operator '+op)

    def collection(self,value):
        if kind(value) == 'list':return ((UNDEFINED,x,i) for i,x in enumerate(value))
        if kind(value) == 'object':return ((k,value[k],i) for i,k in enumerate(sorted(value)))
        raise BexError('collection operation needs object or list')

    def query(self,op,b):
        source=self.expr(b['in']);rows=self.collection(source)
        acc=self.expr(b['init']) if op=='$reduce' else UNDEFINED
        names=[b[k] for k in ('item','key','index','acc') if k in b]
        old={n:self.frame.get(n,UNDEFINED) for n in names};present={n for n in names if n in self.frame}
        output={} if op=='$filter' and kind(source) == 'object' else []
        try:
            for key,val,i in rows:
                self.gas.charge('forEachItem');self.frame[b['item']]=self.copy(val)
                if 'key'in b:self.frame[b['key']]=key
                if 'index'in b:self.frame[b['index']]=i
                if 'acc'in b:self.frame[b['acc']]=acc
                result=self.expr(b['where'] if 'where'in b else b['expr'])
                if op=='$reduce':acc=result
                elif op=='$map':output.append(result)
                elif op=='$flatMap':
                    if kind(result) != 'list':raise BexError('flatMap item is not a list')
                    self.gas.charge('valueMember',len(result));output.extend(result)
                elif truthy(result):
                    if op=='$some':return True
                    if op=='$find':return self.copy(val)
                    if op=='$findEntry':return {'val':self.copy(val),'index':i,**({'key':key} if key is not UNDEFINED else {})}
                    if type(output) is dict:output[key]=self.copy(val)
                    else:output.append(self.copy(val))
            return acc if op=='$reduce' else False if op=='$some' else UNDEFINED if op in {'$find','$findEntry'} else output
        finally:
            for n in names:
                if n in present:self.frame[n]=old[n]
                else:self.frame.pop(n,None)

    def append_change(self,p,*,evaluated=False):
        if kind(p) != 'object' or set(p)-{'op','path','val'} or not {'op','path'}<=p.keys():raise BexError('malformed patch')
        operation=required_text(p['op']) if evaluated else self.textarg(p['op'])
        if operation not in {'add','replace','remove'}:raise BexError('unsupported patch op')
        if evaluated:
            path=required_text(p['path'])
            if not path.startswith('/'):path=self.context.scope.rstrip('/')+'/'+path
            if path in ('','/'):path=self.context.scope
            segments(path)
        else:path=self.path(p['path'])
        val=UNDEFINED if operation=='remove' else p.get('val',UNDEFINED) if evaluated else self.expr(p['val']) if 'val'in p else UNDEFINED
        if operation!='remove' and val is UNDEFINED:raise BexError('patch val is required')
        self.sized('appendChangeBase',val)
        self.changes.append({'op':operation,'path':path,**({'val':self.copy(val)} if operation!='remove' else {})})

    def append_event(self,value):
        if value is UNDEFINED:raise BexError('undefined event')
        self.sized('appendEventBase',value);self.events.append(self.copy(value))

    def block(self,statements):
        for statement in statements:
            self.gas.charge('statementBase');op=operator(statement);b=statement[op]
            if op=='$let':
                if 'vars'in b:
                    vs=b['vars']
                    if 'order'in b:
                        for n in b['order']:self.frame[n]=self.expr(vs[n])
                    else:self.frame.update({n:self.expr(vs[n]) for n in sorted(vs)})
                else:self.frame[b['name']]=self.expr(b['expr'])
            elif op=='$set':self.frame[b['name']]=self.expr(b['expr'])
            elif op=='$if':self.block(b.get('then',[]) if truthy(self.expr(b['cond'])) else b.get('else',[]))
            elif op=='$forEach':
                source=self.expr(b['in'])
                for key,val,i in self.collection(source):
                    self.gas.charge('forEachItem')
                    self.frame[b['item']]=self.copy(val) if kind(source) == 'list' or 'key'in b else dict(key=key,val=self.copy(val))
                    if 'key'in b:self.frame[b['key']]=key
                    if 'index'in b:self.frame[b['index']]=i if kind(source) == 'list' else UNDEFINED
                    self.block(b['do'])
            elif op=='$appendChange':self.append_change(b)
            elif op=='$appendChanges':
                arr=self.expr(b)
                if kind(arr) != 'list':raise BexError('appendChanges needs list')
                for p in arr:self.append_change(p,evaluated=True)
            elif op=='$appendEvent':self.append_event(self.expr(b))
            elif op=='$appendEvents':
                arr=self.expr(b)
                if kind(arr) != 'list':raise BexError('appendEvents needs list')
                for e in arr:self.append_event(e)
            elif op=='$call':self.function(b['function'],{k:self.expr(b.get('args',{})[k]) for k in sorted(b.get('args',{}))})
            elif op=='$return':raise _Return(self.default() if b is None else self.expr(b))
            elif op=='$returnIf':
                if truthy(self.expr(b['cond'])):raise _Return(self.expr(b['expr']) if 'expr'in b else self.default())
            elif op=='$fail':raise ExecutionRejected(self.to_text(self.expr(b['message'] if type(b) is dict and 'message'in b else b)))
            elif op=='$failIf':
                if truthy(self.expr(b['cond'])):raise ExecutionRejected(self.to_text(self.expr(b.get('message','BEX failure'))))
            else:raise BexError('unknown statement '+str(op))
