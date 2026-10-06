"""Data-only static compilation. There is no Python eval/exec or BEX recursion."""
from __future__ import annotations
from dataclasses import dataclass
from .values import CompileError, clone

RESERVED = set('name description type itemType keyType valueType value items blueId blue schema constraints mergePolicy properties contracts $previous $previousItems $pos $replace $empty'.split())
STATIC = {'type','itemType','keyType','valueType','blue','schema'}
UNARY = set('$nodeBlueId $unwrap $kind $text $integer $number $boolean $object $list $not $truthy $empty $isEmpty $exists $keys $entries $size $objectFromEntries'.split())
ARRAY = set('$concat $pointerJoin $startsWith $sliceAfter $eq $ne $gt $gte $lt $lte $and $or $coalesce $default $add $subtract $multiply $divide $listConcat $merge'.split())
CONSTANT = {'$null','$emptyObject','$emptyList','$changeset','$events'}
READS = {'$document','$event','$currentContract','$resultValue','$binding','$steps','$var','$const'}
QUERY = {'$map','$filter','$flatMap','$reduce','$some','$find','$findEntry'}
EXPR = UNARY | ARRAY | CONSTANT | READS | QUERY | {'$literal','$is','$isKind','$join','$split','$listGet','$get','$objectSet','$pointerGet','$pointerSet','$includes','$hasKey','$choose','$call','$intrinsic'}
STMT = {'$let','$set','$if','$forEach','$appendChange','$appendChanges','$appendEvent','$appendEvents','$call','$return','$returnIf','$fail','$failIf'}
KINDS = {'undefined','null','text','integer','double','boolean','object','list'}


def operator(value):
    if type(value) is dict and len(value)==1:
        key = next(iter(value))
        if type(key) is str and key.startswith('$'): return key
    return None


def object_shape(value, required=(), optional=()):
    if type(value) is not dict: raise CompileError('operator body must be an object')
    if not set(required) <= value.keys(): raise CompileError(f'missing required fields: {set(required)-value.keys()}')
    if value.keys() - set(required) - set(optional): raise CompileError(f'unknown operand fields: {value.keys()-set(required)-set(optional)}')


def name(value, *, container=False):
    if type(value) is not str or not value: raise CompileError('nonempty static name required')
    if container and value in RESERVED: raise CompileError(f'reserved user-container name: {value}')
    return value


def static(value):
    pending=[value]
    while pending:
        current=pending.pop()
        if operator(current):raise CompileError('executable form in static Blue position')
        if type(current) is dict:pending.extend(reversed(tuple(current.values())))
        elif type(current) is list:pending.extend(reversed(current))


def static_positions(value, depth=0):
    pending=[value]
    while pending:
        current=pending.pop()
        if type(current) is dict:
            for k,v in current.items():
                if type(k) is not str:raise CompileError('object keys must be Text')
                if k in STATIC:static(v)
            pending.extend(reversed(tuple(current.values())))
        elif type(current) is list:pending.extend(reversed(current))

@dataclass(frozen=True)
class Program:
    source: dict
    selected_entry: str | None
    operator_inventory: tuple[str,...]

