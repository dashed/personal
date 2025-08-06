-- State Database Schema for Dotfiles Management System
-- SQLite 3.35+ required for JSON functions and generated columns
-- Location: ~/.local/state/dotfiles/state.db

-- Enable foreign key constraints
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;  -- Write-Ahead Logging for better concurrency

-- ============================================================================
-- VERSION TRACKING
-- ============================================================================

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

INSERT OR IGNORE INTO schema_version (version, description) 
VALUES (1, 'Initial schema creation');

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- System information and metadata
CREATE TABLE IF NOT EXISTS system_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hostname TEXT NOT NULL,
    username TEXT NOT NULL,
    platform TEXT NOT NULL,  -- 'darwin', 'linux', 'windows'
    arch TEXT NOT NULL,       -- 'x86_64', 'arm64'
    dotfiles_version TEXT NOT NULL,
    python_version TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_sync_at TIMESTAMP,
    UNIQUE(hostname, username)
);

-- Transactions for atomic operations
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,  -- UUID format
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT CHECK(status IN ('pending', 'in_progress', 'completed', 'failed', 'rolled_back')) DEFAULT 'pending',
    variant TEXT NOT NULL,
    dry_run BOOLEAN DEFAULT 0,
    user TEXT NOT NULL,
    hostname TEXT NOT NULL,
    error_message TEXT,
    metadata JSON  -- Additional transaction context
);

-- Individual operations within transactions
CREATE TABLE IF NOT EXISTS operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT NOT NULL,
    sequence_num INTEGER NOT NULL,  -- Order within transaction
    operation_type TEXT NOT NULL,   -- 'link', 'copy', 'brew_install', etc.
    status TEXT CHECK(status IN ('pending', 'executing', 'success', 'failed', 'skipped', 'rolled_back')) DEFAULT 'pending',
    
    -- Operation details
    src_path TEXT,
    dst_path TEXT,
    original_content TEXT,      -- For rollback (could be file content or metadata)
    original_checksum TEXT,     -- SHA256 of original file
    new_checksum TEXT,          -- SHA256 after operation
    
    -- Operation configuration from TOML
    config JSON NOT NULL,       -- Full step config from dotfiles.toml
    
    -- Execution details
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    rollback_data JSON,         -- Data needed for rollback
    
    FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE CASCADE,
    UNIQUE(transaction_id, sequence_num)
);

-- Currently applied configuration steps
CREATE TABLE IF NOT EXISTS applied_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    step_hash TEXT UNIQUE NOT NULL,  -- Hash of the step config for change detection
    operation_type TEXT NOT NULL,
    src_path TEXT,
    dst_path TEXT,
    checksum TEXT,                    -- Current file checksum for drift detection
    config JSON NOT NULL,             -- Full step configuration
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    applied_by_transaction TEXT,
    last_verified_at TIMESTAMP,       -- For drift detection
    is_current BOOLEAN DEFAULT 1,     -- False if overridden by another step
    
    FOREIGN KEY (applied_by_transaction) REFERENCES transactions(id)
);

-- Backup references
CREATE TABLE IF NOT EXISTS backups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_id INTEGER,
    backup_path TEXT NOT NULL,        -- Full path to backup
    original_path TEXT NOT NULL,      -- Original file path
    backup_type TEXT CHECK(backup_type IN ('file', 'directory', 'symlink')) NOT NULL,
    size_bytes INTEGER,
    checksum TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,              -- For retention policy
    is_deleted BOOLEAN DEFAULT 0,
    
    FOREIGN KEY (operation_id) REFERENCES operations(id) ON DELETE SET NULL
);

-- Track one-time operations
CREATE TABLE IF NOT EXISTS run_once_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_hash TEXT UNIQUE NOT NULL,  -- Hash of command + checksum
    command TEXT NOT NULL,
    checksum TEXT,
    variant TEXT,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    executed_by_transaction TEXT,
    exit_code INTEGER,
    output TEXT,
    
    FOREIGN KEY (executed_by_transaction) REFERENCES transactions(id)
);

-- Package installation tracking
CREATE TABLE IF NOT EXISTS installed_packages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    package_manager TEXT NOT NULL,    -- 'brew', 'apt', 'npm', etc.
    package_name TEXT NOT NULL,
    version TEXT,
    installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    installed_by_transaction TEXT,
    is_pinned BOOLEAN DEFAULT 0,      -- Version pinned?
    metadata JSON,                     -- Package-specific metadata
    
    FOREIGN KEY (installed_by_transaction) REFERENCES transactions(id),
    UNIQUE(package_manager, package_name)
);

