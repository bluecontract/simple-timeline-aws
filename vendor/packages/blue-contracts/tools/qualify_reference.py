import sys,subprocess,os,tempfile
from pathlib import Path
r=Path(__file__).resolve().parents[1];sys.path.insert(0,str(r/'tools'));from release import runtime_tree
names=['test_signature_exact','test_direct_call_and_workflow_order','test_nested_call','test_unknown_operation_fails_before_observers','test_invalid_arguments','test_checkpoint_original_event','test_duplicate_timestamp_conflict','test_exact_precondition_success','test_replay_identical','test_snapshot_tamper_rejected','test_shared_gas_exhaustion_rolls_back','test_parent_cannot_patch_child']
with tempfile.TemporaryDirectory(prefix='blue-selected-') as d:
 src=runtime_tree(Path(d)/'src');env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(src)+os.pathsep+str(src.parent),BLUE_BENCHMARK_ROOT=d)
 cmd=[sys.executable,'-m','pytest','-q']+[str(r.parent/'verification/reference/blue-contracts/python/tests/contracts_event/test_contracts_event_api.py')+'::EventAPI::'+n for n in names]
 raise SystemExit(subprocess.run(cmd,cwd=d,env=env).returncode)
