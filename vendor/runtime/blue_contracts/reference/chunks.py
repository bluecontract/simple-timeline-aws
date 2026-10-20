"""Verified sequential chunks of the same atomic completion machine (A11).

Native candidates carry an issuer-held execution capability. At a data-only
boundary, acceptance verifies by deterministic re-execution under the bound
inputs, installed runtimes and gas prefix. A digest alone is never execution
proof. Physical verification work is not appended a second time to logical gas.
"""
from copy import copy, deepcopy
from dataclasses import asdict
from algorithms import blue as L
from .model import Outcome, Meter, require, closed, digest, canonical
from .completion import vector, committed
from .storage import export_snapshot, import_snapshot


def clone_run(run):
    require(run.frame is None and not run.suspended, 'OPEN_LOCAL_FRAME')
    result=copy(run)
    shared={'engine','blue','reg','input','graph'}
    for key,value in vars(run).items():
        if key not in shared:setattr(result,key,deepcopy(value))
    result.graph=copy(run.graph)
    for key,value in vars(run.graph).items():
        if key not in {'state','registry','blue','archive','meter','logical'}:
            setattr(result.graph,key,deepcopy(value))
    result.graph.state=result.state;result.graph.meter=result.meter;result.graph.changes=result.changes
    result.graph.logical=copy(run.graph.logical)
    for key,value in vars(run.graph.logical).items():
        if key not in {'blue','meter'}:setattr(result.graph.logical,key,deepcopy(value))
    result.graph.logical.meter=result.meter
    return result


class ChunkToken:
    """Opaque native capability. to_data() is the explicit portable boundary."""
    def __init__(self,attempt,descriptor):
        self._attempt=attempt
        self._descriptor=deepcopy(descriptor)
    @property
    def identity(self):return self._descriptor['identity']
    @property
    def descriptor(self):return deepcopy(self._descriptor)
    def to_data(self):
        attempt=self._attempt
        require(attempt._token is self, 'STALE_CHUNK_TOKEN')
        return {'format':'contracts.chunk-input/completion-1','token':self.descriptor,
                'input':attempt.input_data(), 'history':deepcopy(attempt._history)}


class ChunkResult:
    def __init__(self,wire):self._wire=deepcopy(wire)
    def to_data(self):return deepcopy(self._wire)


class Attempt:
    def __init__(self,run):
        self.run=run
        self.outcome=run.guard(run.begin_work)
        self._token=None
        self._candidates={}
        self._history=[]
        self._finished=False
        self._input_data=None

    def next_chunk(self):
        require(not self._finished, 'ATTEMPT_FINISHED')
        if self.outcome is not None:return None
        if self._token is not None:return self._token
        members=self.run.guard(self.run.ready)
        if isinstance(members,Outcome):self.outcome=members;return None
        if members is None:return None
        run=self.run;phase=run.phase
        record=committed('chunk',dict(attempt=run.invocation,unit=sorted(members),phase=phase.name,
            position=len(self._history),beforeViews=vector(run.state,members),
            dependencies=vector(run.state,{e.target for e in run.state.edges.values() if e.source in members}),
            pending={k:[dict(source=b.source,serial=b.serial,completion=b.completion,output=list(b.output),
                             tickets=[t.wire() for t in b.tickets],after=b.after,roundSeal=b.round_seal)
                        for b in phase.pending[k]] for k in sorted(members)},
            lifecycle={k:phase.initialization[k] for k in sorted(members) if k in phase.initialization},
            seeds={k:[asdict(s) for s in phase.seeds.get(k,[])] for k in sorted(members)},
            routes={k:[ticket.wire() for ticket in phase.initial_routes.get(k,run.capture_routes(k))] for k in sorted(members)},
            activations=dict(sorted(run.activation.items())),
            profile=run.meter.policy(),logicalPrefix=run.logical_commitment(),
            runtimeBindings=list(run.reg.runtime_bindings)))
        self._token=ChunkToken(self,record)
        return self._token

    def execute_chunk(self,token):
        require(token is self._token and token is not None, 'STALE_CHUNK_TOKEN')
        run=clone_run(self.run)
        unit=set(token._descriptor['unit'])
        outcome=run.guard(lambda:run.run_unit(run.phase,unit))
        wire=committed('chunk-result',dict(token=token.identity,
            outcome=outcome.observations() if outcome is not None else None,
            snapshot=run.state.wire(),events=run.events,work=run.work,changes=run.changes,
            checkpoints=run.writes,gas=run.meter.used,rejected=run.meter.rejected,
            turns=run.turns,rounds=run.rounds,units=run.units,logicalPrefix=run.logical_commitment()))
        result=ChunkResult(wire)
        # Store a separate immutable wire copy. Mutating a returned object cannot
        # turn an unexecuted result into an admitted execution capability.
        self._candidates[wire['identity']]=(deepcopy(wire),run,outcome)
        return result

    def accept_chunk(self,token,completion):
        require(not self._finished and self.outcome is None, 'ATTEMPT_FINISHED')
        descriptor=token.descriptor if isinstance(token,ChunkToken) else closed(token,{'format','token','input','history'})['token']
        require(self._token is not None and descriptor==self._token._descriptor, 'STALE_CHUNK_TOKEN')
        wire=completion.to_data() if isinstance(completion,ChunkResult) else deepcopy(completion)
        closed(wire,{'identity','token','outcome','snapshot','events','work','changes','checkpoints','gas','rejected','turns','rounds','units','logicalPrefix'})
        require(wire['token']==self._token.identity, 'CHUNK_INPUT_MISMATCH')
        require(committed('chunk-result',{k:v for k,v in wire.items() if k!='identity'})==wire,'INVALID_CHUNK_COMMITMENT')
        candidate=self._candidates.get(wire['identity'])
        if candidate is None:
            # A portable worker's result has no in-process capability. Verify the
            # entire execution, including failure/gas prefix, with local code.
            self.run.engine.observe_execution('verificationReplay', token=self._token.identity)
            self.run.engine._verifying_completion=True
            try:verified=self.execute_chunk(self._token)
            finally:self.run.engine._verifying_completion=False
            require(canonical(verified.to_data())==canonical(wire),'INVALID_CHUNK_EXECUTION')
            candidate=self._candidates[verified.to_data()['identity']]
        require(canonical(candidate[0])==canonical(wire), 'INVALID_CHUNK_EXECUTION')
        self._history.append({'token':self._token.identity,'result':wire['identity']})
        self.run,self.outcome=candidate[1],candidate[2]
        self._token=None;self._candidates={}
        return self

    def finish(self):
        require(not self._finished, 'ATTEMPT_FINISHED')
        require(self.outcome is not None or self.next_chunk() is None, 'UNFINISHED_ATTEMPT')
        if self.outcome is None:self.outcome=self.run.guard(self.run.finish_work)
        self._finished=True
        return self.outcome

    def finish_local(self):
        """Drive the same machine without crossing a portable chunk boundary.

        Only an untouched, locally owned attempt can take this path. Logical
        unit completion, preflight, gas charges and rollback are unchanged;
        transport commitments and defensive copies are unnecessary when no
        token or candidate has escaped to a worker.
        """
        require(not self._finished, 'ATTEMPT_FINISHED')
        require(self._token is None and not self._history and not self._candidates,
                'CHUNKED_ATTEMPT_ALREADY_STARTED')
        while self.outcome is None:
            members=self.run.guard(self.run.ready)
            if isinstance(members,Outcome):self.outcome=members;break
            if members is None:break
            self.outcome=self.run.guard(lambda:self.run.run_unit(self.run.phase,members))
        if self.outcome is None:self.outcome=self.run.guard(self.run.finish_work)
        self._finished=True
        return self.outcome

    def input_data(self):
        require(not getattr(self.run, 'receiving', False), 'RECEIVING_PORTABLE_EXPORT_UNSUPPORTED')
        if self._input_data is None:
            run=self.run;engine=run.engine
            # Carry provider evidence for BlueIds constructed by an executable
            # body as well as structurally reachable exact input records.
            content=engine.blue.language.provider.snapshot()
            self._input_data=committed('chunk-origin',dict(
                snapshot=export_snapshot(engine,run.input,require_initialized=False),
                event=run.event_id,timestamp=run.timestamp,admission=run.admission,
                views=[export_snapshot(engine,engine.archive.versions[sid]) for _,sid in run.views],
                content=content,policy=run.meter.policy(),externalEvidence=run.admission_evidence))
        return deepcopy(self._input_data)


