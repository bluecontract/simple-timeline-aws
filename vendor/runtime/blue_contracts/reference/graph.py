"""Finite rooted views, dynamic reconciliation, routes and Language SCC identity."""
from dataclasses import dataclass
from copy import deepcopy
from algorithms import blue as L
from .model import Document,Snapshot,Edge,NeedResources,require,token,integer,segments,pointer,prefix,digest,LIMITS

@dataclass(frozen=True)
class Link:
    """SDK-only bundle reference, never a Blue runtime patch value."""
    document:str

def components(vertices,edges):
    """Iterative SCC partition and deterministic deepest-first condensation order."""
    vs=sorted(vertices);out={v:[] for v in vs};rev={v:[] for v in vs}
    for e in sorted(edges,key=lambda e:(e.source,e.path,e.target)):
        if e.source in out and e.target in out:out[e.source].append(e.target);rev[e.target].append(e.source)
    seen=set();finish=[]
    for start in vs:
        if start in seen:continue
        stack=[(start,False)]
        while stack:
            v,leaving=stack.pop()
            if leaving:finish.append(v);continue
            if v in seen:continue
            seen.add(v);stack.append((v,True));stack.extend((w,False) for w in reversed(sorted(set(out[v]))) if w not in seen)
    seen=set();groups=[]
    for start in reversed(finish):
        if start in seen:continue
        group=[];stack=[start]
        while stack:
            v=stack.pop()
            if v in seen:continue
            seen.add(v);group.append(v);stack.extend(sorted(set(rev[v])-seen,reverse=True))
        groups.append(tuple(sorted(group)))
    owner={v:g for g in groups for v in g};deps={g:{owner[w] for v in g for w in out[v] if owner[w]!=g} for g in groups};result=[];done=set()
    while len(done)<len(groups):
        ready=sorted(g for g in groups if g not in done and deps[g]<=done);require(bool(ready),'INTERNAL_COMPONENT_ORDER');g=ready[0];done.add(g);result.append(g)
    return result

class Archive:
    """Verified immutable views with explicit choice; never a latest-head lookup."""
    def __init__(self):self.versions={};self.roots={};self.choices={}
    def add(self,snapshot):
        identity=snapshot.identity;root_id=snapshot.documents[snapshot.root].blue_id;old=self.versions.get(identity)
        require(old is None or old.wire()==snapshot.wire(),'CONFLICTING_PROCESS_VIEW');self.versions[identity]=snapshot.copy();self.roots.setdefault(root_id,set()).add(identity)
    def bind(self,blue_id,snapshot_id):
        require(snapshot_id in self.roots.get(blue_id,set()),'UNKNOWN_PROCESS_VIEW');self.choices[blue_id]=snapshot_id
    def bindings(self):
        result=[]
        for key,ids in sorted(self.roots.items()):
            selected=self.choices.get(key)
            if selected is None and len(ids)==1:selected=next(iter(ids))
            if selected is not None:result.append((key,selected))
        return tuple(result)
    def restrict(self,bindings):
        require(len(bindings)==len({x[0] for x in bindings}),'DUPLICATE_PROCESS_VIEW_BINDING');out=Archive()
        for key,identity in bindings:
            require(identity in self.roots.get(key,set()),'UNKNOWN_PROCESS_VIEW',blueId=key,identity=identity)
            out.add(self.versions[identity]);out.bind(key,identity)
        return out
    def get(self,blue_id):
        if blue_id not in self.roots:return None
        selected=dict(self.bindings()).get(blue_id);require(selected is not None,'AMBIGUOUS_PROCESS_VIEW',blueId=blue_id)
        return self.versions[selected].copy()

