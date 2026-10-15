local LrDialogs = import "LrDialogs"
local LrFunctionContext = import "LrFunctionContext"
local LrTasks = import "LrTasks"
local Controller = require "ConnectionController"
local Core = require "ConnectionCore"
local Client = require "ExistingPhotoClient"
local Browser = require "ExistingPhotoBrowser"

-- postAsyncTaskWithContext is specifically required by SDK15 LrHttp.post.
LrFunctionContext.postAsyncTaskWithContext("FGA existing public photos", function(context)
    local dependencies = Controller.discoveryDependencies()
    dependencies.thumbnailTransportQualified = false
    dependencies.request = Client.authenticatedRequest(dependencies, Core)
    if not Client.PRODUCTION_QUALIFIED then
        LrDialogs.message("Existing public photos unavailable",
            "Hosted photo discovery, fresh verification, current memberships, and thumbnail transport are awaiting qualification. The read-only client is installed; no request was sent.", "info")
        return
    end
    local ok = LrTasks.pcall(Browser.run, context, dependencies)
    if not ok then
        LrDialogs.message("Existing public photos unavailable",
            "The read-only workflow could not be completed. Reopen it to retry.", "warning")
    end
end)