def restore_origin(engine,data):
    from .processor import Run
    closed(data,{'identity','snapshot','event','timestamp','admission','views','content','policy'},{'externalEvidence'})
    require(committed('chunk-origin',{k:v for k,v in data.items() if k!='identity'})==data,'INVALID_CHUNK_ORIGIN')
    require(type(data['admission']) is bool,'INVALID_RECORD')
    require((data['event'] is None and data['timestamp'] is None) if data['admission'] else
            type(data['event']) is str and type(data['timestamp']) is int,'INVALID_RECORD')
    for view in data['views']:
        snapshot=import_snapshot(engine,view,view['identity'])
        engine.archive.bind(snapshot.documents[snapshot.root].blue_id,snapshot.identity)
    snapshot=import_snapshot(engine,data['snapshot'],data['snapshot']['identity'],require_initialized=False)
    engine.blue.language.provider.merge_responses(data['content']);engine.blue.refresh()
    event=L.Ref(L.final_id(data['event'])) if data['event'] is not None else None
    if event is not None:engine.blue.certify(event)
    policy=closed(data['policy'],{'shared','local','profile'})
    require(Meter(policy['shared'],policy['local'],snapshot.documents).policy()==policy,'INVALID_GAS_POLICY')
    run=Run(engine,snapshot,event,data['timestamp'],policy['shared'],admission=data['admission'],local_limits=policy['local'],admission_evidence=data.get('externalEvidence'))
    # import_snapshot may add the original uninitialized snapshot to the archive;
    # the selected evidence inventory remains exactly that supplied at begin.
    bindings=tuple((v['snapshot']['documents'][next(i for i,d in enumerate(v['snapshot']['documents']) if d['key']==v['snapshot']['root'])]['blueId'],v['identity']) for v in data['views'])
    run.views=tuple(sorted(bindings));run.graph.archive=engine.archive.restrict(run.views)
    return Attempt(run)


def execute(engine,token):
    if isinstance(token,ChunkToken):
        require(token._attempt.run.engine is engine,'WRONG_CHUNK_EXECUTOR')
        return token._attempt.execute_chunk(token)
    closed(token,{'format','token','input','history'})
    require(token['format']=='contracts.chunk-input/completion-1','INCOMPATIBLE_CHUNK_FORMAT')
    attempt=restore_origin(engine,token['input'])
    require(type(token['history']) is list,'INVALID_CHUNK_HISTORY')
    for row in token['history']:
        closed(row,{'token','result'})
        current=attempt.next_chunk()
        require(current is not None and current.identity==row['token'],'INVALID_CHUNK_HISTORY')
        result=attempt.execute_chunk(current)
        require(result.to_data()['identity']==row['result'],'INVALID_CHUNK_HISTORY')
        attempt.accept_chunk(current,result)
    current=attempt.next_chunk()
    require(current is not None and canonical(current.descriptor)==canonical(token['token']),'CHUNK_INPUT_MISMATCH')
    return attempt.execute_chunk(current)
