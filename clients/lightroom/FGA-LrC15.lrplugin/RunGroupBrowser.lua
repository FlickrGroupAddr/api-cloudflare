local LrTasks = import "LrTasks"
LrTasks.startAsyncTask(function()
    require("GroupBrowser").run()
end)
