"""Small in-process integration facade. See SDK.md for trust and durability limits."""
from blue_runtime_bootstrap import activate
activate()
from blue_contracts.catalogue import Catalogue
from blue_contracts.legacy_processor import Processor
from blue_coordination.closure import ClosureHost
from blue_coordination.provider import MemoryTimelineProvider
from blue_coordination.feeder import Feeder
from blue_coordination.language import MISSING

class Stack:
    def __init__(self,language=None,*,bex=None,catalogue=None,attachment_mode='FULL_HISTORY'):
        if catalogue is not None and language is not None and catalogue.language is not language:
            raise ValueError("catalogue and language instances disagree")
        self.catalogue=catalogue if catalogue is not None else Catalogue(language)
        self.processor=Processor(self.catalogue,bex=bex)
        self.host=ClosureHost(self.catalogue,processor=self.processor,attachment_mode=attachment_mode)
        self.providers={};self._entry_roots={}
        self.provider=MemoryTimelineProvider(self.catalogue.blue,self.catalogue.registry,
            entry_type=self.catalogue.id('Coordination/Timeline Entry'),
            evidence_type=self.catalogue.id('Reference/Completeness Evidence'),
            signing_key=b'blue-stack-local-provider-fixture-key')
        self.feeder=Feeder(self.host,self.catalogue.blue,self.catalogue.registry,self.providers)
        self.host.on_commit=self.sync_routes
        self.host.validate_routes=self.validate_routes

    def validate_routes(self, state):
        from blue_contracts.patch import CapabilityError
        for channels in state.channels.values():
            for channel in channels:
                for source in channel.sources:
                    actors=self.provider._actors.get(source.timeline_blue_id)
                    if actors is not None and source.actor_blue_id not in actors:
                        raise CapabilityError('Timeline actor conflicts with its registered owners')

    def admit_graph(self,documents,edges=None,*,public_roots=None):
        result=self.host.admit_graph(documents,edges or {},public_roots=public_roots or tuple(documents))
        self.sync_routes(result)
        return result

    def sync_routes(self, roots=None):
        sources={}
        for root in (self.host.roots if roots is None else roots):
            for view in self.host.load_root(root).views:
                self._entry_roots.setdefault(view.document_id,root)
                if view.document_id in self.host.roots:self._entry_roots[view.document_id]=view.document_id
                for channel in view.channels:
                    for source in channel.sources:sources.setdefault(source.timeline_blue_id,set()).add(source.actor_blue_id)
        for timeline,actors in sources.items():
            blue=self.catalogue.blue
            allowed=self.provider._actors.get(timeline)
            if allowed is not None:
                if not actors<=allowed:raise ValueError('Timeline actor conflicts with its registered owners')
            else:self.provider.register(blue.get(timeline),tuple(blue.get(x) for x in sorted(actors)))
            self.providers[timeline]=self.provider

    def call(self,document,operation,request=MISSING,*,channel='owner',timestamp=10,actor=None,authority=MISSING):
        root=self._entry_roots.get(document)
        if root is None:raise ValueError('document has no admitted input route')
        snapshot=self.host.load_root(root)
        candidates=[c for v in snapshot.views if v.document_id==document for c in v.channels if c.address.channel_key==channel]
        if not candidates:raise ValueError('no admitted channel for document')
        ch=candidates[0]
        if not ch.sources:raise ValueError('channel has no attributed sources')
        source=ch.sources[0];blue=self.catalogue.blue
        message=self.catalogue.typed('Coordination/Operation Request',channel=channel,operation=operation)
        if request is not MISSING:message['request']=request
        msg=blue.admit_value(self.catalogue.normalize_types(message))
        return self.provider.emit(blue.get(source.timeline_blue_id),blue.get(actor or source.actor_blue_id),msg,
                                  observed_timestamp=timestamp,authority=authority)

    def close_before(self,before):
        for tid in self.providers:self.provider.close_before(tid,before)

    def drain(self,root,*,gas_limit=100000,max_steps=1000):
        result=self.feeder.drain(root,gas_limit=gas_limit,max_steps=max_steps)
        return result

    def state(self,root,document=None):return self.host.selected(root,document)
