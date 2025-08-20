-- ============================================================================
-- PHASE 4: ADVANCED SAFETY AND ROLLBACK - SCHEMA ENHANCEMENTS
-- ============================================================================
-- These tables support advanced configuration change tracking, orphaned
-- operation management, and restoration capabilities.

-- ============================================================================
-- CONFIGURATION VERSION TRACKING
-- ============================================================================

-- Track configuration file versions
CREATE TABLE IF NOT EXISTS config_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_hash TEXT UNIQUE NOT NULL,
    config_content TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_mtime TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON
);

CREATE INDEX IF NOT EXISTS idx_config_versions_hash ON config_versions(config_hash);
CREATE INDEX IF NOT EXISTS idx_config_versions_created ON config_versions(created_at);

-- ============================================================================
-- ORPHANED OPERATIONS TRACKING
-- ============================================================================

-- Track operations that have been orphaned for potential restoration
CREATE TABLE IF NOT EXISTS orphaned_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_applied_step_id INTEGER NOT NULL,
    step_hash TEXT NOT NULL,
    dst_path TEXT,
    operation_type TEXT,
    config JSON,
    orphaned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    orphaned_by_transaction TEXT,
    orphaned_reason TEXT,  -- 'removed_from_config', 'modified', 'variant_changed', etc.
    restoration_data JSON,  -- Data needed to restore (includes backup paths, etc.)
    restored_at TIMESTAMP,
    restored_by_transaction TEXT,
    FOREIGN KEY (original_applied_step_id) REFERENCES applied_steps(id),
    FOREIGN KEY (orphaned_by_transaction) REFERENCES transactions(id),
    FOREIGN KEY (restored_by_transaction) REFERENCES transactions(id)
);

CREATE INDEX IF NOT EXISTS idx_orphaned_ops_path ON orphaned_operations(dst_path);
CREATE INDEX IF NOT EXISTS idx_orphaned_ops_type ON orphaned_operations(operation_type);
CREATE INDEX IF NOT EXISTS idx_orphaned_ops_date ON orphaned_operations(orphaned_at);
CREATE INDEX IF NOT EXISTS idx_orphaned_ops_restored ON orphaned_operations(restored_at);

-- ============================================================================
-- CONFIGURATION CHANGE HISTORY
-- ============================================================================

-- Track configuration changes between versions
CREATE TABLE IF NOT EXISTS config_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    old_version_id INTEGER,
    new_version_id INTEGER,
    change_type TEXT,  -- 'add_step', 'remove_step', 'modify_step', 'reorder', etc.
    affected_path TEXT,
    old_config JSON,
    new_config JSON,
    change_metadata JSON,  -- Additional context about the change
    FOREIGN KEY (old_version_id) REFERENCES config_versions(id),
    FOREIGN KEY (new_version_id) REFERENCES config_versions(id)
);

CREATE INDEX IF NOT EXISTS idx_config_changes_date ON config_changes(changed_at);
CREATE INDEX IF NOT EXISTS idx_config_changes_type ON config_changes(change_type);
CREATE INDEX IF NOT EXISTS idx_config_changes_path ON config_changes(affected_path);

-- ============================================================================
-- ENHANCED DRIFT DETECTION
-- ============================================================================

-- Store configuration drift detection results (enhanced version)
CREATE TABLE IF NOT EXISTS config_drift_detection (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    config_version_id INTEGER,
    variant TEXT,
    total_drift INTEGER,
    drift_results JSON,  -- Serialized drift analysis with detailed results
    orphaned_count INTEGER GENERATED ALWAYS AS (
        json_extract(drift_results, '$.orphaned_count')
    ) STORED,
    modified_count INTEGER GENERATED ALWAYS AS (
        json_extract(drift_results, '$.modified_count')
    ) STORED,
    new_count INTEGER GENERATED ALWAYS AS (
        json_extract(drift_results, '$.new_count')
    ) STORED,
    resolved_at TIMESTAMP,
    resolved_by_transaction TEXT,
    resolution_type TEXT,  -- 'reconcile', 'clean', 'ignore', 'manual'
    FOREIGN KEY (config_version_id) REFERENCES config_versions(id),
    FOREIGN KEY (resolved_by_transaction) REFERENCES transactions(id)
);

CREATE INDEX IF NOT EXISTS idx_drift_detection_date ON config_drift_detection(checked_at);
CREATE INDEX IF NOT EXISTS idx_drift_detection_variant ON config_drift_detection(variant);
CREATE INDEX IF NOT EXISTS idx_drift_detection_resolved ON config_drift_detection(resolved_at);

-- ============================================================================
-- CLEANUP HISTORY
-- ============================================================================

-- Track cleanup operations for audit and restoration
CREATE TABLE IF NOT EXISTS cleanup_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT NOT NULL,
    cleaned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    operation_count INTEGER,
    files_removed INTEGER,
    files_backed_up INTEGER,
    cleanup_type TEXT,  -- 'orphaned', 'modified', 'all', 'selective'
    cleanup_filters JSON,  -- Filters used (paths, operations, before date, etc.)
    cleanup_result JSON,  -- Detailed results including errors
    dry_run BOOLEAN DEFAULT 0,
    FOREIGN KEY (transaction_id) REFERENCES transactions(id)
);

