local LrBinding = import "LrBinding"
local LrDate = import "LrDate"
local LrDialogs = import "LrDialogs"
local LrFileUtils = import "LrFileUtils"
local LrLogger = import "LrLogger"
local LrPathUtils = import "LrPathUtils"
local LrTasks = import "LrTasks"
local LrView = import "LrView"
local Client = require "ExistingPhotoClient"
local Browser = {}
Browser.THUMBNAIL_BYTES = 262144
Browser.PAGE_BYTES = 1310720
Browser.THUMBNAIL_TIMEOUT = 15
local active = false
local logger = LrLogger("FGA-LrC15-existing-photos")
local loggingEnabled = pcall(function() logger:enable("logfile") end)

local function report(dependencies, state)
    if dependencies.logState then pcall(dependencies.logState, state) end
end
local function remove(dependencies, directory)
    if not directory then return true end
    local ok, deleted = pcall(function()
        if not LrFileUtils.exists(directory) then return true end
        return LrFileUtils.delete(directory)
    end)
    if not ok or not deleted then
        report(dependencies, "unavailable")
        if loggingEnabled then pcall(function() logger:warn("thumbnail_cache_cleanup_failed") end) end
        return false
    end
    return true
end
local function write(path, bytes)
    local file = io.open(path, "wb")
    if not file then return false end
    local ok, written = pcall(function() return file:write(bytes) end)
    local closed, closeResult = pcall(function() return file:close() end)
    return ok and written ~= nil and closed and closeResult ~= nil
end
Browser.validImage = Client.validImage
local function stagePage(dependencies, directory, page)
    if not LrFileUtils.createAllDirectories(directory) then return nil end
    local total, staged = 0, {}
    for index, photo in ipairs(page.photos) do
        if dependencies.cancelled and dependencies.cancelled() then return nil end
        local bytes, mediaType = Client.thumbnail(dependencies, photo, page)
        if dependencies.cancelled and dependencies.cancelled() then return nil end
        if not bytes then return nil end
        total = total + #bytes
        if total > Browser.PAGE_BYTES then return nil end
        if dependencies.cancelled and dependencies.cancelled() then return nil end
        local path = LrPathUtils.child(directory, string.format("image-%03d.%s", index,
            mediaType == "image/png" and "png" or "jpg"))
        if not write(path, bytes) then return nil end
        staged[index] = {photo=photo, path=path}
    end
    return staged
end
local function showPage(context, page, rows, duplicated)
    local factory = LrView.osFactory()
    local properties = LrBinding.makePropertyTable(context)
    properties.selected = nil
    local column = {bind_to_object=properties, spacing=factory:control_spacing()}
    for _, row in ipairs(rows) do
        local photo = row.photo
        column[#column + 1] = factory:row {
            spacing=factory:control_spacing(),
            factory:radio_button {title="", value=LrView.bind "selected", checked_value=photo.flickrPhotoId},
            factory:picture {value=row.path, width=150, height=150, frame_width=1},
            factory:column {
                spacing=factory:label_spacing(),
                factory:static_text {title=photo.title ~= "" and photo.title or "(Untitled)", width_in_chars=54, height_in_lines=2},
                factory:static_text {title="Taken: " .. photo.dateTaken, width_in_chars=54},
                factory:static_text {title="Uploaded (Unix seconds): " .. photo.dateUploaded, width_in_chars=54},
                factory:static_text {title="Exact Flickr photo ID: " .. photo.flickrPhotoId,
                    width_in_chars=54, height_in_lines=3, selectable=true},
            },
        }
    end
    if #rows == 0 then column[#column + 1] = factory:static_text {
        title=#page.photos == 0 and "No public photos observed" or "These photos were already shown on another page.",
        width_in_chars=76, height_in_lines=2,
    } end
    local result = LrDialogs.presentModalDialog {
        title="Add Groups to Existing Flickr Photoâ€¦",
        contents=factory:column {
            bind_to_object=properties, spacing=factory:control_spacing(),
            factory:static_text {title="Select a public Flickr photo. This workflow does not upload, replace, delete, move, or create a catalog publish record.",
                width_in_chars=80, height_in_lines=2},
            factory:static_text {title="Observed " .. page.observedAt .. " Â· advisory page " .. tostring(page.page)
                .. " of " .. tostring(page.pages) .. " Â· total " .. tostring(page.total), width_in_chars=80, height_in_lines=2},
            factory:static_text {title="Pages can change while browsing. " .. tostring(duplicated)
                .. " repeated photo IDs hidden on this page.", width_in_chars=80, height_in_lines=2},
            factory:scrolled_view {width=760, height=500, factory:column(column)},
        },
        actionVerb="Verify Photo",
        actionBinding={enabled={bind_to_object=properties, key="selected", transform=function(value) return value ~= nil end}},
        cancelVerb="Cancel",
        accessoryView=factory:row {
            factory:push_button {title="Previous", enabled=page.page > 1,
                action=function(button) LrDialogs.stopModalWithResult(button, "previous") end},
            factory:push_button {title="Next", enabled=page.page < page.pages,
                action=function(button) LrDialogs.stopModalWithResult(button, "next") end},
        },
        resizable="vertically",
    }
    return result, properties.selected
