-- Copyright 2026 Terry Ott. MIT License.
-- Source-only qualification package identity. Per-file and aggregate SHA2-256
-- digests are external manifest.json fields to avoid a self-referential hash.
return {
    schemaVersion=1, version='0.0.1.2', hostMajor=15, hostVersion='15.6', sdkVersion='15.3',
    sourceOnly=true, productionQualified=false, nativeSchedulingProven=false,
    manifest='manifest.json', hashAlgorithm='SHA2-256',
    staging='new_private_directory_outside_source_checkout',
    entry='Run.lua', automaticEntry=false,
    qualificationMenu=true, qualificationOnlyProvider=true,
    metadataProvider='MetadataDefinition.lua', maximumRunSeconds=1800,
    transport='synthetic_only_no_network',
    retainedRealData=false,
}