class Compiler:
    def __init__(self, *, intrinsic_ids=()):
        self.intrinsic_ids = frozenset(intrinsic_ids)

    def compile(self, source, *, definition=None, entry=None):
        if type(source) is not dict: raise CompileError('program must be an object')
        merged = clone(source)
        if definition is not None:
            if type(definition) is not dict: raise CompileError('definition must be an object')
            for k in ('constants','functions'):
                if type(definition.get(k,{})) is not dict or type(merged.get(k,{})) is not dict:
                    raise CompileError('name container must be object')
                merged[k] = {**clone(definition.get(k,{})), **merged.get(k,{})}
        self.source = merged
        self.constants = merged.get('constants',{})
        self.functions = merged.get('functions',{})
        if type(self.constants) is not dict or type(self.functions) is not dict: raise CompileError('name container must be object')
        for key in (*self.constants,*self.functions): name(key,container=True)
        for val in self.constants.values(): static(val)
        static_positions(merged)
        self.calls = {key:set() for key in self.functions}
        self.calls['<root>'] = set()
        self.inventory = set()
        for f,body in self.functions.items():
            if type(body) is not dict: raise CompileError('function must be an object')
            args=body.get('args',{})
            if type(args) is not dict: raise CompileError('function args must be a name container')
            for a,pattern in args.items(): name(a,container=True); static(pattern)
            self.body(body,set(args),f)
        selected=entry if entry is not None else merged.get('entry')
        if selected is not None:
            name(selected,container=True)
            if selected not in self.functions: raise CompileError('unknown entry function')
            if self.functions[selected].get('args'): raise CompileError('entry function must have no arguments')
        self.body(merged,set(),'<root>')
        done=set();active=set()
        for f in self.calls:
            pending=[(f,False)]
            while pending:
                key,leave=pending.pop()
                if leave:active.remove(key);done.add(key);continue
                if key in active:raise CompileError('recursive function call graph')
                if key in done:continue
                active.add(key);pending.append((key,True))
                pending.extend((g,False) for g in sorted(self.calls[key],reverse=True))
        return Program(merged,selected,tuple(sorted(self.inventory)))

    def body(self,body,slots,current):
        if 'expr' in body: self.expr(body['expr'],slots,current)
        elif 'do' in body: self.block(body['do'],slots,current)

    def call(self,b,slots,current):
        object_shape(b,('function',),('args',))
        f=name(b['function'],container=True)
        if f not in self.functions: raise CompileError('unknown function '+f)
        args=b.get('args',{})
        if type(args) is not dict:raise CompileError('call args must be object')
        for k in args: name(k,container=True)
        if args.keys()!=self.functions[f].get('args',{}).keys():raise CompileError('call argument set mismatch')
        for v in args.values():self.expr(v,slots,current)
        self.calls[current].add(f)

    def expr(self,v,slots,current):
        op=operator(v)
        if op is None:
            if type(v) is list:
                for a in v:self.expr(a,slots,current)
            elif type(v) is dict:
                for k,a in v.items():
                    if k not in STATIC:self.expr(a,slots,current)
            elif type(v) not in (str,int,float,bool,type(None)):
                from decimal import Decimal
                if type(v) is not Decimal:raise CompileError('invalid literal value')
            return
        if op not in EXPR:raise CompileError('unknown expression operator '+op)
        self.inventory.add(op);b=v[op]
        if op=='$literal' or op in CONSTANT:return
        if op in UNARY:self.expr(b,slots,current);return
        if op in ARRAY:
            if type(b) is not list:raise CompileError(op+' needs an operand list')
            if op in {'$startsWith','$sliceAfter','$eq','$ne','$gt','$gte','$lt','$lte'} and len(b)!=2:raise CompileError('exactly two operands required')
            if op in {'$add','$subtract','$multiply','$divide'} and not b:raise CompileError('at least one arithmetic operand required')
            for a in b:self.expr(a,slots,current)
            return
        if op in {'$var','$const'}:
            if type(b) is str:n=b
            else:object_shape(b,('name',),('path',));n=name(b['name']);self.expr(b.get('path',''),slots,current)
            if n not in (slots if op=='$var' else self.constants):raise CompileError('unknown '+op+' '+n)
            return
        if op in READS:
            if type(b) is dict and operator(b) is None:
                allowed={'path','view'} if op in {'$document','$resultValue'} else {'name','path'} if op=='$binding' else {'step','path'} if op=='$steps' else {'path'}
                object_shape(b,(),allowed)
                for x in b.values():self.expr(x,slots,current)
            else:self.expr(b,slots,current)
            return
        if op=='$is':
            object_shape(b,('node','pattern'));static(b['pattern']);self.expr(b['node'],slots,current);return
        if op=='$isKind':
            object_shape(b,('val','kind'));k=b['kind'];ks=k if type(k) is list else [k]
            if not ks or any(type(x) is not str or x not in KINDS for x in ks):raise CompileError('invalid kind test')
            self.expr(b['val'],slots,current);return
        if op=='$call':self.call(b,slots,current);return
        if op=='$intrinsic':
            if type(b) is not dict or type(b.get('type')) is not dict or set(b['type'])!={'blueId'}:raise CompileError('intrinsic needs static exact type BlueId')
            if b['type']['blueId'] not in self.intrinsic_ids:raise CompileError('unknown intrinsic exact type')
            for k,x in b.items():
                if k!='type':self.expr(x,slots,current)
            return
        if op in QUERY:
            bodykey='where' if op in {'$filter','$some','$find','$findEntry'} else 'expr'
            required=['in','item',bodykey]+(['acc','init'] if op=='$reduce' else [])
            object_shape(b,required,('key','index'))
            self.expr(b['in'],slots,current)
            if op=='$reduce':self.expr(b['init'],slots,current)
            names=[name(b[k],container=True) for k in ('item','key','index','acc') if k in b]
            if len(set(names))!=len(names):raise CompileError('collection bindings must differ')
            self.expr(b[bodykey],slots|set(names),current);return
        shapes={
            '$join':(('list','separator'),()),'$split':(('text','separator'),('limit',)),
            '$listGet':(('list','index'),('default',)),'$get':(('object','key'),()),
            '$objectSet':(('object','key','val'),()),'$pointerGet':(('object','path'),('default',)),
            '$pointerSet':(('object','path'),('op','val')),'$includes':(('list','val'),()),
            '$hasKey':(('object','key'),()),'$choose':(('cond','then'),('else',))}
        req,opt=shapes[op];object_shape(b,req,opt)
        for x in b.values():self.expr(x,slots,current)

    def block(self,statements,slots,current):
        if type(statements) is not list:raise CompileError('statement block must be a list')
        for statement in statements:
            op=operator(statement)
            if op not in STMT:raise CompileError('unknown or malformed statement')
            self.inventory.add(op);b=statement[op]
            if op=='$let':
                if type(b) is not dict:raise CompileError('$let body must be object')
                if 'vars' in b:
                    object_shape(b,('vars',),('order',));variables=b['vars']
                    if type(variables) is not dict:raise CompileError('vars must be object')
                    for n in variables:name(n,container=True)
                    order=b.get('order')
                    if order is not None:
                        if type(order) is not list or len(order)!=len(variables) or set(order)!=variables.keys():raise CompileError('order must name every variable exactly once')
                        for n in order:self.expr(variables[n],slots,current);slots.add(n)
                    else:
                        for expr in variables.values():self.expr(expr,slots,current)
                        slots.update(variables)
                else:
                    object_shape(b,('name','expr'));n=name(b['name'],container=True);self.expr(b['expr'],slots,current);slots.add(n)
            elif op=='$set':
                object_shape(b,('name','expr'))
                if b['name'] not in slots:raise CompileError('$set requires declared variable')
                self.expr(b['expr'],slots,current)
            elif op=='$if':
                object_shape(b,('cond',),('then','else'));self.expr(b['cond'],slots,current)
                a,z=set(slots),set(slots);self.block(b.get('then',[]),a,current);self.block(b.get('else',[]),z,current);slots.update(a&z)
            elif op=='$forEach':
                object_shape(b,('in','item','do'),('key','index'));self.expr(b['in'],slots,current)
                names=[name(b[k],container=True) for k in ('item','key','index') if k in b]
                if len(set(names))!=len(names):raise CompileError('loop bindings must differ')
                slots.update(names);self.block(b['do'],slots,current)
            elif op=='$appendChange':
                object_shape(b,('op','path'),('val',))
                for v in b.values():self.expr(v,slots,current)
            elif op=='$call':self.call(b,slots,current)
            elif op in {'$returnIf','$failIf'}:
                key='expr' if op=='$returnIf' else 'message'
                object_shape(b,('cond',),(key,));self.expr(b['cond'],slots,current)
                if key in b:self.expr(b[key],slots,current)
            elif op=='$fail' and type(b) is dict and 'message' in b:
                object_shape(b,('message',));self.expr(b['message'],slots,current)
            else:self.expr(b,slots,current)
