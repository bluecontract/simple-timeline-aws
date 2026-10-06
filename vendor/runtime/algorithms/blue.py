"""Executable algorithms of Blue Language Specification 1.0.
The Markdown specification embeds this file without a separate translation.
"""
from __future__ import annotations
import copy
import hashlib
import json
import math
import re
import struct
from decimal import Decimal
from dataclasses import dataclass, field, replace
from fractions import Fraction
from functools import lru_cache
from typing import Any
from contextlib import contextmanager

# === A01: Values, failures and constants ===
CORE = {
    'Text': 'GX7CFUmSDrE2MzptunLCCdZwnuwwrenRQqEnHL4x3uoC',
    'Integer': 'E2LM6qgzWG9ttagq2xTmiZkgYEAgkYedFCmU9v7NnVEq',
    'Double': '9eWaHYz2vKrFofdHTHAizNNu8xP6QE3WQ5y7DGrGZvyJ',
    'Boolean': 'AwvXD961fmnmqcSQhjMA7r15HpVh39cefb6ZTyUz2Fm2',
    'List': '85ip88snCGrgUNdi1rUFqqAxcxwVGKV2g4LjsKoyKmXK',
    'Dictionary': '5WQ4tVb4gUUdZa7EfaiUa2XKQwgAurvfYY3ALPauxcAF',
}
CORE_NAME = {v:k for k,v in CORE.items()}
TYPES = frozenset(('type','itemType','keyType','valueType'))
LABELS = frozenset(('name','description'))
# specification is a reference-valued, non-inherited metadata slot.
# It is not a literal label, a type-position alias, or an ordinary field.
SPECIFICATION = 'specification'
REFERENCE_METADATA = frozenset((SPECIFICATION,))
METADATA = LABELS | REFERENCE_METADATA
LITERALS = LABELS | {'value'}
HEADERS = TYPES | METADATA | {'schema','mergePolicy','contracts'}
RESERVED = HEADERS | {'value','items','blueId','blue','properties','constraints'}
CONTROLS = frozenset(('$pos','$replace','$previous','$previousItems'))
ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
SAFE = 9007199254740991
ZERO = '0' * 44
NUMBER = re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z', re.ASCII)
INTEGER_TEXT = re.compile(r'(?:0|-[1-9][0-9]*|[1-9][0-9]*)\Z', re.ASCII)
INDEX = re.compile(r'(?:0|[1-9][0-9]*)\Z', re.ASCII)
ABSENT = object()

class Failure(Exception):
    """A semantic failure with non-identity-bearing, portable diagnostic data.

    None means an unestablished location; the empty pointer means the root.
    The legacy category/detail remain stable for programmatic comparisons.
    """
    def __init__(self, category, detail='', path=None, *, expected=None, actual=None,
                 keyword=None, phase=None, goal=None, hint=None):
        self.category, self.detail, self.path = category, detail, path
        self.expected, self.actual = expected, actual
        self.keyword, self.phase, self.goal = keyword, phase, goal
        self.hint = hint
        self.document_type = None
        self.node_name = None
        super().__init__(category + (': '+detail if detail else ''))

    @property
    def message(self):
        return failure_message(self)

    def __str__(self):
        return self.category + ': ' + self.message

    def as_dict(self):
        result = {'category':self.category, 'detail':self.detail,
                  'path':self.path, 'message':self.message}
        for key,value in (('expected',self.expected),('actual',self.actual),
                          ('keyword',self.keyword),('phase',self.phase),
                          ('goal',self.goal),('hint',self.hint),
                          ('documentType',self.document_type),('nodeName',self.node_name)):
            if value is not None: result[key]=copy.deepcopy(value)
        return result


def require(test, category, detail='', **diagnostic):
    if not test: raise Failure(category, detail, **diagnostic)


def diagnostic_type(tid, c=None):
    """Display exact identities; never fetch merely to improve an error message."""
    if tid is None: return None
    if tid in CORE_NAME:
        return {'blueId':tid, 'name':CORE_NAME[tid], 'core':True}
    result={'blueId':tid, 'core':False}
    n=c.bodies.get(tid) if c is not None else None
    if isinstance(n,Node) and n.has('name'):
        # c.bodies contains independently established exact content only.
        result['name']=diagnostic_literal(n.get('name'))
    return result


def diagnostic_literal(value):
    """Bound output size without altering a validation input or Blue content."""
    if value is ABSENT: return None
    if isinstance(value,NumberToken): return {'numberToken':value.text[:256]}
    if isinstance(value,Ref): return {'blueId':value.id}
    if isinstance(value,Node): return {'blueId':identity(value),'kind':value.kind()}
    if isinstance(value,Fraction):
        return {'numerator':integer_text(value.numerator),'denominator':integer_text(value.denominator)}
    if type(value) is int and abs(value)>SAFE: return {'integer':integer_text(value)}
    if isinstance(value,str) and len(value)>256:
        return {'preview':value[:256], 'truncated':True, 'length':len(value)}
    if type(value) in (str,bool,int,float) or value is None: return value
    if isinstance(value,(tuple,list)):
        return {'length':len(value),'preview':[diagnostic_literal(x) for x in value[:8]]}
    return {'kind':type(value).__name__}


def diagnostic_value(value=ABSENT, tid=None, c=None, kind=None):
    result={'present':value is not ABSENT}
    if tid is not None: result['type']=diagnostic_type(tid,c)
    if kind is not None: result['kind']=kind
    if value is not ABSENT: result['value']=diagnostic_literal(value)
    return result


def diagnostic_type_name(value):
    if not isinstance(value,dict): return 'a compatible type'
    if value.get('core'): return value['name']
    name=value.get('name')
    if isinstance(name,str): return name + ' (custom type ' + value['blueId'] + ')'
    return 'type ' + value.get('blueId','<unknown>')


def diagnostic_display(value):
    if isinstance(value,dict) and 'numerator' in value and 'denominator' in value:
        return value['numerator'] if value['denominator']=='1' else value['numerator']+'/'+value['denominator']
    if isinstance(value,dict) and 'integer' in value: return value['integer']
    if isinstance(value,dict) and 'numberToken' in value: return value['numberToken']
    if isinstance(value,dict) and 'preview' in value and value.get('truncated'):
        return json.dumps(value['preview'],ensure_ascii=False)+' [truncated]'
    return json.dumps(value,ensure_ascii=False,separators=(',',':'))


def failure_message(error):
    where = ('the document root' if error.path=='' else error.path or 'the requested node')
    expected=error.expected or {}; actual=error.actual or {}
    et=diagnostic_type_name(expected.get('type'))
    at=diagnostic_type_name(actual.get('type'))
    if error.category=='FixedValueConflict' and 'value' in expected and 'value' in actual:
        msg='The value at '+where+' is fixed to '+diagnostic_display(expected['value'])
        if expected.get('type'): msg+=' ('+et+')'
        msg+='; received '+diagnostic_display(actual['value'])
        if actual.get('type'): msg+=' ('+at+')'
        return msg+'. An inherited fixed value cannot be changed.'
    if error.category=='TypeCompatibilityViolation' and expected.get('type') and actual.get('type'):
        msg='Expected '+et+' at '+where+'; received '+at
        if 'value' in actual: msg+=' ('+diagnostic_display(actual['value'])+')'
        return msg+'.'
    if error.category=='SchemaViolation' and error.detail in ('scalar payload required','list payload required','payload required'):
        label=et if expected.get('type') else expected.get('kind','payload')
        return 'A '+label+' value is required at '+where+', but no payload was supplied.'
    if error.category=='SchemaWeakening':
        msg='The schema at '+where+' weakens the inherited '+(error.keyword or error.detail)+' requirement'
        if 'value' in expected and 'value' in actual:
            msg+=' (inherited '+diagnostic_display(expected['value'])+', supplied '+diagnostic_display(actual['value'])+')'
        return msg+'. A subtype may only retain or tighten it.'
    if error.category=='SchemaViolation' and error.keyword:
        msg='The value at '+where+' violates '+error.keyword
        if 'value' in actual: msg+=' (received '+diagnostic_display(actual['value'])+')'
        if 'value' in expected: msg+='; required '+diagnostic_display(expected['value'])
        return msg+'.'
    if error.category=='ProviderUnavailable':
        return 'Required content is unavailable at '+where+': '+error.detail+'. Validation is incomplete; the document was not admitted.'
    if error.category=='ProviderBlueIdMismatch':
        return 'Content supplied for '+error.detail+' could not be verified at '+where+'. It cannot be used as trusted content.'
    # Core names are used for display only; retained detail and exact IDs are not edited.
    detail=error.detail
    for tid,name in CORE_NAME.items(): detail=detail.replace(tid,name)
    return (detail or error.category)+' at '+where+'.'


@contextmanager
def error_scope(c, path=None, phase=None):
    old_path,old_phase=c.diagnostic_path,c.diagnostic_phase
    if path is not None: c.diagnostic_path=path
    if phase is not None: c.diagnostic_phase=phase
    try:
        yield
    except Failure as error:
        if error.path is None: error.path=c.diagnostic_path
        if error.phase is None: error.phase=c.diagnostic_phase
        if error.goal is None: error.goal=c.diagnostic_goal
        root=c.diagnostic_root
        if isinstance(root,Node):
            t=root.get('type')
            if error.document_type is None and isinstance(t,Ref):
                error.document_type=diagnostic_type(t.id,c)
            if error.node_name is None and root.has('name'):
                error.node_name=diagnostic_literal(root.get('name'))
        if error.hint is None and error.goal=='value' and error.category=='SchemaViolation' and error.detail in ('scalar payload required','list payload required','payload required'):
            error.hint='Supply a payload for a completed value. To declare a type without a payload, explicitly validate as Definition instead.'
        raise
    finally:
        c.diagnostic_path,c.diagnostic_phase=old_path,old_phase

@dataclass(frozen=True)
class NumberToken:
    text: str
    @property
    def decimal(self): return any(c in self.text for c in '.eE')

@dataclass(frozen=True)
class Ref:
    id: str
    # A body is installed only by successful verification, never by public input.
    body: Any = field(default=None, compare=False, repr=False)

@dataclass(frozen=True)
class Local:
    index: int

@dataclass(frozen=True)
class Node:
    fields: tuple
    def get(self,k,default=ABSENT): return dict(self.fields).get(k,default)
    def has(self,k): return k in dict(self.fields)
    def keys(self): return tuple(k for k,_ in self.fields)
    def ordinary(self): return tuple(k for k,_ in self.fields if k not in RESERVED)
    def kind(self):
        if self.has('value'): return 'scalar'
        if self.has('items'): return 'list'
        if self.ordinary() or not self.fields: return 'object'
        return 'none'

def key_order(s): return s.encode('utf-16-be','strict')
def ordered(xs): return sorted(xs, key=key_order)
def node(m): return Node(tuple((k,m[k]) for k in ordered(m)))
def changed(n, /, **updates):
    m=dict(n.fields)
    for k,v in updates.items():
        if v is ABSENT: m.pop(k,None)
        else: m[k]=v
    return node(m)
def obj_fields(n): return {k:n.get(k) for k in n.ordinary()}
def scalar(t,v): return node({'type':Ref(CORE.get(t,t)), 'value':v})
def list_node(xs): return node({'items':tuple(xs)})
def pointer(path,k): return path+'/'+str(k).replace('~','~0').replace('/','~1')

@dataclass
class Limits:
    # Optional host controls: exceeding one establishes incomplete work only.
    text_bytes: int | None = None
    depth: int | None = None
    values: int | None = None
    numeric_chars: int | None = None
    decimal_scale: int | None = None
    steps: int | None = None
    fetches: int | None = None

    def __post_init__(self):
        for value in vars(self).values():
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError('host limits must be nonnegative integers or None')


def within(value, bound):
    return bound is None or value <= bound


def integer_text(value):
    return str(Decimal(value))


def parse_integer(text):
    return int(Decimal(text))

@dataclass
class Context:
    provider: dict = field(default_factory=dict)
    aliases: dict = field(default_factory=lambda:dict(CORE))
    directive_aliases: dict = field(default_factory=dict)
    limits: Limits = field(default_factory=Limits)
    bodies: dict = field(default_factory=dict)
    proofs: dict = field(default_factory=dict)
    demands: list = field(default_factory=list)
    plans: dict = field(default_factory=dict)
    presence_cache: dict = field(default_factory=dict)
    heads: dict = field(default_factory=dict)
    validation_cache: set = field(default_factory=set)
    plan_active: list = field(default_factory=list)
    operand_active: set = field(default_factory=set)
    operand_descriptions: dict = field(default_factory=dict)
    work: int = 0
    diagnostic_path: str = ''
    diagnostic_phase: str = 'operation'
    diagnostic_goal: str|None = None
    diagnostic_root: Any = None
    def step(self):
        self.work += 1
        require(within(self.work, self.limits.steps),'OperationLimitExceeded','steps')
    def remember(self,n):
        if isinstance(n,Node): self.bodies[identity(n)]=n
        return n

# === A02: Parsing, token preservation and rational arithmetic ===
def checked_unicode(s):
    require(isinstance(s,str),'InvalidSyntax','string expected')
    require(not any(0xD800 <= ord(c) <= 0xDFFF for c in s),'InvalidSyntax','unpaired surrogate')
    return s

def pairs_no_duplicates(pairs):
    m={}
    for k,v in pairs:
        checked_unicode(k)
        require(k not in m,'DuplicateKey',k)
        m[k]=v
    return m

def parse(text, fmt='json', limits=None):
    lim=limits or Limits()
    try:
        if isinstance(text,bytes): text=text.decode('utf-8','strict')
        require(isinstance(text,str),'InvalidSyntax','text expected')
        require(within(len(text.encode('utf-8','strict')), lim.text_bytes),'OperationLimitExceeded','text bytes')
        if fmt == 'json':
            def num(s):
                require(NUMBER.fullmatch(s) is not None,'InvalidSyntax','number')
                require(within(len(s),lim.numeric_chars),'OperationLimitExceeded','number token')
                return NumberToken(s)
            def bad(s): raise Failure('InvalidSyntax','non-JSON number '+s)
            x=json.loads(text,parse_int=num,parse_float=num,parse_constant=bad,object_pairs_hook=pairs_no_duplicates)
        elif fmt == 'yaml': x=parse_yaml(text)
        else: raise Failure('UnsupportedFormat',fmt)
        count=0
        pending=[('value',x,1)]
        while pending:
            task,v,d=pending.pop()
            if task=='key':checked_unicode(v);continue
            count+=1
            require(within(d,lim.depth) and within(count,lim.values),'OperationLimitExceeded','parse bounds')
            if isinstance(v,str):checked_unicode(v)
            elif isinstance(v,NumberToken):
                require(within(len(v.text),lim.numeric_chars),'OperationLimitExceeded','number token')
            elif isinstance(v,dict):
                for k,a in reversed(tuple(v.items())):
                    pending.append(('value',a,d+1));pending.append(('key',k,0))
            elif isinstance(v,list):pending.extend(('value',a,d+1) for a in reversed(v))
        require(x is not None,'InvalidRoot')
        return x
    except RecursionError as e:
        raise Failure('OperationLimitExceeded','parser recursion') from e
    except (UnicodeError,json.JSONDecodeError,ValueError) as e:
        if isinstance(e,Failure): raise
        raise Failure('InvalidSyntax',str(e)) from e

def plain_scalar(s):
    if s in ('','null'): return None
    if s == 'true': return True
    if s == 'false': return False
    if NUMBER.fullmatch(s): return NumberToken(s)
    return s

