from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from . import Language, MemoryProvider, Failure

def main():
    ap=argparse.ArgumentParser(description='Blue Language 1.0 Python reference implementation')
    ap.add_argument('operation',choices=['identify','canonicalize','inspect','validate','resolve','query','expand','collapse','minimize','publish','verify','raw-identify','publish-raw'])
    ap.add_argument('input',nargs='?',default='-',help='input file, - for stdin, or a BlueId for verify')
    ap.add_argument('--format',choices=['json','yaml'],default='json')
    ap.add_argument('--mode',choices=['source','exact','direct','canonical'],default='source')
    ap.add_argument('--goal',choices=['definition','value'],default='value')
    ap.add_argument('--provider',type=Path)
    ap.add_argument('--path',action='append',default=[])
    ap.add_argument('--question',default='value')
    a=ap.parse_args();provider=MemoryProvider.load(a.provider)if a.provider and a.provider.exists()else MemoryProvider();lang=Language(provider)
    try:
        if a.operation=='verify':result=lang.verify(a.input)
        else:
            text=sys.stdin.buffer.read()if a.input=='-'else Path(a.input).read_bytes()
            opts={'format':a.format,'mode':a.mode}
            if a.operation in ['identify','canonicalize','inspect','publish','validate','resolve','minimize']:opts['goal']=a.goal
            if a.operation=='query':result=lang.query(text,a.path[0]if a.path else'',a.question,**opts)
            elif a.operation in ['expand','collapse']:result=getattr(lang,a.operation)(text,a.path or[''],**opts)
            else:result=getattr(lang,a.operation.replace('-','_'))(text,**opts)
        if a.operation in ('publish','publish-raw') and a.provider:provider.dump(a.provider)
        if a.operation=='query':
            report={**result,'requestedBlueIds':lang.last_demands}
            code=0 if result.get('outcome') in ('Established','Absent') else 2
        else:
            report={'outcome':'Established','result':result,'requestedBlueIds':lang.last_demands}
            code=0
        print(json.dumps(report,ensure_ascii=False,sort_keys=True))
        return code
    except Failure as e:
        status='Incomplete'if e.category in ['ProviderUnavailable','OperationLimitExceeded']else'Invalid'
        print(json.dumps({'outcome':status,**e.as_dict(),'requestedBlueIds':lang.last_demands},ensure_ascii=False,sort_keys=True))
        return 2

if __name__=='__main__':sys.exit(main())
