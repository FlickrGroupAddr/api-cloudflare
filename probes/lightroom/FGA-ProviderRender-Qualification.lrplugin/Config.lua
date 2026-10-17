-- Copyright 2026 Terry Ott. MIT License.
-- Finite source packet; none of these declarations is native host evidence.
return {
    VERSION='0.0.1.2', SDK='15.3', EXPECTED_HOST={major=15,minor=6},
    PRODUCTION_QUALIFIED=false, NATIVE_SCHEDULING_PROVEN=false,
    MAX_RECEIPTS=64,
    CASES={'selection_absent','selection_none','selection_groups',
        'selection_edit_after_freeze','photo_failure_isolation','target_rejected',
        'catalog_changed','activation_changed','cancelled','render_failed',
        'missing_file','oversized_file','file_changed','cleanup_revocation'},
    PRE_START_POINT='OrdinaryAlbumProvider.prepareBeforeRendering',
    PRE_START_REQUIREMENT='Native.lua finishes preparation before '
        ..'its first renditions call. '
        ..'processRenderedPhotos is too late and remains disabled.',
    EXECUTION_STATUS='native_dispatch_source_prepared_not_executed',
}
