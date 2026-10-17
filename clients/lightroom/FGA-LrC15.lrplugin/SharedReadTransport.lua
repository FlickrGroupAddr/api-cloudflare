-- Copyright 2026 Terry Ott. MIT License.
-- Disabled policy adapter. Returned byte limits are post-allocation only.
local Module = {PRODUCTION_QUALIFIED=false, POLICY_VERSION="shared-read-v1-2026-10-17",
    ORIGIN="https://flickrgroupaddr.com", MAX_RESPONSE_BYTES=2097152, TIMEOUT_SECONDS=30}
local Core = require "ConnectionCore"
local json = require "dkjson"
local function integer(v, minimum, maximum)
    return type(v)=="number" and v>=minimum and v<=maximum and v==math.floor(v)
end
local function encode(v)
    return (v:gsub("([^A-Za-z0-9_.~-])",function(c) return string.format("%%%02X",c:byte()) end))
end
local function component(v)
    if type(v)~="string" or #v>384 then return nil end
    local decoded=v:gsub("%%(%x%x)",function(c) return string.char(tonumber(c,16)) end)
    if encode(decoded)~=v then return nil end
    return decoded
end
local function opaque(v)
    return type(v)=="string" and #v>=1 and #v<=128 and v:match("^[A-Za-z0-9][A-Za-z0-9@._:%-]*$")~=nil
end
local function number(v,maximum)
    return type(v)=="string" and v:match("^[1-9]%d*$") and #v<=16
        and integer(tonumber(v),1,maximum) and string.format("%.0f",tonumber(v))==v
end
-- Match the clients' finite READ surface. Never accept a URL, thumbnail, OAuth,
-- browser route, unknown parameter, duplicate query key or arbitrary API path.
function Module.allowedPath(path)
    if type(path)~="string" or #path>2048 then return false end
    if path=="/api/v001/installations/current" then return true,65536 end
    local base,query=path:match("^([^?]+)%?([^?]+)$")
    if not base then return false end
    local fields={}
    for pair in (query.."&"):gmatch("(.-)&") do
        local key,value=pair:match("^([a-z_]+)=([^=&]+)$")
        if not key or fields[key] then return false end
        fields[key]=value
    end
    local allowed={}
    local function only(names)
        for name in names:gmatch("%S+") do allowed[name]=true end
        for key in pairs(fields) do if not allowed[key] then return false end end
        return true
    end
    if base=="/api/v001/existing-public-photos" then
        return only("page page_size") and number(fields.page,1000000)
            and number(fields.page_size,100) and true or false,Module.MAX_RESPONSE_BYTES
    elseif base=="/api/v001/groups" then
        return only("page_size snapshot_revision after_group_id") and number(fields.page_size,100)
            and ((fields.snapshot_revision==nil and fields.after_group_id==nil)
                or (number(fields.snapshot_revision,9007199254740991)
                    and opaque(component(fields.after_group_id)))) and true or false,Module.MAX_RESPONSE_BYTES
    elseif base:match("^/api/v001/photo%-bindings/([^/]+)/group%-memberships$") then
        local binding=base:match("^/api/v001/photo%-bindings/([^/]+)/group%-memberships$")
        return opaque(component(binding)) and only("page_size observation_revision after_group_id")
            and number(fields.page_size,100)
            and ((fields.observation_revision==nil and fields.after_group_id==nil)
                or (number(fields.observation_revision,9007199254740991)
                    and opaque(component(fields.after_group_id)))) and true or false,Module.MAX_RESPONSE_BYTES
    elseif base=="/api/v001/group-submission-intents" then
        local time=component(fields.before_created_at)
        return only("view page_size photo_binding_id before_created_at before_intent_id")
            and fields.view=="history" and fields.page_size=="100"
            and opaque(component(fields.photo_binding_id))
            and ((fields.before_created_at==nil and fields.before_intent_id==nil)
                or (type(time)=="string" and #time<=40
                    and time:match("^%d%d%d%d%-%d%d%-%d%dT%d%d:%d%d:%d%d[%.%d]*Z$")
                    and opaque(component(fields.before_intent_id)))) and true or false,Module.MAX_RESPONSE_BYTES
    end
    return false
