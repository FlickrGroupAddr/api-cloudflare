-- Copyright 2026 Terry Ott. MIT License.
-- Dormant same-tuple recovery. No SDK imports, upload, signing or default HTTP.
local C=require "UploadAttemptCodec"
local N=C.null
local M={PRODUCTION_QUALIFIED=false,MAX_RESPONSE_BYTES=4096,MAX_PROOF_ATTEMPTS=3}
local fields=C.fields
local scopeFields=fields("publishServiceLocalId fgaPublishServiceId publishedCollectionLocalId photoUuid")
local fenceFields=fields("storeRevision gateRevision attemptNumber recordRevision metadataRevision")
local responseFields=fields("schemaVersion fgaPhotoBindingId sourceKind flickrPhotoId linkedFlickrRevision verificationRevision verifiedAt")
local sources=fields("fga_direct_upload existing_public_flickr_photo photographer_reconciled_ambiguous_upload")
local function result(state,detail) return {state=state,detail=detail} end
local function same(a,b,keys)
    if type(a)~="table" or type(b)~="table" then return false end
    for k in pairs(keys) do if a[k]~=b[k] then return false end end
    return true
end
local function scopeValid(s)
    return C.object(s,scopeFields) and C.integer(s.publishServiceLocalId,1)
        and C.opaque(s.fgaPublishServiceId) and C.integer(s.publishedCollectionLocalId,1) and C.uuid(s.photoUuid)
end
local function component(s)
    return (s:gsub("([^A-Za-z0-9_.~-])",function(c) return string.format("%%%02X",string.byte(c)) end))
end
local function ready(r)
    return r and r.state=="ready" and type(r.record)=="table" and r.record~=N
end
local function known(r)
    return C.opaque(r.flickrPhotoId) and (r.uploadPhase=="returned_id" or r.uploadPhase=="ambiguity_resolution_pending")
        and (r.resultKind=="returned_upload_id" or r.resultKind=="photographer_assertion")
        and type(r.photoProof)=="table" and r.photoProof~=N
        and type(r.catalogPublication)=="table" and r.catalogPublication~=N
end
local function headerValue(headers,name)
    local value
    for _,h in ipairs(headers) do
        if h.field:lower()==name then
            if value~=nil then return nil,false end
            value=h.value
        end
    end
    return value,true
