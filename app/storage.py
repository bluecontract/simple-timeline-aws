"""Atomic commit of immutable S3 snapshots through a DynamoDB compare-and-swap."""
import gzip,hashlib,json,random,time,uuid
from .catalogue import Catalogue
from .console import ConsoleView
from blue_language.physical import PhysicalCache

class Busy(Exception):pass

class StateStore:
    def __init__(self,table,s3,bucket,endpoint,name,seed,provider_company='',provider_website=''):
        self.table,self.s3,self.bucket=table,s3,bucket
        self.endpoint,self.name,self.seed=endpoint,name,seed
        self.provider_company,self.provider_website=provider_company,provider_website
        self.cached=None;self.cache_revision=None;self.physical=PhysicalCache(65536)
        self.read_snapshot=None;self.read_revision=None

    def _snapshot(self,pointer):
        if not pointer:return None
        if self.read_snapshot is None or self.read_revision!=pointer['revision']:
            packed=self.s3.get_object(Bucket=self.bucket,Key=pointer['key'])['Body'].read()
            if hashlib.sha256(packed).hexdigest()!=pointer['sha256']:raise RuntimeError('Snapshot integrity failure')
            self.read_snapshot=json.loads(gzip.decompress(packed))
            self.read_revision=pointer['revision']
        return self.read_snapshot

    def read_owner(self,path,query):
        # Always check the committed pointer, including after another Lambda's
        # write. A cached read model can never outlive its committed revision.
        for _ in range(2):
            pointer=self.table.get_item(Key={'pk':'STATE'},ConsistentRead=True).get('Item')
            snapshot=self._snapshot(pointer)
            if snapshot is not None and 'console' in snapshot:
                return ConsoleView(snapshot).read(path,query)
            # One-time migration of an older snapshot (or first initialization),
            # using the same CAS and admission path as any other state commit.
            self.execute(lambda c:None,write=True)
        raise Busy('Console initialization; retry')

    def execute(self,operation,write=False):
        with self.physical.scope():
            for attempt in range(5):
                pointer=self.table.get_item(Key={'pk':'STATE'},ConsistentRead=True).get('Item')
                revision=pointer['revision'] if pointer else None
                if self.cached is None or self.cache_revision!=revision:
                    snapshot=self._snapshot(pointer)
                    self.cached=Catalogue(self.endpoint,self.name,self.seed,snapshot,self.provider_company,self.provider_website)
                    self.cache_revision=revision
                try:
                    result=operation(self.cached)
                    if not write and pointer:return result
                    raw=json.dumps(self.cached.snapshot(),ensure_ascii=False,separators=(',',':')).encode()
                    packed=gzip.compress(raw,mtime=0);new_revision=uuid.uuid4().hex;key='snapshots/'+new_revision+'.json.gz'
                    self.s3.put_object(Bucket=self.bucket,Key=key,Body=packed,ContentType='application/gzip',ServerSideEncryption='AES256')
                    item={'pk':'STATE','revision':new_revision,'key':key,'sha256':hashlib.sha256(packed).hexdigest(),'updatedAt':int(time.time())}
                    arguments={'Item':item,'ConditionExpression':'revision = :r','ExpressionAttributeValues':{':r':revision}} if pointer else {'Item':item,'ConditionExpression':'attribute_not_exists(pk)'}
                    try:self.table.put_item(**arguments)
                    except Exception as exc:
                        self.cached=None
                        if getattr(exc,'response',{}).get('Error',{}).get('Code')!='ConditionalCheckFailedException':raise
                        time.sleep(random.uniform(.02,.08)*(attempt+1));continue
                    self.cache_revision=new_revision
                    return result
                except Exception:
                    self.cached=None
                    raise
            raise Busy('Concurrent changes; retry using the same idempotency key')