end
local failureMessages = {
    flickr_link_changed="The linked Flickr account changed. Reopen this browser to obtain a new observation.",
    photo_owner_mismatch="The selected photo is not owned by the configured Flickr account.",
    existing_photo_not_public="The selected photo is no longer public.",
    invalid_existing_photo="The selected Flickr photo could not be verified.",
    invalid_token="The Plugin Code is invalid. Reconnect in Plug-in Manager.",
}
local function unavailable(title, reason)
    LrDialogs.message(title, failureMessages[reason]
        or "The complete current observation could not be loaded. Retry by reopening the browser.", "warning")
end
local function displayMemberships(binding, observation)
    local factory = LrView.osFactory()
    local rows = {spacing=factory:label_spacing()}
    for _, group in ipairs(observation.groups) do
        rows[#rows + 1] = factory:static_text {title=group.displayName .. "  [" .. group.flickrGroupId .. "]",
            width_in_chars=82, height_in_lines=2, selectable=true}
    end
    if #observation.groups == 0 then rows[#rows + 1] = factory:static_text {
        title="No current Flickr group memberships observed.", width_in_chars=82,
    } end
    LrDialogs.presentModalDialog {
        title="Currently in Flickr groups",
        contents=factory:column {
            factory:static_text {title="Exact Flickr photo ID: " .. binding.flickrPhotoId, selectable=true, width_in_chars=82, height_in_lines=3},
            factory:static_text {title="Fresh photo verification: " .. binding.verifiedAt, width_in_chars=82},
            factory:static_text {title="Membership observed: " .. observation.observedAt .. " Â· " .. tostring(#observation.groups)
                .. " groups. Membership can change afterward.", width_in_chars=82, height_in_lines=2},
            factory:scrolled_view {width=760, height=440, factory:column(rows)},
            factory:static_text {title="This read-only view does not select or submit groups to add.", width_in_chars=82},
        },
        actionVerb="Close", cancelVerb="Close", resizable="vertically",
    }
end
function Browser.run(context, dependencies)
    if active then return nil, "busy" end
    if dependencies.thumbnailTransportQualified ~= true then
        LrDialogs.message("Existing public photos unavailable",
            "Thumbnail transport and the Lightroom Classic 15.6 workflow still require qualification. No photo request was sent.", "info")
        return nil, "qualification_required"
    end
    active = true
    local closed, runDirectory = false, nil
    local previousCancelled = dependencies.cancelled
    dependencies.cancelled = function() return closed or (previousCancelled and previousCancelled()) or false end
    context:addCleanupHandler(function()
        closed = true
        remove(dependencies, runDirectory)
        dependencies.cancelled = previousCancelled
        active = false
    end)
    local root = LrPathUtils.child(LrPathUtils.getStandardFilePath("temp"), "fga-existing-photos")
    runDirectory = LrFileUtils.chooseUniqueFileName(LrPathUtils.child(root,
        "run-" .. string.format("%.6f", LrDate.currentTime())))
    local pageNumber, seen = 1, {}
    while not dependencies.cancelled() do
        report(dependencies, "loading")
        local ok, page, reason = LrTasks.pcall(Client.discover, dependencies, pageNumber)
        if not ok or not page then
            report(dependencies, "unavailable")
            unavailable("Public photos unavailable", reason)
            return nil, reason or "unavailable"
        end
        local pageDirectory = LrPathUtils.child(runDirectory, "page")
        local stagedOk, staged = LrTasks.pcall(stagePage, dependencies, pageDirectory, page)
        if dependencies.cancelled() then
            remove(dependencies, pageDirectory)
            report(dependencies, "cancelled")
            return nil, "cancelled"
        end
        if not stagedOk or not staged then
            remove(dependencies, pageDirectory)
            unavailable("Public photos unavailable", nil)
            return nil, "thumbnail_unavailable"
        end
        local rows, repeated = {}, 0
        for _, row in ipairs(staged) do
            local id = row.photo.flickrPhotoId
            if seen[id] == nil or seen[id] == pageNumber then
                rows[#rows + 1] = row
                seen[id] = pageNumber
            else repeated = repeated + 1 end
        end
        report(dependencies, #rows == 0 and "empty" or "available")
        local action, selected = showPage(context, page, rows, repeated)
        if not remove(dependencies, pageDirectory) then
            unavailable("Public photos unavailable", nil)
            return nil, "thumbnail_unavailable"
        end
        if action == "next" then pageNumber = pageNumber + 1
        elseif action == "previous" then pageNumber = pageNumber - 1
        elseif action == "ok" and selected then
            local exists = false
            for _, row in ipairs(rows) do if row.photo.flickrPhotoId == selected then exists = true end end
            if not exists then return nil, "invalid_selection" end
            local proved, binding, proofReason = LrTasks.pcall(Client.prove, dependencies,
                selected, page.linkedFlickrRevision)
            if not proved or not binding then unavailable("Photo verification unavailable", proofReason); return nil, proofReason end
            local read, observation, membershipReason = LrTasks.pcall(Client.memberships, dependencies, binding)
            if dependencies.cancelled() then return nil, "cancelled" end
            if not read or not observation then unavailable("Membership Unavailable", membershipReason); return nil, membershipReason end
            displayMemberships(binding, observation)
            return binding, observation
        else
            closed = true
            report(dependencies, "cancelled")
            return nil, "cancelled"
        end
    end
    return nil, "cancelled"
end
return Browser
