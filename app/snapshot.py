"""Restore previously admitted objects from a verified, runtime-bound snapshot."""
import copy,json
from algorithms import blue as B


def restore_objects(exact,objects):
    language=exact.language
    context=language.processing_context()
    pending=[]
    for bid,obj in objects.items():
        source=json.dumps(obj,sort_keys=True,separators=(',',':'))
        # Reuse immutable dependency evidence while keeping per-object limits.
        # Rebuilding a resolver copies the growing store for every history item.
        context.work=0
        context.demands.clear()
        node=B.input_node({'text':source,'format':'json','mode':'source'},context)
        raw_id=B.identity(node)
        if isinstance(node,B.Ref):
            body=B.open_exact(node,context)
            if '#' not in raw_id:context.remember(body)
        else:
            context.remember(node)
        if raw_id!=bid:
            pending.append((bid,obj,source))
        else:
            exact.objects[bid]=copy.deepcopy(obj)
            exact._identified[source]=bid

    # Publish each resolved body once, rather than repeatedly exporting the
    # shared dependency closure through publish_raw for every saved object.
    for bid,body in list(context.bodies.items()):
        if bid in B.CORE.values() or '#' in bid:continue
        context.work=0
        context.demands.clear()
        language.provider.set_exact(bid,B.export_exact(body,context))

    # Source spelling may contain inherited duplicates removed at admission.
    # Keep the existing canonical admission and identity check for those cases.
    for bid,obj,source in pending:
        document=language.create(source,format='json')
        if document.blue_id!=bid:raise ValueError('CORRUPT_STATE')
        language.publish_document(document)
        exact.objects[bid]=copy.deepcopy(obj)
        exact._identified[source]=bid
