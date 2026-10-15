return {
    LrSdkVersion = 15.3,
    LrSdkMinimumVersion = 15.0,
    LrToolkitIdentifier = "com.sixbuckssolutions.flickrgroupaddr.outboxprobe.lrc15",
    LrPluginName = "FGA catalog outbox fixture probe",
    LrLibraryMenuItems = {
        { title = "Outbox fixture: receipt preflight (no catalog access)", file = "Preflight.lua" },
        { title = "Outbox fixture: write and test rollback", file = "Write.lua" },
        { title = "Outbox fixture: verify after restart", file = "Verify.lua" },
    },
    VERSION = { major = 0, minor = 0, revision = 2, build = 6 },
}
