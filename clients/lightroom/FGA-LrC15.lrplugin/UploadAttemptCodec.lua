-- Copyright 2026 Terry Ott. MIT License.
-- Private, strict JSON primitives for the upload recovery store. No SDK imports.
local json = require "dkjson"
local M = {null=json.null, MAX_INTEGER=9007199254740991}
function M.integer(v, minimum)
    return type(v)=="number" and v>=minimum and v<=M.MAX_INTEGER and v==math.floor(v)
end
function M.opaque(v)
    -- Existing selection/binding ID grammar is deliberately narrower than the
    -- contract's 256-byte outer ceiling. Do not widen the controlling validator.
    return type(v)=="string" and #v>=1 and #v<=128
        and string.match(v,"^[A-Za-z0-9][A-Za-z0-9@._:%-]*$")~=nil
end
function M.uuid(v)
    return type(v)=="string" and #v==36 and
        string.match(v,"^%x%x%x%x%x%x%x%x%-%x%x%x%x%-%x%x%x%x%-%x%x%x%x%-%x%x%x%x%x%x%x%x%x%x%x%x$")~=nil
end
function M.object(v, fields)
    if type(v)~="table" or v==json.null then return false end
    for k in pairs(v) do if not fields[k] then return false end end
    for k in pairs(fields) do if v[k]==nil then return false end end
    return true
end
function M.fields(names)
    local result={}
    for name in string.gmatch(names,"%S+") do result[name]=true end
    return result
end
function M.array(v, limit, persisted)
    if type(v)~="table" or v==json.null or #v>limit then return false end
    if persisted then
        local mt=getmetatable(v)
        if type(mt)~="table" or mt.__jsontype~="array" then return false end
    end
    local n=0
    for k in pairs(v) do if not M.integer(k,1) or k>#v then return false end; n=n+1 end
    return n==#v
end
function M.newArray() return setmetatable({},{__jsontype="array"}) end
function M.clone(v)
    if type(v)~="table" or v==json.null then return v end
    local result={}
    for k,c in pairs(v) do result[k]=M.clone(c) end
    local mt=getmetatable(v)
    if type(mt)=="table" and mt.__jsontype=="array" then return setmetatable(result,{__jsontype="array"}) end
    return result