CREATE INDEX IF NOT EXISTS idx_cleanup_history_date ON cleanup_history(cleaned_at);
CREATE INDEX IF NOT EXISTS idx_cleanup_history_type ON cleanup_history(cleanup_type);

-- ============================================================================
-- ENHANCED TABLES (ALTER EXISTING)
-- ============================================================================

-- Add config version tracking to applied_steps (if column doesn't exist)
-- Note: SQLite doesn't support ALTER TABLE ADD COLUMN IF NOT EXISTS
-- This will need to be handled programmatically in migration
-- ALTER TABLE applied_steps ADD COLUMN config_version_id INTEGER REFERENCES config_versions(id);

-- Add drift handling to transactions (if columns don't exist)
-- ALTER TABLE transactions ADD COLUMN config_drift_handled BOOLEAN DEFAULT 0;
-- ALTER TABLE transactions ADD COLUMN config_version_id INTEGER REFERENCES config_versions(id);

-- ============================================================================
-- VIEWS FOR PHASE 4
-- ============================================================================

-- Current configuration drift summary
CREATE VIEW IF NOT EXISTS configuration_drift_summary AS
SELECT 
    cd.checked_at,
    cd.variant,
    cd.total_drift,
    cd.orphaned_count,
    cd.modified_count,
    cd.new_count,
    cv.config_hash,
    cv.file_path,
    cd.resolved_at IS NOT NULL as is_resolved,
    cd.resolution_type
FROM config_drift_detection cd
JOIN config_versions cv ON cd.config_version_id = cv.id
WHERE cd.id IN (
    SELECT MAX(id) FROM config_drift_detection
    GROUP BY variant
);

-- All currently orphaned operations (not yet restored)
CREATE VIEW IF NOT EXISTS current_orphaned_operations AS
SELECT 
    oo.*,
    as2.dst_path as original_dst_path,
    as2.operation_type as original_operation_type,
    as2.applied_at as original_applied_at
FROM orphaned_operations oo
JOIN applied_steps as2 ON oo.original_applied_step_id = as2.id
WHERE oo.restored_at IS NULL
ORDER BY oo.orphaned_at DESC;

-- Configuration change timeline
CREATE VIEW IF NOT EXISTS config_change_timeline AS
SELECT 
    cc.changed_at,
    cc.change_type,
    cc.affected_path,
    cv_old.config_hash as old_hash,
    cv_new.config_hash as new_hash,
    cc.change_metadata
FROM config_changes cc
LEFT JOIN config_versions cv_old ON cc.old_version_id = cv_old.id
LEFT JOIN config_versions cv_new ON cc.new_version_id = cv_new.id
ORDER BY cc.changed_at DESC;

-- Restoration candidates (orphaned operations with available backups)
CREATE VIEW IF NOT EXISTS restoration_candidates AS
SELECT 
    oo.*,
    json_extract(oo.restoration_data, '$.backup_path') as backup_path,
    json_extract(oo.restoration_data, '$.backup_exists') as backup_exists,
    (julianday('now') - julianday(oo.orphaned_at)) as days_orphaned
FROM orphaned_operations oo
WHERE oo.restored_at IS NULL
  AND json_extract(oo.restoration_data, '$.restorable') = 1
ORDER BY oo.orphaned_at DESC;

-- ============================================================================
-- INDEXES FOR PHASE 4
-- ============================================================================

-- Optimize queries for drift analysis
CREATE INDEX IF NOT EXISTS idx_applied_steps_config_version 
ON applied_steps(config_version_id) WHERE config_version_id IS NOT NULL;

-- Optimize restoration queries
CREATE INDEX IF NOT EXISTS idx_orphaned_ops_restorable 
ON orphaned_operations(restored_at, orphaned_by_transaction) 
WHERE restored_at IS NULL;

-- Optimize cleanup history queries
CREATE INDEX IF NOT EXISTS idx_cleanup_history_transaction 
ON cleanup_history(transaction_id, cleanup_type);

-- ============================================================================
-- TRIGGERS FOR PHASE 4
-- ============================================================================

-- Automatically track configuration changes
CREATE TRIGGER IF NOT EXISTS track_config_changes
AFTER INSERT ON config_versions
BEGIN
    -- Check if there's a previous version
    INSERT INTO config_changes (
        old_version_id,
        new_version_id,
        change_type,
        change_metadata
    )
    SELECT 
        (SELECT MAX(id) FROM config_versions WHERE id < NEW.id),
        NEW.id,
        'config_updated',
        json_object(
            'hash_changed', 1,
            'file_path', NEW.file_path
        )
    WHERE EXISTS (SELECT 1 FROM config_versions WHERE id < NEW.id);
END;

-- Automatically update orphaned operations when restored
CREATE TRIGGER IF NOT EXISTS update_restored_timestamp
AFTER UPDATE OF restored_by_transaction ON orphaned_operations
WHEN NEW.restored_by_transaction IS NOT NULL AND OLD.restored_by_transaction IS NULL
BEGIN
    UPDATE orphaned_operations 
    SET restored_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;