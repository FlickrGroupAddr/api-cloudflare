-- Copyright 2026 Terry Ott. MIT License.
-- Manual entries only. Loading this fixture does not start a task.
return {LrSdkVersion=15.3,LrSdkMinimumVersion=15.3,
    LrToolkitIdentifier='com.sixbuckssolutions.fga.providerrender.evidence.lrc15',
    LrPluginName='FGA native evidence (unqualified)',
    LrMetadataProvider='MetadataDefinition.lua',
    LrLibraryMenuItems={{title='Prepare exact native evidence phase...',file='Run.lua'}},
    LrExportServiceProvider={title='FGA synthetic evidence ONLY',file='EvidenceProvider.lua'},
    VERSION={major=0,minor=0,revision=1,build=1}}
