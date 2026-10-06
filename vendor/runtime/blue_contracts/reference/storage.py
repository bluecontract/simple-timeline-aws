"""Verified snapshots, portable invocation capsules and atomic local publication.

Expected commitments must come from a trusted source. Serialization and hashing
are not provider authentication or authorization.
"""
from copy import deepcopy
import json,sqlite3
from algorithms import blue as L
from .model import Snapshot,Document,Edge,ChannelLife,ContractError,require,closed,digest,canonical,integer,token,Meter

def export_snapshot(engine,snapshot,*,require_initialized=True):
    engine.validate(snapshot,require_initialized=require_initialized);records={}
    for _,doc in sorted(snapshot.documents.items()):records.update(L.admitted_records(doc.body,engine.blue.context))
    # Implementations are installed separately, but their exact declarative
    # bindings and semantic resources must survive a portable cold restore.
    for binding in snapshot.runtimes:
        for name in ('type_id','semantics_id'):
            records.update(L.admitted_records(L.Ref(binding[name]),engine.blue.context))
    return {'snapshot':snapshot.wire(),'identity':snapshot.identity,'content':records}
def import_snapshot(engine,package,expected_identity,*,require_initialized=True):
    closed(package,{'snapshot','identity','content'});require(package['identity']==expected_identity,'UNTRUSTED_SNAPSHOT_COMMITMENT');wire=closed(package['snapshot'],{'root','documents','edges','generation','revision','release','runtimes'})
    require(digest('contracts.snapshot/completion-1',wire)==expected_identity,'INVALID_SNAPSHOT_COMMITMENT');require(wire['release']==engine.registry.specification,'INCOMPATIBLE_RELEASE')
    language=engine.blue.language;c=language.processing_context();c.provider.update(deepcopy(package['content']));docs={}
    for row in wire['documents']:
        closed(row,{'key','blueId','channels','channelSerials','edgeSerials','birth'});key=token(row['key']);require(key not in docs,'DUPLICATE_DOCUMENT_KEY');n=L.Ref(L.final_id(row['blueId']));L.open_exact(n,c);L.strict_certify(n,c,'value');lives={}
        for k,v in row['channels'].items():
            token(k);closed(v,{'generation','signature'});integer(v['generation'],1);lives[k]=ChannelLife(v['generation'],v['signature'])
        for counters in (row['channelSerials'],row['edgeSerials']):
            require(type(counters) is dict,'INVALID_GENERATIONS')
            for k,v in counters.items():token(k);integer(v,1)
        docs[key]=Document(key,n,row['blueId'],lives,dict(row['channelSerials']),dict(row['edgeSerials']),token(row['birth']) if row['birth'] is not None else None)
    edges={}
    for row in wire['edges']:
        e=Edge(**closed(row,{'source','path','target','generation'}));integer(e.generation,1);require(e.key not in edges,'DUPLICATE_EDGE');edges[e.key]=e
    state=Snapshot(wire['root'],docs,edges,integer(wire['generation']),integer(wire['revision']),wire['release'],tuple(wire['runtimes']));require(state.identity==expected_identity,'INVALID_SNAPSHOT_COMMITMENT');old=engine.blue.context
    try:engine.blue.context=c;engine.validate(state,require_initialized=require_initialized)
    finally:engine.blue.context=old
    language.provider.merge_responses(package['content']);engine.blue.refresh();engine.archive.add(state);return state

def compare_replay(saved,actual):
    closed(saved,{'observations','receipt'});require(digest('contracts.result/completion-1',saved['observations'])==saved['receipt'],'INVALID_RECEIPT')
    return {'verified':canonical(saved['observations'])==canonical(actual.observations()),'expected':saved['receipt'],'actual':actual.receipt}

