#!/usr/bin/env python3
"""Serial, process-isolated measurement of the current three-input Contracts API.

Run only after qualification finishes. No gas policy or runtime code is changed.
The separate automatic-engine benchmark measures the browser engine's storage path.
"""
from pathlib import Path
import argparse
from collections import defaultdict
import datetime
import hashlib
import json
import os
import platform
import resource
import subprocess
import sys
import tempfile
import time

try:
    from .source_metadata import git_metadata
except ImportError:
    from source_metadata import git_metadata

ROOT = Path(os.environ.get('BLUE_BENCHMARK_ROOT',Path(__file__).resolve().parents[1]))
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
from tools.release_metadata import current_release

CASES = {
    'counter': {}, 'unused-20': {'operations': 20}, 'unused-60': {'operations': 60},
    'records-100': {'records': 100}, 'records-500': {'records': 500},
    'managed-5': {'children': 4}, 'managed-17': {'children': 16},
    'shared-5-edges': {'children': 5, 'shared': True},
    'cycle-2': {'cycle': 2}, 'cycle-4': {'cycle': 4},
    'history-8': {'history': 8}, 'history-24': {'history': 24},
    'gas-rejection': {'expensive': True},
}


def sha(data): return hashlib.sha256(data).hexdigest()
def wire(data): return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def source_binding():
    return {str(p.relative_to(ROOT)): sha(p.read_bytes())
            for name in ('src', 'specifications', 'apps/workbench', 'tools')
            for p in sorted((ROOT/name).rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and not any(x.endswith('.egg-info') for x in p.parts)}


def memory():
    # RSS snapshots are outside the timed interval. ru_maxrss is a process-life
    # high-water mark, not a claim of isolated per-phase allocation or heap size.
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform=='darwin' else 1024)
    if sys.platform=='darwin':
        import ctypes
        class TaskInfo(ctypes.Structure):
            _fields_=[('virtual_size',ctypes.c_uint64),('resident_size',ctypes.c_uint64),('rest',ctypes.c_byte*80)]
        info=TaskInfo();lib=ctypes.CDLL('/usr/lib/libproc.dylib')
        size=lib.proc_pidinfo(os.getpid(),4,0,ctypes.byref(info),ctypes.sizeof(info))
        rss=info.resident_size if size else None
    else:rss=int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
    return {'residentBytes':rss, 'processPeakResidentBytes':peak}


def phase(rows, name, fn, cache=None):
    row={'phase':name,'startedAt':utc(),'memoryBefore':memory()}
    before=cache.stats() if cache else {}
    start=time.perf_counter();cpu=time.process_time()
    try:
        value=fn();row['status']='OK';return value
    except BaseException as error:
        from blue_host import HostIncomplete
        row['status']='HOST_INCOMPLETE' if isinstance(error,HostIncomplete) else 'ERROR'
        row['error']={'type':type(error).__name__,'detail':str(error)}
        raise
    finally:
        row.update(wallSeconds=time.perf_counter()-start,cpuSeconds=time.process_time()-cpu)
        row['memoryAfter']=memory();row['finishedAt']=utc()
        if cache:row['cacheDelta']={k:cache.stats()[k]-before[k] for k in ('hits','misses')}
        rows.append(row)