-- Audit log (append-only)
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT NOT NULL,         -- 'sync', 'rollback', 'backup', 'error', etc.
    severity TEXT CHECK(severity IN ('debug', 'info', 'warning', 'error', 'critical')) DEFAULT 'info',
    transaction_id TEXT,
    operation_id INTEGER,
    user TEXT NOT NULL,
    hostname TEXT NOT NULL,
    message TEXT NOT NULL,
    details JSON,                      -- Additional context
    
    FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE SET NULL,
    FOREIGN KEY (operation_id) REFERENCES operations(id) ON DELETE SET NULL
);

-- Drift detection results
CREATE TABLE IF NOT EXISTS drift_detection (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    applied_step_id INTEGER,
    expected_checksum TEXT,
    actual_checksum TEXT,
    drift_type TEXT CHECK(drift_type IN ('modified', 'deleted', 'permissions', 'ownership')),
    details JSON,
    
    FOREIGN KEY (applied_step_id) REFERENCES applied_steps(id) ON DELETE CASCADE
);

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Current system state
CREATE VIEW IF NOT EXISTS current_state AS
SELECT 
    as2.dst_path,
    as2.operation_type,
    as2.src_path,
    as2.checksum,
    as2.applied_at,
    as2.config
FROM applied_steps as2
WHERE as2.is_current = 1
ORDER BY as2.dst_path;

-- Recent transactions
CREATE VIEW IF NOT EXISTS recent_transactions AS
SELECT 
    t.id,
    t.started_at,
    t.completed_at,
    t.status,
    t.variant,
    t.user,
    t.hostname,
    COUNT(o.id) as operation_count,
    SUM(CASE WHEN o.status = 'success' THEN 1 ELSE 0 END) as success_count,
    SUM(CASE WHEN o.status = 'failed' THEN 1 ELSE 0 END) as failed_count
FROM transactions t
LEFT JOIN operations o ON t.id = o.transaction_id
GROUP BY t.id
ORDER BY t.started_at DESC
LIMIT 50;

-- Pending rollbacks
CREATE VIEW IF NOT EXISTS pending_rollbacks AS
SELECT 
    t.id as transaction_id,
    t.started_at,
    t.error_message,
    COUNT(o.id) as operations_to_rollback
FROM transactions t
JOIN operations o ON t.id = o.transaction_id
WHERE t.status = 'failed' 
    AND o.status = 'success'
    AND o.rollback_data IS NOT NULL
GROUP BY t.id
ORDER BY t.started_at DESC;

-- Backup statistics
CREATE VIEW IF NOT EXISTS backup_stats AS
SELECT 
    COUNT(*) as total_backups,
    SUM(size_bytes) as total_size_bytes,
    COUNT(CASE WHEN is_deleted = 0 THEN 1 END) as active_backups,
    COUNT(CASE WHEN expires_at < CURRENT_TIMESTAMP AND is_deleted = 0 THEN 1 END) as expired_backups,
    MIN(created_at) as oldest_backup,
    MAX(created_at) as newest_backup
FROM backups;

-- Drift summary
CREATE VIEW IF NOT EXISTS drift_summary AS
SELECT 
    dd.drift_type,
    COUNT(*) as count,
    MAX(dd.checked_at) as last_detected
FROM drift_detection dd
JOIN applied_steps as2 ON dd.applied_step_id = as2.id
WHERE as2.is_current = 1
GROUP BY dd.drift_type;

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Auto-update transaction completion time
CREATE TRIGGER IF NOT EXISTS update_transaction_completed
AFTER UPDATE OF status ON transactions
FOR EACH ROW
WHEN NEW.status IN ('completed', 'failed', 'rolled_back') AND OLD.status != NEW.status
BEGIN
    UPDATE transactions 
    SET completed_at = CURRENT_TIMESTAMP 
    WHERE id = NEW.id;
END;

-- Auto-update operation completion time
CREATE TRIGGER IF NOT EXISTS update_operation_completed
AFTER UPDATE OF status ON operations
FOR EACH ROW
WHEN NEW.status IN ('success', 'failed', 'rolled_back') AND OLD.status != NEW.status
BEGIN
    UPDATE operations 
    SET completed_at = CURRENT_TIMESTAMP 
    WHERE id = NEW.id;
END;

-- Audit log trigger for transactions
CREATE TRIGGER IF NOT EXISTS audit_transaction_changes
AFTER UPDATE ON transactions
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (event_type, transaction_id, user, hostname, message, details)
    VALUES (
        'transaction_status_change',
        NEW.id,
        NEW.user,
        NEW.hostname,
        'Transaction status changed from ' || OLD.status || ' to ' || NEW.status,
        json_object('old_status', OLD.status, 'new_status', NEW.status)
    );
END;

