"""Provider presentation fields; endpoint identity is separate from website claims."""
from urllib.parse import urlsplit

def initial_details(name,company='',website=''):
    if not isinstance(name,str) or not 1<=len(name.strip())<=120:raise ValueError('INVALID_PROVIDER_NAME')
    if not isinstance(company,str) or len(company.strip())>200:raise ValueError('INVALID_PROVIDER_COMPANY')
    if not isinstance(website,str) or len(website)>2048:raise ValueError('INVALID_PROVIDER_WEBSITE')
    website=website.strip()
    if website:
        parts=urlsplit(website)
        if parts.scheme!='https' or not parts.hostname or parts.username is not None or parts.password is not None or any(c.isspace() for c in website):raise ValueError('INVALID_PROVIDER_WEBSITE')
    result={'displayName':name.strip()}
    if company.strip():result['companyName']=company.strip()
    if website:result['website']=website
    return result

def resolved_details(definition,provider):
    result={}
    for field in ('displayName','companyName','website','endpoint'):
        value=provider.get(field,definition.get(field))
        if isinstance(value,str):result[field]=value
    # The first release stored ProviderName in companyName. Retain its claims
    # and exact identity rather than adding fields to already signed objects.
    if not result.get('displayName'):result['displayName']=result.get('companyName',definition.get('name','Timeline Provider'))
    return result

def inline_provider(value,provider_id,provider):
    if isinstance(value,list):return [inline_provider(x,provider_id,provider) for x in value]
    if isinstance(value,dict):
        if value=={'blueId':provider_id}:return provider
        return {k:inline_provider(v,provider_id,provider) for k,v in value.items()}
    return value
