-- Copyright 2026 Terry Ott. MIT License.
-- Prepared source only. Do not load/invoke without the later native action gate.
local paths,files,tasks=import "LrPathUtils",import "LrFileUtils",import "LrTasks"
local contexts,http,date=import "LrFunctionContext",import "LrHttp",import "LrDate"
local Digest,Application,System=import "LrDigest",import "LrApplication",import "LrSystemInfo"
local Dialogs,View,Progress=import "LrDialogs",import "LrView",import "LrProgressScope"
local root="C:\\Temp\\FGA-fixed-origin-v1"
local probe=_PLUGIN.path
local release=paths.child(paths.parent(paths.parent(paths.parent(probe))),"clients/lightroom/FGA-LrC15.lrplugin")
local function read(path,limit)
    local f=assert(io.open(path,"rb"));local value=f:read(limit+1);f:close()
    assert(value and #value<=limit);return value
end
local function write(path,bytes)
    local f=io.open(path,"wb");if not f then return false end
    local ok,value=pcall(function() return f:write(bytes) end)
    local closed,result=pcall(function() return f:close() end)
    return ok and value~=nil and closed and result~=nil
end
local function remove(path)
    if not path then return true end
    local ok,value=pcall(function() return not files.exists(path) or files.delete(path) end)
    return ok and value and true or false
end
-- Isolated finite module loading leaves release source and package.loaded intact.
local modules,sourceBytes={},{}
local function bytes(name,path)
    if not sourceBytes[name] then sourceBytes[name]=read(path,1048576) end
    return sourceBytes[name]
end
local function probeModule(name)
    return assert(loadstring(bytes("probe/"..name..".lua",paths.child(probe,name..".lua")),name))()
end
local function load(name)
    if modules[name] then return modules[name] end
    assert(({ConnectionCore=true,ExistingPhotoClient=true,SharedReadTransport=true,dkjson=true})[name])
    local chunk=assert(loadstring(bytes("release/"..name..".lua",paths.child(release,name..".lua")),name))
    local env=setmetatable({require=load},{__index=_G});setfenv(chunk,env)
    modules[name]=chunk();return modules[name]
end
contexts.postAsyncTaskWithContext("FGA fixed-origin v1",function(context)
    local C=probeModule("Config")
    local Q=probeModule("Qualification")
    local json=load("dkjson")
    local state={schemaVersion=1,version=C.VERSION,productionQualified=false,
        readTransportQualified=false,thumbnailTransportQualified=false,
        nativeGetAbortSupported=false,allocationBoundProven=false,redirectProtectionProven=false,
        reason="preflight_rejected",completePages=0,pictureControls=0,observerConfirmedPages=0,
        staleResultsDiscarded=0,navigation=0,nativeCalls=0,cacheCleanupConfirmed=false}
    local closed,protocol,cache,config=false,nil,nil,nil
    local progress=Progress{title="Fixed-origin finite characterization",functionContext=context}
    progress:setCancelable(true)
    -- One owner; context outlives every yielding GET and modal view. Cleanup
    -- runs after task return/error; no independent task can delete this cache.
    context:addCleanupHandler(function()
        closed=true
        if protocol then pcall(protocol.close) end
        protocol=nil;config=nil;modules={};sourceBytes={}
        state.cacheCleanupConfirmed=remove(cache)
        if not state.cacheCleanupConfirmed then state.reason="cache_cleanup_failed" end
        pcall(function() progress:done() end)
        if state.run then
            local final=paths.child(root,"receipt-"..state.run..".json")
            local temp=final..".tmp"
            -- No payload, capability, synthetic bearer, URL, title, path, raw
            -- SDK error or credential-store value enters this terminal receipt.
            if write(temp,json.encode(state)) and not files.exists(final) then files.move(temp,final) end
        end
    end)
    local function now() return date.currentTime()+978307200 end
    local function cancelled()
        if closed or progress:isCanceled() or files.exists(paths.child(root,"STOP")) then closed=true end
        return closed
    end
    local ok=tasks.pcall(function()
        local raw=read(paths.child(root,"target.json"),16384)
        local Read=load("SharedReadTransport")
        config=Read.decode(raw)
        assert(C.validate(config,now()))
        local host=Application.versionTable()
        assert(host.major==15 and host.minor==6 and type(host.build_version)=="string")
        state.run=config.run;state.case=config.case;state.mode=config.mode
        state.configSha256=Digest.SHA256.digest(raw)
        state.workerSha256=config.workerSha256;state.configurationSha256=config.configurationSha256
        state.host={major=host.major,minor=host.minor,revision=host.revision,
            buildSha256=Digest.SHA256.digest(host.build_version),osSha256=Digest.SHA256.digest(System.osVersion()),sdk=C.SDK}
        state.sources={}
        for _,name in ipairs(C.SOURCES) do
            local kind,file=name:match("^([^/]+)/(.+)$")
            local hash=Digest.SHA256.digest(bytes(name,paths.child(kind=="probe" and probe or release,file)))
            assert(hash==config.sources[name]);state.sources[name]=hash
        end
        -- Consume only the exact validated config. A used target cannot replay.
        local used=paths.child(root,"target-"..config.run..".used.json")
        assert(not files.exists(used) and files.move(paths.child(root,"target.json"),used))
        cache=files.chooseUniqueFileName(paths.child(root,"cache-"..config.run))
        assert(files.createAllDirectories(cache))
        protocol=assert(Q.dependencies(C,config,{now=now,cancelled=cancelled,current=function() return not closed end,
            call=tasks.pcall,get=function(url,headers,timeout)
                state.nativeCalls=state.nativeCalls+1
                return http.get(url,headers,timeout)
            end},Read,load("ConnectionCore"),load("ExistingPhotoClient")))
        state.reason="execution_failed"
        Q.execute(config,{protocol=protocol,cancelled=cancelled,
            stage=function(index,bytes,media)
                if cancelled() then return nil end
                local file=paths.child(cache,"image-"..index..(media=="image/png" and ".png" or ".jpg"))
                return write(file,bytes) and file or nil
            end,
            clearPage=function() return remove(cache) and files.createAllDirectories(cache) end,
            show=function(page,rows)
                if cancelled() then return "cancel",false end
                local f=View.osFactory();local column={spacing=f:control_spacing()}
                for _,row in ipairs(rows) do column[#column+1]=f:row{
                    f:picture{value=row.path,width=150,height=150},
                    f:static_text{title=row.photo.title,width_in_chars=40,height_in_lines=2}}
                end
                local action=Dialogs.presentModalDialog{title="Fixed-origin qualification page "..page.page,
                    contents=f:column{f:static_text{title="Observe every image before confirming this complete page."},
                        f:column(column)},actionVerb="All images rendered",cancelVerb="Cancel",
                    accessoryView=f:row{
                        f:push_button{title="Previous",enabled=page.page==2,
                            action=function(button) Dialogs.stopModalWithResult(button,"previous") end},
                        f:push_button{title="Next",enabled=page.page==1,
                            action=function(button) Dialogs.stopModalWithResult(button,"next") end}}}
                -- Explicit human observation is recorded separately from picture
                -- creation. Confirmation closes this finite run; reopen for navigation.
                return action,action=="ok"
            end},load("ExistingPhotoClient"),state)
    end)
    if not ok and state.reason~="execution_failed" then state.reason="preflight_rejected" end
end)