-- Mark old applied steps as not current when new one is applied to same dst
CREATE TRIGGER IF NOT EXISTS update_applied_steps_current
AFTER INSERT ON applied_steps
FOR EACH ROW
BEGIN
    UPDATE applied_steps 
    SET is_current = 0 
    WHERE dst_path = NEW.dst_path 
        AND id != NEW.id 
        AND is_current = 1;
END;

-- ============================================================================
-- STORED PROCEDURES (as SQL functions)
-- ============================================================================

-- Function to start a new transaction
-- Usage: SELECT start_transaction('personal', 0, 'username', 'hostname');
CREATE TRIGGER IF NOT EXISTS generate_transaction_id
AFTER INSERT ON transactions
FOR EACH ROW
WHEN NEW.id IS NULL
BEGIN
    UPDATE transactions 
    SET id = lower(hex(randomblob(16)))
    WHERE rowid = NEW.rowid;
END;

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Transaction indexes
CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_transactions_started ON transactions(started_at DESC);

-- Operation indexes
CREATE INDEX IF NOT EXISTS idx_operations_transaction ON operations(transaction_id);
CREATE INDEX IF NOT EXISTS idx_operations_status ON operations(status);
CREATE INDEX IF NOT EXISTS idx_operations_dst_path ON operations(dst_path);

-- Applied steps indexes
CREATE INDEX IF NOT EXISTS idx_applied_dst ON applied_steps(dst_path);
CREATE INDEX IF NOT EXISTS idx_applied_current ON applied_steps(is_current);
CREATE INDEX IF NOT EXISTS idx_applied_checksum ON applied_steps(checksum);

-- Backup indexes
CREATE INDEX IF NOT EXISTS idx_backups_expires ON backups(expires_at);
CREATE INDEX IF NOT EXISTS idx_backups_original ON backups(original_path);
CREATE INDEX IF NOT EXISTS idx_backups_not_deleted ON backups(is_deleted, expires_at);

-- Run once tracking index
CREATE INDEX IF NOT EXISTS idx_run_once_hash ON run_once_tracking(operation_hash);

-- Package manager index
CREATE INDEX IF NOT EXISTS idx_packages_manager ON installed_packages(package_manager);

-- Audit log indexes
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_severity ON audit_log(severity);
CREATE INDEX IF NOT EXISTS idx_audit_event ON audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_transaction ON audit_log(transaction_id);

-- Drift detection index
CREATE INDEX IF NOT EXISTS idx_drift_checked ON drift_detection(checked_at DESC);

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- Insert system info on first run
INSERT OR IGNORE INTO system_info (hostname, username, platform, arch, dotfiles_version, python_version)
VALUES (
    'unknown',  -- Will be updated by application
    'unknown',  -- Will be updated by application
    'unknown',  -- Will be updated by application
    'unknown',  -- Will be updated by application
    '1.0.0',
    '3.12.0'
);

-- ============================================================================
-- MAINTENANCE QUERIES
-- ============================================================================

-- Clean up old backups (to be run periodically)
-- DELETE FROM backups 
-- WHERE expires_at < CURRENT_TIMESTAMP 
--   AND is_deleted = 0;

-- Vacuum database (to be run periodically)
-- VACUUM;

-- Analyze for query optimization (to be run periodically)
-- ANALYZE;

-- ============================================================================
-- USAGE EXAMPLES
-- ============================================================================

/*
-- Start a new transaction
INSERT INTO transactions (id, variant, user, hostname, status)
VALUES ('550e8400-e29b-41d4-a716-446655440000', 'personal', 'john', 'mac-laptop', 'in_progress');

-- Record an operation
INSERT INTO operations (transaction_id, sequence_num, operation_type, config, status)
VALUES ('550e8400-e29b-41d4-a716-446655440000', 1, 'link', 
        '{"src": "zsh/zshrc", "dst": "~/.zshrc"}', 'success');

-- Check for drift
SELECT * FROM current_state 
WHERE checksum != (
    -- Calculate actual checksum of file
    SELECT actual_checksum FROM drift_detection 
    WHERE applied_step_id = current_state.id
);

-- Get rollback data for failed transaction
SELECT o.* FROM operations o
JOIN transactions t ON o.transaction_id = t.id
WHERE t.id = '550e8400-e29b-41d4-a716-446655440000'
  AND o.status = 'success'
ORDER BY o.sequence_num DESC;

-- Find all changes to a specific file
SELECT 
    o.transaction_id,
    o.operation_type,
    o.started_at,
    o.status,
    t.user
FROM operations o
JOIN transactions t ON o.transaction_id = t.id
WHERE o.dst_path = '/home/user/.zshrc'
ORDER BY o.started_at DESC;
*/