end
local function finite(v) return type(v)=="number" and v==v and v~=math.huge and v~=-math.huge end
local function utf8(v)
    local i=1
    while i<=#v do
        local a,b=v:byte(i),v:byte(i+1)
        local width=a<128 and 1 or a>=194 and a<=223 and 2 or a>=224 and a<=239 and 3
            or a>=240 and a<=244 and 4
        if not width or i+width-1>#v then return false end
        for j=i+1,i+width-1 do local c=v:byte(j); if c<128 or c>191 then return false end end
        if (a==224 and b<160) or (a==237 and b>159) or (a==240 and b<144) or (a==244 and b>143) then return false end
        i=i+width
    end
    return true
end
local function strictJson(body, decode)
    local pos, length = 1, #body
    local function char() return string.sub(body, pos, pos) end
    local function white()
        while char() == " " or char() == "\t" or char() == "\r" or char() == "\n" do pos = pos + 1 end
    end
    local function jsonString()
        if char() ~= '"' then return nil end
        local start = pos
        pos = pos + 1
        while pos <= length do
            local current = char()
            if current == '"' then pos = pos + 1; return string.sub(body, start, pos - 1) end
            if string.byte(current) < 32 then return nil end
            if current == "\\" then
                pos = pos + 1
                current = char()
                if current == "u" then
                    if not string.match(string.sub(body, pos + 1, pos + 4), "^%x%x%x%x$") then return nil end
                    pos = pos + 4
                elseif current ~= '"' and current ~= "\\" and current ~= "/" and current ~= "b"
                    and current ~= "f" and current ~= "n" and current ~= "r" and current ~= "t" then return nil end
            end
            pos = pos + 1
        end
        return nil
    end
    local function digits()
        local start = pos
        while string.match(char(), "^[0-9]$") do pos = pos + 1 end
        return pos > start
    end
    local value
    value = function(depth)
        if depth > 32 then return false end
        white()
        local current = char()
        if current == '"' then return jsonString() ~= nil end
        if current == "{" or current == "[" then
            local object, keys = current == "{", {}
            local finish = object and "}" or "]"
            pos = pos + 1
            white()
            if char() == finish then pos = pos + 1; return true end
            while true do
                if object then
                    local rawKey = jsonString()
                    if not rawKey then return false end
                    local ok, key = pcall(decode, rawKey)
                    if not ok or type(key) ~= "string" or keys[key] then return false end
                    keys[key] = true
                    white()
                    if char() ~= ":" then return false end
                    pos = pos + 1
                end
                if not value(depth + 1) then return false end
                white()
                if char() == finish then pos = pos + 1; return true end
                if char() ~= "," then return false end
                pos = pos + 1
                white()
            end
        end
        for _, literal in ipairs({"true", "false", "null"}) do
            if string.sub(body, pos, pos + #literal - 1) == literal then
                pos = pos + #literal
                return true
            end
        end
        if current == "-" then pos = pos + 1 end
        if char() == "0" then pos = pos + 1
        elseif string.match(char(), "^[1-9]$") then digits()
        else return false end
        if char() == "." then pos = pos + 1; if not digits() then return false end end
        if char() == "e" or char() == "E" then
            pos = pos + 1
            if char() == "+" or char() == "-" then pos = pos + 1 end
            if not digits() then return false end
        end
        return true
    end
    if not value(1) then return false end
    white()
    return pos == length + 1
end


-- Strict grammar precedes bundled dkjson so explicit null, empty object and
-- empty array remain distinct, duplicate decoded keys cannot be overwritten,
-- and permissive dkjson extensions never enter the existing protocol clients.
function Module.decode(bytes)
    if type(bytes)~="string" or #bytes>Module.MAX_RESPONSE_BYTES or not utf8(bytes)
        or not strictJson(bytes,json.decode) then return nil end
    local value,position,err=json.decode(bytes,1,json.null)
    if err or position~=#bytes+1 and bytes:sub(position):find("[^ \t\r\n]") then return nil end
    local function valid(v,depth)
        if depth>32 then return false end
        if v==json.null then return true end
        if type(v)=="number" then return finite(v) end
        if type(v)=="string" then return utf8(v) end
        if type(v)~="table" then return type(v)=="boolean" end
        for k,item in pairs(v) do
            if type(k)=="string" and not utf8(k) or not valid(item,depth+1) then return false end
        end
        return true
    end
    if not valid(value,1) then return nil end
    return value
end
Module.encode=json.encode
Module.jsonNull=json.null
local function trimOWS(value)
    return (value:gsub("^[ \t]*",""):gsub("[ \t]*$",""))
end
local function jsonMediaType(value)
    local media=trimOWS(value):lower()
    if media=="application/json" then return true end
    local charset=media:match('^application/json[ \t]*;[ \t]*charset=(.+)$')
    return charset=="utf-8" or charset=='"utf-8"'
end
-- Recognize directive/token boundaries without repairing whitespace inside a
-- token. Quoted extension values may contain commas and escaped quotes.
local function noStore(value)
    local pos,length,found=1,#value,false
    local function char() return value:sub(pos,pos) end
    local function ows()
        while char()==" " or char()=="\t" do pos=pos+1 end
    end
    local function token()
        local text=value:sub(pos):match("^([!#$%%&'*+.^_`|~A-Za-z0-9%-]+)")
        if not text then return nil end
        pos=pos+#text
        return text
    end
    while true do
        ows()
        local name=token()
        if not name then return false end
        local store=name:lower()=="no-store"
        if char()=="=" then
            if store then return false end
            pos=pos+1
            if char()=='"' then
                pos=pos+1
                while pos<=length and char()~='"' do
                    if char()=="\\" then
                        pos=pos+1
                        if pos>length then return false end
                    end
                    pos=pos+1
                end
                if char()~='"' then return false end
                pos=pos+1
            elseif not token() then return false end
        end
        if store then found=true end
        ows()
        if pos==length+1 then return found end
        if char()~="," then return false end
        pos=pos+1
    end
end
local function response(bytes,headers,limit,image)
    if type(bytes)~="string" or #bytes>limit or type(headers)~="table"
        or headers.error~=nil or not integer(headers.status,200,599) or headers.status>=300 and headers.status<400
        or headers.status~=200 and headers.status~=202 and headers.status<400 then return nil,{} end
    local values,count={},0
    for key,h in pairs(headers) do
        if type(key)=="number" then
            if not integer(key,1,#headers) or type(h)~="table" or type(h.field)~="string"
                or not h.field:match("^[!#$%%&'*+.^_`|~%w%-]+$") or type(h.value)~="string"
                or h.value:find("[%z\1-\8\10-\31\127]") then return nil,{} end
            count=count+1
            local name=h.field:lower()
            if name=="location" or values[name] then return nil,{} end
            values[name]=h.value
        elseif key~="status" and key~="error" then return nil,{} end
    end
    if count~=#headers then return nil,{} end
    local media=values["content-type"] or ""
    if not noStore(values["cache-control"] or "") then return nil,{} end
    if image then
        -- Signature/format checks remain with the actual thumbnail client.
        if headers.status~=200 or media~="image/png" and media~="image/jpeg" then return nil,{} end
    elseif not jsonMediaType(media) then return nil,{} end
    local length=values["content-length"]
    if length and (not length:match("^%d+$") or #length>10 or tonumber(length)~=#bytes) then return nil,{} end
    local document
    if not image then
        document=Module.decode(bytes)
        if type(document)~="table" or getmetatable(document).__jsontype~="object" then return nil,{} end
    end
    if headers.status==401 then
        local code=type(document.error)=="table" and document.error.code or nil
        if code~="invalid_token" or values["www-authenticate"]~='Bearer realm="fga-api", error="invalid_token"' then
            return nil,{}
        end
    end
    -- Copy only interpreted headers. Native error tables may contain raw URLs
    -- or exception text and are deliberately never returned to the clients.
    local safe={status=headers.status}
    for _,name in ipairs({"content-type","cache-control","content-length","retry-after","www-authenticate"}) do
        if values[name] then safe[#safe+1]={field=name,value=values[name]} end
    end
    return bytes,safe
end
function Module.response(bytes,headers,limit) return response(bytes,headers,limit,false) end
function Module.new() return nil,"qualification_required" end
-- Both compositions share the credential, current-context, cancellation and
-- returned-byte gates. The caller supplies a yield-safe protector; GET must
-- never be enclosed in Lua 5.1's built-in pcall in the native composition.
local function adapterFor(d,policy,expectedCredential)
    if type(d)~="table" then return nil,"adapter_unavailable" end
    for _,name in ipairs({"get","call","retrieve","current","cancelled","now"}) do
        if type(d[name])~="function" then return nil,"adapter_unavailable" end
    end
    local closed,credential=false,nil
    local function gate()
        if closed then return false end
        local ok,same=d.call(function()
            if d.current()~=true or d.cancelled()~=false then return false end
            local candidate=d.retrieve(Core.CANDIDATE_KEY)
            local current=d.retrieve(Core.CURRENT_KEY)
            if candidate~=nil and candidate~="" or not Core.isCanonicalCredential(current) then return false end
            if expectedCredential and current~=expectedCredential then return false end
            if credential==nil then credential=current end
            return credential==current
        end)
        if not ok or same~=true then closed=true; credential=nil; return false end
        return true
    end
    local adapter={expectedInstallationId=d.expectedInstallationId,capabilities={readTransport=false,proofTransport=false,thumbnailTransport=false},
        decode=Module.decode,encode=json.encode,jsonNull=json.null,PRODUCTION_QUALIFIED=false}
    function adapter.cancel() closed=true; credential=nil end
    function adapter.cancelled() return not gate() end
    function adapter.retrieve(key)
        if key~=Core.CURRENT_KEY and key~=Core.CANDIDATE_KEY or not gate() then return nil end
        return key==Core.CURRENT_KEY and credential or nil
    end
    function adapter.protect(fn)
        if not gate() then return nil,{} end
        local ok,a,b=d.call(fn)
        if not gate() or not ok then return nil,{} end
        return a,b
    end
    function adapter.httpGet(url,headers,timeout)
        if type(url)~="string" or url:sub(1,#Module.ORIGIN)~=Module.ORIGIN then return nil,{} end
        local path=url:sub(#Module.ORIGIN+1)
        local allowed,limit,expectedTimeout,image=policy(path)
        if not allowed or timeout~=expectedTimeout or not gate() then return nil,{} end
        if type(headers)~="table" or #headers~=1 then return nil,{} end
        local count=0
        for key in pairs(headers) do if key~=1 then return nil,{} end; count=count+1 end
        local h=headers[1]
        if count~=1 or type(h)~="table" or h.field~="Authorization"
            or h.value~="Bearer "..credential then return nil,{} end
        for key in pairs(h) do if key~="field" and key~="value" then return nil,{} end end
        local ok,bytes,responseHeaders,start,finish=d.call(function()
            local before=d.now()
            if not finite(before) then return nil,nil,nil,nil end
            -- This expresses requested policy, not proven native redirect,
            -- preallocation, hard total deadline or disconnect controls.
            local body,result=d.get(Module.ORIGIN..path,
                {{field="Authorization",value="Bearer "..credential}},expectedTimeout)
            return body,result,before,d.now()
        end)
        if not gate() then return nil,{} end
        if not ok or not finite(start) or not finite(finish) or finish<start
            or finish-start>=expectedTimeout then return nil,{} end
        return response(bytes,responseHeaders,limit,image)
    end
    return adapter
end
-- Synthetic-only entry point: no native dependency composition belongs here.
function Module.offline(d)
    return adapterFor(d,function(path)
        local allowed,limit=Module.allowedPath(path)
        return allowed,limit,Module.TIMEOUT_SECONDS,false
    end)
end
-- Separately versioned fixed-origin qualification only. No caller-supplied
-- allowlist, arbitrary photo ID, revision, API route or URL is accepted.
-- Only the fixture's pinned synthetic bearer can enter this composition.
-- Keep this finite set aligned with FGA-FixedOrigin-v1.lrplugin/Config.lua;
-- changing that fixture requires a reviewed source/configuration binding.
local qualificationPaths={
    ["/api/v001/installations/current"]=30,
    ["/api/v001/existing-public-photos?page=1&page_size=1"]=30,
    ["/api/v001/existing-public-photos/photo/thumbnail?page=1&page_size=1&linked_flickr_revision=1"]=15,
    ["/api/v001/existing-public-photos?page=1&page_size=2"]=30,
    ["/api/v001/existing-public-photos?page=2&page_size=2"]=30,
    ["/api/v001/existing-public-photos/photo1/thumbnail?page=1&page_size=2&linked_flickr_revision=1"]=15,
    ["/api/v001/existing-public-photos/photo2/thumbnail?page=1&page_size=2&linked_flickr_revision=1"]=15,
    ["/api/v001/existing-public-photos/photo3/thumbnail?page=2&page_size=2&linked_flickr_revision=1"]=15,
}
function Module.qualification(d)
    return adapterFor(d,function(path)
        local timeout=qualificationPaths[path]
        if not timeout then return false end
        local image=timeout==15
        local allowed,limit=Module.allowedPath(path)
        if not image and not allowed then return false end
        return true,image and 262144 or limit,timeout,image
    end,string.rep("0000-",12).."0000")
end
return Module
