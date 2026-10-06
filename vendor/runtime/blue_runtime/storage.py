"""SQLite CAS + atomic outbox adapter, with caller-supplied snapshot verification.

This journal is wired to complete local host recovery by blue_runtime.durable.
The validator must establish the snapshot's Language/Coordination obligations.
The SHA-256 envelope digest detects accidental corruption, not hostile database
rewriting. Durable local storage is an explicit trust boundary. Outbox delivery
is at least once; consumers deduplicate on event_id, not payload identity.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
import hashlib
import json
import sqlite3

class StoreError(RuntimeError): pass
class Conflict(StoreError): pass
class CorruptStore(StoreError): pass

def _wire(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)

def _hash(value):return hashlib.sha256(_wire(value).encode()).hexdigest()

def _text(value,name):
    if not isinstance(value,str) or not value:raise ValueError(name+' must be nonempty text')
    return value

@dataclass(frozen=True)
class Commit:
    root: str
    generation: int
    receipt_id: str
    replayed: bool

class SQLiteJournal:
    def __init__(self,path:str|Path,*,validate_snapshot:Callable[[dict],None]):
        if not callable(validate_snapshot):raise TypeError('snapshot verifier is mandatory')
        self.validate_snapshot=validate_snapshot
        self.connection=sqlite3.connect(str(path),isolation_level=None,timeout=10,check_same_thread=False)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('PRAGMA synchronous=FULL')
        self.connection.execute('PRAGMA foreign_keys=ON')
        self.connection.executescript('''
CREATE TABLE IF NOT EXISTS roots(root TEXT PRIMARY KEY,generation INTEGER NOT NULL,snapshot TEXT NOT NULL,digest TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS receipts(root TEXT NOT NULL,receipt TEXT NOT NULL,generation INTEGER NOT NULL,digest TEXT NOT NULL,PRIMARY KEY(root,receipt));
CREATE TABLE IF NOT EXISTS outbox(sequence INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT UNIQUE NOT NULL,root TEXT NOT NULL,receipt TEXT NOT NULL,ordinal INTEGER NOT NULL,payload TEXT NOT NULL,digest TEXT NOT NULL,acknowledged INTEGER NOT NULL DEFAULT 0);
''')
    def close(self):self.connection.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()

    def load(self,root:str):
        row=self.connection.execute('SELECT generation,snapshot,digest FROM roots WHERE root=?',(_text(root,'root'),)).fetchone()
        if row is None:return None
        generation,wire,digest=row
        try:value=json.loads(wire)
        except ValueError as error:raise CorruptStore('invalid stored JSON') from error
        if _hash(value)!=digest:raise CorruptStore('snapshot checksum mismatch')
        self.validate_snapshot(value)
        return generation,value

    def commit(self,root:str,expected_generation:int,receipt_id:str,snapshot:dict,events:list) -> Commit:
        _text(root,'root');_text(receipt_id,'receipt')
        if type(expected_generation) is not int or expected_generation<0:raise ValueError('invalid expected generation')
        if type(snapshot) is not dict or type(events) is not list:raise TypeError('snapshot object and events list required')
        # Defensive JSON round-trip forbids non-JSON values and isolates callers.
        snapshot=json.loads(_wire(snapshot));events=json.loads(_wire(events))
        self.validate_snapshot(snapshot)
        envelope={'root':root,'expected':expected_generation,'receipt':receipt_id,'snapshot':snapshot,'events':events}
        digest=_hash(envelope);c=self.connection;c.execute('BEGIN IMMEDIATE')
        try:
            existing=c.execute('SELECT generation,digest FROM receipts WHERE root=? AND receipt=?',(root,receipt_id)).fetchone()
            if existing:
                if existing[1]!=digest:raise Conflict('receipt replay has different inputs')
                c.execute('COMMIT');return Commit(root,existing[0],receipt_id,True)
            current=c.execute('SELECT generation FROM roots WHERE root=?',(root,)).fetchone()
            actual=0 if current is None else current[0]
            if actual!=expected_generation:raise Conflict('root generation changed')
            generation=actual+1
            c.execute('INSERT INTO roots VALUES(?,?,?,?) ON CONFLICT(root) DO UPDATE SET generation=excluded.generation,snapshot=excluded.snapshot,digest=excluded.digest',
                      (root,generation,_wire(snapshot),_hash(snapshot)))
            c.execute('INSERT INTO receipts VALUES(?,?,?,?)',(root,receipt_id,generation,digest))
            for ordinal,event in enumerate(events):
                event_id=_hash({'root':root,'receipt':receipt_id,'ordinal':ordinal})
                c.execute('INSERT INTO outbox(event_id,root,receipt,ordinal,payload,digest) VALUES(?,?,?,?,?,?)',
                          (event_id,root,receipt_id,ordinal,_wire(event),_hash(event)))
            c.execute('COMMIT');return Commit(root,generation,receipt_id,False)
        except BaseException:
            if c.in_transaction:c.execute('ROLLBACK')
            raise

    def pending(self,limit:int=100):
        if type(limit) is not int or limit<=0:raise ValueError('limit must be positive')
        rows=self.connection.execute('SELECT event_id,root,receipt,ordinal,payload,digest FROM outbox WHERE acknowledged=0 ORDER BY sequence LIMIT ?',(limit,)).fetchall()
        out=[]
        for eid,root,receipt,ordinal,payload,digest in rows:
            try:value=json.loads(payload)
            except ValueError as error:raise CorruptStore('invalid outbox JSON') from error
            if _hash(value)!=digest:raise CorruptStore('outbox checksum mismatch')
            out.append({'event_id':eid,'root':root,'receipt':receipt,'ordinal':ordinal,'payload':value})
        return out

    def acknowledge(self,event_id:str):
        result=self.connection.execute('UPDATE outbox SET acknowledged=1 WHERE event_id=?',(_text(event_id,'event ID'),))
        if result.rowcount!=1:raise KeyError(event_id)
