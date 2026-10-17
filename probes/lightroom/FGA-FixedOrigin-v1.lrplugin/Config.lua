-- Copyright 2026 Terry Ott. MIT License.
-- Finite qualification policy, independent of release registration.
local C={VERSION="fixed-origin-native-v1", ORIGIN="https://flickrgroupaddr.com",
    CREDENTIAL=string.rep("0000-",12).."0000", SDK="15.3",PREFLIGHT_CASE="png"}
C.FAULT_THUMBNAIL="/api/v001/existing-public-photos/photo/thumbnail?page=1&page_size=1&linked_flickr_revision=1"
C.SOURCES={"probe/Info.lua","probe/Config.lua","probe/Qualification.lua","probe/Run.lua",
    "release/ConnectionCore.lua","release/ExistingPhotoClient.lua",
    "release/SharedReadTransport.lua","release/dkjson.lua"}
C.CASES={}
for name in ("ok invalid-auth png jpeg exact-limit declared-excess undeclared-excess upstream-error "..
    "truncation wrong-media wrong-signature redirect stall missing-auth bad-auth bad-query "..
    "final-installation final-link final-grant foreign-identity private-photo foreign-destination "..
    "edge-redirect-301 edge-redirect-302 edge-redirect-303 edge-redirect-307 edge-redirect-308 "..
    "edge-wrong-media edge-malformed-png edge-truncated-png edge-declared-excess edge-undeclared-excess"):gmatch("%S+") do
    C.CASES[name]=true
end
C.PATHS={["/api/v001/installations/current"]=30,
    ["/api/v001/existing-public-photos?page=1&page_size=1"]=30,
    ["/api/v001/existing-public-photos/photo/thumbnail?page=1&page_size=1&linked_flickr_revision=1"]=15,
    ["/api/v001/existing-public-photos?page=1&page_size=2"]=30,
    ["/api/v001/existing-public-photos?page=2&page_size=2"]=30}
for i=1,3 do
    local page=i==3 and 2 or 1
    C.PATHS["/api/v001/existing-public-photos/photo"..i.."/thumbnail?page="..page..
        "&page_size=2&linked_flickr_revision=1"]=15
end
local function exact(t,names)
    if type(t)~="table" then return false end
    local count,wanted=0,0
    for k in pairs(t) do if not names[k] then return false end; count=count+1 end
    for _ in pairs(names) do wanted=wanted+1 end
    return count==wanted
end
local function hex(v,n) return type(v)=="string" and #v==n and v:match("^[a-f0-9]+$") end
function C.installation(case)
    if case=="ok" or case:match("^edge%-") then case="png" end
    if case=="invalid-auth" then case="bad-auth" end
    return "qualification-"..case.."-install"
end
-- Authentication and discovery use the explicit compliant PNG namespace. Only
-- the one fault thumbnail switches to its configured isolated stimulus case.
function C.requestCase(config,path)
    if type(config)~="table" or not C.PATHS[path] then return nil end
    if config.mode=="fault" then
        if path==C.FAULT_THUMBNAIL then return config.case end
        if path=="/api/v001/installations/current"
            or path=="/api/v001/existing-public-photos?page=1&page_size=1" then return C.PREFLIGHT_CASE end
        return nil
    end
    if path==C.FAULT_THUMBNAIL or path=="/api/v001/existing-public-photos?page=1&page_size=1" then return nil end
    return config.case
end
function C.validate(v,now)
    if not exact(v,{schemaVersion=true,version=true,run=true,capability=true,case=true,
        mode=true,startsAt=true,expiresAt=true,sources=true,workerSha256=true,configurationSha256=true})
        or v.schemaVersion~=1 or v.version~=C.VERSION or not hex(v.run,32)
        or not hex(v.capability,64) or not C.CASES[v.case]
        or not ({fault=true,browser=true,cancel=true,stale=true})[v.mode]
        or v.mode~="fault" and v.case~="ok" then return false end
    if type(now)~="number" or now~=now or type(v.startsAt)~="number" or type(v.expiresAt)~="number"
        or v.startsAt~=math.floor(v.startsAt) or v.expiresAt~=math.floor(v.expiresAt)
        or v.startsAt>now or now>=v.expiresAt or v.expiresAt-v.startsAt>600
        or v.expiresAt<=v.startsAt or not hex(v.workerSha256,64)
        or not hex(v.configurationSha256,64) then return false end
    local names={}; for _,name in ipairs(C.SOURCES) do names[name]=true end
    if not exact(v.sources,names) then return false end
    for _,hash in pairs(v.sources) do if not hex(hash,64) then return false end end
    return true
end
return C
