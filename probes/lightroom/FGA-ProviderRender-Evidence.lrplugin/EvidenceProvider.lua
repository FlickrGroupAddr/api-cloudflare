-- Copyright 2026 Terry Ott. MIT License.
-- Ordinary Publish is refused unless Native accepts exact fresh qualification scope.
local Tasks=import 'LrTasks'
local callbacks=require('OrdinaryAlbumProvider').new{
    pcall=Tasks.pcall,pluginId='com.sixbuckssolutions.fga.providerrender.evidence.lrc15',
    verifyService=function() return {ok=false} end}
callbacks.allowFileFormats={'PNG'}
callbacks.canExportVideo=false
callbacks.exportPresetFields={{key='evidenceOnly',default=true}}
callbacks.startDialog=function(settings) settings.LR_canExport=true end
callbacks.getCollectionBehaviorInfo=function()
    return {defaultCollectionName='Default evidence refusal',defaultCollectionCanBeDeleted=false,
        canAddCollection=true,maxCollectionSetDepth=0}
end
callbacks.processRenderedPhotos=function(functionContext,exportContext)
    return require('Native').callback(functionContext,exportContext)
end
return callbacks