class Graph:
    def __init__(self,snapshot,registry,archive,meter=None,cause=None):
        self.state=snapshot;self.registry=registry;self.blue=registry.blue;self.archive=archive;self.meter=meter;self.cause=cause
        self.aliases={};self.resets=set();self.added=[];self.changes=[];self.topology_changed=False;self.allocation=0;self.refresh_aliases()
        self.dirty=set();self.finalized={k:d.body for k,d in snapshot.documents.items() if d.blue_id};self.partition=None
        self.path_headers=set();self.verified_bindings=set()
        from .work import LogicalWork
        self.logical=LogicalWork(self.blue,meter) if meter else None
        if self.logical:
            for d in snapshot.documents.values():
                if d.blue_id and isinstance(d.body,L.Node):self.blue.note_identity(d.body,d.blue_id)
            self.logical.carried_roots.update(d.blue_id for d in snapshot.documents.values() if d.blue_id)
            # Exact installed definitions are identity evidence, not evidence
            # that a definition is a valid completed business value.
            self.logical.bound_identities.update(registry.types.values())
            self.logical.bound_identities.add(registry.specification)
    def charge(self,c,n=1):
        if self.meter:self.meter.contracts(c,n)
    def refresh_aliases(self):
        # Only identities currently bound to a vertex are live references.
        # Continuing occurrences have explicit edges; an old exact address is
        # resolved through the selected archive, never through a newer vertex.
        self.aliases={}
        live=self.reachable()
        for k,d in self.state.documents.items():
            if k not in live:continue
            if d.blue_id:self.aliases.setdefault(d.blue_id,set()).add(k)
    def terminated(self,key):return self.registry.marker(self.state.documents[key].body,'terminated') is not None
    def reachable(self,*,active=False,terminating=frozenset()):
        seen=set();pending=[self.state.root]
        while pending:
            k=pending.pop()
            if k in seen:continue
            if active and (k in terminating or self.terminated(k)):continue
            seen.add(k);pending.extend(e.target for _,e in sorted(self.state.edges.items(),reverse=True) if e.source==k)
        return seen
    def paths(self,body):
        e=self.registry.contracts(body).get('embedded')
        if e is None:return ()
        require(e['_role']=='embedding','INVALID_EMBEDDING');paths=[]
        header=self.blue.identity(self.blue.exact(e['_recipe']))
        first=header not in self.path_headers
        if first:self.path_headers.add(header)
        for p in e.get('paths',[]):
            if first:
                self.charge('embeddedPathEntryRead')
                for _ in segments(p):self.charge('embeddedPathSegmentValidated')
            require(type(p) is str and segments(p) and all(segments(p)) and segments(p)[0]!='contracts','INVALID_EMBEDDED_PATH')
            if self.blue.select(body,p) is not None:paths.append(p)
        for base in e.get('collectionPaths',[]):
            if first:
                self.charge('embeddedPathEntryRead')
                for _ in segments(base):self.charge('embeddedPathSegmentValidated')
            require(type(base) is str and segments(base) and segments(base)[0]!='contracts','INVALID_EMBEDDED_PATH');r=self.blue.select(body,base)
            if r is None:continue
            h=self.blue.head(r);require(h.kind in ('object','none') and h.items is None and h.value is L.ABSENT,'EMBEDDED_COLLECTION_NOT_OBJECT')
            for name in sorted(h.fields):paths.append(base+pointer([name]))
        require(len(paths)==len(set(paths)),'DUPLICATE_EMBEDDED_PATH');paths=sorted(paths,key=segments)
        for i,p in enumerate(paths):
            for q in paths[i+1:]:require(not prefix(p,q),'OVERLAPPING_EMBEDDED_PATH')
        return tuple(paths)
    def fresh_key(self,source,path,tid):
        self.allocation+=1
        return digest('contracts.vertex/1',{'input':self.cause or self.state.identity,'source':source,'path':path,'ordinal':self.allocation,'value':tid})
    def import_target(self,source,path,node,birth):
        tid=self.blue.identity(node);known=self.aliases.get(tid,set());require(len(known)<=1,'AMBIGUOUS_LIVE_REFERENCE',blueId=tid)
        if known:return next(iter(known))
        imported=self.archive.get(tid)
        if imported is not None:
            mapping={}
            for key,doc in sorted(imported.documents.items()):
                same=self.aliases.get(doc.blue_id,set());candidates=[s for s in same if self.state.documents[s].channel_lives==doc.channel_lives]
                require(len(candidates)<=1,'AMBIGUOUS_LIVE_REFERENCE',blueId=doc.blue_id)
                # Preserve established member origins when an archived view is
                # embedded in another root. A simultaneous different view of
                # the same key still needs a distinct local occurrence vertex.
                mapping[key]=(candidates[0] if candidates else key if key not in self.state.documents
                              else self.fresh_key(source,path+'/'+key,doc.blue_id))
            for key,doc in sorted(imported.documents.items()):
                new=mapping[key]
                if new in self.state.documents:continue
                clone=deepcopy(doc);clone.key=new;self.state.documents[new]=clone;self.added.append(new)
            for edge in sorted(imported.edges.values(),key=lambda e:e.key):
                mapped=Edge(mapping[edge.source],edge.path,mapping[edge.target],edge.generation);old=self.state.edges.get(mapped.key)
                require(old is None or old==mapped,'IMPORTED_GRAPH_CONFLICT');self.state.edges[mapped.key]=mapped
            observer=getattr(self.registry,'observe_attachment',None)
            if observer is not None:
                observer({mapping[key]:doc.blue_id for key,doc in imported.documents.items()})
            self.refresh_aliases();return mapping[imported.root]
        body=self.blue.open(node);h=self.blue.head(body);require(h.kind in ('object','none') and h.items is None and h.value is L.ABSENT,'EMBEDDED_DOCUMENT_NOT_OBJECT')
        for reserved in ('initialized','terminated','checkpoint'):
            if self.registry.marker(body,reserved) is not None:raise NeedResources(tid)
        key=self.fresh_key(source,path,tid);self.state.documents[key]=Document(key,body,tid,birth=birth);self.aliases.setdefault(tid,set()).add(key);self.added.append(key);return key
    def reconcile(self,birth=None,*,owner=None,replaced=()):
        # A frame owns one declaration map. Existing peers are pinned; only
        # newly discovered children may be traversed during its reconciliation.
        original=set(self.state.documents)
        visited=set();todo=[owner if owner is not None else self.state.root]
        while todo:
            key=todo.pop(0)
            if key in visited:continue
            visited.add(key);d=self.state.documents[key];required=self.paths(d.body);current={p:e for (s,p),e in self.state.edges.items() if s==key}
            for path in sorted(set(current)-set(required)):
                e=self.state.edges.pop((key,path));self.record('REMOVE',e,None)
            for path in required:
                r=self.blue.select(d.body,path);require(r is not None,'MISSING_EMBEDDED_PATH');n=self.blue.exact(r);tid=self.blue.identity(n);e=self.state.edges.get((key,path))
                target=e.target if e and tid==self.state.documents[e.target].blue_id else self.import_target(key,path,n,birth)
                if e is None or target!=e.target or any(prefix(p,path) for p in replaced):
                    if e:self.record('REMOVE',e,None)
                    generation=d.edge_serials.get(path,0)+1;integer(generation);d.edge_serials[path]=generation
                    new=Edge(key,path,target,generation);self.state.edges[(key,path)]=new;self.record('ADD',None,new)
                if owner is None or target not in original:todo.append(target)
        self.refresh_aliases()
    def record(self,kind,before,after):
        self.topology_changed=True;self.changes.append(dict(ordinal=len(self.changes),kind=kind,before=before.wire() if before else None,after=after.wire() if after else None))
        edge=after or before;self.dirty.update((edge.source,edge.target))
        if self.meter:self.meter.owner=edge.source
        self.charge('processEmbeddedEdgeExamined')
        if kind=='ADD' and edge.target in self.added:self.charge('closureExpanded')
    def observe_partition(self):
        relevant=self.reachable()
        partition=components(relevant,self.state.edges.values())
        previous=self.logical.partition if self.logical else self.partition
        if previous!=partition:
            prior=set(previous or ())
            for group in partition:
                if group in prior:continue
                if self.meter and not set(group)&relevant:continue
                for key in group:
                    if self.meter:self.meter.owner=key
                    self.charge('componentMemberPartitioned')
                for edge in sorted(self.state.edges.values(),key=lambda e:e.key):
                    if edge.source in group:
                        if self.meter:self.meter.owner=edge.source
                        self.charge('componentEdgePartitioned')
                if prior:self.charge('componentPartitionChanged')
            self.partition=partition
            if self.logical:self.logical.partition=partition
        return partition
    def finalize(self,*,validate=True,members=None):
        selected=set(self.state.documents) if members is None else set(members)
        self.observe_partition()
        partition=components(selected,self.state.edges.values())
        for group in partition:
            members=set(group);edges=[e for e in self.state.edges.values() if e.source in members];bodies={k:self.state.documents[k].body for k in group}
            replacements={k:[] for k in group}
            for e in sorted(edges,key=lambda e:(e.source,e.path)):
                if e.target not in members:
                    current=self.blue.exact(self.blue.select(bodies[e.source],e.path))
                    if self.blue.identity(current)!=self.state.documents[e.target].blue_id:
                        if self.meter:self.meter.owner=e.source
                        self.charge('containingReferenceUpdated')
                        replacements[e.source].append((e.path,L.Ref(self.state.documents[e.target].blue_id)))
            for k in group:
                if replacements[k]:
                    if self.meter:self.meter.owner=k
                    candidate=self.blue.substitute(bodies[k],replacements[k])
                    if self.logical:self.logical.establish(candidate,bodies[k])
                    bodies[k]=candidate
            changed=bool(members&self.dirty) or any(self.blue.identity(bodies[k])!=self.state.documents[k].blue_id for k in group)
            if not changed:continue
            cyclic=len(group)>1 or any(e.source==e.target for e in edges);positions={k:i for i,k in enumerate(group)}
            if cyclic:
                if self.meter:self.meter.owner=''
                self.charge('tentativeComponentFinalization')
            for k in group:
                if self.meter:self.meter.owner=k
                n=bodies[k]
                if cyclic:n=self.blue.substitute(n,[(e.path,L.Local(positions[e.target])) for e in sorted(edges,key=lambda e:(e.source,e.path)) if e.source==k and e.target in positions])
                if self.logical:self.logical.establish(n,None if cyclic else self.finalized.get(k),token=(lambda i:'this#'+str(i)) if cyclic else None,scope=tuple((member,self.state.documents[member].blue_id) for member in group) if cyclic else None)
            if cyclic:
                for k in group:
                    if self.meter:self.meter.owner=k
                    self.charge('cyclicMemberFinalized')
                for k,(tid,body) in self.blue.finalize_component(group,bodies,edges).items():
                    self.state.documents[k].body=L.Ref(tid,body);self.state.documents[k].blue_id=tid
            else:
                k=group[0];body=bodies[k];self.blue.remember(body);self.state.documents[k].body=body;self.state.documents[k].blue_id=self.blue.identity(body)
            if validate:
                for k in group:
                    if self.meter:self.meter.owner=k
                    if self.logical:self.logical.validate(self.state.documents[k].body,self.finalized.get(k))
                    else:self.blue.certify(self.state.documents[k].body)
            for k in group:self.finalized[k]=self.state.documents[k].body
        self.dirty.difference_update(selected);self.refresh_aliases()
        return self.state

    def finalize_local(self,key):
        """Validate an owned body without refreshing any peer or self pin.

        The document's blue_id remains its sealed input address until its turn
        seals. A private body is never registered as a live managed alias.
        """
        doc=self.state.documents[key]
        self.blue.remember(doc.body)
        if self.logical:self.logical.validate(doc.body,self.finalized.get(key))
        else:self.blue.certify(doc.body)
        self.finalized[key]=doc.body
    def verify_edges(self):
        for k,d in sorted(self.state.documents.items()):
            require(k==d.key and (self.blue.identity(d.body)==d.blue_id or '#' in d.blue_id),'INVALID_DOCUMENT_RECORD')
            if '#' in d.blue_id:
                proved=self.blue.open(L.Ref(d.blue_id));require(self.blue.identity(proved)==self.blue.identity(self.blue.open(d.body)),'INVALID_CYCLIC_BODY')
            self.blue.certify(d.body);paths=set(self.paths(d.body));actual={p for s,p in self.state.edges if s==k};require(paths==actual,'INVALID_GRAPH_BINDINGS')
            for p in sorted(paths):
                e=self.state.edges[(k,p)];require(e.target in self.state.documents,'MISSING_GRAPH_VERTEX')
                require(self.blue.identity(self.blue.exact(self.blue.select(d.body,p)))==self.state.documents[e.target].blue_id,'INVALID_GRAPH_BINDING',path=p)
                require(e.generation==d.edge_serials.get(p),'INVALID_EDGE_GENERATION')
    def routes(self,origin):
        active=self.reachable(active=True)
        if origin not in active:return []
        incoming={k:[] for k in self.state.documents}
        for e in self.state.edges.values():
            if e.source in active and e.target in active:incoming[e.target].append(e)
        todo=[(origin,(),frozenset({origin}))];result=[]
        while todo:
            node,route,seen=todo.pop()
            for e in sorted(incoming[node],key=lambda e:(e.source,e.path,e.generation),reverse=True):
                if e.source in seen and e.source!=origin:continue
                self.charge('processEmbeddedEdgeExamined');new=(e,)+route;result.append((e.source,''.join(x.path for x in new),new))
                if e.source!=origin:todo.append((e.source,new,seen|{e.source}))
        return sorted(result,key=lambda x:(x[0],x[1],tuple(e.occurrence for e in x[2])))
    def direct_routes(self, origin):
        active=self.reachable(active=True)
        if origin not in active:return []
        result=[]
        for edge in sorted(self.state.edges.values(),key=lambda e:(e.source,e.path,e.generation)):
            if edge.target==origin and edge.source in active:
                self.charge('processEmbeddedEdgeExamined')
                result.append((edge.source,edge.path,(edge,)))
        return result

    def route_live(self,route):
        active=self.reachable(active=True)
        return all(self.state.edges.get(e.key)==e and e.source in active and e.target in active for e in route)