def parse_yaml(text):
    # Only YAML presentation/folding is delegated; scalar resolution is above.
    from vendor import yaml
    try:
        for t in yaml.scan(text,Loader=yaml.BaseLoader):
            require(not isinstance(t,(yaml.tokens.TagToken,yaml.tokens.AnchorToken,yaml.tokens.AliasToken,yaml.tokens.DirectiveToken)),
                    'InvalidSyntax','YAML tag, alias, anchor or directive')
        docs=list(yaml.compose_all(text,Loader=yaml.BaseLoader))
        require(len(docs)==1 and docs[0] is not None,'InvalidSyntax','one YAML document required')
        def convert(n):
            if isinstance(n,yaml.nodes.ScalarNode):
                return n.value if n.style is not None else plain_scalar(n.value)
            if isinstance(n,yaml.nodes.SequenceNode): return [convert(a) for a in n.value]
            require(isinstance(n,yaml.nodes.MappingNode),'InvalidSyntax','YAML node')
            pairs=[]
            for k,v in n.value:
                key=convert(k)
                require(isinstance(key,str) and not (key=='<<' and getattr(k,'style',None) is None),'InvalidSyntax','YAML key')
                pairs.append((key,convert(v)))
            return pairs_no_duplicates(pairs)
        return convert(docs[0])
    except yaml.YAMLError as e: raise Failure('InvalidSyntax',str(e)) from e

def decimal_rational(s,limits=None):
    lim=limits or Limits()
    require(isinstance(s,str) and NUMBER.fullmatch(s),'InvalidScalar','decimal syntax')
    require(within(len(s),lim.numeric_chars),'OperationLimitExceeded','number length')
    neg=s.startswith('-'); s=s[1:] if neg else s
    q=re.split('[eE]',s); mant=q[0]; exponent=parse_integer(q[1]) if len(q)==2 else 0
    p=mant.split('.'); digits=''.join(p); exponent-=len(p[1]) if len(p)==2 else 0
    require(within(abs(exponent),lim.decimal_scale),'OperationLimitExceeded','decimal scale')
    a=parse_integer(digits) * (-1 if neg else 1)
    return Fraction(a*10**exponent,1) if exponent>=0 else Fraction(a,10**(-exponent))

def nearest_integer(q):
    n,r=divmod(q.numerator,q.denominator)
    return n+(2*r>q.denominator or (2*r==q.denominator and n%2==1))

def pow2(e): return Fraction(2**e,1) if e>=0 else Fraction(1,2**(-e))
def round_binary64(q):
    q=Fraction(q)
    if not q: return 0.0
    sign=1<<63 if q<0 else 0; q=abs(q)
    e=q.numerator.bit_length()-q.denominator.bit_length()
    if q<pow2(e): e-=1
    if e < -1022:
        m=nearest_integer(q/pow2(-1074)); bits=m
    else:
        m=nearest_integer(q/pow2(e-52))
        if m==2**53: m//=2; e+=1
        require(e<=1023,'InvalidScalar','binary64 overflow')
        bits=((e+1023)<<52)+(m-2**52)
    return struct.unpack('>d',(sign+bits).to_bytes(8,'big'))[0]

def rational(v):
    require(type(v) in (int,float),'InvalidScalar','numeric value required')
    require(type(v) is int or math.isfinite(v),'InvalidScalar','nonfinite')
    return Fraction(v)

def encode_scalar(own,x,limits=None):
    lim=limits or Limits()
    if own is None:
        if isinstance(x,str): own=CORE['Text']
        elif type(x) is bool: own=CORE['Boolean']
        elif isinstance(x,NumberToken): own=CORE['Double' if x.decimal else 'Integer']
        elif type(x) is int: own=CORE['Integer']
        elif type(x) is float: own=CORE['Double']
        else: raise Failure('InvalidScalar')
    if own==CORE['Integer']:
        if isinstance(x,str):
            require(INTEGER_TEXT.fullmatch(x),'InvalidScalar','canonical Integer text')
            require(within(len(x),lim.numeric_chars),'OperationLimitExceeded','Integer length')
            value=parse_integer(x)
        elif isinstance(x,NumberToken):
            if not x.decimal: require(abs(parse_integer(x.text))<=SAFE,'InvalidScalar','unsafe integer token')
            q=decimal_rational(x.text,lim)
            require(q.denominator==1,'InvalidScalar','fractional Integer')
            value=q.numerator
        elif type(x) is int: value=x
        else: raise Failure('InvalidScalar','Integer payload')
        require(within(len(integer_text(value)),lim.numeric_chars),'OperationLimitExceeded','Integer length')
        return own, value if abs(value)<=SAFE else integer_text(value)
    if own==CORE['Double']:
        if isinstance(x,NumberToken): v=round_binary64(decimal_rational(x.text,lim))
        elif isinstance(x,str): v=round_binary64(decimal_rational(x,lim))
        elif type(x) is int: v=round_binary64(Fraction(x))
        elif type(x) is float: v=x
        else: raise Failure('InvalidScalar','Double payload')
        require(math.isfinite(v),'InvalidScalar','nonfinite')
        return own, 0.0 if v==0 else v
    if own==CORE['Text']:
        require(isinstance(x,str),'InvalidScalar','Text payload'); return own,checked_unicode(x)
    if own==CORE['Boolean']:
        require(type(x) is bool,'InvalidScalar','Boolean payload'); return own,x
    # An opaque custom type does not authorize contextual conversion during naming.
    if isinstance(x,NumberToken):
        if not x.decimal:
            v=parse_integer(x.text); require(abs(v)<=SAFE,'InvalidScalar','unsafe integer token')
        else: v=round_binary64(decimal_rational(x.text,lim))
    else: v=x
    require(type(v) in (str,bool,int,float),'InvalidScalar','literal expected')
    if type(v) is int: require(abs(v)<=SAFE,'InvalidScalar','unsafe custom integer')
    if type(v) is float:
        require(math.isfinite(v),'InvalidScalar','nonfinite')
        # Under a custom own type, these spellings have the same numeric
        # commitment. Do not retain a host category that identity erased.
        if v.is_integer() and abs(v)<=SAFE: v=int(v)
    return own, (0.0 if type(v) is float and v==0 else v)

# === A03: Canonical bytes, hashes and exact normalization ===
@lru_cache(maxsize=8192)
def number_text(v):
    if v==0: return '0'
    sign='-' if v<0 else ''; q=Fraction(abs(v))
    e=len(str(q.numerator))-len(str(q.denominator))
    def ten(k): return Fraction(10**k,1) if k>=0 else Fraction(1,10**(-k))
    while q<ten(e): e-=1
    while q>=ten(e+1): e+=1
    for k in range(1,18):
        choices=[]
        for n in (e,e+1,e+2):
            scale=ten(n-k); a=q//scale
            for s in (a,a+1):
                if 10**(k-1)<=s<10**k:
                    try: match=round_binary64(s*scale)==abs(v)
                    except Failure: match=False
                    if match: choices.append((abs(s*scale-q),s%2,s,k,n))
        if choices:
            _,_,s,k,n=min(choices); d=str(s)
            if k<=n<=21: result=d+'0'*(n-k)
            elif 0<n<=21 and n<k: result=d[:n]+'.'+d[n:]
            elif -6<n<=0: result='0.'+'0'*(-n)+d
            else: result=d[0]+('.'+d[1:] if k>1 else '')+'e'+('+' if n-1>=0 else '-')+str(abs(n-1))
            return sign+result
    raise Failure('InternalError','shortest decimal')

def json_quote(s): return json.dumps(checked_unicode(s),ensure_ascii=False,separators=(',',':'))
def canonical_text(x):
    if x is None: return 'null'
    if type(x) is bool: return 'true' if x else 'false'
    if type(x) is str: return json_quote(x)
    if type(x) is int:
        require(abs(x)<=SAFE,'InvalidHashHelper','unsafe numeric Integer')
        return str(x)
    if type(x) is float:
        require(math.isfinite(x),'InvalidHashHelper','nonfinite')
        return number_text(x)
    if isinstance(x,(list,tuple)): return '['+','.join(canonical_text(a) for a in x)+']'
    if isinstance(x,dict): return '{'+','.join(json_quote(k)+':'+canonical_text(x[k]) for k in ordered(x))+'}'
    raise Failure('InvalidHashHelper',type(x).__name__)

def b58(data):
    z=len(data)-len(data.lstrip(b'\0')); n=int.from_bytes(data,'big'); out=''
    while n: n,r=divmod(n,58); out=ALPHABET[r]+out
    return '1'*z+out

