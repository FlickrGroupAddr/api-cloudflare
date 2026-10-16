-- Loading/invoking this prepared fixture requires ticket #0059 action approval.
local paths=import "LrPathUtils"
local files=import "LrFileUtils"
local tasks=import "LrTasks"
local contexts=import "LrFunctionContext"
local http=import "LrHttp"
local date=import "LrDate"
local Progress=import "LrProgressScope"
local P=require "Post"
local release=paths.child(paths.parent(paths.parent(paths.parent(_PLUGIN.path))),"clients/lightroom/FGA-LrC15.lrplugin")
local json=dofile(paths.child(release,"dkjson.lua"))
local proof=dofile(paths.child(release,"ExistingPhotoClient.lua"))
local batch=dofile(paths.child(release,"GroupSubmissionClient.lua"))
local root="C:\\Temp\\FGA-group-post-v1"
if files.exists(paths.child(root,"target.used.json")) then return end
contexts.postAsyncTaskWithContext("FGA synthetic POST v1",function(context)
 local stopped=false
 context:addCleanupHandler(function() stopped=true end)
 local progress=Progress{title="Synthetic POST characterization",functionContext=context}
 progress:setCancelable(true)
 local activeRunId
 local function cancel()
  if stopped or progress:isCanceled() then stopped=true;return true end
  local f=io.open(paths.child(root,"stop.json"),"rb")
  if f then
   local bytes=f:read(4097);f:close()
   local value,pos,err=json.decode(bytes,1,json.null)
   -- Unknown/malformed stop files also stop; they can never resume a task.
   stopped=true
   if #bytes<=4096 and not err and type(value)=="table" and value.runId==activeRunId
    and value.planVersion==P.VERSION and value.schemaVersion==1 and value.stop==true
    and bytes:sub(pos):match("^%s*$") then return true end
   return true
  end
  return false
 end
 local function read(path) local f=assert(io.open(path,"rb"));local bytes=f:read(65537);f:close();assert(#bytes<=65536);return bytes end
 local state={schemaVersion=1,planVersion=P.VERSION,outcome="failed",reasonCode="fixture_failure",
  remoteCleanupConfirmed=false,productionQualified=false,postCalls=0,getCalls=0}
 local ok,result=tasks.pcall(function()
  local bytes=read(paths.child(root,"target.json"))
  local config,pos,err=json.decode(bytes,1,json.null)
  assert(not err and bytes:sub(pos):match("^%s*$"),"target_invalid")
  assert(P.validate(config,math.floor(date.currentTime()+978307200)),"target_invalid")
  activeRunId=config.runId;state.runId=config.runId
  local target,used=paths.child(root,"target.json"),paths.child(root,"target.used.json")
  assert(not files.exists(used),"target_already_consumed")
  assert(files.move(target,used),"target_consumption_unconfirmed")
  -- Exact deterministic wire bytes from the existing SDK clients.
  local codec={encode=function(v) return json.encode(v,{keyorder={"schemaVersion","photoBinding","fgaPhotoBindingId","expectedVerificationRevision","flickrGroupIds"}}) end}
  return P.execute(config,{state=state,now=function() return date.currentTime()+978307200 end,cancelled=cancel,
   beforeCase=function(id) progress:setCaption("Case "..id) end,
   post=http.post,get=http.get,json=codec,proof=proof,batch=batch})
 end)
 if ok then state=result end
 state.responseReferencesCleared=true
 local temporary,status=paths.child(root,"status.json.tmp"),paths.child(root,"status.json")
 local f=assert(io.open(temporary,"wb"));assert(f:write(json.encode(state)));assert(f:close())
 if files.exists(status) then assert(files.delete(status)) end
 assert(files.move(temporary,status));progress:done()
end)