def prepare_bundle(registry,members,root,bindings=None,archive=None):
    blue=registry.blue;token(root);require(root in members,'MISSING_ROOT');explicit={} if bindings is None else dict(bindings);nodes={}
    for key,raw in sorted(members.items()):
        token(key)
        def unpack(x,path=()):
            if isinstance(x,Link):explicit[(key,pointer(path))]=x.document;return {}
            if isinstance(x,dict):return {k:unpack(v,path+(k,)) for k,v in x.items()}
            if isinstance(x,list):return [unpack(v,path+(str(i),)) for i,v in enumerate(x)]
            return x
        try:n=L.prepare_source(blue.normalize_input(unpack(raw)),blue.context)
        except L.Failure as e:blue.translate(e)
        h=blue.head(n);require(h.kind in ('object','none') and h.items is None and h.value is L.ABSENT,'PROCESSING_DOCUMENT_NOT_OBJECT')
        for reserved in ('initialized','terminated','checkpoint'):require(registry.marker(n,reserved) is None,'AUTHORED_PROCESSOR_STATE',key=reserved)
        nodes[key]=Document(key,n)
    s=Snapshot(root,nodes,release=registry.specification,runtimes=registry.runtime_bindings)
    for (source,path),target in sorted(explicit.items()):
        require(source in nodes and target in nodes,'MISSING_GRAPH_VERTEX');nodes[source].edge_serials[path]=1;s.edges[(source,path)]=Edge(source,path,target,1)
    g=Graph(s,registry,archive or Archive());g.finalize(validate=False);g.reconcile();g.finalize();g.verify_edges();require(set(members)<=g.reachable(),'DISCONNECTED_AUTHORING_BUNDLE');blue.retain([d.body for _,d in sorted(s.documents.items())]);return s
