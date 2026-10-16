-- Synthetic SDK boundary; actual factory/client/workflow/store modules run unchanged.
local baseImport=import
taskCalls,sleepSlices,taskStarts,passwordReads=0,0,0,0
progress={cancelled=false}
function progress:isCanceled() return self.cancelled end
function progress:setCancelable(value) assert(value==true) end
function progress:attachToFunctionContext(value) assert(value==context) end
local modules={
    LrDate={currentTime=function()
        if clockSamples and #clockSamples>0 then return table.remove(clockSamples,1) end
        return 1
    end},
    LrApplication={activeCatalog=function() return activeCatalog end},
    LrPasswords={retrieve=function(key,_,pluginId)
        passwordReads=passwordReads+1
        assert(pluginId=='com.sixbuckssolutions.flickrgroupaddr.lrc15')
        return deps.retrieve(key)
    end},
    LrProgressScope=function() return progress end,
    LrTasks={pcall=function(fn,...)
        taskCalls=taskCalls+1
        return pcall(fn,...)
    end,sleep=function(seconds)
        assert(seconds<=0.1)
        sleepSlices=sleepSlices+1
        if onSleep then onSleep() end
    end},
    LrFunctionContext={callWithContext=baseImport('LrFunctionContext').callWithContext,
    postAsyncTaskWithContext=function(_,fn)
        taskStarts=taskStarts+1
        fn(context)
        for _,handler in ipairs(cleanup) do handler() end
        cleanup={}
    end}
}
import=function(name) return modules[name] or baseImport(name) end
_PLUGIN=plugin
transport={capabilities=deps.capabilities,httpGet=function(...)
    local bytes,headers=deps.httpGet(...)
    if afterGet then afterGet() end
    return bytes,headers
end,httpPost=deps.httpPost,batchPost=deps.batchPost}
options={transport=transport,expectedInstallationId='installation-1'}
factory=require 'GroupWorkflowAdapterFactory'
function startFactory(consumer)
    factory.start(options,consumer or function(c,d)
        captured=d
        return require('ExistingPhotoGroupWorkflow').run(c,d)
    end,function(result) finalResult=result end)
    return finalResult
end
