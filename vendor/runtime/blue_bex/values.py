"""BEX runtime values, distinct from Blue nodes and Python truthiness.

Null is internal only in this corrected-boundary profile. UNDEFINED is not null.
No function in this module hashes or admits a Blue document.
"""
from __future__ import annotations
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import math
import re
from typing import Any

class BexError(Exception):
    code = 'BEX_RUNTIME_ERROR'

class CompileError(BexError):
    code = 'BEX_COMPILE_ERROR'

class BoundaryError(BexError):
    code = 'BEX_OUTPUT_INVALID'

class ResourceError(BexError):
    code = 'PORTABLE_LIMIT_EXCEEDED'

class ExecutionRejected(BexError):
    code = 'EXECUTION_REJECTED'

class _Undefined:
    def __repr__(self): return 'UNDEFINED'
    def __copy__(self): return self
    def __deepcopy__(self, memo): return self
UNDEFINED = _Undefined()


class HostValue:
    """Trusted immutable host collection, never executable program syntax.

    The host supplies path-local access and a finite, exact Blue output. Copying
    a value retains the same captured view; it must not traverse its children.
    """
    def __copy__(self): return self
    def __deepcopy__(self, memo): return self
    def blue_output(self): raise NotImplementedError
    def output_view(self): return self  # Finite lazy view used for output sizing.
    def accounting_view(self):
        """Finite metering form; only an evidence-bearing host may override.

        This does not change kind, reads, equality, or semantic output. Generic
        host collections retain ordinary traversal/construction accounting.
        """
        return self.output_view()
    def value_kind(self): raise NotImplementedError
    def comparison_key(self): return id(self)


def clone(value: Any) -> Any:
    holder=[None];pending=[(holder,0,value)];memo={}
    while pending:
        target,key,current=pending.pop()
        if type(current) not in (dict,list):target[key]=deepcopy(current);continue
        if id(current) in memo:target[key]=memo[id(current)];continue
        out={} if type(current) is dict else [None]*len(current)
        target[key]=out;memo[id(current)]=out
        rows=current.items() if type(current) is dict else enumerate(current)
        pending.extend((out,k,v) for k,v in reversed(tuple(rows)))
    return holder[0]


def kind(value: Any) -> str:
    if isinstance(value, HostValue): return value.value_kind()
    if value is UNDEFINED: return 'undefined'
    if value is None: return 'null'
    if type(value) is bool: return 'boolean'
    if type(value) is int: return 'integer'
    if type(value) in (Decimal, float):
        if not number(value).is_finite(): raise BexError('non-finite number')
        return 'double'
    if type(value) is str: return 'text'
    if type(value) is dict: return 'object'
    if type(value) is list: return 'list'
    raise BexError(f'not a BEX value: {type(value).__name__}')


def truthy(value: Any) -> bool:
    k = kind(value)
    if k in ('undefined', 'null'): return False
    if k == 'boolean': return value
    if k in ('text', 'object', 'list'): return len(value) != 0
    return True  # In particular, numeric zero is TRUE in BEX.


def number(value: Any) -> Decimal:
    if type(value) is Decimal: result = value
    elif type(value) is int: result = Decimal(value)
    elif type(value) is float:
        if not math.isfinite(value): raise BexError('non-finite Double')
        result = Decimal(repr(value))
    elif type(value) is str:
        if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?', value, flags=re.ASCII):
            raise BexError('invalid numeric text')
        try: result = Decimal(value)
        except InvalidOperation as e: raise BexError('invalid numeric text') from e
    else: raise BexError('numeric conversion requires Integer, Double or Text')
    if not result.is_finite(): raise BexError('non-finite number')
    return result


def integer(value: Any) -> int:
    if type(value) is str:
        if not re.fullmatch(r'(?:0|-[1-9][0-9]*|[1-9][0-9]*)', value, flags=re.ASCII):
            raise BexError('integer text is not canonical')
        return int(Decimal(value))
    n = number(value)
    if n != n.to_integral_value(): raise BexError('non-integral number')
    return int(n)


def text(value: Any) -> str:
    k = kind(value)
    if k in ('undefined', 'null'): return ''
    if k == 'boolean': return 'true' if value else 'false'
    if k == 'integer': return str(Decimal(value))  # Avoid Python's configurable int-to-string digit guard.
    if k in ('double', 'text'): return str(value) if type(value) is not float else str(number(value))
    raise BexError('cannot implicitly render a collection as Text')


def required_text(value: Any) -> str:
    if value is UNDEFINED or value is None: raise BexError('missing/null path, name, operation or key')
    return text(value)


