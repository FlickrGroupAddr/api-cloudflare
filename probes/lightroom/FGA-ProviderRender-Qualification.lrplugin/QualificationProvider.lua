-- Copyright 2026 Terry Ott. MIT License.
-- Isolated test-provider registration only. Native Publish always refuses.
local Tasks=import 'LrTasks'
local callbacks=require('OrdinaryAlbumProvider').newQualification{
    pcall=Tasks.pcall,
    pluginId='com.sixbuckssolutions.fga.providerrender.qualification.lrc15',
    verifyService=function() return {ok=false} end,
}
callbacks.allowFileFormats={'PNG','JPEG'}
callbacks.canExportVideo=false
callbacks.exportPresetFields={{key='qualificationOnly',default=true}}
callbacks.startDialog=function(settings) settings.LR_canExport=true end
callbacks.processRenderedPhotos=function(_functionContext,_exportContext)
    error('Use the explicit qualification menu after exact-artifact consent',0)
end
return callbacks
