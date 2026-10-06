"""Password-only owner sessions. Ed25519 reader authentication lives in the protocol."""
import base64,hashlib,hmac,secrets,time
from http.cookies import SimpleCookie

COOKIE='timeline_owner'
SESSION_SECONDS=12*60*60

def password_hash(password,salt):
    return hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1,dklen=32).hex()

class OwnerSessions:
    def __init__(self,table,secret):self.table,self.secret=table,secret
    def token(self,headers):
        c=SimpleCookie()
        try:c.load(headers.get('cookie',''));return c[COOKIE].value if COOKIE in c else None
        except Exception:return None
    def pk(self,token):return 'SESSION#'+hashlib.sha256(token.encode()).hexdigest()
    def authenticated(self,headers):
        token=self.token(headers)
        if not token or len(token)>128:return False
        item=self.table.get_item(Key={'pk':self.pk(token)},ConsistentRead=True).get('Item')
        return bool(item and item['expiresAt']>int(time.time()) and item.get('credentialTag')==self.secret['passwordHash'])
    def origin(self,headers,endpoint):
        return hmac.compare_digest(headers.get('origin',''),endpoint)
    def login(self,password,source_ip):
        if not isinstance(password,str) or len(password)>256:raise PermissionError('Invalid password')
        # Fixed-window counter is atomic, and does not store the originating IP.
        period=int(time.time())//300
        ratekey='LOGIN#'+hashlib.sha256(source_ip.encode()).hexdigest()+'#'+str(period)
        result=self.table.update_item(Key={'pk':ratekey},UpdateExpression='ADD attempts :one SET expiresAt = :expires',ExpressionAttributeValues={':one':1,':expires':(period+2)*300},ReturnValues='ALL_NEW')
        if int(result['Attributes']['attempts'])>20:raise PermissionError('Too many login attempts; try again in five minutes')
        if not hmac.compare_digest(password_hash(password,self.secret['salt']),self.secret['passwordHash']):raise PermissionError('Invalid password')
        token=secrets.token_urlsafe(32)
        self.table.put_item(Item={'pk':self.pk(token),'expiresAt':int(time.time())+SESSION_SECONDS,'credentialTag':self.secret['passwordHash']})
        return f'{COOKIE}={token}; Path=/; Max-Age={SESSION_SECONDS}; HttpOnly; Secure; SameSite=Strict'
    def logout(self,headers):
        token=self.token(headers)
        if token:self.table.delete_item(Key={'pk':self.pk(token)})
        return f'{COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Strict'
