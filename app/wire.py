"""Application-boundary exact wire, without changing stored Blue documents."""
from blue_language import CORE

TYPE_FIELDS=frozenset(('type','itemType','keyType','valueType'))

def with_aliases(value,aliases):
    for name,bid in CORE.items():
        if name in aliases and aliases[name]!=bid:raise ValueError('NATIVE_TYPE_ALIAS_CONFLICT')
    types={**aliases,**CORE}
    def convert(node):
        if isinstance(node,list):return [convert(x) for x in node]
        if isinstance(node,dict):
            result={}
            for key,child in node.items():
                if key in TYPE_FIELDS and isinstance(child,str):
                    if child not in types:raise ValueError('UNKNOWN_TYPE_ALIAS')
                    result[key]={'blueId':types[child]}
                else:result[key]=convert(child)
            return result
        return node
    return convert(value)

def wire(exact,value):return with_aliases(value,exact.language.aliases)
