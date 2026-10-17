-- Pure configuration boundary. SDK serialization and durable settings adapters are injected.
local Client = {}
local fields = {schemaVersion=true,fgaPublishServiceId=true,issuingInstallationId=true,
    linkedFlickrRevision=true,serviceRevision=true}
local function exact(value, keys)
    if type(value)~='table' then return false end
    for k in pairs(value) do if not keys[k] then return false end end
    for k in pairs(keys) do if value[k]==nil then return false end end
    return true
end
local function validId(value)
    return type(value)=='string' and #value==36
        and value:match('^%x%x%x%x%x%x%x%x%-%x%x%x%x%-4%x%x%x%-[89ab]%x%x%x%-%x%x%x%x%x%x%x%x%x%x%x%x$')~=nil
        and value==value:lower()
end
local function validIdentity(v)
    return exact(v,fields) and v.schemaVersion==1 and validId(v.fgaPublishServiceId)
        and type(v.issuingInstallationId)=='string' and #v.issuingInstallationId<=128
        and v.issuingInstallationId:match('^[A-Za-z0-9][A-Za-z0-9@._:%-]*$')~=nil
        and type(v.linkedFlickrRevision)=='number' and v.linkedFlickrRevision>=1
        and v.linkedFlickrRevision<=9007199254740991 and v.linkedFlickrRevision%1==0
        and v.serviceRevision==1
end
local function same(a,b)
    if not validIdentity(a) or not validIdentity(b) then return false end
    for k in pairs(fields) do if a[k]~=b[k] then return false end end
    return true
end
local function copy(v)
    local result={} for k in pairs(fields) do result[k]=v[k] end return result
end
local function stop(code) return {ok=false,code=code} end
local function decode(response, status)
    if type(response)~='table' or response.status~=status or type(response.headers)~='table'
        or response.headers['Cache-Control']~='no-store'
        or response.headers['X-Content-Type-Options']~='nosniff'
        or response.headers['Referrer-Policy']~='no-referrer' then return nil end
    local body=response.body
    local keys={linkStatus=true} for k in pairs(fields) do keys[k]=true end
    if not exact(body,keys) then return nil end
    local identity=copy(body)
    if not validIdentity(identity) or (body.linkStatus~='ready' and body.linkStatus~='link_changed'
        and body.linkStatus~='link_unavailable') then return nil end
    return identity,body.linkStatus
end
function Client.new(deps)
    assert(type(deps)=='table' and type(deps.withServiceLock)=='function'
        and type(deps.read)=='function' and type(deps.save)=='function'
        and type(deps.hasRetainedRecords)=='function' and type(deps.request)=='function')
    local self={}
    local function resume(settings, saved)
        if not validIdentity(saved) then return stop('identity_repair_required') end
        local response=deps.request('GET','/api/v001/publish-services/'..saved.fgaPublishServiceId,nil)
        local identity,status=decode(response,200)
        if not identity then return stop('identity_read_failed') end
        if not same(saved,identity) or not same(deps.read(settings),saved) then return stop('identity_repair_required') end
        if status~='ready' then return stop(status) end
        return {ok=true,identity=copy(identity),linkStatus=status}
    end
    local function locked(settings, configure)
        local ok,result=pcall(function()
            return deps.withServiceLock(settings,function()
                -- nil alone means absent. Partial, malformed or failed reads must not look absent.
                local saved=deps.read(settings)
                if saved~=nil then return resume(settings,saved) end
                if not configure then return stop('identity_missing') end
                if deps.hasRetainedRecords(settings)~=false then return stop('identity_repair_required') end
                local response=deps.request('POST','/api/v001/publish-services',{schemaVersion=1})
                local identity,status=decode(response,201)
                if not identity or status~='ready' or response.headers.Location~='/api/v001/publish-services/'..identity.fgaPublishServiceId then
                    return stop('identity_create_failed')
                end
                -- The response grants no use authority until exact durable save/readback.
                local observed=deps.read(settings)
                if observed~=nil then return resume(settings,observed) end
                if deps.save(settings,copy(identity))~=true then return stop('identity_save_failed') end
                if not same(deps.read(settings),identity) then return stop('identity_save_failed') end
                return {ok=true,identity=copy(identity),linkStatus='ready'}
            end)
        end)
        if not ok or type(result)~='table' then return stop('identity_adapter_failed') end
        return result
    end
    function self:configure(settings) return locked(settings,true) end
    function self:verifyService(settings) return locked(settings,false) end
    return self
end
Client.validIdentity=validIdentity
return Client
