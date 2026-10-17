-- Copyright 2026 Terry Ott. MIT License.
-- Test-only registration and manual entry. No automatic run callback.
return {LrSdkVersion=15.3,LrSdkMinimumVersion=15.3,
    LrToolkitIdentifier='com.sixbuckssolutions.fga.providerrender.qualification.lrc15',
    LrPluginName='FGA provider/render qualification (unqualified)',
    LrMetadataProvider='MetadataDefinition.lua',
    LrLibraryMenuItems={{title='Run exact provider/render qualification...',file='Run.lua'}},
    LrExportServiceProvider={title='FGA synthetic qualification ONLY',file='QualificationProvider.lua'},
    VERSION={major=0,minor=0,revision=1,build=2}}