end
local function framed(body,h,path)
    if type(body)~="string" or #body>M.MAX_RESPONSE_BYTES or type(h)~="table"
        or (h.status~=200 and h.status~=201) or #h>64 then return false end
    local count,bytes=0,0
    for k,v in pairs(h) do
        if k~="status" then
            if not C.integer(k,1) or k>#h or not C.object(v,fields("field value"))
                or type(v.field)~="string" or #v.field==0 or #v.field>256
                or not v.field:match("^[A-Za-z0-9-]+$") or type(v.value)~="string" or #v.value>256
                or v.value:find("[%z\1-\31\127]") then return false end
            count=count+1; bytes=bytes+#v.field+#v.value
        end
    end
    if count~=#h or bytes>4096 then return false end
    local media,ok1=headerValue(h,"content-type")
    local cache,ok2=headerValue(h,"cache-control")
    local length,ok3=headerValue(h,"content-length")
    local location,ok4=headerValue(h,"location")
    if not ok1 or not ok2 or not ok3 or not ok4 or type(media)~="string" or type(cache)~="string" then return false end
    media=media:lower():gsub("%s","")
    if media~="application/json" and media~="application/json;charset=utf-8" then return false end
    if not (","..cache:lower():gsub("%s","")..","):find(",no%-store,") then return false end
    if length and (not length:match("^%d+$") or tonumber(length)~=#body) then return false end
    return (h.status~=201 or location==path) and (location==nil or location==path)
end
local function projection(body,headers,path,photoId,revision)
    if not framed(body,headers,path) then return nil end
    local v=C.decode(body,M.MAX_RESPONSE_BYTES)
    if not C.object(v,responseFields) or v.schemaVersion~=1 or not C.opaque(v.fgaPhotoBindingId)
        or not sources[v.sourceKind] or v.flickrPhotoId~=photoId or v.linkedFlickrRevision~=revision
        or not C.integer(v.linkedFlickrRevision,1) or not C.integer(v.verificationRevision,1)
        or not C.time(v.verifiedAt) then return nil end
    return {fgaPhotoBindingId=v.fgaPhotoBindingId,flickrPhotoId=v.flickrPhotoId,
        linkedFlickrRevision=v.linkedFlickrRevision,verificationRevision=v.verificationRevision}
end
local definitive={[400]=true,[401]=true,[403]=true,[404]=true,[409]=true,[422]=true}
function M.new(options)
    options=options or {}
    local R={}
    local store,repair,protect=options.store,options.catalogRepair,options.pcall
    local attempts=options.proofAttempts or 1
    local transport=options.proofTransport
    local validBudget=C.integer(attempts,1) and attempts<=M.MAX_PROOF_ATTEMPTS
        and (attempts==1 or type(options.backoff)=="function")
    local busy=false
    local stopped={}
    local function linkedRevision()
        local ok,value=protect(function() return options.linkedFlickrRevision() end)
        return ok and value or nil
    end
    local function inspect(scope,photo,number,now)
        local observed=store:inspect(scope,photo,now,number)
        if not ready(observed) then
            return nil,observed and observed.state=="ready" and result("missing_correlation") or observed or result("storage_unavailable")
        end
        if not same(observed.record,scope,scopeFields) or observed.record.attemptNumber~=number then return nil,result("scope_invalid") end
        return observed
    end
    local function unchanged(scope,photo,number,now,previous)
        local nextValue,err=inspect(scope,photo,number,now)
        if not nextValue then return nil,err end
        if not same(previous.fence,nextValue.fence,fenceFields) then return nil,result("revision_conflict") end
        return nextValue
    end
    -- The journal's private gate can yield after the catalog adapter has
    -- observed its relationship. This final observation has no gate or yield.
    local function catalogObservation(scope,number,record)
        local observation=type(repair)=="table" and type(repair.observe)=="function"
            and repair:observe(scope,number,record.flickrPhotoId) or nil
        if type(observation)~="table" or observation.state~="catalog_identity_observed" then
            return result(record.resultKind=="photographer_assertion" and "reconciled_catalog_write_pending"
                or "catalog_write_pending",observation and observation.state or "catalog_repair_unavailable")
        end
    end
    local function verified(scope,number,observed)
        local localErr=catalogObservation(scope,number,observed.record)
        return localErr or result("hosted_photo_verified")
    end
    local function localRepair(scope,photo,number,now,observed)
        -- An earlier acknowledgement is not a current catalog observation:
        -- Undo or a user edit may have changed the remote ID since that gate.
        if type(repair)~="table" or type(repair.repair)~="function" then return nil,result("catalog_repair_unavailable") end
        local fixed=repair:repair(scope,number,now)
        if type(fixed)~="table" or fixed.state~="catalog_acknowledged" then
            return nil,result(observed.record.resultKind=="photographer_assertion" and "reconciled_catalog_write_pending"
                or "catalog_write_pending",fixed and fixed.state or "catalog_repair_unavailable")
        end
        local fresh,err=inspect(scope,photo,number,now)
        if not fresh then return nil,err end
        if not known(fresh.record) or fresh.record.flickrPhotoId~=observed.record.flickrPhotoId
            or fresh.record.fgaUploadAuthorizationId~=observed.record.fgaUploadAuthorizationId
            or fresh.record.resultKind~=observed.record.resultKind or fresh.record.catalogPublication.state~="acknowledged" then
            return nil,result("revision_conflict")
        end
        return fresh
    end
    local function attention(scope,photo,number,now,observed,detail)
        local fresh,err=unchanged(scope,photo,number,now,observed)
        if not fresh then return err end
        local saved=store:checkpointNeedsAttention(scope,photo,fresh.fence,"photoProof",now)
        -- A failed persistence/readback must not reset the activation's budget.
        -- A later process can rely only on whatever actually survived storage.
        stopped[number]={scope=C.clone(scope),detail=detail}
        local outcome=result(fresh.record.resultKind=="photographer_assertion" and "reconciliation_needs_attention"
            or "uploaded_proof_needs_attention",detail)
        outcome.attentionPersisted=type(saved)=="table" and saved.state=="needs_attention"
        if not outcome.attentionPersisted then outcome.storageState=saved and saved.state or "storage_unavailable" end
        return outcome
    end
    local function run(scope,photo,number,now,retryAttention)
        if not scopeValid(scope) or not C.integer(number,1) or not C.time(now) then return result("scope_invalid") end
        scope=C.clone(scope)
        local observed,err=inspect(scope,photo,number,now)
        if not observed then return err end
        local r=observed.record
        if observed.classification=="catalog_repair_required" then return result("catalog_repair_required") end
        if not known(r) then return result(r.uploadPhase=="dispatch_may_have_started" and "upload_outcome_unknown" or r.uploadPhase) end
        -- An acknowledged hosted commit is never requested again, including when
        -- the catalog write failed or the process stopped before local repair.
        if r.photoProof.state=="acknowledged" then
            local fixed,localErr=localRepair(scope,photo,number,now,observed)
            return fixed and verified(scope,number,fixed) or localErr
        end
        local held=stopped[number]
        if (r.photoProof.state=="needs_attention" or (held and same(held.scope,scope,scopeFields))) and retryAttention~=true then
            return result(r.resultKind=="photographer_assertion" and "reconciliation_needs_attention"
                or "uploaded_proof_needs_attention","explicit_retry_required")
        end
        if not C.opaque(r.fgaUploadAuthorizationId) then
            return attention(scope,photo,number,now,observed,"missing_correlation")
        end
        -- ADR0011 keeps the known returned ID useful before hosted proof.
        if r.resultKind=="returned_upload_id" then
            observed,err=localRepair(scope,photo,number,now,observed)
            if not observed then return err end
            r=observed.record
            -- A concurrent safe worker may have completed proof while the
            -- catalog adapter was reacquiring its gate. Honor that commit.
            if r.photoProof.state=="acknowledged" then return verified(scope,number,observed) end
            if r.photoProof.state=="needs_attention" and retryAttention~=true then
                return result("uploaded_proof_needs_attention","explicit_retry_required")
            end
        end
        if not validBudget or type(transport)~="table" or type(transport.capabilities)~="table"
            or transport.capabilities.uploadPhotoProof~=true or type(transport.request)~="function"
            or type(options.linkedFlickrRevision)~="function" then
            return result("proof_transport_unavailable")
        end
        local revision=linkedRevision()
        if not C.integer(revision,1) then return attention(scope,photo,number,now,observed,"linked_flickr_unavailable") end
        observed,err=unchanged(scope,photo,number,now,observed)
        if not observed then return err end
        local path="/api/v001/upload-authorizations/"..component(r.fgaUploadAuthorizationId)
            ..(r.resultKind=="photographer_assertion" and "/ambiguity-resolution" or "/photo-binding")
        local bytes=C.encode({schemaVersion=1,flickrPhotoId=r.flickrPhotoId})
        local detail="proof_budget_exhausted"
        for index=1,attempts do
            -- request must bound its own origin, duration, redirects and body
            -- consumption. This dormant client supplies no native fallback.
            local localErr
            local ok,body,headers=protect(function()
                -- Normal proof requires the catalog boundary still to exist
                -- immediately before invocation, including every backoff retry.
                if r.resultKind=="returned_upload_id" then
                    localErr=catalogObservation(scope,number,r)
                    if localErr then return nil,nil end
                end
                return transport.request("PUT",path,bytes,M.MAX_RESPONSE_BYTES)
            end)
            if localErr then return localErr end
            local fresh,stale=unchanged(scope,photo,number,now,observed)
            if not fresh then return stale end
            if linkedRevision()~=revision then
                return attention(scope,photo,number,now,fresh,"flickr_link_changed")
            end
            -- Recheck after the injected link callback too; it may yield.
            fresh,stale=unchanged(scope,photo,number,now,fresh)
            if not fresh then return stale end
            observed=fresh
            local proof=ok and projection(body,headers,path,r.flickrPhotoId,revision) or nil
            if proof then
                local ack=store:acknowledgeProof(scope,photo,observed.fence,proof,now)
                if not ack or ack.state~="proof_acknowledged" then return ack or result("storage_unavailable") end
                stopped[number]=nil
                local committed,readErr=inspect(scope,photo,number,now)
                if not committed then return readErr end
                if committed.record.photoProof.state~="acknowledged"
                    or committed.record.photoProof.fgaPhotoBindingId~=proof.fgaPhotoBindingId
                    or committed.record.photoProof.linkedFlickrRevision~=proof.linkedFlickrRevision
                    or committed.record.photoProof.verificationRevision~=proof.verificationRevision then return result("revision_conflict") end
                local fixed,localErr=localRepair(scope,photo,number,now,committed)
                return fixed and verified(scope,number,fixed) or localErr
            end
            local status=type(headers)=="table" and headers.status or nil
            if definitive[status] then
                return attention(scope,photo,number,now,observed,"proof_refused")
            end
            if ok and (status==200 or status==201) then detail="proof_response_invalid" end
            if index<attempts then
                local waitOk,waited=protect(function() return options.backoff(2^(index-1)) end)
                observed,err=unchanged(scope,photo,number,now,observed)
                if not observed then return err end
                if not waitOk or waited~=true then return attention(scope,photo,number,now,observed,"proof_retry_stopped") end
                if linkedRevision()~=revision then
                    return attention(scope,photo,number,now,observed,"flickr_link_changed")
                end
                observed,err=unchanged(scope,photo,number,now,observed)
                if not observed then return err end
            end
        end
        return attention(scope,photo,number,now,observed,detail)
    end
    function R:resume(scope,photo,number,now,retryAttention)
        if busy then return result("recovery_busy") end
        if type(protect)~="function" or type(store)~="table" or type(store.inspect)~="function" then return result("adapter_unavailable") end
        busy=true
        local ok,outcome=protect(function() return run(scope,photo,number,now,retryAttention) end)
        busy=false
        return ok and outcome or result("recovery_unavailable")
    end
    return R
end
return M
