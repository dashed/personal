"""
Unit tests for StateDatabase module.
"""

import pytest

from dotfiles_sync import __version__
from dotfiles_sync.state_database import StateDatabase


class TestStateDatabase:
    """Test StateDatabase functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create an in-memory database for testing."""
        db = StateDatabase(":memory:")
        yield db
        db.close()

    def test_database_initialization(self, temp_db):
        """Test that database is properly initialized with schema."""
        # Check that tables exist
        cursor = temp_db.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        expected_tables = {
            "system_info",
            "transactions",
            "operations",
            "backups",
            "drift_detection",
            "applied_steps",
            "run_once_tracking",
            "installed_packages",
            "audit_log",
        }

        assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"

    def test_version_stored_correctly(self, temp_db):
        """Test that package version is stored correctly in system_info."""
        # Query system_info table
        cursor = temp_db.conn.cursor()
        cursor.execute("SELECT dotfiles_version FROM system_info")
        result = cursor.fetchone()

        assert result is not None, "No system_info record found"
        stored_version = result[0]

        # Check that the stored version matches the package version
        assert stored_version == __version__, (
            f"Version mismatch: stored={stored_version}, expected={__version__}"
        )

    def test_version_not_hardcoded(self):
        """Test that version is not hardcoded in state_database.py."""
        # Read the state_database.py file to check for hardcoded versions
        import dotfiles_sync.state_database
        import inspect

        source = inspect.getsource(dotfiles_sync.state_database)

        # Check that "1.0.0" doesn't appear as a hardcoded version
        # (It might appear in comments or error messages, but not as the version value)
        assert '"1.0.0",' not in source and "'1.0.0'," not in source, (
            "Version should not be hardcoded in state_database.py"
        )

        # Verify it imports and uses __version__
        assert "__version__" in source, "state_database.py should use __version__"

    def test_get_current_applied_steps(self, temp_db):
        """Test get_current_applied_steps method."""
        # Insert some test data
        cursor = temp_db.conn.cursor()
        cursor.execute(
            """
            INSERT INTO applied_steps (step_hash, operation_type, src_path, dst_path, checksum, config, applied_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            ("hash1", "link", "/src/file1", "/dst/file1", "checksum1", '{"op": "link"}'),
        )
        cursor.execute(
            """
            INSERT INTO applied_steps (step_hash, operation_type, src_path, dst_path, checksum, config, applied_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            ("hash2", "copy", "/src/file2", "/dst/file2", "checksum2", '{"op": "copy"}'),
        )
        temp_db.conn.commit()

        # Test the method
        steps = temp_db.get_current_applied_steps()

        assert len(steps) == 2
        assert steps[0]["operation_type"] == "link"
        assert steps[1]["operation_type"] == "copy"

    def test_find_applied_step_by_path(self, temp_db):
        """Test find_applied_step_by_path method."""
        # Insert test data
        cursor = temp_db.conn.cursor()
        cursor.execute(
            """
            INSERT INTO applied_steps (step_hash, operation_type, src_path, dst_path, checksum, config, applied_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            ("hash1", "link", "/src/file1", "/dst/file1", "checksum1", '{"op": "link"}'),
        )
        temp_db.conn.commit()

        # Test finding existing path
        step = temp_db.find_applied_step_by_path("/dst/file1")
        assert step is not None
        assert step["dst_path"] == "/dst/file1"
        assert step["operation_type"] == "link"

        # Test finding non-existing path
        step = temp_db.find_applied_step_by_path("/dst/nonexistent")
        assert step is None

    def test_update_step_last_verified(self, temp_db):
        """Test update_step_last_verified method."""
        # Insert test data
        cursor = temp_db.conn.cursor()
        cursor.execute(
            """
            INSERT INTO applied_steps (step_hash, operation_type, src_path, dst_path, checksum, config, applied_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            ("hash1", "link", "/src/file1", "/dst/file1", "checksum1", '{"op": "link"}'),
        )
        temp_db.conn.commit()

        # Get the inserted ID
        step_id = cursor.lastrowid

        # Get initial last_verified_at
        cursor.execute("SELECT last_verified_at FROM applied_steps WHERE id = ?", (step_id,))
        initial_verified = cursor.fetchone()[0]

        # Update last_verified
        temp_db.update_step_last_verified(step_id)

        # Check it was updated
        cursor.execute("SELECT last_verified_at FROM applied_steps WHERE id = ?", (step_id,))
        updated_verified = cursor.fetchone()[0]

        assert updated_verified is not None
        assert updated_verified != initial_verified

    def test_get_drift_history(self, temp_db):
        """Test get_drift_history method."""
        cursor = temp_db.conn.cursor()

        # First insert applied_steps records to satisfy foreign key
        for i in range(5):
            cursor.execute(
                """
                INSERT INTO applied_steps (step_hash, operation_type, src_path, dst_path, checksum, config, applied_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (
                    f"hash{i}",
                    "link",
                    f"/src/file{i}",
                    f"/dst/file{i}",
                    f"checksum{i}",
                    '{"op": "link"}',
                ),
            )

        # Now insert drift detection records
        for i in range(5):
            cursor.execute(
                """
                INSERT INTO drift_detection (applied_step_id, drift_type, details, checked_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (i + 1, "modified", f'{{"change": "test{i}"}}'),
            )
        temp_db.conn.commit()

        # Test with limit
        history = temp_db.get_drift_history(limit=3)
        assert len(history) == 3

        # Test with higher limit
        history = temp_db.get_drift_history(limit=10)
        assert len(history) == 5

    def test_get_failed_transactions(self, temp_db):
        """Test get_failed_transactions method."""
        # Insert test transactions
        cursor = temp_db.conn.cursor()

        # Insert a failed transaction
        cursor.execute(
            """
            INSERT INTO transactions (id, variant, user, hostname, status, dry_run, started_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            ("trans1", "default", "testuser", "testhost", "failed", 0),
        )

        # Insert a successful transaction (should not be returned)
        cursor.execute(
            """
            INSERT INTO transactions (id, variant, user, hostname, status, dry_run, started_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            ("trans2", "default", "testuser", "testhost", "completed", 0),
        )

        temp_db.conn.commit()

        # Test the method
        failed = temp_db.get_failed_transactions(limit=10)

        assert len(failed) == 1
        assert failed[0]["id"] == "trans1"
        assert failed[0]["status"] == "failed"

    def test_cleanup_old_transactions(self, temp_db):
        """Test cleanup_old_transactions method."""
        import datetime

        cursor = temp_db.conn.cursor()

        # Insert old transaction (should be cleaned up)
        old_date = (datetime.datetime.now() - datetime.timedelta(days=35)).isoformat()
        cursor.execute(
            """
            INSERT INTO transactions (id, variant, user, hostname, status, dry_run, started_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            ("old_trans", "default", "testuser", "testhost", "completed", 0, old_date, old_date),
        )

        # Insert recent transaction (should not be cleaned up)
        recent_date = (datetime.datetime.now() - datetime.timedelta(days=5)).isoformat()
        cursor.execute(
            """
            INSERT INTO transactions (id, variant, user, hostname, status, dry_run, started_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "recent_trans",
                "default",
                "testuser",
                "testhost",
                "completed",
                0,
                recent_date,
                recent_date,
            ),
        )

        temp_db.conn.commit()

        # Run cleanup
        cleaned = temp_db.cleanup_old_transactions(days=30)

        # Check results
        assert cleaned == 1

        # Verify old transaction was deleted
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE id = 'old_trans'")
        assert cursor.fetchone()[0] == 0

        # Verify recent transaction still exists
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE id = 'recent_trans'")
        assert cursor.fetchone()[0] == 1


# Transaction context tests would go here, but the implementation
# in TransactionContext doesn't have the methods we're testing.
# These should be integration tests instead.