end
function M.less(a,b)
    for i=1,math.min(#a,#b) do
        local x,y=string.byte(a,i),string.byte(b,i)
        if x~=y then return x<y end
    end
    return #a<#b
end
function M.time(v)
    if type(v)~="string" or #v>32 then return false end
    local y,m,d,h,n,s,tail=string.match(v,"^(%d%d%d%d)%-(%d%d)%-(%d%d)T(%d%d):(%d%d):(%d%d)(.*)$")
    if not y or (tail~="Z" and not string.match(tail,"^%.%d+Z$")) then return false end
    y,m,d=tonumber(y),tonumber(m),tonumber(d)
    local days={31,28,31,30,31,30,31,31,30,31,30,31}
    if y%4==0 and (y%100~=0 or y%400==0) then days[2]=29 end
    return y>=1 and m>=1 and m<=12 and d>=1 and d<=days[m]
        and tonumber(h)<=23 and tonumber(n)<=59 and tonumber(s)<=59
end
function M.utf8(body)
    local i=1
    while i<=#body do
        local a=string.byte(body,i)
        local count,lo,hi=0,128,191
        if a<128 then count=0
        elseif a>=194 and a<=223 then count=1
        elseif a>=224 and a<=239 then
            count=2; if a==224 then lo=160 elseif a==237 then hi=159 end
        elseif a>=240 and a<=244 then
            count=3; if a==240 then lo=144 elseif a==244 then hi=143 end
        else return false end
        if count>0 then
            local b=string.byte(body,i+1)
            if not b or b<lo or b>hi then return false end
            for j=2,count do
                b=string.byte(body,i+j); if not b or b<128 or b>191 then return false end
            end
        end
        i=i+count+1
    end
    return true
end
-- The decoder uses IEEE doubles. Validate the mathematical decimal value before
-- conversion so a fractional/unsafe lexeme cannot round into a valid revision.
-- Exact integral decimal/exponent spellings remain valid JSON integers.
function M.safeIntegerToken(token)
    local sign,whole,fraction,exponent=string.match(token,"^(%-?)(%d+)%.?(%d*)[eE]?(.*)$")
    if not whole then return false end
    local coefficient=string.gsub(whole..fraction,"^0+","")
    if coefficient=="" then return true end
    if sign=="-" then return false end -- Every numeric field has minimum zero or one.
    local exponentSign=1
    if string.sub(exponent,1,1)=="-" then exponentSign=-1; exponent=string.sub(exponent,2)
    elseif string.sub(exponent,1,1)=="+" then exponent=string.sub(exponent,2) end
    exponent=string.gsub(exponent,"^0+","")
    -- A nonzero coefficient cannot cancel an exponent larger than this bounded
    -- property's digit count. Avoid tonumber on an arbitrarily long exponent.
    if #exponent>8 then return false end
    local shift=exponentSign*(exponent=="" and 0 or tonumber(exponent)) - #fraction
    local integer
    if shift>=0 then
        if #coefficient+shift>16 then return false end
        integer=coefficient..string.rep("0",shift)
    else
        local retained=#coefficient+shift
        if retained<1 or retained>16 or string.find(string.sub(coefficient,retained+1),"[^0]") then return false end
        integer=string.sub(coefficient,1,retained)
    end
    return #integer<16 or (#integer==16 and not M.less("9007199254740991",integer))
end
-- Validate JSON grammar and duplicate keys before dkjson's permissive decoder.
function M.strict(body)
    if type(body)~="string" or not M.utf8(body) then return false end
    local p,n=1,#body
    local function c() return string.sub(body,p,p) end
    local function ws() while string.match(c(),"^[ \t\r\n]$") do p=p+1 end end
    local function str()
        if c()~='"' then return nil end
        local start=p; p=p+1
        while p<=n do
            local ch=c()
            if ch=='"' then p=p+1; return string.sub(body,start,p-1) end
            if string.byte(ch)<32 then return nil end
            if ch=="\\" then
                p=p+1; ch=c()
                if ch=="u" then
                    local hex=string.sub(body,p+1,p+4)
                    if not string.match(hex,"^%x%x%x%x$") then return nil end
                    local code=tonumber(hex,16); p=p+4
                    if code>=55296 and code<=56319 then
                        local low=string.sub(body,p+1,p+6)
                        if not string.match(low,"^\\u%x%x%x%x$") then return nil end
                        local value=tonumber(string.sub(low,3),16)
                        if value<56320 or value>57343 then return nil end
                        p=p+6
                    elseif code>=56320 and code<=57343 then return nil end
                elseif not string.find('"\\/bfnrt',ch,1,true) or ch=="" then return nil end
            end
            p=p+1
        end
        return nil
    end
    local function digits()
        local start=p; while string.match(c(),"^[0-9]$") do p=p+1 end; return p>start
    end
    local val
    val=function(depth)
        if depth>16 then return false end
        ws(); local ch=c()
        if ch=='"' then return str()~=nil end
        if ch=="{" or ch=="[" then
            local object,keys=ch=="{",{}
            local finish=object and "}" or "]"
            p=p+1; ws(); if c()==finish then p=p+1; return true end
            while true do
                if object then
                    local raw=str(); if not raw then return false end
                    local key=json.decode(raw)
                    if type(key)~="string" or keys[key] then return false end
                    keys[key]=true; ws(); if c()~=":" then return false end; p=p+1
                end
                if not val(depth+1) then return false end
                ws(); if c()==finish then p=p+1; return true end
                if c()~="," then return false end; p=p+1; ws()
            end
        end
        for _,literal in ipairs({"true","false","null"}) do
            if string.sub(body,p,p+#literal-1)==literal then p=p+#literal; return true end
        end
        local numberStart=p
        if ch=="-" then p=p+1 end
        if c()=="0" then p=p+1
        elseif string.match(c(),"^[1-9]$") then digits()
        else return false end
        if c()=="." then p=p+1; if not digits() then return false end end
        if c()=="e" or c()=="E" then
            p=p+1; if c()=="+" or c()=="-" then p=p+1 end
            if not digits() then return false end
        end
        return M.safeIntegerToken(string.sub(body,numberStart,p-1))
    end
    if not val(1) then return false end; ws(); return p==n+1
end
function M.decode(raw, maximum)
    if type(raw)~="string" or #raw>maximum or not M.strict(raw) then return nil end
    local value,_,err=json.decode(raw,1,json.null)
    return not err and value or nil
end
function M.encode(document)
    -- Lua 5.1 tostring rounds large exact integers; retain dkjson's documented
    -- custom-encoder convention already used by the catalog group store.
    local function adapt(v)
        if type(v)=="number" then
            return setmetatable({},{__tojson=function() return string.format("%.0f",v) end})
        end
        if type(v)~="table" or v==json.null then return v end
        local result={}
        for k,c in pairs(v) do result[k]=adapt(c) end
        return setmetatable(result,getmetatable(v))
    end
    return json.encode(adapt(document))
end
return M