class Journal:
    def __init__(self,path,engine):
        self.engine=engine;self.db=sqlite3.connect(str(path),isolation_level=None);self.db.execute('PRAGMA foreign_keys=ON');self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS heads(name TEXT PRIMARY KEY, identity TEXT NOT NULL, package TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS receipts(id TEXT PRIMARY KEY, slot TEXT NOT NULL, evidence TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY, receipt TEXT NOT NULL, event TEXT NOT NULL, acknowledged INTEGER NOT NULL DEFAULT 0);
        ''')
    def close(self):self.db.close()
    def initialize(self,name,snapshot):
        package=export_snapshot(self.engine,snapshot)
        try:self.db.execute('INSERT INTO heads VALUES(?,?,?)',(token(name),snapshot.identity,json.dumps(package,ensure_ascii=False)))
        except sqlite3.IntegrityError as e:raise ContractError('SLOT_ALREADY_EXISTS') from e
    def load(self,name):
        row=self.db.execute('SELECT identity,package FROM heads WHERE name=?',(name,)).fetchone();require(row is not None,'UNKNOWN_SLOT');return import_snapshot(self.engine,json.loads(row[1]),row[0])
    def commit(self,name,result,*,fail_before_commit=False):
        require(result.commits,'NONCOMMITTING_RESULT');package=export_snapshot(self.engine,result.snapshot);record={'observations':result.observations(),'receipt':result.receipt};self.db.execute('BEGIN IMMEDIATE')
        try:
            prior=self.db.execute('SELECT evidence,slot FROM receipts WHERE id=?',(result.receipt,)).fetchone()
            if prior is not None:
                require(prior[1]==name,'RECEIPT_SLOT_MISMATCH');require(json.loads(prior[0])==record,'RECEIPT_COLLISION');self.db.execute('ROLLBACK');return 'ALREADY_COMMITTED'
            row=self.db.execute('SELECT identity FROM heads WHERE name=?',(name,)).fetchone();require(row is not None and row[0]==result.input_identity,'COMPARE_AND_SWAP_CONFLICT')
            self.db.execute('UPDATE heads SET identity=?,package=? WHERE name=?',(result.snapshot.identity,json.dumps(package,ensure_ascii=False),name));self.db.execute('INSERT INTO receipts VALUES(?,?,?)',(result.receipt,name,json.dumps(record,ensure_ascii=False)))
            for event in result.public_events:self.db.execute('INSERT INTO outbox(id,receipt,event) VALUES(?,?,?)',(event['identity'],result.receipt,json.dumps(event,ensure_ascii=False)))
            if fail_before_commit:raise ContractError('INJECTED_STORAGE_FAILURE')
            self.db.execute('COMMIT');return 'COMMITTED'
        except Exception:
            if self.db.in_transaction:self.db.execute('ROLLBACK')
            raise
    def pending(self):return [json.loads(row[0]) for row in self.db.execute('SELECT event FROM outbox WHERE acknowledged=0 ORDER BY rowid')]
    def acknowledge(self,occurrence):self.db.execute('UPDATE outbox SET acknowledged=1 WHERE id=?',(occurrence,))

def export_invocation(engine, snapshot, event, eventTimestamp):
    """Portable replay input, not a second processor interface."""
    integer(eventTimestamp)
    event = engine.blue.node(event) if isinstance(event,(L.Node,L.Ref)) else engine.blue.source(event)
    content = L.admitted_records(event,engine.blue.context)
    views = [export_snapshot(engine,engine.archive.versions[sid]) for _,sid in engine.archive.bindings()]
    data = {'input':export_snapshot(engine,snapshot),'event':{'blueId':engine.blue.identity(event)},
            'eventTimestamp':eventTimestamp,'views':views,'content':content,
            'gasPolicy':Meter(engine.gas_limit,engine.local_limits,snapshot.documents).policy()}
    return {'invocation':data,'identity':digest('contracts.capsule/completion-1',data)}


def import_invocation(engine, package, expected_identity):
    """Verify the capsule, restore its configured gas policy, return three inputs."""
    closed(package,{'invocation','identity'})
    require(package['identity']==expected_identity and
            digest('contracts.capsule/completion-1',package['invocation'])==expected_identity,
            'INVALID_CAPSULE_COMMITMENT')
    data=closed(package['invocation'],{'input','event','eventTimestamp','views','content','gasPolicy'})
    integer(data['eventTimestamp']);closed(data['event'],{'blueId'})
    language=engine.blue.language;c=language.processing_context()
    c.provider.update(deepcopy(data['content']))
    event=L.Ref(L.final_id(data['event']['blueId']))
    L.strict_certify(event,c,'value')
    language.provider.merge_responses(data['content']);engine.blue.refresh()
    for view in data['views']:
        snapshot=import_snapshot(engine,view,view['identity'])
        engine.archive.bind(snapshot.documents[snapshot.root].blue_id,snapshot.identity)
    snapshot=import_snapshot(engine,data['input'],data['input']['identity'])
    policy=closed(data['gasPolicy'],{'shared','local','profile'})
    require(Meter(policy['shared'],policy['local'],snapshot.documents).policy()==policy,'INVALID_GAS_POLICY')
    engine.gas_limit=policy['shared'];engine.local_limits=deepcopy(policy['local'])
    return snapshot,event,data['eventTimestamp']