def fixture(options):
    from blue_contracts import Link
    def typed(name, **fields):return {'type':'Contracts/'+name,**fields}
    def node(name):
        increment={'$appendChange':{'op':'replace','path':'/count','val':{'$add':[{'$document':'/count'},1]}}}
        steps=[typed('Compute',do=[increment])]
        doc={'name':name,'count':0,'contracts':{'input':typed('External Channel')}}
        for i in range(options.get('operations',1)):
            # Different bodies keep unused declarations distinct exact content.
            doc['contracts']['op'+str(i)]=typed('Sequential Workflow Operation',channel='input',
                steps=steps if i==0 else [typed('Compute',expr=i)])
        return doc
    members={'root':node('root')};target='root';read_path='/count'
    count=options.get('cycle',0)
    if count:
        names=['root']+['node'+str(i) for i in range(1,count)]
        members={name:node(name) for name in names}
        for i,name in enumerate(names):
            members[name]['peer']=Link(names[(i+1)%count])
            members[name]['seen']=0
            members[name]['contracts']['embedded']=typed('Process Embedded',paths=['/peer'])
            members[name]['contracts']['op0']['steps'].append(typed('Update Document',changeset=[
                {'op':'replace','path':'/seen','val':{'$document':'/peer/count'}}]))
    elif options.get('children'):
        paths=[]
        for i in range(options['children']):
            key='child0' if options.get('shared') else 'child'+str(i)
            members.setdefault(key,node(key));members['root']['child'+str(i)]=Link(key);paths.append('/child'+str(i))
        members['root']['contracts']['embedded']=typed('Process Embedded',paths=paths)
        target='child0';read_path='/child0/count'
    if options.get('records'):
        members['root']['records']=[{'sku':'SKU-'+str(i),'price':i,'details':{'tags':['a','b'],'quantities':[1,2,3]}}
                                   for i in range(options['records'])]
    if options.get('expensive'):
        members['root']['contracts']['op0']['steps']=[typed('Compute',do=[{'$forEach':{
            'in':list(range(2000)),'item':'x','do':[{'$appendEvent':{'number':{'$var':'x'}}}]}}])]
    return members,target,read_path


def outcome(row,result):
    counters=defaultdict(lambda:{'charges':0,'units':0,'gas':0})
    for charge in result.gas_trace:
        key=charge['namespace']+'.'+charge['counter'];d=counters[key]
        d['charges']+=1;d['units']+=charge['units'];d['gas']+=charge['amount']
    row.update(outcome=result.status,gas=result.gas,rejected=result.rejected,receipt=result.receipt,
               snapshot=result.snapshot.identity,rootBlueId=result.snapshot.documents[result.snapshot.root].blue_id,
               managedDocuments=len(result.snapshot.documents),managedEdges=len(result.snapshot.edges),
               completions=len(result.completions),rounds=len(result.rounds),events=len(result.event_trace),
               checkpoints=len(result.checkpoints),gasCounters=dict(counters),diagnostic=result.diagnostic)


def restore_worker(path):
    from blue_contracts import Processor,import_invocation
    from blue_language.physical import PhysicalCache
    from blue_host import HostIncomplete
    rows=[];package=json.loads(path.read_text())
    try:
        with PhysicalCache(65536).scope():
            p=phase(rows,'cold_runtime_setup',lambda:Processor(local_driver=True))
            state,event,timestamp=phase(rows,'cold_restore',lambda:import_invocation(p,package,package['identity']))
            assert state.identity==package['invocation']['input']['identity']
        return {'status':'OK','phases':rows,'snapshot':state.identity,'eventTimestamp':timestamp,'pid':os.getpid()}
    except HostIncomplete as error:
        return {'status':'HOST_INCOMPLETE','reason':error.reason,'phases':rows,'pid':os.getpid()}