def ordered_keys(value, charge=None):
    """Prepay a portable key-order envelope; never inspect child values."""
    n=len(value)
    if charge:charge('valueMember',n)
    keys=list(value)
    rounds=(n-1).bit_length() if n else 0
    if charge:
        charge('valueMember',n*rounds)
        charge('textWork',sum((len(key)+63)//64 for key in keys)*(rounds+1))
    return sorted(keys)


def equal(a: Any, b: Any, charge=None) -> bool:
    def members(x,y,ordered):
        for key in ordered:yield x[key],y[key]
    pending, active = [(iter(((a,b),)),None)], set()
    while pending:
        try:a,b = next(pending[-1][0])
        except StopIteration:
            _,pair=pending.pop()
            if pair is not None:active.remove(pair)
            continue
        if charge:charge('valueMember')
        ka,kb = kind(a),kind(b)
        if ka in ('integer','double') and kb in ('integer','double'):
            both_integers=type(a) is int and type(b) is int
            if charge:
                limbs=[max(1,(abs(x).bit_length()+31)//32) for x in (a,b) if type(x) is int]
                charge('integerWork',sum(n if both_integers else n*n for n in limbs))
            if (a!=b if both_integers else number(a)!=number(b)):return False
            continue
        if ka != kb:return False
        if ka in ('object','list'):
            pair = (a.comparison_key() if isinstance(a,HostValue) else id(a),
                    b.comparison_key() if isinstance(b,HostValue) else id(b))
            if pair in active:continue
            active.add(pair)
            if ka=='list':
                if len(a)!=len(b):return False
                pending.append((iter(zip(a,b)),pair))
            else:
                left,right=ordered_keys(a,charge),ordered_keys(b,charge)
                if left!=right:return False
                pending.append((members(a,b,left),pair))
        elif ka=='text' and charge:
            if len(a)!=len(b):return False
            for offset in range(0,len(a),64):
                charge('textWork',2)
                if a[offset:offset+64]!=b[offset:offset+64]:return False
        elif ka!='undefined' and a!=b:return False
    return True


def utf16_length(s: str) -> int:
    try: return len(s.encode('utf-16-le')) // 2
    except UnicodeEncodeError as e: raise BexError('unpaired Unicode surrogate') from e


def size_parts(v, charge=None):
    """Finite output-size fragments in code-point/index preorder.

    The consumer charges each yielded quantity before resuming this generator.
    Descendant lookups are lazy; key ordering and scalar encoding are prepaid.
    Host accounting views retain established exact identities rather than chase
    their materialized bodies. New native containers still visit every child.
    """
    pending=[iter((v,))]
    while pending:
        try:current=next(pending[-1])
        except StopIteration:
            pending.pop();continue
        if isinstance(current,HostValue):current=current.accounting_view()
        k=kind(current)
        if k in ('undefined','null'):continue
        if k=='list':
            yield len(current)
            pending.append(iter(current))
        elif k=='object':
            yield len(current)
            keys=ordered_keys(current,charge)
            for key in keys:
                if charge:charge('textWork',(len(key)+63)//64)
                yield utf16_length(key)
            pending.append(map(current.__getitem__,keys))
        else:
            if charge and type(current) is int:
                charge('integerWork',max(1,(abs(current).bit_length()+31)//32)**2)
            rendered=text(current)
            if charge:charge('textWork',(len(rendered)+63)//64)
            yield max(1,utf16_length(rendered))


def estimated_size(v):
    return sum(size_parts(v))


def segments(path: str) -> list[str]:
    if type(path) is not str: raise BexError('pointer must be Text')
    # BEX value pointers designate root by both empty and slash. Language's own
    # query API has a different empty-member rule; never delegate blindly.
    if path in ('', '/'): return []
    if not path.startswith('/'): raise BexError('absolute value pointer required')
    out = []
    for part in path[1:].split('/'):
        if re.search(r'~(?![01])', part): raise BexError('invalid JSON pointer escape')
        out.append(part.replace('~1', '/').replace('~0', '~'))
    return out


def escape(part: str) -> str:
    return part.replace('~', '~0').replace('/', '~1')


def index(segment: str, length: int, *, add: bool = False) -> int:
    if add and segment == '-': return length
    if not re.fullmatch(r'0|[1-9][0-9]*', segment, flags=re.ASCII): raise BexError('noncanonical list index')
    result = int(Decimal(segment))
    if result > length or (result == length and not add): raise BexError('list index outside bounds')
    return result


def pointer_get(value: Any, path: str) -> Any:
    at = value
    for s in segments(path):
        if kind(at) == 'object': at = at.get(s, UNDEFINED)
        elif kind(at) == 'list':
            try: at = at[index(s,len(at))]
            except BexError: return UNDEFINED
        else: return UNDEFINED
    return at


def pointer_overlay(value: Any, path: str, replacement: Any, *, remove: bool = False, charge=None) -> Any:
    """Persistent overlay; copy the selected spine, never recursive descendants."""
    parts=segments(path)
    if not parts:return UNDEFINED if remove else clone(replacement)
    spine=[];at=value
    for offset,s in enumerate(parts):
        if at is None or at is UNDEFINED:at={}
        k=kind(at);last=offset==len(parts)-1
        if k not in ('object','list'):raise BexError('scalar pointer target parent')
        if k=='object':out={key:at[key] for key in ordered_keys(at,charge)}
        else:
            if charge:charge('valueMember',len(at))
            out=list(at)
        key=s if k=='object' else index(s,len(out),add=last and not remove)
        spine.append((out,key))
        if not last:at=out.get(key,UNDEFINED) if k=='object' else out[key]
    result=UNDEFINED if remove else clone(replacement)
    for offset,(out,key) in enumerate(reversed(spine)):
        if isinstance(out,dict):
            if offset==0 and result is UNDEFINED:out.pop(key,None)
            else:out[key]=result
        elif key==len(out):out.append(result)
        else:out[key]=result
        result=out
    return result


def blue_value(value: Any, *, _in_object: bool = False) -> Any:
    """Prepare semantic output; the Language MUST then admit it.

    Undefined object members are omitted. Null is NEVER rewritten to {}.
    Decimal rounds to finite binary64 using Python's correctly-rounded conversion.
    """
    if isinstance(value, HostValue): return value.blue_output()
    k = kind(value)
    if k == 'undefined': raise BoundaryError('undefined is not a Blue value')
    if k == 'null': raise BoundaryError('BEX null is not a Blue node; use $emptyObject explicitly')
    if k == 'object': return {a: blue_value(b) for a,b in value.items() if b is not UNDEFINED}
    if k == 'list': return [blue_value(v) for v in value]
    if k == 'double':
        f = float(value)
        if not math.isfinite(f): raise BoundaryError('Double output overflow')
        return f
    return value
