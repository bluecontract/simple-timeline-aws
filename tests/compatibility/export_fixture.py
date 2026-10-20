"""Export real signed provider histories for verification by the MyOS Java runtime."""
from pathlib import Path
import json
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.catalogue import Catalogue, PhysicalCache
from reference import ref


def export(destination):
    with PhysicalCache(65536).scope(), patch('app.catalogue.now', return_value=100):
        c = Catalogue('https://compatibility.example', 'Compatibility test', b'\x11' * 32)
        timeline = c.create_timeline('External party', False, 'timeline')
        tid = c.e.identity(timeline)
        access = c.create_access('Agreement readers', [tid], ['22' * 32], 'grant')
        aid = access['blueId']
        phases = []
        for key, keys in [('initial', ['22' * 32]), ('add-reader', ['22' * 32, '33' * 32]),
                          ('unchanged', ['22' * 32, '33' * 32]), ('revoke', [])]:
            if key != 'initial':
                c.update_access(aid, [tid], keys, key)
            row = c.list_access()[0]
            query = c.p.request('Read Timeline Request', timeline=ref(row['controlTimeline']), limit=50)
            response = c.protocol('/timelines/read', c.export(query))
            access_query = c.p.request('Get Timeline Access Request', access=ref(aid))
            phases.append(dict(name=key, query=c.export(query), response=response,
                               accessResponse=c.protocol('/access/get', c.export(access_query)),
                               current=c.object(row['current']), currentId=row['current']))
        # Include the exact dependency closure, not a caller-supplied claim of trust.
        objects = {}
        for bid in [*c.e.objects, c.provider_type]:
            admitted = c.e.language.load(bid, goal='definition' if bid == c.provider_type else 'value')
            for content_id, record in admitted.dependency_responses().items():
                objects[content_id] = json.loads(record['text'])
        Path(destination).write_text(json.dumps(dict(
            provider=c.export(c.p.provider), descriptor=c.descriptor(aid), accessId=aid,
            initial=c.object(aid), phases=phases, objects=objects)))


if __name__ == '__main__':
    export(sys.argv[1])
