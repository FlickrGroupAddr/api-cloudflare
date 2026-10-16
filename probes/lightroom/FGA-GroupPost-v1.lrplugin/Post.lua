-- Offline-prepared finite SDK15.3 POST fixture; never a production transport.
local P={VERSION="fga-group-post-v1",TIMEOUT=15,MAX_RESPONSE=2097153}
P.CASES={"proof","batch-one","batch-sixty","status-400","status-401","status-409",
 "status-429","status-503","oversize-success","oversize-error","timeout","lost-response",
 "same-301","cross-301","same-302","cross-302","same-303","cross-303",
 "same-307","cross-307","same-308","cross-308","cancel"}
local function integer(n,a,b) return type(n)=="number" and n==math.floor(n) and n>=a and n<=b end
function P.validate(c,now)
 if type(c)~="table" or c.schemaVersion~=1 or c.planVersion~=P.VERSION
  or type(c.runId)~="string" or #c.runId~=24 or not c.runId:match("^[a-f0-9]+$")
  or c.runId==string.rep("0",24) or type(c.subdomain)~="string" or #c.subdomain>63
  or not (c.subdomain:match("^[a-z0-9]$") or c.subdomain:match("^[a-z0-9][a-z0-9%-]*[a-z0-9]$"))
  or type(c.access)~="string" or #c.access~=64 or not c.access:match("^[a-f0-9]+$")
  or type(c.canary)~="string" or #c.canary~=42 or not c.canary:match("^SYNTHETIC%-[a-f0-9]+$")
  or not integer(now,1,100000000000) or not integer(c.expiresAtUnix,now+600,now+1200) then return nil end
 local keys={schemaVersion=true,planVersion=true,runId=true,subdomain=true,access=true,canary=true,expiresAtUnix=true}
 for k in pairs(c) do if not keys[k] then return nil end end
 return "https://fga-post-src-"..c.runId.."."..c.subdomain..".workers.dev"
end
local function header(h,wanted)
 if type(h)~="table" then return nil end
 local found
 for _,v in ipairs(h) do
  if type(v)=="table" and type(v.field)=="string" and v.field:lower()==wanted then
   if found~=nil or type(v.value)~="string" then return nil end
   found=v.value
  end
 end
 return found
end
local errors={timedOut=true,cancelled=true,networkConnectionLost=true,cannotConnectToHost=true,redirectError=true}
function P.observe(id,body,h,before,after,canceled)
 local code=type(h)=="table" and type(h.error)=="table" and h.error.errorCode
 local partial=type(h)=="table" and h.partial_data
 local status=type(h)=="table" and h.status
 return {caseId=id,status=integer(status,100,599) and status or 0,
  bodyBytes=type(body)=="string" and #body or 0,partialBytes=type(partial)=="string" and #partial or 0,
  errorCategory=code and (errors[code] and code or "other_network_error") or "none",
  markerMatches=header(h,"x-fga-post-probe")==P.VERSION,
  noStore=header(h,"cache-control")=="no-store",locationPresent=header(h,"location")~=nil,
  retryAfterTwo=header(h,"retry-after")=="2",challengePresent=header(h,"www-authenticate")~=nil,
  canceledAfter=canceled,observedWallMs=after>=before and math.floor((after-before)*1000) or -1}
end
function P.execute(c,d)
 local state=d.state or {}
 state.schemaVersion=1;state.planVersion=P.VERSION;state.outcome="failed";state.reasonCode="target_invalid"
 state.cases={};state.postCalls=0;state.getCalls=0;state.remoteCleanupConfirmed=false;state.productionQualified=false
 local source=P.validate(c,math.floor(d.now()))
 if not source then return state end
 state.runId=c.runId
 state.reasonCode="fixture_failure"
 local previous=d.now()
 local function guard()
  local t=d.now()
  if d.cancelled() then return "cancelled" end
  if t~=t or t<previous then return "clock_invalid" end
  previous=t
  if t>=c.expiresAtUnix-240 then return "cleanup_margin" end
 end
 for _,id in ipairs(P.CASES) do
  local reason=guard();if reason then state.reasonCode=reason;state.outcome="stopped";return state end
  local groups={};for i=1,(id=="batch-sixty" and 60 or 1) do groups[i]="SYNTHETIC-GROUP-"..string.format("%02d",i) end
  local body
  if id=="proof" then body=d.proof.encodeProof({schemaVersion=1,flickrPhotoId="SYNTHETIC-PHOTO",expectedLinkedFlickrRevision=1},d.json.encode)
  else
   -- Exercise the actual batch encoder/call contract with a known synthetic
   -- canonical-format value, then replace its auth value with the canary.
   d.batch.submit("SYNTHETIC-BINDING",1,groups,string.rep("0000-",12).."0000",
    function(path,bytes,headers) assert(path=="/api/v001/group-submission-batches");body=bytes;assert(headers[2].value=="application/json") end,d.json.encode)
  end
  assert(type(body)=="string" and #body<=16384,"synthetic_body_invalid")
  if d.beforeCase then d.beforeCase(id) end
  reason=guard();if reason then state.reasonCode=reason;state.outcome="stopped";return state end
  -- Batch object key ordering from dkjson is stable here only after explicit
  -- key order is supplied by the runtime codec wrapper in Run.lua.
  local before=d.now();state.postCalls=state.postCalls+1
  local bytes,h=d.post(source.."/v1/cases/"..id,body,{
   {field="Authorization",value="Bearer "..c.canary},{field="Content-Type",value="application/json"},
   {field="X-FGA-Post-Access",value=c.access}},"POST",P.TIMEOUT)
  state.cases[#state.cases+1]=P.observe(id,bytes,h,before,d.now(),d.cancelled())
  local latest=state.cases[#state.cases]
  latest.withinFinitePlan=latest.bodyBytes<=P.MAX_RESPONSE and latest.partialBytes<=P.MAX_RESPONSE
  bytes,h,body=nil,nil,nil
  if not latest.withinFinitePlan then state.outcome="failed";state.reasonCode="finite_response_exceeded";return state end
  reason=guard();if reason then state.reasonCode=reason;state.outcome="stopped";return state end
 end
 -- Source report is authoritative even when redirect or lost-response bytes
 -- never reached this task. Its raw JSON is never copied into the receipt.
 local reportGuard=guard()
 if reportGuard then state.outcome="stopped";state.reasonCode=reportGuard;return state end
 state.getCalls=1
 local bytes,h=d.get(source.."/v1/report",{{field="X-FGA-Post-Access",value=c.access}},P.TIMEOUT)
 state.report=P.observe("report",bytes,h,d.now(),d.now(),d.cancelled())
 state.reportRecorded=type(bytes)=="string" and #bytes<=65536 and type(h)=="table" and h.status==200
 bytes,h=nil,nil
 local reason=guard()
 state.outcome=reason and "stopped" or "characterized"
 state.reasonCode=reason or "measurements_require_external_receipt_review"
 state.responseReferencesCleared=true
 return state
end
return P