def sample(case, profile=False):
    from blue_contracts import Processor,Journal,export_invocation
    from blue_language.physical import PhysicalCache
    from blue_host import HostIncomplete
    options=CASES[case];rows=[];result={'case':case,'options':options,'phases':rows,'pid':os.getpid(),'startedAt':utc()}
    cache=PhysicalCache(65536)
    with tempfile.TemporaryDirectory(prefix='blue-release-measure-') as directory, cache.scope():
        p=phase(rows,'runtime_setup',lambda:Processor(local_driver=True),cache)
        members,target,path=fixture(options)
        # Exact fixture encoding includes Link targets rather than object addresses.
        from dataclasses import asdict,is_dataclass
        result['fixtureSha256']=sha(json.dumps(members,sort_keys=True,default=lambda x:asdict(x) if is_dataclass(x) else str(x)).encode())
        result['ordinaryStructuredRecords']=options.get('records',0)
        try:
            initial=phase(rows,'admission',lambda:p.admit(members),cache);outcome(rows[-1],initial)
            if not initial.commits:result['status']=initial.status;return result
            state=initial.snapshot
            result['managedDocuments']=len(state.documents);result['managedEdges']=len(state.edges)
            journal=Journal(Path(directory)/'journal.sqlite',p)
            try:
                phase(rows,'durable_initialize',lambda:journal.initialize('root',state),cache)
                def event(i):return {'sequence':i,'operation':p.typed('Operation Request',
                    channel='input',operation='op0',document={'blueId':state.documents[target].blue_id})}
                # Each invocation gets a distinct original event; one warm-up is
                # retained, never silently discarded from raw evidence.
                for i in range(options.get('history',0)+1):
                    out=phase(rows,'warmup' if i==0 else 'history_processing',lambda i=i:p.process(state,event(i),i+1),cache)
                    outcome(rows[-1],out)
                    if not out.commits:
                        assert out.snapshot.identity==state.identity and not out.public_events
                        result['status']=out.status;return result
                    phase(rows,'history_commit',lambda:journal.commit('root',out),cache);state=out.snapshot
                request=event(options.get('history',0)+1);timestamp=options.get('history',0)+2
                before=state
                selected_views=p.archive.bindings()
                out=phase(rows,'warm_processing',lambda:p.process(before,request,timestamp),cache);outcome(rows[-1],out)
                if not out.commits:
                    assert out.snapshot.identity==before.identity and not out.public_events
                    result['status']=out.status;return result
                phase(rows,'durable_commit',lambda:journal.commit('root',out),cache)
                assert p.read(out.snapshot,path)==options.get('history',0)+2
                result['businessResultVerified']=True
                # A replay capsule needs the selected input plus exact archive
                # views, not only the resulting body's structural content.
                # Use the original invocation's inventory, excluding its result.
                p.archive=p.archive.restrict(selected_views)
                def export():
                    if os.environ.get('BLUE_MEASURE_CORE_REUSE'):
                        from blue_runtime.core_reuse import export_collection
                        with export_collection():capsule=export_invocation(p,before,request,timestamp)
                    else:capsule=export_invocation(p,before,request,timestamp)
                    return capsule,wire(capsule)
                capsule,encoded=phase(rows,'portable_export',export,cache)
                rows[-1].update(bytes=len(encoded),views=len(capsule['invocation']['views']))
                capsule_path=Path(directory)/'capsule.json';capsule_path.write_bytes(encoded)
                child=phase(rows,'cold_restore_process',lambda:subprocess.run(
                    [sys.executable,str(Path(__file__).resolve()),'--restore',str(capsule_path)]+(['--accelerated'] if os.environ.get('BLUE_MEASURE_ACCELERATED') else [])+(['--core-reuse'] if os.environ.get('BLUE_MEASURE_CORE_REUSE') else []),
                    cwd=ROOT,capture_output=True,text=True,check=True),cache)
                result['coldRestore']=json.loads(child.stdout)
                if result['coldRestore']['status']=='HOST_INCOMPLETE':
                    result.update(status='HOST_INCOMPLETE',reason=result['coldRestore']['reason']);return result
                if profile:
                    import cProfile,pstats
                    profiler=cProfile.Profile();replay=profiler.runcall(p.process,before,request,timestamp)
                    assert replay.observations()==out.observations()
                    stats=pstats.Stats(profiler)
                    top=sorted(stats.stats.items(),key=lambda item:item[1][2],reverse=True)[:25]
                    result['profile']=[{'file':k[0],'line':k[1],'function':k[2],'primitiveCalls':v[0],
                        'calls':v[1],'selfSeconds':v[2],'cumulativeSeconds':v[3]} for k,v in top]
                    result['profileNote']='Separate replay after timed phases; instrumented times are not baseline timings.'
                result['status']='APPLIED';return result
            finally:journal.close()
        except HostIncomplete as error:
            result.update(status='HOST_INCOMPLETE',reason=error.reason);return result
        except Exception as error:
            result.update(status='HARNESS_OR_RUNTIME_ERROR',error=type(error).__name__+': '+str(error));return result
        finally:result['finishedAt']=utc()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core-reuse',action='store_true');parser.add_argument('--accelerated',action='store_true');parser.add_argument('--output',type=Path);parser.add_argument('--samples',type=int,default=3)
    parser.add_argument('--cases',nargs='+',choices=CASES,default=list(CASES))
    parser.add_argument('--worker',choices=CASES);parser.add_argument('--restore',type=Path)
    parser.add_argument('--profile',action='store_true',help='Separate diagnostic replay after all timed phases.')
    args=parser.parse_args()
    if args.accelerated:os.environ['BLUE_MEASURE_ACCELERATED']='1'
    if args.core_reuse:os.environ['BLUE_MEASURE_CORE_REUSE']='1'
    if args.restore or args.worker:
        from contextlib import ExitStack
        with ExitStack() as scopes:
            if args.core_reuse:
                from blue_runtime.core_reuse import core_reuse_scope
                scopes.enter_context(core_reuse_scope())
            if args.accelerated:
                from blue_runtime.indexed_topology import topology_scope
                from blue_runtime.sealed import sealed_scope
                from blue_runtime.syntax_cache import syntax_scope
                for scope in (topology_scope,sealed_scope,syntax_scope):scopes.enter_context(scope())
            print(json.dumps(restore_worker(args.restore) if args.restore else sample(args.worker,args.profile)))
        return 0
    if args.output is None or args.samples<1:parser.error('provide --output and a positive --samples')
    binding=source_binding();args.output.mkdir(parents=True,exist_ok=False)
    origin=git_metadata(ROOT)
    report={'startedAt':utc(),'release':current_release(),'source':binding,'sourceSha256':sha(wire(binding)),
        'gitCommit':origin['commit'],
        'dirty':origin['dirtyPaths'],
        'sourceOrigin':origin,
        'environment':{'python':sys.version,'platform':platform.platform(),'machine':platform.machine(),
            'logicalCpus':os.cpu_count(),'sqlite':__import__('sqlite3').sqlite_version},
        'method':{'coreReuse':args.core_reuse,'accelerated':args.accelerated,'serial':True,'samplesPerCase':args.samples,'cacheCapacity':65536,'localDriver':True,
            'gasMaximum':100000,'durability':'Contracts Journal: SQLite WAL synchronous=FULL; commit includes snapshot validation/export',
            'warmup':'one recorded successful transition plus explicitly selected retained history',
            'coldRestore':'new interpreter and fresh physical cache; OS disk cache is not flushed',
            'memory':'RSS snapshots outside timed intervals; process lifetime high-water marks, not per-phase allocation peaks',
            'cpu':'process_time for current process; cold_restore_process parent CPU excludes child; child CPU reported separately',
            'scope':'isolated core + snapshot Journal; not automatic Coordination incremental publication or HTTP latency'},'samples':[]}
    for case in args.cases:
        for index in range(args.samples):
            argv=[sys.executable,str(Path(__file__).resolve()),'--worker',case]+(['--profile'] if args.profile else [])+(['--accelerated'] if args.accelerated else [])+(['--core-reuse'] if args.core_reuse else [])
            start=utc();run=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True)
            stem=args.output/f'{case}-{index+1}'
            stem.with_suffix('.stdout.json').write_text(run.stdout);stem.with_suffix('.stderr.log').write_text(run.stderr)
            command={'argv':argv,'startedAt':start,'finishedAt':utc(),'exitCode':run.returncode}
            stem.with_suffix('.command.json').write_text(json.dumps(command,indent=2)+'\n')
            if run.returncode:row={'case':case,'status':'PROCESS_ERROR','diagnostic':run.stderr}
            else:row=json.loads(run.stdout)
            row.update(sample=index+1,command=command);report['samples'].append(row)
            report['sourceUnchanged']=binding==source_binding()
            (args.output/'measurements.json').write_text(json.dumps(report,indent=2)+'\n')
            print(case,index+1,row['status'],flush=True)
    report['finishedAt']=utc();report['sourceUnchanged']=binding==source_binding()
    (args.output/'measurements.json').write_text(json.dumps(report,indent=2)+'\n')
    return int(not report['sourceUnchanged'] or any(r['status'] in ('PROCESS_ERROR','HARNESS_OR_RUNTIME_ERROR') for r in report['samples']))


if __name__=='__main__':raise SystemExit(main())