def plain_id(s):
    require(isinstance(s,str) and s and all(c in ALPHABET for c in s),'InvalidBlueId')
    n=0
    for c in s: n=n*58+ALPHABET.index(c)
    z=len(s)-len(s.lstrip('1'))
    data=b'\0'*z+(n.to_bytes((n.bit_length()+7)//8,'big') if n else b'')
    require(len(data)==32 and b58(data)==s,'InvalidBlueId')
    return s

def final_id(s):
    require(isinstance(s,str),'InvalidBlueId')
    if '#' not in s: return plain_id(s)
    p=s.split('#'); require(len(p)==2 and INDEX.fullmatch(p[1]),'InvalidBlueId')
    plain_id(p[0]); return s

def H(raw): return b58(hashlib.sha256(canonical_text(raw).encode('utf-8')).digest())
def append_id(p,e): return H({'$listCons':{'prev':{'blueId':p},'elem':{'blueId':e}}})
def list_id(xs,token=None):
    p=H({'$list':'empty'})
    for x in xs: p=append_id(p,identity(x,token))
    return p

def helper(n,token=None):
    m={}
    for k,v in n.fields:
        if k in LITERALS: m[k]=v
        elif k=='items': m[k]={'blueId':list_id(v,token)}
        elif k=='mergePolicy': m[k]={'blueId':identity(scalar('Text',v),token)}
        else: m[k]={'blueId':identity(v,token)}
    return m

def identity(n,token=None):
    if isinstance(n,Ref): return n.id
    if isinstance(n,Local):
        require(token is not None,'InvalidBlueId','local edge outside cyclic operation')
        return token(n.index)
    require(isinstance(n,Node),'InvalidBlueIdInput')
    if n.keys()==('items',): return list_id(n.get('items'),token)
    return H(helper(n,token))

def contains_local(n):
    if isinstance(n,Local): return True
    if isinstance(n,Ref): return False
    if isinstance(n,Node):
        return any(contains_local(a) for k,v in n.fields if k not in LITERALS|{'mergePolicy'}
                   for a in (v if k=='items' else (v,)))
    return False

def normalize(x,c=None,mode='exact',symbolic=False):
    c=c or Context(); c.step()
    if isinstance(x,(Node,Ref,Local)):
        require(symbolic or not contains_local(x),'InvalidBlueId')
        return x
    require(x is not None,'InvalidExactNode')
    if isinstance(x,dict) and 'blueId' in x:
        require(set(x)=={'blueId'},'InvalidReferenceShape')
        s=x['blueId']
        if symbolic and isinstance(s,str) and re.fullmatch(r'this#(?:0|[1-9][0-9]*)',s):
            return Local(int(s[5:]))
        return Ref(final_id(s))
    if isinstance(x,list): x={'items':x}
    elif not isinstance(x,dict): x={'value':x}
    require(not set(x)&{'blue','properties','constraints'},'InvalidNodeShape','reserved key')
    m={k:v for k,v in x.items() if v is not None}
    require(all(isinstance(k,str) for k in m),'InvalidNodeShape','keys')
    for k in LABELS:
        if k in m: checked_unicode(m[k])
    if 'mergePolicy' in m: require(m['mergePolicy'] in ('positional','append-only'),'InvalidNodeShape','mergePolicy')
    ordinary=set(m)-RESERVED
    require(sum(('value' in m,'items' in m,bool(ordinary)))<=1,'InvalidNodeShape','payload kinds')
    for k in (TYPES|REFERENCE_METADATA)&set(m):
        if mode=='direct': require(isinstance(m[k],dict) and set(m[k])=={'blueId'} or isinstance(m[k],Ref),'InvalidBlueIdInput','type position')
        require(not isinstance(m[k],str),'UnknownTypeAlias')
        with error_scope(c,pointer(c.diagnostic_path,k)):
            n=normalize(m[k],c,'exact',symbolic)
        if contains_local(n): m[k]=n
        else:
            c.remember(n); m[k]=Ref(identity(n))
    if 'value' in m:
        t=m.get('type'); tid=t.id if isinstance(t,Ref) else ('symbolic' if t is not None else None)
        with error_scope(c):
            try: tid,val=encode_scalar(tid,m['value'],c.limits)
            except Failure as error:
                if error.expected is None: error.expected=diagnostic_value(tid=tid,c=c,kind='scalar')
                if error.actual is None: error.actual=diagnostic_value(m['value'])
                raise
        if t is None: m['type']=Ref(tid)
        m['value']=val
    for k in list(m):
        if k in TYPES|LITERALS|{'mergePolicy'}: continue
        if k=='items':
            require(isinstance(m[k],(list,tuple)),'InvalidNodeShape','items')
            values=[]
            for i,v in enumerate(m[k]):
                with error_scope(c,pointer(pointer(c.diagnostic_path,'items'),i)):
                    values.append(normalize(v,c,mode,symbolic))
            m[k]=tuple(values)
        else:
            with error_scope(c,pointer(c.diagnostic_path,k)):
                m[k]=normalize(m[k],c,mode,symbolic)
    n=node(m)
    if not contains_local(n): c.remember(n)
    return n

HOLE = node({'$empty':scalar('Boolean',True)})
HOLE_ID = identity(HOLE)
def is_hole(n): return identity(n)==HOLE_ID

# === A04: Lossless export and verified graph access ===
def export_tree(n):
    if isinstance(n,Ref): return {'blueId':n.id}
    if isinstance(n,Local): return {'blueId':'this#'+str(n.index)}
    m={}
    for k,v in n.fields:
        if k in LITERALS|{'mergePolicy'}: m[k]=v
        elif k=='items': m[k]=[export_tree(a) for a in v]
        else: m[k]=export_tree(v)
    return m['items'] if set(m)=={'items'} else m

def wire_text(x):
    if isinstance(x,NumberToken): return x.text
    if type(x) is float:
        t=number_text(x)
        return t+'.0' if not any(c in t for c in '.eE') else t
    if isinstance(x,list): return '['+','.join(wire_text(a) for a in x)+']'
    if isinstance(x,tuple): return '['+','.join(wire_text(a) for a in x)+']'
    if isinstance(x,dict): return '{'+','.join(json_quote(k)+':'+wire_text(x[k]) for k in ordered(x))+'}'
    return canonical_text(x)

def canonicalize_node(n,c):
    if isinstance(n,Ref): return n
    require(isinstance(n,Node),'InvalidExactNode')
    m={}
    for k,v in n.fields:
        if k in LITERALS|{'mergePolicy'}: m[k]=v
        elif k in TYPES:
            c.remember(v);m[k]=Ref(identity(v))
        elif k=='items': m[k]=tuple(canonicalize_node(a,c) for a in v)
        else: m[k]=canonicalize_node(v,c)
    return node(m)


def export_exact(n,c=None):
    c=c or Context()
    n=canonicalize_node(n,c)
    text=wire_text(export_tree(n))
    m=normalize(parse(text,limits=(c.limits if c else None)),Context(limits=(c.limits if c else Limits())))
    require(identity(m)==identity(n),'InternalError','export changed identity')
    return text

def open_exact(n,c):
    c.step()
    if isinstance(n,Node): return n
    require(isinstance(n,Ref),'InvalidExactNode')
    final_id(n.id)
    if n.body is not None: return n.body
    if n.id in c.bodies: return c.bodies[n.id]
    require(within(len(c.demands)+1,c.limits.fetches),'OperationLimitExceeded','provider count')
    c.demands.append(n.id)
    if n.id not in c.provider: raise Failure('ProviderUnavailable',n.id)
    response=c.provider[n.id]
    if isinstance(response,dict) and 'partialObject' in response:
        require(set(response)=={'partialObject','completeDirectManifest'},'InvalidProviderMode','manifest envelope')
        require(type(response['completeDirectManifest']) is bool,'InvalidProviderMode','manifest completeness')
        if not response['completeDirectManifest']:
            raise Failure('ProviderUnavailable',n.id)
        response={'text':wire_text(response['partialObject']),'mode':'exact'}
    if isinstance(response,dict) and 'outcome' in response:
        require(set(response)=={'outcome'},'InvalidProviderMode','outcome envelope')
        if response['outcome'] in ('NotFound','Unavailable'):
            raise Failure('ProviderUnavailable',n.id)
        if response['outcome']=='InvalidEvidence': raise Failure('ProviderBlueIdMismatch',n.id)
        raise Failure('InvalidProviderMode','unknown provider outcome')
    if '#' in n.id:
        require(isinstance(response,dict) and 'proof' in response and set(response)<={'proof','body'},'InvalidCyclicProof')
        h=verify_member(n.id,response['proof'],response.get('body'),c)
        return h.body
    if isinstance(response,Node): body=response
    else:
        require(isinstance(response,dict) and 'text' in response and
                set(response)<={'text','format','mode','environment'},'InvalidProviderMode','content envelope')
        mode=response.get('mode','exact')
        require(mode in ('exact','source'),'InvalidProviderMode','content role')
        try:
            raw=parse(response['text'],response.get('format','json'),c.limits)
        except Failure as failure:
            if failure.category in ('OperationLimitExceeded','ProviderUnavailable'): raise
            raise Failure('ProviderBlueIdMismatch',n.id) from failure
        if mode=='source':
            expected={'specification':'1.0','aliases':c.aliases,'directiveAliases':c.directive_aliases}
            require(response.get('environment')==expected,'InvalidProviderMode','unbound Source environment')
            body=prepare_source(raw,c)
        else:
            require('environment' not in response,'InvalidProviderMode','environment on exact body')
            try:
                body=normalize(raw,c)
            except Failure as failure:
                if failure.category in ('OperationLimitExceeded','ProviderUnavailable'): raise
                raise Failure('ProviderBlueIdMismatch',n.id) from failure
    require(isinstance(body,Node) and identity(body)==n.id,'ProviderBlueIdMismatch',n.id)
    c.bodies[n.id]=body
    return body

def path_parts(p):
    require(isinstance(p,str) and (p=='' or p.startswith('/')),'InvalidPath')
    if not p: return []
    result=[]
    for s in p[1:].split('/'):
        require(not re.search(r'~(?![01])',s),'InvalidPath')
        result.append(s.replace('~1','/').replace('~0','~'))
    return result

def exact_at(n,parts,c):
    if not parts: return n
    body=open_exact(n,c); k=parts[0]
    if k=='blueId': return ABSENT
    v=body.get(k)
    if v is ABSENT: return ABSENT
    if k=='items':
        if len(parts)==1: return tuple(v)
        require(INDEX.fullmatch(parts[1]),'InvalidPath','list index')
        i=int(parts[1]); return ABSENT if i>=len(v) else exact_at(v[i],parts[2:],c)
    if k in LITERALS|{'mergePolicy'}: return v if len(parts)==1 else ABSENT
    return exact_at(v,parts[1:],c)

def map_at(n,parts,c,fn):
    if not parts: return fn(n)
    b=open_exact(n,c); k=parts[0]; v=b.get(k)
    require(v is not ABSENT and k!='blueId','PathAbsent')
    if k=='items':
        require(len(parts)>=2 and INDEX.fullmatch(parts[1]),'InvalidPath')
        i=int(parts[1]); require(i<len(v),'PathAbsent')
        a=list(v); a[i]=map_at(a[i],parts[2:],c,fn); b=changed(b,items=tuple(a))
    else:
        require(k not in LITERALS|{'mergePolicy'},'InvalidPath','not a node position')
        b=changed(b,**{k:map_at(v,parts[1:],c,fn)})
    return Ref(n.id,b) if isinstance(n,Ref) and '#' in n.id else b

def expand(n,paths,c):
    out=n
    def reveal(x):
        b=open_exact(x,c)
        return Ref(x.id,b) if isinstance(x,Ref) and '#' in x.id else b
    for p in sorted(set(paths),key=lambda p:(len(path_parts(p)),key_order(p))):
        out=map_at(out,path_parts(p),c,reveal)
    require(identity(out)==identity(n),'InternalError','expansion')
    return out

def collapse(n,paths,c):
    out=n
    for p in sorted(set(paths),key=lambda p:(-len(path_parts(p)),key_order(p))):
        out=map_at(out,path_parts(p),c,lambda a:Ref(identity(a)))
    require(identity(out)==identity(n),'InternalError','collapse')
    return out


def split_fragments(exact,paths,c):
    """Split selected nodes and their structural ancestors, preserving exact IDs."""
    selected={()}
    for path in paths:
        parts=tuple(path_parts(path))
        target=exact_at(exact,parts,c)
        require(isinstance(target,(Node,Ref)),'InvalidPath','fragment node')
        for end in range(1,len(parts)+1):
            prefix=parts[:end]
            value=exact_at(exact,prefix,c)
            if isinstance(value,(Node,Ref)): selected.add(prefix)
    out=exact;fragments={}
    for parts in sorted(selected,key=lambda p:(-len(p),tuple(key_order(x) for x in p))):
        value=exact_at(out,parts,c)
        require(isinstance(value,(Node,Ref)),'InvalidPath','fragment path')
        rid=identity(value)
        # A selected reference is a demand, not a reason to silently omit a cut.
        # Cyclic bodies stay indexed by the member ID; the SDK also exports proofs.
        fragments[rid]=open_exact(value,c)
        if parts: out=map_at(out,parts,c,lambda old:Ref(identity(old)))
    require(identity(out)==identity(exact),'InternalError','fragment identity')
    return out,dict(sorted(fragments.items()))

# === A05: Constraint records, exact predicates and monotone schema refinement ===
SCHEMA_KEYS = frozenset(('required','minItems','maxItems','uniqueItems','minFields','maxFields',
                        'minimum','maximum','exclusiveMinimum','exclusiveMaximum','multipleOf',
                        'minLength','maxLength','enum'))
COUNT_PAIRS = (('minItems','maxItems'),('minFields','maxFields'),('minLength','maxLength'))
COUNT_KEYS = frozenset(k for p in COUNT_PAIRS for k in p)
NUMERIC_KEYS = frozenset(('minimum','maximum','exclusiveMinimum','exclusiveMaximum','multipleOf'))

@dataclass(frozen=True)
class Bound:
    value: Fraction
    exclusive: bool

@dataclass
class Constraint:
    required: bool|None = None
    unique: bool|None = None
    counts: dict = field(default_factory=dict)
    lower: Bound|None = None
    upper: Bound|None = None
    lower_facets: tuple = ()       # authored endpoints, before effective conjunction
    upper_facets: tuple = ()
    multiple: Fraction|None = None
    enum: tuple|None = None   # conjunction of finite alternative groups
    enum_values: dict = field(default_factory=dict)

def stronger_lower(a,b):
    if a is None: return b
    if b is None: return a
    return max((a,b),key=lambda x:(x.value,x.exclusive))
def stronger_upper(a,b):
    if a is None: return b
    if b is None: return a
    return min((a,b),key=lambda x:(x.value,not x.exclusive))
def lower_implies(a,b):
    return b is None or (a is not None and (a.value>b.value or
           a.value==b.value and (a.exclusive or not b.exclusive)))
def upper_implies(a,b):
    return b is None or (a is not None and (a.value<b.value or
           a.value==b.value and (a.exclusive or not b.exclusive)))
def lcm_int(a,b): return abs(a//math.gcd(a,b)*b)
def lcm_rational(a,b):
    return Fraction(lcm_int(a.numerator,b.numerator),math.gcd(a.denominator,b.denominator))

def scalar_description(n,c):
    """Read a schema operand only after certifying its own completed value."""
    rid=identity(n)
    if rid in c.operand_descriptions: return c.operand_descriptions[rid]
    require(rid not in c.operand_active,'SchemaVocabularyError','recursive schema operand')
    require(within(len(c.operand_active)+1,c.limits.depth),'OperationLimitExceeded','schema operand depth')
    c.operand_active.add(rid)
    try:
        result=certified_scalar_description(n,c)
        c.operand_descriptions[rid]=result
        return result
    finally:
        c.operand_active.remove(rid)


def certified_scalar_description(n,c):
    n=open_exact(n,c)
    require(n.kind() in ('scalar','none'),'SchemaVocabularyError','scalar operand')
    own=n.get('type'); tid=own.id if isinstance(own,Ref) else None
    require(tid is not None,'SchemaVocabularyError','scalar type required')
    core=domain_core(tid,c)
    require(core in ('Text','Integer','Double','Boolean'),'SchemaVocabularyError','scalar domain')
    values=[]
    if n.has('value'): values.append(n.get('value'))
    for t in ancestry(tid,c):
        if t in CORE_NAME: break
        b=open_exact(Ref(t),c)
        require(b.kind() in ('none','scalar'),'SchemaVocabularyError','scalar ancestry')
        if b.has('value'): values.append(b.get('value'))
    require(values,'SchemaVocabularyError','scalar payload required')
    vals=[scalar_effective(v,core) for v in values]
    require(all(type(v)==type(vals[0]) and v==vals[0] for v in vals),'FixedValueConflict','scalar operand')
    certify(n,c,'value')
    return tid,core,vals[0]

def scalar_key(type_id,core,value):
    # Labels do not participate in scalar predicate equality; the exact type does.
    wire = integer_text(value) if core=='Integer' and abs(value)>SAFE else value
    return canonical_text({'type':{'blueId':type_id},'value':wire})

def primitive_key(core,value):
    v=integer_text(value) if core=='Integer' and abs(value)>SAFE else value
    return canonical_text({'core':core,'value':v})

def enum_accepts(entry,type_id,core,value,c):
    t,k,v=entry
    return primitive_key(k,v)==primitive_key(core,value) and type_subtype(type_id,t,c)

def enum_groups_imply(a,b,c):
    if b.enum is None: return True
    if a.enum is None: return False
    c=c or Context()
    for parent_group in b.enum:
        covered=False
        for child_group in a.enum:
            if all(any(enum_accepts(b.enum_values[p],*a.enum_values[q],c)
                       for p in parent_group) for q in child_group):
                covered=True;break
        if not covered: return False
    return True


def read_schema(n,c):
    if n is ABSENT: return Constraint()
    n=open_exact(n,c)
    require(n.kind()=='object' and set(n.keys())<=SCHEMA_KEYS,'SchemaVocabularyError','schema map')
    s=Constraint()
    for k,v in n.fields:
        if k=='enum':
            a=open_exact(v,c)
            require(a.kind()=='list' and a.keys()==('items',),'SchemaVocabularyError','enum sequence')
            vals={}
            for i,item in enumerate(a.get('items')):
                with error_scope(c,pointer(pointer(pointer(c.diagnostic_path,k),'items'),i)):
                    tid,core,value=scalar_description(item,c)
                key=scalar_key(tid,core,value); vals[key]=(tid,core,value)
            require(vals,'SchemaViolation','empty enum')
            s.enum=(frozenset(vals),); s.enum_values=vals
        elif k in ('required','uniqueItems'):
            with error_scope(c,pointer(c.diagnostic_path,k)):
                _,core,value=scalar_description(v,c)
            require(core=='Boolean' and type(value) is bool,'SchemaVocabularyError',k)
            if k=='required': s.required=value
            else: s.unique=value
        elif k in COUNT_KEYS:
            with error_scope(c,pointer(c.diagnostic_path,k)):
                _,core,value=scalar_description(v,c)
            require(core=='Integer' and type(value) is int and 0<=value<=SAFE,'SchemaVocabularyError',k)
            s.counts[k]=value
        else:
            with error_scope(c,pointer(c.diagnostic_path,k)):
                _,core,value=scalar_description(v,c)
            require(core in ('Integer','Double'),'SchemaVocabularyError',k)
            q=rational(value)
            if k=='multipleOf':
                require(q>0,'SchemaVocabularyError','positive multipleOf');s.multiple=q
            elif k in ('minimum','exclusiveMinimum'):
                b=Bound(q,k.startswith('exclusive'));s.lower_facets+=(b,);s.lower=stronger_lower(s.lower,b)
            else:
                b=Bound(q,k.startswith('exclusive'));s.upper_facets+=(b,);s.upper=stronger_upper(s.upper,b)
    check_consistency(s)
    return s

def check_consistency(s):
    for lo,hi in COUNT_PAIRS:
        if lo in s.counts and hi in s.counts:
            require(s.counts[lo]<=s.counts[hi],'SchemaViolation',lo+' > '+hi)
    if s.lower is not None and s.upper is not None:
        require(s.lower.value<s.upper.value or
                s.lower.value==s.upper.value and not (s.lower.exclusive or s.upper.exclusive),
                'SchemaViolation','empty interval')
    require(s.multiple is None or s.multiple>0,'SchemaVocabularyError','multipleOf')
    require(s.enum is None or all(len(g)>0 for g in s.enum),'SchemaViolation','empty enum')


def check_schema_narrowing(parent,authored,c=None):
    # Omission inherits. An explicitly weaker replacement is an error.
    if parent.required is True and authored.required is not None:
        require(authored.required is True,'SchemaWeakening','required',keyword='required',expected={'value':True},actual={'value':authored.required})
    if parent.unique is True and authored.unique is not None:
        require(authored.unique is True,'SchemaWeakening','uniqueItems',keyword='uniqueItems',expected={'value':True},actual={'value':authored.unique})
    for lo,hi in COUNT_PAIRS:
        if lo in parent.counts and lo in authored.counts:
            require(authored.counts[lo]>=parent.counts[lo],'SchemaWeakening',lo,keyword=lo,expected={'value':parent.counts[lo]},actual={'value':authored.counts[lo]})
        if hi in parent.counts and hi in authored.counts:
            require(authored.counts[hi]<=parent.counts[hi],'SchemaWeakening',hi,keyword=hi,expected={'value':parent.counts[hi]},actual={'value':authored.counts[hi]})
    for bound in authored.lower_facets or (() if authored.lower is None else (authored.lower,)):
        require(lower_implies(bound,parent.lower),'SchemaWeakening','lower bound',
            keyword='exclusiveMinimum' if bound.exclusive else 'minimum',
            expected={'value':diagnostic_literal(parent.lower.value),'exclusive':parent.lower.exclusive} if parent.lower else {},
            actual={'value':diagnostic_literal(bound.value),'exclusive':bound.exclusive})
    for bound in authored.upper_facets or (() if authored.upper is None else (authored.upper,)):
        require(upper_implies(bound,parent.upper),'SchemaWeakening','upper bound',
            keyword='exclusiveMaximum' if bound.exclusive else 'maximum',
            expected={'value':diagnostic_literal(parent.upper.value),'exclusive':parent.upper.exclusive} if parent.upper else {},
            actual={'value':diagnostic_literal(bound.value),'exclusive':bound.exclusive})
    if authored.multiple is not None and parent.multiple is not None:
        require((authored.multiple/parent.multiple).denominator==1,'SchemaWeakening','multipleOf',keyword='multipleOf',
                expected={'value':diagnostic_literal(parent.multiple)},actual={'value':diagnostic_literal(authored.multiple)})
    if authored.enum is not None and parent.enum is not None:
        require(enum_groups_imply(authored,parent,c),'SchemaWeakening','enum')


def conjoin_schema(a,b):
    # This combines independently applicable obligations; it is not override admission.
    s=Constraint()
    s.required=None if a.required is None and b.required is None else bool(a.required or b.required)
    s.unique=None if a.unique is None and b.unique is None else bool(a.unique or b.unique)
    for lo,hi in COUNT_PAIRS:
        vs=[z.counts[lo] for z in (a,b) if lo in z.counts]
        if vs: s.counts[lo]=max(vs)
        vs=[z.counts[hi] for z in (a,b) if hi in z.counts]
        if vs: s.counts[hi]=min(vs)
    s.lower=stronger_lower(a.lower,b.lower); s.upper=stronger_upper(a.upper,b.upper)
    s.multiple=lcm_rational(a.multiple,b.multiple) if a.multiple is not None and b.multiple is not None else a.multiple or b.multiple
    groups=tuple(dict.fromkeys((a.enum or ())+(b.enum or ())))
    s.enum=groups or None
    s.enum_values={**a.enum_values,**b.enum_values}
    if groups:
        # A primitive payload mismatch proves emptiness without guessing domain overlap.
        common=None
        for g in groups:
            payloads={primitive_key(s.enum_values[k][1],s.enum_values[k][2]) for k in g}
            common=payloads if common is None else common&payloads
        require(common,'SchemaViolation','enum payload intersection is empty')
    check_consistency(s)
    return s

def refine_schema(parent,authored,c=None):
    check_schema_narrowing(parent,authored,c)
    return conjoin_schema(parent,authored)


def schema_implies(candidate,parent,c=None):
    # Complete procedural refinement relation for this vocabulary, facet by facet.
    if parent.required and not candidate.required: return False
    if parent.unique and not candidate.unique: return False
    for lo,hi in COUNT_PAIRS:
        if lo in parent.counts and candidate.counts.get(lo,0)<parent.counts[lo]: return False
        if hi in parent.counts and candidate.counts.get(hi,math.inf)>parent.counts[hi]: return False
    if not lower_implies(candidate.lower,parent.lower) or not upper_implies(candidate.upper,parent.upper): return False
    if parent.multiple is not None:
        if candidate.multiple is None or (candidate.multiple/parent.multiple).denominator!=1: return False
    if parent.enum is not None and not enum_groups_imply(candidate,parent,c): return False
    return True


def schema_kinds(s):
    groups=[]
    if s.lower is not None or s.upper is not None or s.multiple is not None: groups.append({'Integer','Double'})
    if any(k in s.counts for k in ('minLength','maxLength')): groups.append({'Text'})
    if any(k in s.counts for k in ('minItems','maxItems')) or s.unique is not None: groups.append({'List'})
    if any(k in s.counts for k in ('minFields','maxFields')): groups.append({'Dictionary'})
    if s.enum is not None:
        for group in s.enum: groups.append({s.enum_values[k][1] for k in group})
    return set.intersection(*groups) if groups else None


def validate_schema(h,present,goal,is_root,c):
    s=h.constraints; check_consistency(s)
    applicable=schema_kinds(s)
    known=h.core or {'object':'Dictionary','list':'List'}.get(h.kind)
    if known is None and h.kind=='scalar' and h.value is not ABSENT:
        known={bool:'Boolean',int:'Integer',float:'Double',str:'Text'}.get(type(h.value))
    if applicable is not None:
        require(known is None or known in applicable,'SchemaViolation','wrong payload kind')
        require(bool(applicable),'SchemaViolation','incompatible keyword kinds')
    if goal=='definition':
        if applicable is None: return
        if not concrete(h,c): return
    if not is_root and s.required and not present:
        raise Failure('SchemaViolation','required',keyword='required',expected={'present':True},actual={'present':False})
    if not present: return
    if goal=='value':
        if h.kind=='scalar': require(h.value is not ABSENT,'SchemaViolation','scalar payload required',
                    expected={**diagnostic_value(tid=h.type_id or CORE.get(h.core),c=c,kind='scalar'),'present':True},
                    actual=diagnostic_value())
        if h.kind=='list': require(h.items is not None,'SchemaViolation','list payload required',
                    expected={**diagnostic_value(tid=h.type_id or CORE.get(h.core),c=c,kind='List'),'present':True},
                    actual=diagnostic_value())
    dependent=applicable is not None
    if dependent: require(h.kind!='none' and (h.kind!='scalar' or h.value is not ABSENT),'SchemaViolation','payload required',
                    expected={**diagnostic_value(tid=h.type_id or CORE.get(h.core),c=c,kind=h.kind),'present':True},actual=diagnostic_value())
    if h.kind=='scalar' and h.value is not ABSENT:
        v=h.value
        if known in ('Integer','Double'):
            q=rational(v)
            if s.lower: require(q>s.lower.value or q==s.lower.value and not s.lower.exclusive,'SchemaViolation','lower bound',
                    keyword='exclusiveMinimum' if s.lower.exclusive else 'minimum',
                    expected={'value':diagnostic_literal(s.lower.value)},actual=diagnostic_value(v,h.type_id,c))
            if s.upper: require(q<s.upper.value or q==s.upper.value and not s.upper.exclusive,'SchemaViolation','upper bound',
                    keyword='exclusiveMaximum' if s.upper.exclusive else 'maximum',
                    expected={'value':diagnostic_literal(s.upper.value)},actual=diagnostic_value(v,h.type_id,c))
            if s.multiple is not None: require((q/s.multiple).denominator==1,'SchemaViolation','multipleOf',
                    keyword='multipleOf',expected={'value':diagnostic_literal(s.multiple)},actual=diagnostic_value(v,h.type_id,c))
        if known=='Text': check_count(s,'minLength','maxLength',len(v))
        if s.enum is not None:
            require(all(any(enum_accepts(s.enum_values[k],h.type_id or CORE[known],known,v,c) for k in g) for g in s.enum),'SchemaViolation','enum')
    if h.kind=='list' and h.items is not None:
        check_count(s,'minItems','maxItems',len(h.items))
        if s.unique:
            ids=[]
            for i,a in enumerate(h.items):
                with error_scope(c,pointer(pointer(c.diagnostic_path,'items'),i)):
                    ids.append(recipe_exact_id(a,c))
            require(len(ids)==len(set(ids)),'SchemaViolation','uniqueItems',keyword='uniqueItems',
                    expected={'value':True},actual={'value':False})
    if h.kind=='object':
        count=0
        for k,r in h.fields.items():
            with error_scope(c,pointer(c.diagnostic_path,k)):
                count+=bool(present_recipe(r,c))
        check_count(s,'minFields','maxFields',count)


def check_count(s,lo,hi,n):
    keyword=lo if n<s.counts.get(lo,0) else hi
    require(n>=s.counts.get(lo,0) and n<=s.counts.get(hi,math.inf),'SchemaViolation',lo+'/'+hi,
            keyword=keyword,expected={'value':s.counts.get(keyword)},actual={'value':n})


def describe_constraints(s):
    def q(x): return {'numerator':integer_text(x.numerator),'denominator':integer_text(x.denominator)}
    out={}
    if s.required is not None: out['required']=s.required
    if s.unique is not None: out['uniqueItems']=s.unique
    out.update(s.counts)
    if s.lower: out['lower']={**q(s.lower.value),'exclusive':s.lower.exclusive}
    if s.upper: out['upper']={**q(s.upper.value),'exclusive':s.upper.exclusive}
    if s.multiple is not None: out['multipleOf']=q(s.multiple)
    if s.enum is not None: out['enumAll']=[[json.loads(k) for k in sorted(g)] for g in sorted(s.enum,key=lambda g:tuple(sorted(g))) ]
    return out

# === A06: Declaration recipes, type ancestry and effective head resolution ===
@dataclass(frozen=True)
class Recipe:
    parts: tuple
    requirements: tuple = ()        # exact type identities required by a container
    def key(self):
        return (tuple(identity(x) for x in self.parts),self.requirements)

@dataclass
class Head:
    type_id: str|None = None
    core: str|None = None
    kind: str = 'none'
    labels: dict = field(default_factory=dict)
    specification: Ref|None = None
    constraints: Constraint = field(default_factory=Constraint)
    authored_schema: Constraint|None = None
    policy: str|None = None
    item_type: str|None = None
    key_type: str|None = None
    value_type: str|None = None
    value: Any = ABSENT
    fields: dict = field(default_factory=dict)
    items: tuple|None = None
    contracts: Any = None
    empty_object: bool = False
    origin: Any = None
    origins: tuple = ()


def recipe(*parts,requirements=()):
    # Repeating an identical contribution does not duplicate content or obligations.
    flat=[]
    req=list(requirements)
    for p in parts:
        if isinstance(p,Recipe): flat.extend(p.parts);req.extend(p.requirements)
        elif p is not None: flat.append(p)
    seen=set(); keep=[]
    for n in reversed(flat):
        k=identity(n)
        if k not in seen: keep.append(n);seen.add(k)
    return Recipe(tuple(reversed(keep)),tuple(dict.fromkeys(req)))


def copy_head(h):
    # Exact nodes/recipes are immutable; never deepcopy the ABSENT sentinel.
    return replace(h,labels=dict(h.labels),fields=dict(h.fields),
                   constraints=copy.deepcopy(h.constraints))


def ancestry(t,c):
    out=[];seen=set()
    while t is not None:
        require(t not in seen,'TypeCycle',t)
        seen.add(t);out.append(t)
        if t in CORE_NAME: break
        n=open_exact(Ref(t),c)
        r=n.get('type')
        t=r.id if isinstance(r,Ref) else None
    return out


def domain_core(t,c):
    if t is None: return None
    a=ancestry(t,c)
    if a[-1] in CORE_NAME: return CORE_NAME[a[-1]]
    last=open_exact(Ref(a[-1]),c)
    return {'object':'Dictionary','list':'List'}.get(last.kind())


def type_plan(t,c):
    # Prepare an ordinary parent chain bottom-up, without using Python's call
    # stack as a type-depth ceiling. Cross-field/schema recursion retains the
    # existing active-plan cycle checks in _type_plan_one.
    chain=[];seen=set();current=t
    while current not in c.plans:
        require(current not in seen and current not in c.plan_active,'TypeCycle',current)
        require(within(len(c.plan_active)+len(chain)+1,c.limits.depth),'OperationLimitExceeded','type depth')
        seen.add(current);chain.append(current)
        if current in CORE_NAME:break
        parent=open_exact(Ref(current),c).get('type')
        if not isinstance(parent,Ref):break
        current=parent.id
    for current in reversed(chain):_type_plan_one(current,c)
    c.step()
    return copy_head(c.plans[t])


def _type_plan_one(t,c):
    c.step()
    if t in c.plans: return copy_head(c.plans[t])
    require(t not in c.plan_active,'TypeCycle',t)
    require(within(len(c.plan_active)+1,c.limits.depth),'OperationLimitExceeded','type depth')
    c.plan_active.append(t)
    try:
        if t in CORE_NAME:
            core=CORE_NAME[t]
            h=Head(core=core,kind=('list' if core=='List' else 'object' if core=='Dictionary' else 'scalar'))
        else:
            h=single_head(open_exact(Ref(t),c),c)
        c.plans[t]=copy_head(h)
        try:
            if schema_kinds(h.constraints) is not None:
                validate_schema(h,True,'definition',True,c)
        except Exception:
            c.plans.clear()
            raise
        return h
    finally: c.plan_active.pop()


def as_requirement(t,c):
    h=type_plan(t,c)
    h.labels={}; h.specification=None; h.type_id=t; h.authored_schema=None
    return h


def scalar_effective(v,core):
    if core=='Integer':
        if isinstance(v,str):
            require(INTEGER_TEXT.fullmatch(v),'TypeCompatibilityViolation','Integer text')
            return parse_integer(v)
        if type(v) is float:
            require(math.isfinite(v) and Fraction(v).denominator==1,'TypeCompatibilityViolation','Integer value')
            return Fraction(v).numerator
        require(type(v) is int,'TypeCompatibilityViolation','Integer value')
        return v
    if core=='Double':
        require(type(v) in (int,float),'TypeCompatibilityViolation','Double value')
        f=round_binary64(Fraction(v)) if type(v) is int else v
        require(math.isfinite(f),'InvalidScalar'); return f
    if core=='Text': require(type(v) is str,'TypeCompatibilityViolation','Text value')
    if core=='Boolean': require(type(v) is bool,'TypeCompatibilityViolation','Boolean value')
    return v


def choose_type(parent,child,value,c):
    if parent is None: return child
    if child is None or child==parent: return parent
    pc=domain_core(parent,c);cc=domain_core(child,c)
    # Primitive spelling of a value may receive a narrower contextual interpretation.
    # This is not a subtype declaration and never rewrites its exact origin.
    if value is not ABSENT and child in CORE_NAME:
        if pc==cc: return parent
        if pc=='Integer' and cc=='Text' and type(value) is str and INTEGER_TEXT.fullmatch(value): return parent
    require(type_subtype(child,parent,c),'TypeCompatibilityViolation',str(child)+' is not a subtype of '+str(parent),
            expected=diagnostic_value(tid=parent,c=c), actual=diagnostic_value(value,child,c))
    return child


def single_head(n,c):
    c.step(); n=open_exact(n,c)
    t=n.get('type');tid=t.id if isinstance(t,Ref) else None
    inherited=as_requirement(tid,c) if tid else Head()
    h=Head(type_id=tid,core=domain_core(tid,c) if tid else {'object':'Dictionary','list':'List'}.get(n.kind()),kind=n.kind(),origin=n,origins=(n,),
           labels={k:n.get(k) for k in LABELS if n.has(k)},
           specification=None if n.get(SPECIFICATION) is ABSENT else n.get(SPECIFICATION),
           policy=None if n.get('mergePolicy') is ABSENT else n.get('mergePolicy'),
           empty_object=(n.kind()=='object' and not n.ordinary()))
    for field_name,attr in (('itemType','item_type'),('keyType','key_type'),('valueType','value_type')):
        x=n.get(field_name)
        if isinstance(x,Ref): setattr(h,attr,x.id)
    if n.has('schema'):
        with error_scope(c,pointer(c.diagnostic_path,'schema')):
            h.authored_schema=read_schema(n.get('schema'),c)
        h.constraints=h.authored_schema
    if n.has('value'):
        try: h.value=scalar_effective(n.get('value'),h.core)
        except Failure as error:
            error.expected=error.expected or diagnostic_value(tid=tid,c=c)
            error.actual=error.actual or diagnostic_value(n.get('value'),c=c)
            raise
    h.fields={k:recipe(n.get(k)) for k in n.ordinary()}
    if n.has('items'): h.items=tuple(recipe(x) for x in n.get('items'))
    if n.has('contracts'):
        h.contracts=recipe(n.get('contracts'))
    return merge_heads(inherited,h,c)


def concrete_node(n,c,active=None,type_depth=0):
    # Presence is reachability of an actual payload, or a cycle made solely of
    # ordinary-value edges. Type-declaration cycles do not manufacture values.
    # A finite graph walk avoids exponential unfolding of recursive repositories.
    root=identity(n)
    if root in c.presence_cache: return c.presence_cache[root]
    pending=[n]; seen=set(); ordinary={}
    while pending:
        value=pending.pop(); key=identity(value)
        if key in seen: continue
        c.step(); seen.add(key)
        if key in c.presence_cache:
            if c.presence_cache[key]: c.presence_cache[root]=True; return True
            ordinary[key]=(); continue
        body=open_exact(value,c)
        if body.has('value') or body.has('items') or not body.fields:
            c.presence_cache[root]=True; return True
        children=[body.get(k) for k in body.ordinary()]
        ordinary[key]=tuple(identity(x) for x in children)
        pending.extend(children)
        parent=body.get('type')
        if isinstance(parent,Ref) and parent.id not in CORE_NAME: pending.append(parent)
    # Remove all acyclic ordinary-edge vertices. Remaining vertices contain an
    # ordinary-value cycle, equivalent to the former same-type-depth back edge.
    indegree={key:0 for key in seen}
    for targets in ordinary.values():
        for key in targets: indegree[key]+=1
    queue=[key for key,value in indegree.items() if value==0]; removed=0
    while queue:
        key=queue.pop(); removed+=1
        for target in ordinary.get(key,()):
            indegree[target]-=1
            if indegree[target]==0: queue.append(target)
    result=removed<len(seen)
    c.presence_cache[root]=result
    return result


def concrete(h,c,seen=None):
    return any(concrete_node(n,c) for n in h.origins)


def present_recipe(r,c): return concrete(head(r,c),c)


def head(r,c):
    c.step()
    if not isinstance(r,Recipe): r=recipe(r)
    key=r.key()
    cacheable=not c.plan_active and not getattr(c,'subtype_active',()) and not c.operand_active
    if cacheable and key in c.heads: return copy_head(c.heads[key])
    h=Head()
    for t in r.requirements:
        h=merge_heads(h,as_requirement(t,c),c)
    for n in r.parts: h=merge_heads(h,single_head(n,c),c)
    if cacheable: c.heads[key]=copy_head(h)
    return h


def narrow_type_slot(p,q,c):
    if q is None: return p
    if p is None or p==q: return q
    require(type_subtype(q,p,c),'TypeCompatibilityViolation','collection type widening',
            expected=diagnostic_value(tid=p,c=c),actual=diagnostic_value(tid=q,c=c))
    return q


def merge_heads(p,q,c):
    c.step(); out=copy_head(p)
    out.type_id=choose_type(p.type_id,q.type_id,q.value,c)
    out.core=domain_core(out.type_id,c) if out.type_id else p.core or q.core
    if p.core is not None and q.core is not None and p.core!=q.core:
        require(q.value is not ABSENT and p.core=='Integer' and q.core=='Text',
                'TypeCompatibilityViolation','nominal core mismatch')
    out.item_type=narrow_type_slot(p.item_type,q.item_type,c)
    out.key_type=narrow_type_slot(p.key_type,q.key_type,c)
    out.value_type=narrow_type_slot(p.value_type,q.value_type,c)
    if q.authored_schema is not None: check_schema_narrowing(p.constraints,q.authored_schema,c)
    out.constraints=conjoin_schema(p.constraints,q.constraints)
    out.authored_schema=q.authored_schema
    if p.policy is not None and q.policy is not None: require(p.policy==q.policy,'TypeCompatibilityViolation','mergePolicy')
    out.policy=q.policy or p.policy
    for k,v in q.labels.items():
        if k in p.labels and p.labels[k]!=v:
            require(not concrete(p,c),'FixedValueConflict',k)
        out.labels[k]=v
    if q.specification is not None:
        if p.specification is not None and p.specification != q.specification:
            require(not concrete(p,c),'FixedValueConflict',SPECIFICATION)
        out.specification=q.specification
    if q.kind=='none': pass
    elif p.kind=='none':
        out.kind=q.kind;out.value=q.value;out.fields=dict(q.fields);out.items=q.items;out.empty_object=q.empty_object
    elif p.kind!=q.kind:
        # A core declaration has a required kind but no payload; kind remains binding.
        raise Failure('TypeCompatibilityViolation','payload kind')
    elif q.kind=='scalar':
        pv=scalar_effective(p.value,out.core) if p.value is not ABSENT else ABSENT
        qv=scalar_effective(q.value,out.core) if q.value is not ABSENT else ABSENT
        if pv is not ABSENT and qv is not ABSENT:
            require(type(pv)==type(qv) and pv==qv,'FixedValueConflict','scalar',
                    expected=diagnostic_value(pv,p.type_id or CORE.get(p.core),c),
                    actual=diagnostic_value(qv,q.type_id or CORE.get(q.core),c))
        out.value=qv if qv is not ABSENT else pv
    elif q.kind=='object':
        out.fields={k:recipe(p.fields.get(k),q.fields.get(k)) for k in ordered(set(p.fields)|set(q.fields))}
        out.empty_object=p.empty_object or q.empty_object
    elif q.kind=='list':
        if q.items is None: pass
        elif p.items is None: out.items=q.items
        else:
            require(len(q.items)>=len(p.items),'FixedValueConflict','list prefix removed')
            a=[]
            for i,r in enumerate(q.items):
                if i>=len(p.items): a.append(r)
                elif out.policy=='append-only':
                    require(recipe_exact_id(p.items[i],c)==recipe_exact_id(r,c),'FixedValueConflict','append-only prefix')
                    a.append(r)
                elif recipe_is_hole(p.items[i],c): a.append(r)
                else: a.append(recipe(p.items[i],r))
            out.items=tuple(a)
    out.contracts=recipe(p.contracts,q.contracts) if p.contracts is not None or q.contracts is not None else None
    out.origin=q.origin if q.origin is not None else p.origin
    out.origins=recipe(*(p.origins+q.origins)).parts
    known=out.core
    if known:
        kind='list' if known=='List' else 'object' if known=='Dictionary' else 'scalar'
        require(out.kind in ('none',kind),'TypeCompatibilityViolation','core payload kind')
        if out.kind=='none': out.kind=kind
    if out.item_type:
        require(out.kind in ('none','list'),'TypeCompatibilityViolation','itemType on non-list')
        if out.kind=='none': out.kind='list'
    if out.key_type or out.value_type:
        require(out.kind in ('none','object'),'TypeCompatibilityViolation','dictionary metadata on non-object')
        if out.kind=='none': out.kind='object'
    return out


def recipe_is_hole(r,c): return len(r.parts)==1 and not r.requirements and is_hole(r.parts[0])


def type_subtype(child,parent,c):
    if child==parent: return True
    a=ancestry(child,c)
    if parent in a: return True
    if child in CORE_NAME and parent in CORE_NAME: return False
    ch=type_plan(child,c);ph=type_plan(parent,c)
    ch.labels={};ph.labels={};ch.specification=None;ph.specification=None
    if ph.core is not None and ch.core!=ph.core: return False
    if not hasattr(c,'subtype_active'): c.subtype_active=set()
    pair=(child,parent)
    # Recursive field declarations use guarded simulation, not cyclic inheritance.
    if pair in c.subtype_active: return True
    c.subtype_active.add(pair)
    try: return preserves_heads(ch,ph,c,check_type=False)
    finally: c.subtype_active.remove(pair)


def guarantees_schema(h,required,c):
    applicable=schema_kinds(required)
    known=h.core or {'object':'Dictionary','list':'List'}.get(h.kind)
    if known is None and h.kind=='scalar' and h.value is not ABSENT:
        known={bool:'Boolean',int:'Integer',float:'Double',str:'Text'}.get(type(h.value))
    if applicable is not None:
        if known is not None and known not in applicable: return False
        if known is None:
            own_kinds=schema_kinds(h.constraints)
            if own_kinds is None or not own_kinds<=applicable: return False
    # Structural guarantees include fixed payload facts, not only written schema.
    established=copy.deepcopy(h.constraints)
    if concrete(h,c): established.required=True
    if h.items is not None:
        established.counts['minItems']=max(established.counts.get('minItems',0),len(h.items))
    if h.kind=='object':
        guaranteed=sum(bool(head(r,c).constraints.required) or present_recipe(r,c) for r in h.fields.values())
        established.counts['minFields']=max(established.counts.get('minFields',0),guaranteed)
    if schema_implies(established,required,c): return True
    if h.kind=='scalar' and h.value is not ABSENT:
        test=copy_head(h);test.constraints=required
        try:
            validate_schema(test,True,'value',True,c)
            return True
        except Failure as e:
            if e.category=='SchemaViolation': return False
            raise
    # Finite scalar alternatives can prove numeric/string facets without a
    # general satisfiability solver. Domain obligations are still compared.
    if h.kind=='scalar' and h.constraints.enum is not None:
        if required.required and not established.required: return False
        if required.enum is not None and not enum_groups_imply(h.constraints,required,c): return False
        candidates=None;values={}
        for group in h.constraints.enum:
            keys=set()
            for key in group:
                tid,core,value=h.constraints.enum_values[key]
                pk=primitive_key(core,value);keys.add(pk);values[pk]=(core,value)
            candidates=keys if candidates is None else candidates&keys
        viable=0
        for key in sorted(candidates or ()):
            core,value=values[key]
            if h.core is not None and core!=h.core: continue
            own=copy_head(h);own.core=core;own.value=value
            own.constraints.enum=None;own.constraints.enum_values={}
            try: validate_schema(own,True,'value',True,c)
            except Failure as e:
                if e.category=='SchemaViolation': continue
                raise
            viable+=1
            test=copy_head(own);test.constraints=copy.deepcopy(required)
            test.constraints.enum=None;test.constraints.enum_values={}
            try: validate_schema(test,True,'value',True,c)
            except Failure as e:
                if e.category=='SchemaViolation': return False
                raise
        return viable>0
    return False


def preserves_heads(candidate,parent,c,check_type=True):
    # A finite obligation worklist. A repeated pair is processed once after
    # its local obligations have been checked; it is not unconditional success.
    work=[(candidate,parent,check_type)]; seen=set()
    while work:
        a,b,ct=work.pop(); c.step()
        if b.core and a.core!=b.core: return False
        if b.kind!='none' and a.kind!=b.kind: return False
        if ct and b.type_id and (not a.type_id or not type_subtype(a.type_id,b.type_id,c)): return False
        if not guarantees_schema(a,b.constraints,c): return False
        for attr in ('item_type','key_type','value_type'):
            p=getattr(b,attr);q=getattr(a,attr)
            if p and (not q or not type_subtype(q,p,c)): return False
        if b.policy and a.policy!=b.policy: return False
        if b.value is not ABSENT:
            if a.value is ABSENT or type(a.value)!=type(b.value) or a.value!=b.value: return False
        if concrete(b,c):
            for k,v in b.labels.items():
                if a.labels.get(k,ABSENT)!=v: return False
        if concrete(b,c) and b.specification is not None and a.specification != b.specification:
            return False
        pairs=[]
        if b.kind=='object':
            if not set(b.fields)<=set(a.fields): return False
            pairs.extend((a.fields[k],b.fields[k]) for k in b.fields)
        if b.items is not None:
            if a.items is None or len(a.items)<len(b.items): return False
            for i,r in enumerate(b.items):
                if b.policy=='append-only':
                    if recipe_exact_id(a.items[i],c)!=recipe_exact_id(r,c): return False
                elif not recipe_is_hole(r,c):
                    pairs.append((a.items[i],r))
        if b.contracts is not None:
            if a.contracts is None: return False
            pairs.append((a.contracts,b.contracts))
        for x,y in pairs:
            key=(x.key(),y.key())
            if key in seen: continue
            seen.add(key)
            work.append((head(x,c),head(y,c),True))
    return True


def check_key(s,tid,c):
    core=domain_core(tid,c)
    require(core in ('Text','Integer','Double','Boolean'),'TypeCompatibilityViolation','keyType')
    if core=='Text': value=s;canonical=s
    elif core=='Integer':
        require(INTEGER_TEXT.fullmatch(s),'SchemaViolation','noncanonical Integer key')
        value=parse_integer(s);canonical=integer_text(value)
    elif core=='Boolean':
        require(s in ('true','false'),'SchemaViolation','Boolean key')
        value=s=='true';canonical=s
    else:
        value=round_binary64(decimal_rational(s,c.limits));canonical=number_text(value)
    require(s==canonical,'SchemaViolation','noncanonical key')
    literal=integer_text(value) if core=='Integer' and abs(value)>SAFE else value
    validate(recipe(scalar(core,literal),requirements=(tid,)),c,'value')


def validate(r,c,goal='value'):
    r=r if isinstance(r,Recipe) else recipe(r)
    root_path=c.diagnostic_path
    work=[(r,True,root_path)]; seen=set()
    while work:
        q,is_root,path=work.pop()
        with error_scope(c,path,'validation'):
            c.step();key=(q.key(),goal,is_root)
            if key in seen or key in c.validation_cache: continue
            seen.add(key)
            h=head(q,c);present=True if is_root else concrete(h,c)
            validate_schema(h,present,goal,is_root,c)
            if goal=='value' and not present: continue
            for k,ch in reversed(list(h.fields.items())):
                if h.core=='Dictionary' or h.key_type:
                    with error_scope(c,pointer(path,k)):
                        check_key(k,h.key_type or CORE['Text'],c)
                work.append((child_recipe(h,k),False,pointer(path,k)))
            if h.contracts is not None:
                with error_scope(c,pointer(path,'contracts')):
                    ch=head(h.contracts,c)
                    require(ch.kind in ('object','none'),'InvalidNodeShape','contracts map')
                work.append((h.contracts,False,pointer(path,'contracts')))
            if h.items is not None:
                for i,ch in reversed(list(enumerate(h.items))):
                    if goal=='definition' and recipe_is_hole(ch,c): continue
                    work.append((child_recipe(h,i),True,pointer(pointer(path,'items'),i)))
    # Publish successful obligations only after the whole worklist succeeded.
    # Contexts contain fixed immutable inputs and are not shared across calls.
    c.validation_cache.update(seen)
    with error_scope(c,root_path,'validation'):
        return head(r,c)


def child_recipe(h,k):
    """The same independently required child for every effective traversal."""
    if isinstance(k,int):
        part=h.items[k] if h.items is not None and k<len(h.items) else None
        tid=h.item_type
    else:
        part=h.fields.get(k);tid=h.value_type
    return recipe(part,requirements=((tid,) if tid else ())) if part is not None or tid else None


def resolved_at(r,parts,c):
    if not parts: return head(r,c)
    h=head(r,c);k=parts[0]
    if k=='blueId': return ABSENT
    if k=='items':
        if h.items is None: return ABSENT
        if len(parts)==1: return h.items
        require(INDEX.fullmatch(parts[1]),'InvalidPath')
        i=int(parts[1])
        if i>=len(h.items): return ABSENT
        with error_scope(c,pointer(pointer(c.diagnostic_path,'items'),i)):
            return resolved_at(child_recipe(h,i),parts[2:],c)
    if k in ('name','description'): return h.labels.get(k,ABSENT) if len(parts)==1 else ABSENT
    if k==SPECIFICATION:
        if h.specification is None: return ABSENT
        if len(parts)==1: return h.specification
        with error_scope(c,pointer(c.diagnostic_path,k)):
            return resolved_at(recipe(h.specification),parts[1:],c)
    if k=='value': return h.value if len(parts)==1 else ABSENT
    if k=='type': return Ref(h.type_id) if h.type_id and len(parts)==1 else ABSENT
    if k=='schema': return h.constraints if len(parts)==1 else ABSENT
    if k in ('itemType','keyType','valueType'):
        t=getattr(h,{'itemType':'item_type','keyType':'key_type','valueType':'value_type'}[k])
        return Ref(t) if t and len(parts)==1 else ABSENT
    if k=='mergePolicy': return (h.policy or 'positional') if h.kind=='list' and len(parts)==1 else ABSENT
    if k=='contracts':
        if h.contracts is None: return ABSENT
        with error_scope(c,pointer(c.diagnostic_path,'contracts')):
            return resolved_at(h.contracts,parts[1:],c)
    child=h.fields.get(k)
    if child is None: return ABSENT
    with error_scope(c,pointer(c.diagnostic_path,k)):
        return resolved_at(child_recipe(h,k),parts[1:],c)

# === A07: Exact refinement and Language list specialization ===
def merge_schema_exact(a,b,c):
    if a is ABSENT: return b
    if b is ABSENT: return a
    if identity(a)==identity(b): return a
    pa=read_schema(a,c);pb=read_schema(b,c)
    refine_schema(pa,pb,c)
    x=open_exact(a,c);y=open_exact(b,c)
    # The constructor has an ordered base/overlay, not unordered input schemas.
    # Missing keywords inherit; a supplied keyword is retained after narrowing.
    return node({**dict(x.fields),**dict(y.fields)})


def refine_exact(base,overlay,c,allow_hole=False):
    if identity(base)==identity(overlay): return base
    if allow_hole and is_hole(base): return overlay
    b=open_exact(base,c);o=open_exact(overlay,c)
    require(b.kind()=='none' or o.kind() in ('none',b.kind()),'TypeCompatibilityViolation','refinement payload kind')
    # Merge the complete explicit operands, not their type-enriched bodies.
    m=dict(b.fields); bh=single_head(b,c)
    for k,v in o.fields:
        if k in LABELS:
            if k in m and m[k]!=v: require(not concrete(bh,c),'FixedValueConflict',k)
            m[k]=v
        elif k==SPECIFICATION:
            if k in m and identity(m[k])!=identity(v):
                require(not concrete(bh,c),'FixedValueConflict',SPECIFICATION)
            m[k]=v
        elif k in TYPES:
            if k in m:
                if k=='type': m[k]=Ref(choose_type(m[k].id,v.id,o.get('value'),c))
                else: m[k]=Ref(narrow_type_slot(m[k].id,v.id,c))
            else: m[k]=v
        elif k=='schema': m[k]=merge_schema_exact(m.get(k,ABSENT),v,c)
        elif k=='mergePolicy':
            require(k not in m or m[k]==v,'TypeCompatibilityViolation','mergePolicy');m[k]=v
        elif k=='value':
            effective=domain_core(m['type'].id,c) if 'type' in m else None
            nv=scalar_effective(v,effective)
            if k in m:
                old=scalar_effective(m[k],effective)
                require(type(old)==type(nv) and old==nv,'FixedValueConflict','scalar',
                        expected=diagnostic_value(old,m.get('type').id if isinstance(m.get('type'),Ref) else None,c),
                        actual=diagnostic_value(nv,o.get('type').id if isinstance(o.get('type'),Ref) else None,c))
            m[k]=v
        elif k=='items':
            if k not in m: m[k]=v
            else:
                p=m[k]; require(len(v)>=len(p),'FixedValueConflict','list prefix removed')
                if m.get('mergePolicy')=='append-only':
                    require(all(identity(x)==identity(y) for x,y in zip(p,v)),'FixedValueConflict','append-only prefix')
                    m[k]=v
                else:
                    merged=[]
                    for i,(x,y) in enumerate(zip(p,v)):
                        with error_scope(c,pointer(pointer(c.diagnostic_path,'items'),i)):
                            merged.append(refine_exact(x,y,c,allow_hole=True))
                    m[k]=tuple(merged)+tuple(v[len(p):])
        elif k not in m: m[k]=v
        else:
            with error_scope(c,pointer(c.diagnostic_path,k)):
                m[k]=refine_exact(m[k],v,c)
    result=normalize_raw_node(m,c)
    require(b.kind()=='none' or result.kind()==b.kind(),'TypeCompatibilityViolation','lost explicit payload')
    # Keep exact results and their effective checks separate.
    validate(recipe(result),c,'definition')
    return c.remember(result)


def normalize_raw_node(m,c):
    return normalize({k:(list(v) if k=='items' else v) for k,v in m.items()},c)


def recipe_exact_value(r,c):
    require(r.parts,'InvalidOperation','a declaration does not supply an exact value')
    result=r.parts[0]
    for a in r.parts[1:]: result=refine_exact(result,a,c)
    return result

def recipe_exact_id(r,c): return identity(recipe_exact_value(r,c))


def anchor_id(value):
    try: return plain_id(value)
    except Failure as failure:
        if failure.category!='InvalidBlueId': raise
        raise Failure('ListControlViolation','anchor requires a plain valid BlueId') from failure


def specialize_payload(base,edits,appends,policy,anchor,c,prepare_operand):
    require(policy in ('positional','append-only'),'ListControlViolation','policy')
    require(not(edits and appends),'ListControlViolation','mixed edits and elements')
    require(anchor is None or policy=='append-only','ListControlViolation','positional anchor')
    if anchor is not None:
        anchor_id(anchor)
        require(list_id(base)==anchor,'ListControlViolation','anchor mismatch')
    require(len({i for i,_,_ in edits})==len(edits),'ListControlViolation','duplicate index')
    for i,op,value in edits:
        require(type(i) is int and 0<=i<len(base),'ListControlViolation','index')
        require(policy=='positional','ListControlViolation','append-only edit')
    out=list(base)
    for i,op,value in sorted(edits,key=lambda e:e[0]):
        with error_scope(c,pointer(pointer(c.diagnostic_path,'items'),i)):
            operand=prepare_operand(value,i)
        if op=='overlay':
            b=open_exact(base[i],c);o=open_exact(operand,c)
            require(is_hole(base[i]) or b.kind() in ('object','none') and o.kind() in ('object','none'),
                    'ListControlViolation','map overlay needs object operands')
        # Both paths preserve the base. A replacement is not arbitrary mutation.
        with error_scope(c,pointer(pointer(c.diagnostic_path,'items'),i)):
            out[i]=refine_exact(base[i],operand,c,allow_hole=True)
    for value in appends:
        with error_scope(c,pointer(pointer(c.diagnostic_path,'items'),len(out))):
            out.append(prepare_operand(value,len(out)))
    return tuple(out)


def parse_controls(items):
    """Classify syntax only; policy and prefix truth require the inherited head."""
    anchor=None;previous=None;edits=[];values=[]
    for position,x in enumerate(items):
        if isinstance(x,(Ref,Node)): values.append(x);continue
        if isinstance(x,dict) and ('$previous' in x or '$previousItems' in x):
            require(position==0 and anchor is None and previous is None and len(x)==1,
                    'ListControlViolation','prefix assertion must be first and unique')
            if '$previousItems' in x:
                require(type(x['$previousItems']) is bool,'ListControlViolation','previousItems requires Boolean')
                previous=x['$previousItems']
            else:
                a=x['$previous']
                require(isinstance(a,dict) and set(a)=={'blueId'},'ListControlViolation','anchor shape')
                anchor=anchor_id(a['blueId'])
        elif isinstance(x,dict) and '$pos' in x:
            t=x['$pos']
            require(isinstance(t,NumberToken) and not t.decimal,'ListControlViolation','Integer index token')
            i=int(t.text);require(0<=i<=SAFE,'ListControlViolation','index')
            if '$replace' in x:
                require(set(x)=={'$pos','$replace'},'ListControlViolation','replacement shape')
                edits.append((i,'replace',x['$replace']))
            else:
                o={k:v for k,v in x.items() if k!='$pos'}
                require(not set(o)&CONTROLS,'ListControlViolation','mixed control')
                edits.append((i,'replace' if 'value' in o else 'overlay',o))
        elif isinstance(x,dict) and set(x)&CONTROLS:
            raise Failure('ListControlViolation','malformed control')
        else: values.append(x)
    require(not(edits and (values or anchor is not None or previous is not None)),
            'ListControlViolation','positional edits cannot mix with elements or prefix assertions')
    require(len({i for i,_,_ in edits})==len(edits),'ListControlViolation','duplicate index')
    return anchor,previous,edits,values

# === A08: Preprocessing with fixed, content-addressed transform selection ===
INFER_IDS=frozenset(('FGYuTXwaoSKfZmpTysLTLsb8WzSqf43384rKZDkXhxD4','49hrWpkoXavNmK8PpZag11zB2vYwzhQZahwioz6vDk2i'))
ALIAS_IDS=frozenset(('27B7fuxQCS1VAptiCPc2RMkKoutP5qxkh3uDxZ7dr6Eo','53yFLQ3dpuGwa2svHubDyzyhYz9RQNmctiJRdi3gRYr7'))
RENAME_ID='7kEewGH6vogsgUXw3Gdyi73rtb5oQK1L8LWtHbYcG7pB'
APPEND_TEXT_ID='D2DxVxaddbJT5k2YYj3sG35cSdotw1Mz9GpxrdP43nzN'
SET_SOURCE_FIELD_ID='3uVsScHAE36fm2Knz3P6tWY94nuEA7cVDWxci8bY2zGg'


def source_walk(x,bindings,infer=True,substitute=True,in_item=False,path='',limits=None):
    try:
        if isinstance(x,(Node,Ref)): return x
        if isinstance(x,dict) and 'blueId' in x:
            require(set(x)=={'blueId'},'InvalidReferenceShape');final_id(x['blueId']);return copy.deepcopy(x)
        if x is None: return HOLE if in_item else None
        if isinstance(x,list): return [source_walk(a,bindings,infer,substitute,True,pointer(pointer(path,'items'),i),limits=limits) for i,a in enumerate(x)]
        if not isinstance(x,dict): x={'value':x}
        require('blue' not in x and not set(x)&{'properties','constraints'},'InvalidNodeShape','reserved key')
        if in_item and set(x)&CONTROLS:
            if '$previous' in x or '$previousItems' in x:
                require(len(x)==1,'ListControlViolation','prefix assertion shape');return copy.deepcopy(x)
            require('$pos' in x,'ListControlViolation')
            if '$replace' in x:
                require(set(x)=={'$pos','$replace'},'ListControlViolation')
                return {'$pos':x['$pos'],'$replace':source_walk(x['$replace'],bindings,infer,substitute,path=pointer(path,'$replace'),limits=limits)}
            o=source_walk({k:v for k,v in x.items() if k!='$pos'},bindings,infer,substitute,path=path,limits=limits)
            return {'$pos':x['$pos'],**o}
        require('$previousItems' not in x,'ListControlViolation','prefix assertion outside list items')
        m={k:v for k,v in x.items() if v is not None}
        for k in list(m):
            if k in TYPES:
                if isinstance(m[k],str):
                    if substitute:
                        require(m[k] in bindings,'UnknownTypeAlias',m[k]);m[k]={'blueId':bindings[m[k]]}
                else: m[k]=source_walk(m[k],bindings,infer,substitute,path=pointer(path,k),limits=limits)
            elif k==SPECIFICATION:
                require(isinstance(m[k],(dict,Node,Ref)), 'InvalidNodeShape', 'specification requires an explicit node or reference')
                m[k]=source_walk(m[k],bindings,infer,substitute,path=pointer(path,k),limits=limits)
            elif k=='items':
                require(isinstance(m[k],list),'InvalidNodeShape','items')
                m[k]=[source_walk(a,bindings,infer,substitute,True,pointer(pointer(path,k),i),limits=limits) for i,a in enumerate(m[k])]
            elif k not in LITERALS|{'mergePolicy'}: m[k]=source_walk(m[k],bindings,infer,substitute,path=pointer(path,k),limits=limits)
        for k in LABELS&set(m): checked_unicode(m[k])
        if 'mergePolicy' in m: require(m['mergePolicy'] in ('positional','append-only'),'InvalidNodeShape','mergePolicy')
        require(sum(('value' in m,'items' in m,bool(set(m)-RESERVED)))<=1,'InvalidNodeShape','payload kinds')
        if 'value' in m: require(isinstance(m['value'],NumberToken) or type(m['value']) in (str,bool,int,float),'InvalidScalar')
        if 'items' in m and any(isinstance(a,dict) and set(a)&CONTROLS for a in m['items']): parse_controls(m['items'])
        if infer and 'value' in m and 'type' not in m:
            tid,_=encode_scalar(None,m['value'],limits);m['type']={'blueId':tid}
        return m
    except Failure as error:
        if error.path is None: error.path=path
        raise

def config_object(x,c):
    n=normalize(x,c);n=open_exact(n,c)
    require(n.kind() in ('object','none'),'InvalidPreprocessing','configuration object')
    return n


def config_text(n,c):
    n=open_exact(n,c)
    require(n.kind()=='scalar' and set(n.keys())<={'type','value'},'InvalidPreprocessing','Text configuration')
    require(n.get('type')==Ref(CORE['Text']) and type(n.get('value')) is str,'InvalidPreprocessing','Text configuration')
    return n.get('value')


def preprocess(root,c):
    c.step()
    for name,tid in c.aliases.items():
        final_id(tid)
        require(name not in CORE or CORE[name]==tid,'InvalidPreprocessing','core alias rebind')
    if isinstance(root,dict) and 'blueId' in root:
        require(set(root)=={'blueId'},'InvalidReferenceShape')
    raw_directive=root.get('blue',ABSENT) if isinstance(root,dict) else ABSENT
    if raw_directive is ABSENT: d=node({})
    else:
        require(raw_directive is not None,'InvalidPreprocessing','null directive')
        if isinstance(raw_directive,str):
            require(raw_directive in c.directive_aliases,'InvalidPreprocessing','unknown directive alias')
            raw_directive=Ref(plain_id(c.directive_aliases[raw_directive]))
        d=config_object(raw_directive,c)
        require(set(d.keys())<={'imports','transformations','type','name','description'},'InvalidPreprocessing','directive fields')
    bindings=dict(c.aliases)
    if d.has('imports'):
        imports=open_exact(d.get('imports'),c)
        require(imports.kind()=='object' and not set(imports.keys())&RESERVED,'InvalidPreprocessing','imports')
        for alias,r in imports.fields:
            require(isinstance(r,Ref),'InvalidPreprocessing','import target')
            final_id(r.id)
            require(alias not in bindings or bindings[alias]==r.id,'InvalidPreprocessing','alias collision')
            bindings[alias]=r.id
    plans=[]
    if d.has('transformations'):
        ts=open_exact(d.get('transformations'),c)
        require(ts.keys()==('items',),'InvalidPreprocessing','transformation sequence')
        for x in ts.get('items'):
            t=open_exact(x,c);r=t.get('type')
            require(isinstance(r,Ref),'InvalidPreprocessing','exact transformation type')
            tid=r.id;allowed={'type','name','description'}
            if tid in INFER_IDS: plan=('infer',None)
            elif tid in ALIAS_IDS:
                allowed.add('mappings');m=open_exact(t.get('mappings'),c)
                require(m.kind()=='object' and not set(m.keys())&RESERVED,'InvalidPreprocessing','mappings')
                mapping={k:final_id(config_text(v,c)) for k,v in m.fields}
                require(all(k not in CORE or CORE[k]==v for k,v in mapping.items()),'InvalidPreprocessing','core alias rebind')
                plan=('alias',mapping)
            elif tid==RENAME_ID:
                allowed|={'from','to'};plan=('rename',(config_text(t.get('from'),c),config_text(t.get('to'),c)))
            elif tid==APPEND_TEXT_ID:
                allowed|={'field','suffix'};plan=('appendText',(config_text(t.get('field'),c),config_text(t.get('suffix'),c)))
            elif tid==SET_SOURCE_FIELD_ID:
                allowed|={'field','expression','format'}
                require(t.has('field') and t.has('expression'),'InvalidPreprocessing','assignment operands')
                target=config_text(t.get('field'),c)
                require(target!='blue','InvalidPreprocessing','assignment cannot introduce blue')
                fmt=config_text(t.get('format'),c) if t.has('format') else 'json'
                require(fmt in ('json','yaml'),'InvalidPreprocessing','assignment format')
                expression=parse(config_text(t.get('expression'),c),fmt,c.limits)
                require(not has_blue(expression),'InvalidPreprocessing','assignment contains blue')
                plan=('setSourceField',(target,expression))
            else: raise Failure('UnsupportedPreprocessingTransform',tid)
            require(set(t.keys())<=allowed,'InvalidPreprocessing','transformation fields')
            plans.append(plan)
    s=copy.deepcopy(root)
    if isinstance(s,dict): s.pop('blue',None)
    for op,arg in plans:
        if op=='infer': s=source_walk(s,{},True,False,limits=c.limits)
        elif op=='alias': s=substitute_available_aliases(s,arg)
        elif op=='setSourceField':
            target,expression=arg
            require(isinstance(s,dict),'InvalidPreprocessing','assignment requires object Source root')
            s[target]=copy.deepcopy(expression)
        elif op=='rename':
            a,b=arg;require(isinstance(s,dict) and a in s and b not in s,'InvalidPreprocessing','rename')
            s[b]=s.pop(a)
        else:
            k,suffix=arg;require(isinstance(s,dict) and k in s,'InvalidPreprocessing','append Text')
            v=s[k]
            if isinstance(v,dict):
                require(set(v)<={'type','value'} and type(v.get('value')) is str,'InvalidPreprocessing','Text source')
                if 'type' in v: require(v['type'] in ('Text',{'blueId':CORE['Text']}),'InvalidPreprocessing','Text source')
                v['value']+=suffix
            else:
                require(type(v) is str,'InvalidPreprocessing','Text source');s[k]=v+suffix
        require(not has_blue(s),'InvalidPreprocessing','introduced blue')
    return source_walk(s,bindings,True,True,limits=c.limits)


def has_blue(x):
    if isinstance(x,(Node,Ref)): return False
    if isinstance(x,dict): return 'blue' in x or any(has_blue(v) for k,v in x.items() if k not in LITERALS|{'mergePolicy','blueId'})
    if isinstance(x,list): return any(has_blue(v) for v in x)
    return False


def substitute_available_aliases(x,mappings,in_item=False):
    if isinstance(x,(Node,Ref)): return x
    if isinstance(x,list): return [substitute_available_aliases(a,mappings,True) for a in x]
    if not isinstance(x,dict): return x
    if 'blueId' in x: return copy.deepcopy(x)
    out={}
    for k,v in x.items():
        if k in TYPES and isinstance(v,str) and v in mappings: out[k]={'blueId':mappings[v]}
        elif k in LITERALS|{'mergePolicy','$pos'}: out[k]=v
        elif k=='items' and isinstance(v,list): out[k]=[substitute_available_aliases(a,mappings,True) for a in v]
        else: out[k]=substitute_available_aliases(v,mappings)
    return out

# === A09: Source compilation and exact canonicalization ===
def inherited_head(s,lazy_context,c):
    selected=lazy_context() if lazy_context is not None else None
    base=head(selected,c) if selected is not None else Head()
    if isinstance(s,dict) and 'type' in s:
        r=normalize(s['type'],c)
        base=merge_heads(base,as_requirement(identity(r),c),c)
    # Container obligations authored here apply to nested constructors too.
    if isinstance(s,dict):
        headers={k:v for k,v in s.items() if k in {'itemType','keyType','valueType','schema','mergePolicy'}}
        if headers:
            nh=single_head(normalize(headers,c),c)
            # Metadata-only headers are merged against the established container kind.
            if nh.kind=='none': nh.kind=base.kind
            base=merge_heads(base,nh,c)
    return base


def child_context(s,lazy_context,k,c):
    def get():
        h=inherited_head(s,lazy_context,c)
        if k=='contracts': return h.contracts
        result=child_recipe(h,k)
        if isinstance(k,int) and result is not None and (h.policy or 'positional')=='positional':
            # A positional hole supplies no payload-kind requirement. Container
            # itemType obligations remain binding when its replacement is built.
            return recipe(*(n for n in result.parts if not is_hole(n)),requirements=result.requirements)
        return result
    return get

def prepare_source(root,c):
    with error_scope(c,phase='preprocessing'): prepared=preprocess(root,c)
    with error_scope(c,phase='source-construction'): return compile_source(prepared,None,c)


def compile_source(s,lazy_context,c):
    c.step()
    if isinstance(s,(Node,Ref)): return s
    if isinstance(s,dict) and 'blueId' in s: return normalize(s,c)
    if isinstance(s,list): s={'items':s}
    if not isinstance(s,dict): s={'value':s}
    s=dict(s)
    for k in ordered((TYPES|REFERENCE_METADATA)&set(s)):
        if k==SPECIFICATION:
            require(isinstance(s[k],(dict,Node,Ref)), 'InvalidNodeShape', 'specification requires an explicit node or reference')
        with error_scope(c,pointer(c.diagnostic_path,k)):
            d=compile_source(s[k],None,c)
        c.remember(d);s[k]=Ref(identity(d))
    if c.diagnostic_path=='':
        c.diagnostic_root=node({k:v for k,v in s.items() if k in LABELS or k in TYPES and isinstance(v,Ref)})
    if 'items' in s:
        a=s['items'];require(isinstance(a,list),'InvalidNodeShape','items')
        base=inherited_head(s,lazy_context,c)
        require(base.kind in ('none','list'),'TypeCompatibilityViolation','items on non-list')
        policy=base.policy or 'positional'
        elements=tuple(recipe_exact_value(r,c) for r in (base.items or ()))
        anchor,previous,edits,values=parse_controls(a)
        if policy=='append-only':
            require(not edits,'ListControlViolation','append-only edit')
            require(anchor is not None or previous is not None,'ListControlViolation',
                    'append-only items require $previousItems or $previous',
                    path=pointer(c.diagnostic_path,'items'),
                    hint='Use $previousItems: true for a nonempty inherited prefix; false only when it is empty.')
            if previous is not None:
                require(previous is bool(elements),'ListControlViolation','previousItems assertion mismatch',
                        path=pointer(pointer(c.diagnostic_path,'items'),0),
                        expected={'value':bool(elements),'inheritedItems':len(elements)},actual={'value':previous})
            if anchor is not None:
                require(base.items is not None,'ListControlViolation','anchor requires an established inherited payload')
            # Appends use their final index and the container itemType, never None.
            payload=specialize_payload(elements,[],values,policy,anchor,c,
                lambda value,index:compile_source(value,child_context(s,lazy_context,index,c),c))
        else:
            require(anchor is None and previous is None,'ListControlViolation','prefix assertions require append-only policy')
            if edits:
                payload=specialize_payload(elements,edits,[],policy,None,c,
                    lambda value,index:compile_source(value,child_context(s,lazy_context,index,c),c))
            else:
                # A supplied positional sequence presents positions 0..n-1.
                # An omitted items slot inherits; a supplied short sequence truncates
                # the required prefix and is invalid. It never means a suffix.
                require(len(values)>=len(elements),'FixedValueConflict','list prefix removed')
                result=[]
                for i,value in enumerate(values):
                    with error_scope(c,pointer(pointer(c.diagnostic_path,'items'),i)):
                        operand=compile_source(value,child_context(s,lazy_context,i,c),c)
                        result.append(refine_exact(elements[i],operand,c,allow_hole=True) if i<len(elements) else operand)
                payload=tuple(result)
        m={k:v for k,v in s.items() if k!='items'}
        for k in list(m):
            if k not in LITERALS|TYPES|{'mergePolicy'}:
                with error_scope(c,pointer(c.diagnostic_path,k)):
                    m[k]=compile_source(m[k],child_context(s,lazy_context,k,c),c)
        m['items']=list(payload);n=normalize(m,c)
        # Construction is not admission. The public boundary certifies the whole
        # result with its context; structural naming must not fetch unrelated
        # opaque children merely because a Source list was supplied.
        return c.remember(n)
    for k in list(s):
        if k in TYPES|LITERALS|{'mergePolicy','items'}: continue
        with error_scope(c,pointer(c.diagnostic_path,k)):
            s[k]=compile_source(s[k],child_context(s,lazy_context,k,c),c)
    return normalize(s,c)

# === A10: Symbolic cyclic identity and complete owning-set proofs ===
def locals_in(n):
    if isinstance(n,Local): return {n.index}
    if isinstance(n,Ref): return set()
    out=set()
    for k,v in n.fields:
        if k in LITERALS|{'mergePolicy'}: continue
        for a in (v if k=='items' else (v,)): out|=locals_in(a)
    return out


def local_map(n,fn):
    if isinstance(n,Local): return fn(n.index)
    if isinstance(n,Ref): return n
    m={}
    for k,v in n.fields:
        if k in LITERALS|{'mergePolicy'}: m[k]=v
        elif k=='items': m[k]=tuple(local_map(a,fn) for a in v)
        else: m[k]=local_map(v,fn)
    return node(m)


def root_commitment(n,token):
    if n.keys()==('items',): return {'kind':'list','elements':[identity(x,token) for x in n.get('items')]}
    return {'kind':'map','helper':helper(n,token)}


def finalize_set(raw_members,c):
    require(isinstance(raw_members,list) and raw_members,'CircularSetError','members')
    ns=[normalize(x,c,symbolic=True) for x in raw_members]
    require(all(isinstance(x,Node) for x in ns),'CircularSetError','reference root')
    edges=[locals_in(n) for n in ns];size=len(ns)
    require(any(edges) and all(all(0<=v<size for v in es) for es in edges),'CircularSetError','local target')
    for start in range(size):
        seen=set();todo=[start]
        while todo:
            i=todo.pop()
            if i in seen: continue
            seen.add(i);todo.extend(edges[i])
        require(len(seen)==size,'CircularSetError','not strongly connected')
    records=[]
    for i,n in enumerate(ns):
        records.append((identity(n,lambda _:ZERO),canonical_text(root_commitment(n,lambda _:ZERO)).encode('utf-8'),i))
    records.sort()
    require(all(records[i][:2]!=records[i-1][:2] for i in range(1,size)),
            'CircularSetError','ambiguous preliminary members')
    positions={r[2]:j for j,r in enumerate(records)}
    canonical=[local_map(ns[r[2]],lambda i:Local(positions[i])) for r in records]
    master=list_id(canonical,lambda i:'this#'+str(i))
    ids=[master+'#'+str(positions[i]) for i in range(size)]
    bodies=[]
    for n in canonical:
        symbolic_final=local_map(n,lambda i:Ref(master+'#'+str(i)))
        bodies.append(normalize(export_tree(symbolic_final),c))
    return {'master':master,'ids':ids,'canonical':canonical,'bodies':bodies}


def verify_member(expected,proof,body,c):
    final_id(expected);require('#' in expected,'InvalidCyclicProof')
    master,index=expected.split('#');j=int(index)
    if isinstance(proof,str): proof=parse(proof,limits=c.limits)
    require(isinstance(proof,dict) and set(proof)=={'members'},'InvalidCyclicProof','proof envelope')
    z=finalize_set(proof['members'],c)
    require(z['master']==master and 0<=j<len(z['ids']),'InvalidCyclicProof','master/index')
    require(z['ids']==[master+'#'+str(i) for i in range(len(z['ids']))],'InvalidCyclicProof','canonical proof order')
    derived=z['bodies'][j]
    if body is not None:
        if isinstance(body,str): body=parse(body,limits=c.limits)
        if isinstance(body,dict) and 'text' in body: body=parse(body['text'],body.get('format','json'),c.limits)
        given=normalize(body,c)
        require(isinstance(given,Node) and identity(given)==identity(derived),'InvalidCyclicProof','member body')
        derived=given
    c.bodies[expected]=derived;c.proofs[expected]=proof
    return Ref(expected,derived)

# === A11: Semantic equivalence and minimization ===
def same_view(a,b,c):
    a=a if isinstance(a,Recipe) else recipe(a);b=b if isinstance(b,Recipe) else recipe(b)
    todo=[(a,b)];seen=set()
    while todo:
        x,y=todo.pop();key=(x.key(),y.key());c.step()
        if key in seen or x.key()==y.key(): continue
        seen.add(key);p=head(x,c);q=head(y,c)
        if (p.type_id,p.core,p.kind,p.labels,p.specification,p.policy,p.item_type,p.key_type,p.value_type)!=(q.type_id,q.core,q.kind,q.labels,q.specification,q.policy,q.item_type,q.key_type,q.value_type): return False
        if describe_constraints(p.constraints)!=describe_constraints(q.constraints): return False
        if (p.value is ABSENT)!=(q.value is ABSENT): return False
        if p.value is not ABSENT and (type(p.value)!=type(q.value) or p.value!=q.value): return False
        if concrete(p,c)!=concrete(q,c): return False
        if set(p.fields)!=set(q.fields) or (p.contracts is None)!=(q.contracts is None): return False
        if (p.items is None)!=(q.items is None): return False
        if p.items is not None:
            if len(p.items)!=len(q.items): return False
            todo.extend((child_recipe(p,i),child_recipe(q,i)) for i in range(len(p.items)))
        todo.extend((child_recipe(p,k),child_recipe(q,k)) for k in p.fields)
        if p.contracts is not None: todo.append((p.contracts,q.contracts))
    return True


def source_for_exact(n,c,lazy_context=None):
    if isinstance(n,Ref): return {'blueId':n.id}
    raw=export_tree(n)
    if isinstance(raw,list): raw={'items':raw}
    for k in list(raw):
        if k in LITERALS|TYPES|{'mergePolicy','items'}: continue
        raw[k]=source_for_exact(n.get(k),c,child_context(raw,lazy_context,k,c))
    if n.has('items'):
        base=inherited_head(raw,lazy_context,c)
        xs=n.get('items');bs=tuple(recipe_exact_value(r,c) for r in (base.items or ()))
        if base.policy=='append-only':
            require(len(xs)>=len(bs) and all(identity(a)==identity(b) for a,b in zip(bs,xs)),
                    'FixedValueConflict','minimize append-only prefix')
            marker={'$previous':{'blueId':list_id(bs)}} if bs else {'$previousItems':False}
            raw['items']=[marker]+[source_for_exact(xs[i],c,child_context(raw,lazy_context,i,c)) for i in range(len(bs),len(xs))]
        else:
            raw['items']=[source_for_exact(x,c,child_context(raw,lazy_context,i,c)) for i,x in enumerate(xs)]
    return raw['items'] if set(raw)=={'items'} else raw

def reductions(raw):
    # Finite, ordered one-step reductions. No global shortest-source claim.
    if isinstance(raw,dict):
        if set(raw)=={'blueId'}: return
        for k in ordered(raw):
            if k in CONTROLS: continue
            out=dict(raw);del out[k];yield out
        if set(raw)=={'value'}: yield raw['value']
        if set(raw)=={'items'}: yield raw['items']
        for k in ordered(raw):
            if k in CONTROLS|{'blueId'} or k in TYPES: continue
            for v in reductions(raw[k]):
                out=dict(raw);out[k]=v;yield out
    elif isinstance(raw,list):
        for i,x in enumerate(raw):
            for v in reductions(x):
                out=list(raw);out[i]=v;yield out


def minimize(exact,c,goal='value'):
    certify(exact,c,goal)
    c.remember(exact)
    original=recipe(exact)
    raw=source_for_exact(exact,c)
    try:
        candidate=prepare_source(raw,c)
        if not same_view(original,candidate,c): raw={'blueId':identity(exact)}
    except Failure as f:
        if f.category in ('ProviderUnavailable','OperationLimitExceeded','ProviderBlueIdMismatch'): raise
        raw={'blueId':identity(exact)}
    while True:
        before=len(wire_text(raw).encode('utf-8'));accepted=None
        for smaller in reductions(raw):
            if len(wire_text(smaller).encode('utf-8'))>=before: continue
            try:
                prepared=prepare_source(smaller,c)
                certify(prepared,c,goal)
                if same_view(original,prepared,c): accepted=smaller;break
            except Failure as f:
                if f.category in ('ProviderUnavailable','OperationLimitExceeded','ProviderBlueIdMismatch'): raise
        if accepted is None: break
        raw=accepted
    result=prepare_source(raw,c)
    require(same_view(original,result,c),'InternalError','minimization roundtrip')
    return wire_text(raw)

# === A12: Portable observations, demand outcomes and entry points ===
def literal_output(v,core=None):
    if v is ABSENT: return {'outcome':'Absent'}
    if core=='Integer' or type(v) is int: return {'kind':'Integer','decimal':integer_text(v)}
    if core=='Double' or type(v) is float: return {'kind':'Double','bits':struct.pack('>d',float(v)).hex()}
    if type(v) is bool: return {'kind':'Boolean','value':v}
    if type(v) is str: return {'kind':'Text','value':v}
    raise Failure('InvalidOperation','not a literal')


def observe(exact,path,query,c):
    parts=path_parts(path)
    if query=='exactId':
        n=exact_at(exact,parts,c)
        if n is ABSENT: return {'outcome':'Absent'}
        require(isinstance(n,(Node,Ref)),'InvalidOperation','exact node required')
        return {'outcome':'Established','blueId':identity(n)}
    v=resolved_at(recipe(exact),parts,c)
    if v is ABSENT: return {'outcome':'Absent'}
    if isinstance(v,Head):
        if query=='kind': result=v.kind
        elif query=='type':
            if v.type_id is None: return {'outcome':'Absent'}
            result=v.type_id
        elif query=='value':
            if v.value is ABSENT: return {'outcome':'Absent'}
            result=literal_output(v.value,v.core)
        elif query=='constraints': result=describe_constraints(v.constraints)
        elif query=='keys': result=ordered(k for k,r in v.fields.items() if present_recipe(r,c))
        elif query=='length':
            require(v.items is not None,'InvalidOperation','not a list');result=len(v.items)
        elif query=='present':
            if parts and not concrete(v,c): return {'outcome':'Absent'}
            result=True
        elif query==SPECIFICATION:
            if v.specification is None: return {'outcome':'Absent'}
            result={'blueId':v.specification.id}
        elif query in ('name','description'):
            if query not in v.labels: return {'outcome':'Absent'}
            result=v.labels[query]
        else: raise Failure('InvalidOperation',query)
    else:
        require(query=='value','InvalidOperation','literal slot observation')
        result=literal_output(v) if not isinstance(v,(Constraint,Ref)) else describe_constraints(v) if isinstance(v,Constraint) else {'blueId':v.id}
    return {'outcome':'Established','value':result}


def outcome(fn):
    try: return fn()
    except RecursionError:
        return {'outcome':'Incomplete','category':'OperationLimitExceeded'}
    except Failure as e:
        status='Incomplete' if e.category in ('ProviderUnavailable','OperationLimitExceeded') else 'Invalid'
        return {'outcome':status,**e.as_dict()}


def initialize(registry,provider=None,aliases=None,limits=None):
    c=Context(provider=dict(provider or {}),limits=limits or Limits())
    for name,raw in registry.items():
        n=normalize(raw,c)
        require(identity(n)==CORE[name],'RegistryMismatch',name)
        c.bodies[CORE[name]]=n
    require(set(registry)==set(CORE),'RegistryMismatch','six core entries required')
    if aliases:
        for k,v in aliases.items():
            final_id(v);require(k not in CORE or CORE[k]==v,'InvalidPreprocessing','core alias rebind')
            c.aliases[k]=v
    c.work=0
    return c


def input_node(record,c):
    require(set(record)<={'mode','format','text'},'InvalidOperation','input fields')
    require('text' in record,'InvalidOperation','input text')
    mode=record.get('mode','source')
    raw=parse(record['text'],record.get('format','json'),c.limits)
    if mode=='source': return prepare_source(raw,c)
    require(mode in ('exact','direct'),'InvalidOperation','input mode')
    return normalize(raw,c,mode)


def certify(exact,c,goal='value'):
    require(goal in ('value','definition'),'InvalidOperation','validation goal')
    validate(exact,c,'definition')
    return validate(exact,c,'value') if goal=='value' else head(recipe(exact),c)

def check_subtype(child,parent,c):
    validate(Ref(child),c,'definition');validate(Ref(parent),c,'definition')
    return type_subtype(child,parent,c)

# === A13: Strict admission, root duplicate normalization and prefix wire ===
def strict_certify(exact,c,goal='value'):
    """Verify the reachable exact graph, its type definitions, then the requested role."""
    require(goal in ('definition','value'),'InvalidOperation','validation goal')
    root_path=c.diagnostic_path
    todo=[(exact,root_path)];seen=set();type_paths={};key_type_paths={};specification_paths={}
    while todo:
        value,path=todo.pop()
        with error_scope(c,path,'dependency-verification'):
            rid=identity(value);c.step()
            if rid in seen: continue
            seen.add(rid)
            body=open_exact(value,c)
            if path==root_path and c.diagnostic_root is exact:
                c.diagnostic_root=body
            children=[]
            for k,v in body.fields:
                if k in TYPES:
                    require(isinstance(v,Ref),'InvalidNodeShape','type position')
                    p=pointer(path,k);type_paths.setdefault(v.id,p);children.append((v,p))
                    if k=='keyType': key_type_paths.setdefault(v.id,p)
                elif k==SPECIFICATION:
                    require(isinstance(v,Ref),'InvalidNodeShape','specification position')
                    p=pointer(path,k);specification_paths.setdefault(v.id,p);children.append((v,p))
                elif k=='items':
                    children.extend((ch,pointer(pointer(path,k),i)) for i,ch in enumerate(v))
                elif k not in LITERALS|{'mergePolicy'}: children.append((v,pointer(path,k)))
            todo.extend(reversed(children))
    for tid in sorted(type_paths):
        if tid in CORE_NAME: continue
        with error_scope(c,type_paths[tid],'type-definition'):
            certify(Ref(tid),c,'definition')
    for sid in sorted(specification_paths):
        with error_scope(c,specification_paths[sid],'specification-content'):
            certify(Ref(sid),c,'definition')
    for tid in sorted(key_type_paths):
        with error_scope(c,key_type_paths[tid],'type-definition'):
            require(domain_core(tid,c) in ('Text','Integer','Double','Boolean'),
                    'TypeCompatibilityViolation','keyType')
    with error_scope(c,root_path,'validation'):
        certify(exact,c,goal)
    return tuple(sorted(seen))


def omit_root_duplicates(exact,c):
    """Canonical authoring at this creation root; never contextualize child IDs.

    Only an entire ordinary child exactly equal to a child already supplied by
    the root's own type can be omitted. Referenced/existing exact roots are not
    migrated. Never recursively turn a complete child into an ancestor delta.
    Canonicalizing a child as a new root is a separate explicit creation operation.
    """
    if isinstance(exact,Ref) or not exact.has('type'): return exact,()
    inherited=as_requirement(exact.get('type').id,c)
    if not inherited.fields: return exact,()
    m=dict(exact.fields);removed=[]
    for key in exact.ordinary():
        contribution=inherited.fields.get(key)
        if contribution is None or not contribution.parts: continue
        base=recipe_exact_value(contribution,c)
        if identity(m[key])==identity(base):
            del m[key];removed.append(pointer('',key))
    result=node(m)
    if removed:
        require(same_view(exact,result,c),'CanonicalizationError','duplicate removal changed effective view')
        c.remember(result)
    return result,tuple(removed)


def payload_body(prefix,c):
    """Open an exact payload-only prefix; its ID is never an outer typed-list ID."""
    prefix=plain_id(prefix)
    if prefix not in c.bodies:
        # A verified type may already contain that sequence inline.
        for body in tuple(c.bodies.values()):
            if isinstance(body,Node) and body.has('items'):
                candidate=list_node(body.get('items'))
                if identity(candidate)==prefix:
                    c.remember(candidate);break
    body=open_exact(Ref(prefix),c)
    require(body.keys()==('items',),'InvalidCanonicalList','prefix must identify a payload-only list')
    return body


def decode_canonical(raw,c,depth=0,lazy_context=None):
    """Decode the explicitly selected compact canonical wire, not ordinary exact data."""
    c.step();require(within(depth+1,c.limits.depth),'OperationLimitExceeded','canonical depth')
    if isinstance(raw,(Node,Ref)): return raw
    if isinstance(raw,dict) and 'blueId' in raw: return normalize(raw,c)
    if isinstance(raw,list): raw={'items':raw}
    if not isinstance(raw,dict): return normalize(raw,c)
    m=dict(raw)
    # Establish inline/exact type definitions before prefix lookup. This also
    # makes a prefix embedded in an already verified type body discoverable.
    for k in TYPES&set(m):
        require(not isinstance(m[k],str),'UnknownTypeAlias','canonical type position')
        t=decode_canonical(m[k],c,depth+1)
        require(isinstance(t,(Node,Ref)),'InvalidNodeShape','type')
        if isinstance(t,Node): c.remember(t)
        m[k]=Ref(identity(t));open_exact(m[k],c)
    for k,v in tuple(m.items()):
        if k in TYPES|LITERALS|{'mergePolicy'}: continue
        if k=='items':
            require(isinstance(v,list),'InvalidNodeShape','items')
            prefix=();start=0
            if v and isinstance(v[0],dict) and '$previous' in v[0]:
                a=v[0]
                require(set(a)=={'$previous'} and isinstance(a['$previous'],dict)
                        and set(a['$previous'])=={'blueId'},'InvalidCanonicalList','anchor shape')
                base=inherited_head(m,lazy_context,c)
                require(base.policy=='append-only' and base.items is not None,
                        'InvalidCanonicalList','prefix anchor requires an inherited append-only payload')
                pid=anchor_id(a['$previous']['blueId'])
                bs=tuple(recipe_exact_value(r,c) for r in base.items)
                # Validate the payload-only shape first, then the selected-base assertion.
                prefix=payload_body(pid,c).get('items')
                require(list_id(bs)==pid,'InvalidCanonicalList','anchor does not identify the selected inherited prefix')
                start=1
            suffix=[]
            for item in v[start:]:
                require(not(isinstance(item,dict) and set(item)&CONTROLS),
                        'InvalidCanonicalList','controls must be escaped as exact references')
                suffix.append(decode_canonical(item,c,depth+1,child_context(m,lazy_context,len(prefix)+len(suffix),c)))
            require(within(len(prefix)+len(suffix),c.limits.values),'OperationLimitExceeded','canonical items')
            m[k]=list(prefix)+suffix
        else: m[k]=decode_canonical(v,c,depth+1,child_context(m,lazy_context,k,c))
    return normalize(m,c)


def canonical_wire(exact,c,lazy_context=None,depth=0):
    """Return compact exact wire: a prefix anchor contributes no element.

    Compression never changes the exact node. Its full expanded body remains the
    authoritative stored exact representation. The root type's verified base,
    not an arbitrary longest shared prefix, selects the emitted anchor.
    """
    c.step();require(within(depth+1,c.limits.depth),'OperationLimitExceeded','canonical export depth')
    if isinstance(exact,Ref): return {'blueId':exact.id}
    raw=export_tree(exact)
    if isinstance(raw,list): raw={'items':raw}
    m={k:v for k,v in raw.items() if k in LITERALS|TYPES|{'mergePolicy'}}
    for k,v in exact.fields:
        if k in LITERALS|TYPES|{'mergePolicy'}: continue
        if k=='items':
            base=inherited_head(raw,lazy_context,c)
            bs=tuple(recipe_exact_value(r,c) for r in (base.items or ())) if base.kind=='list' else ()
            shared=base.policy=='append-only' and bool(bs) and len(v)>=len(bs) and all(identity(a)==identity(b)for a,b in zip(bs,v))
            output=[];start=0
            if shared:
                prefix=c.remember(list_node(bs));start=len(bs)
                output.append({'$previous':{'blueId':identity(prefix)}})
            for i in range(start,len(v)):
                item=v[i]
                # Escape literal control-shaped exact objects so canonical wire
                # cannot interpret a content element as a prefix instruction.
                if isinstance(item,Node) and set(item.keys())&CONTROLS:
                    c.remember(item);output.append({'blueId':identity(item)})
                else:
                    output.append(canonical_wire(item,c,child_context(raw,lazy_context,i,c),depth+1))
            m[k]=output
        else: m[k]=canonical_wire(v,c,child_context(raw,lazy_context,k,c),depth+1)
    return m['items'] if set(m)=={'items'} else m


def canonical_export(exact,c):
    wire=wire_text(canonical_wire(exact,c))
    rebuilt=decode_canonical(parse(wire,limits=c.limits),c)
    require(identity(rebuilt)==identity(exact),'InternalError','canonical wire changed identity')
    return wire


def admitted_records(exact,c):
    """All exact bodies reachable from a successful root, including list payloads.
    Each response is independently hash-verifiable. No intermediate Source object
    or enriched view is published. Cyclic identities retain owning-set proofs.
    """
    records={};todo=[exact];seen=set()
    while todo:
        n=todo.pop();rid=identity(n);c.step()
        if rid in seen: continue
        seen.add(rid);body=open_exact(n,c)
        if rid not in CORE_NAME:
            if '#' in rid:
                require(rid in c.proofs,'InvalidCyclicProof','publication proof unavailable')
                records[rid]={'proof':wire_text(c.proofs[rid]),'body':export_exact(body,c)}
            else: records[rid]={'text':export_exact(body,c),'mode':'exact'}
        for k,v in body.fields:
            if k=='items':
                p=c.remember(list_node(v));pid=identity(p)
                records[pid]={'text':export_exact(p,c),'mode':'exact'}
                todo.extend(reversed(v))
            elif k not in LITERALS|{'mergePolicy'}: todo.append(v)
    # Canonical export may use a prefix that is only a derived subsequence of a
    # type's complete payload. Retain exactly the additional referenced prefixes.
    compact=canonical_wire(exact,c)
    def prefix_walk(x):
        if isinstance(x,list):
            for z in x: prefix_walk(z)
        elif isinstance(x,dict):
            if set(x)=={'$previous'}:
                rid=x['$previous']['blueId'];b=payload_body(rid,c)
                records[rid]={'text':export_exact(b,c),'mode':'exact'}
            else:
                for v in x.values(): prefix_walk(v)
    prefix_walk(compact)
    return records
