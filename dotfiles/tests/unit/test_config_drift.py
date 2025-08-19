"""
Unit tests for configuration drift detection.

Tests the ConfigDriftDetector class and related functionality for detecting
differences between TOML configuration and database state.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dotfiles_sync.config_drift import (
    ConfigDriftDetector,
    ConfigDriftResult,
    ConfigDriftSummary,
    ConfigDriftType,
    ConfigDriftSeverity,
)
from dotfiles_sync.models import (
    DotfilesConfig,
    PackageConfig,
    StepConfig,
    OperationType,
    Platform,
)
from dotfiles_sync.state_database import StateDatabase


class TestConfigDriftResult:
    """Test ConfigDriftResult model."""

    def test_drift_result_creation(self):
        """Test creating a drift result."""
        result = ConfigDriftResult(
            drift_type=ConfigDriftType.NEW,
            dst_path="/home/user/.bashrc",
            operation_type="link",
            current_step_hash="abc123",
            applied_step_hash=None,
            current_config={"op": "link", "src": "bashrc", "dst": "~/.bashrc"},
            applied_config=None,
            impact="New link operation will be applied",
            severity=ConfigDriftSeverity.INFO,
        )

        assert result.drift_type == ConfigDriftType.NEW
        assert result.dst_path == "/home/user/.bashrc"
        assert result.operation_type == "link"
        assert result.current_step_hash == "abc123"
        assert result.applied_step_hash is None
        assert result.severity == ConfigDriftSeverity.INFO

    def test_drift_result_string_representation(self):
        """Test string representation of drift result."""
        result = ConfigDriftResult(
            drift_type=ConfigDriftType.ORPHANED,
            dst_path="/home/user/.vimrc",
            operation_type="copy",
            impact="Operation no longer in configuration",
        )

        assert str(result) == "orphaned: /home/user/.vimrc (copy)"


class TestConfigDriftSummary:
    """Test ConfigDriftSummary model."""

    def test_drift_summary_creation(self):
        """Test creating a drift summary."""
        new_op = ConfigDriftResult(
            drift_type=ConfigDriftType.NEW,
            dst_path="/home/user/.bashrc",
            operation_type="link",
            impact="New operation",
        )

        summary = ConfigDriftSummary(
            total_drift=1,
            new_operations=[new_op],
            modified_operations=[],
            orphaned_operations=[],
            recommended_action="Run 'dotfiles-sync sync' to apply 1 new operation",
            checked_variant="default",
        )

        assert summary.total_drift == 1
        assert len(summary.new_operations) == 1
        assert summary.has_drift is True
        assert summary.critical_drift_count == 0

    def test_drift_summary_no_drift(self):
        """Test summary with no drift."""
        summary = ConfigDriftSummary(
            total_drift=0,
            new_operations=[],
            modified_operations=[],
            orphaned_operations=[],
            recommended_action="No action needed",
        )

        assert summary.has_drift is False
        assert summary.total_drift == 0

    def test_drift_summary_critical_count(self):
        """Test counting critical drift items."""
        critical_drift = ConfigDriftResult(
            drift_type=ConfigDriftType.MODIFIED,
            dst_path="/etc/important",
            operation_type="copy",
            impact="Critical change",
            severity=ConfigDriftSeverity.ERROR,
        )

        summary = ConfigDriftSummary(
            total_drift=1,
            modified_operations=[critical_drift],
        )

        assert summary.critical_drift_count == 1


class TestConfigDriftDetector:
    """Test ConfigDriftDetector class."""

    @pytest.fixture
    def mock_database(self):
        """Create a mock database."""
        mock_db = MagicMock(spec=StateDatabase)
        return mock_db

    @pytest.fixture
    def sample_config(self):
        """Create a sample configuration."""
        return DotfilesConfig(
            package=PackageConfig(
                name="test-dotfiles",
                version="1.0.0",
            ),
            step=[
                StepConfig(
                    op=OperationType.LINK,
                    src="bashrc",
                    dst="~/.bashrc",
                    variants=["personal"],  # Changed from "all" to avoid overlap
                ),
                StepConfig(
                    op=OperationType.COPY,
                    src="vimrc",
                    dst="~/.vimrc",
                    variants=["default"],
                ),
            ],
        )

    def test_detector_initialization(self, mock_database):
        """Test detector initialization."""
        detector = ConfigDriftDetector(mock_database)
        assert detector.database == mock_database

    def test_detect_drift_no_drift(self, mock_database, sample_config):
        """Test detecting no drift when config matches database."""
        # Setup mock database to return matching applied steps
        # For default variant, we should have vimrc (default variant)
        mock_database.get_current_applied_steps.return_value = [
            {
                "dst_path": str(Path("~/.vimrc").expanduser()),
                "step_hash": "matching_hash",
                "operation_type": "copy",
                "config": '{"op": "copy", "src": "vimrc", "dst": "~/.vimrc"}',
            }
        ]

        detector = ConfigDriftDetector(mock_database)

        # Mock the hash calculation to match
        with patch.object(detector, "_calculate_single_step_hash", return_value="matching_hash"):
            summary = detector.detect_drift(sample_config, variant="default")

        assert summary.total_drift == 0
        assert not summary.has_drift
        assert len(summary.new_operations) == 0
        assert len(summary.modified_operations) == 0
        assert len(summary.orphaned_operations) == 0

    def test_detect_new_operations(self, mock_database, sample_config):
        """Test detecting new operations not in database."""
        # Setup mock database to return empty (no applied steps)
        mock_database.get_current_applied_steps.return_value = []

        detector = ConfigDriftDetector(mock_database)
        summary = detector.detect_drift(sample_config, variant="default")

        # Should detect vimrc as new (it's in default variant)
        assert summary.total_drift == 1
        assert len(summary.new_operations) == 1
        assert summary.new_operations[0].drift_type == ConfigDriftType.NEW
        assert "vimrc" in summary.new_operations[0].dst_path

    def test_detect_orphaned_operations(self, mock_database, sample_config):
        """Test detecting orphaned operations in database but not in config."""
        # Setup mock database to return an operation not in config
        mock_database.get_current_applied_steps.return_value = [
            {
                "dst_path": str(Path("~/.zshrc").expanduser()),
                "step_hash": "orphaned_hash",
                "operation_type": "link",
                "config": '{"op": "link", "src": "zshrc", "dst": "~/.zshrc"}',
            }
        ]

        detector = ConfigDriftDetector(mock_database)
        summary = detector.detect_drift(sample_config, variant="default")

        assert summary.total_drift >= 1
        assert len(summary.orphaned_operations) == 1
        assert summary.orphaned_operations[0].drift_type == ConfigDriftType.ORPHANED
        assert "zshrc" in summary.orphaned_operations[0].dst_path

    def test_detect_modified_operations(self, mock_database, sample_config):
        """Test detecting modified operations with changed configuration."""
        vimrc_path = str(Path("~/.vimrc").expanduser())

        # Setup mock database with different hash for same path
        mock_database.get_current_applied_steps.return_value = [
            {
                "dst_path": vimrc_path,
                "step_hash": "old_hash",
                "operation_type": "copy",
                "config": '{"op": "copy", "src": "old_vimrc", "dst": "~/.vimrc"}',
            }
        ]

        detector = ConfigDriftDetector(mock_database)

        # Mock hash calculation to return different hash
        with patch.object(detector, "_calculate_single_step_hash", return_value="new_hash"):
            summary = detector.detect_drift(sample_config, variant="default")

        assert summary.total_drift >= 1
        assert len(summary.modified_operations) == 1
        assert summary.modified_operations[0].drift_type == ConfigDriftType.MODIFIED
        assert vimrc_path in summary.modified_operations[0].dst_path

    def test_detect_operation_type_change(self, mock_database, sample_config):
        """Test detecting when operation type changes (link to copy)."""
        vimrc_path = str(Path("~/.vimrc").expanduser())

        # Setup database with link operation for what's now a copy
        mock_database.get_current_applied_steps.return_value = [
            {
                "dst_path": vimrc_path,
                "step_hash": "old_hash",
                "operation_type": "link",  # Was link
                "config": '{"op": "link", "src": "vimrc", "dst": "~/.vimrc"}',
            }
        ]

        detector = ConfigDriftDetector(mock_database)
        summary = detector.detect_drift(sample_config, variant="default")

        # Should detect as modified with ERROR severity
        assert len(summary.modified_operations) == 1
        modified = summary.modified_operations[0]
        assert modified.drift_type == ConfigDriftType.MODIFIED
        assert modified.severity == ConfigDriftSeverity.ERROR
        assert "Operation type changed" in modified.impact

    def test_recommend_action_no_drift(self, mock_database):
        """Test recommendation when no drift exists."""
        detector = ConfigDriftDetector(mock_database)
        action = detector._recommend_action([], [], [])
        assert action == "No action needed - configuration is in sync"

    def test_recommend_action_only_new(self, mock_database):
        """Test recommendation for only new operations."""
        detector = ConfigDriftDetector(mock_database)
        new_op = ConfigDriftResult(
            drift_type=ConfigDriftType.NEW,
            dst_path="/test",
            operation_type="link",
            impact="New",
        )
        action = detector._recommend_action([new_op], [], [])
        assert "Run 'dotfiles-sync sync'" in action
        assert "apply 1 new operation" in action

    def test_recommend_action_mixed(self, mock_database):
        """Test recommendation for mixed drift types."""
        detector = ConfigDriftDetector(mock_database)

        new_op = ConfigDriftResult(
            drift_type=ConfigDriftType.NEW,
            dst_path="/new",
            operation_type="link",
            impact="New",
        )
        modified_op = ConfigDriftResult(
            drift_type=ConfigDriftType.MODIFIED,
            dst_path="/mod",
            operation_type="copy",
            impact="Modified",
        )
        orphaned_op = ConfigDriftResult(
            drift_type=ConfigDriftType.ORPHANED,
            dst_path="/old",
            operation_type="link",
            impact="Orphaned",
        )

        action = detector._recommend_action([new_op], [modified_op], [orphaned_op])
        assert "Run 'dotfiles-sync reconcile'" in action
        assert "clean 1 orphaned" in action
        assert "update 1 modified" in action
        assert "apply 1 new" in action

    def test_variant_filtering(self, mock_database):
        """Test that drift detection respects variant filtering."""
        config = DotfilesConfig(
            package=PackageConfig(name="test", version="1.0.0"),
            step=[
                StepConfig(
                    op=OperationType.LINK,
                    src="default_file",
                    dst="~/.default_file",
                    variants=["default"],
                ),
                StepConfig(
                    op=OperationType.LINK,
                    src="work_file",
                    dst="~/.work_file",
                    variants=["work"],
                ),
            ],
        )

        mock_database.get_current_applied_steps.return_value = []

        detector = ConfigDriftDetector(mock_database)

        # Check default variant
        summary_default = detector.detect_drift(config, variant="default")
        assert len(summary_default.new_operations) == 1
        assert "default_file" in summary_default.new_operations[0].dst_path

        # Check work variant
        summary_work = detector.detect_drift(config, variant="work")
        assert len(summary_work.new_operations) == 1
        assert "work_file" in summary_work.new_operations[0].dst_path

    def test_platform_filtering(self, mock_database):
        """Test that drift detection respects platform filtering."""
        config = DotfilesConfig(
            package=PackageConfig(name="test", version="1.0.0"),
            step=[
                StepConfig(
                    op=OperationType.LINK,
                    src="mac_file",
                    dst="~/.mac_file",
                    platforms=[Platform.MACOS],
                ),
                StepConfig(
                    op=OperationType.LINK,
                    src="linux_file",
                    dst="~/.linux_file",
                    platforms=[Platform.LINUX],
                ),
            ],
        )

        mock_database.get_current_applied_steps.return_value = []

        detector = ConfigDriftDetector(mock_database)

        # Check macOS platform
        summary_mac = detector.detect_drift(config, variant="default", platform=Platform.MACOS)
        assert len(summary_mac.new_operations) == 1
        assert "mac_file" in summary_mac.new_operations[0].dst_path

        # Check Linux platform
        summary_linux = detector.detect_drift(config, variant="default", platform=Platform.LINUX)
        assert len(summary_linux.new_operations) == 1
        assert "linux_file" in summary_linux.new_operations[0].dst_path

    def test_calculate_step_hash(self, mock_database):
        """Test step hash calculation consistency."""
        detector = ConfigDriftDetector(mock_database)

        config1 = {"op": "link", "src": "bashrc", "dst": "~/.bashrc"}
        config2 = {"op": "link", "src": "bashrc", "dst": "~/.bashrc"}
        config3 = {"op": "copy", "src": "bashrc", "dst": "~/.bashrc"}

        hash1 = detector._calculate_single_step_hash(config1)
        hash2 = detector._calculate_single_step_hash(config2)
        hash3 = detector._calculate_single_step_hash(config3)

        # Same config should produce same hash
        assert hash1 == hash2
        # Different config should produce different hash
        assert hash1 != hash3

    def test_get_orphaned_step_hashes(self, mock_database):
        """Test getting orphaned step hashes."""
        mock_database.get_current_applied_steps.return_value = [
            {"step_hash": "hash1"},
            {"step_hash": "hash2"},
            {"step_hash": "hash3"},
        ]

        detector = ConfigDriftDetector(mock_database)

        # Mock loading config with only hash1 and hash2
        with patch.object(detector, "_get_current_step_configs"):
            with patch.object(detector, "_calculate_step_hashes") as mock_calc_hashes:
                mock_calc_hashes.return_value = {"path1": "hash1", "path2": "hash2"}

                # Import ConfigLoader from the correct module
                with patch("dotfiles_sync.config.ConfigLoader"):
                    orphaned = detector.get_orphaned_step_hashes()

        # hash3 should be orphaned
        assert "hash3" in orphaned
        assert "hash1" not in orphaned
        assert "hash2" not in orphaned


class TestDatabaseDriftMethods:
    """Test database methods for drift detection."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db = StateDatabase(db_path=tmp.name)
            yield db
            db.close()

    def test_get_applied_step_hashes_by_variant(self, temp_db):
        """Test getting applied step hashes."""
        # Start a transaction and apply some steps
        with temp_db.transaction("test", "user", "host") as tx:
            temp_db.record_applied_step(
                tx,
                operation_type="link",
                config={"op": "link", "src": "bashrc", "dst": "~/.bashrc"},
                src_path="bashrc",
                dst_path="/home/user/.bashrc",
            )

        # Get applied hashes
        hashes = temp_db.get_applied_step_hashes_by_variant()

        assert "/home/user/.bashrc" in hashes
        assert hashes["/home/user/.bashrc"]["operation_type"] == "link"
        assert hashes["/home/user/.bashrc"]["step_hash"] is not None

    def test_find_orphaned_operations(self, temp_db):
        """Test finding orphaned operations."""
        # Apply some steps
        with temp_db.transaction("test", "user", "host") as tx:
            temp_db.record_applied_step(
                tx,
                operation_type="link",
                config={"op": "link", "src": "file1", "dst": "~/.file1"},
                dst_path="/home/user/.file1",
            )
            temp_db.record_applied_step(
                tx,
                operation_type="copy",
                config={"op": "copy", "src": "file2", "dst": "~/.file2"},
                dst_path="/home/user/.file2",
            )

        # Get all applied steps to find their hashes
        all_steps = temp_db.get_current_applied_steps()
        hash1 = all_steps[0]["step_hash"]
        # hash2 = all_steps[1]["step_hash"]  # Not needed for this test

        # Find orphaned with only hash1 in current config
        orphaned = temp_db.find_orphaned_operations({hash1})

        assert len(orphaned) == 1
        assert orphaned[0]["dst_path"] == "/home/user/.file2"

    def test_mark_operations_as_orphaned(self, temp_db):
        """Test marking operations as orphaned."""
        # Apply a step
        with temp_db.transaction("test", "user", "host") as tx:
            temp_db.record_applied_step(
                tx,
                operation_type="link",
                config={"op": "link", "src": "file", "dst": "~/.file"},
                dst_path="/home/user/.file",
            )

        # Get the step hash
        steps = temp_db.get_current_applied_steps()
        assert len(steps) == 1
        assert steps[0]["is_current"] == 1
        step_hash = steps[0]["step_hash"]

        # Mark as orphaned
        with temp_db.transaction("test", "user", "host") as tx:
            affected = temp_db.mark_operations_as_orphaned([step_hash], tx.id)

        assert affected == 1

        # Verify it's marked as not current
        steps_after = temp_db.get_current_applied_steps()
        assert len(steps_after) == 0  # No current steps

    def test_remove_orphaned_operations(self, temp_db):
        """Test removing orphaned operations."""
        # Apply a step
        with temp_db.transaction("test", "user", "host") as tx:
            temp_db.record_applied_step(
                tx,
                operation_type="link",
                config={"op": "link", "src": "file", "dst": "~/.file"},
                dst_path="/home/user/.file",
            )

        # Get the step hash
        steps = temp_db.get_current_applied_steps()
        step_hash = steps[0]["step_hash"]

        # Remove the operation
        with temp_db.transaction("test", "user", "host") as tx:
            affected = temp_db.remove_orphaned_operations([step_hash], tx.id)

        assert affected == 1

        # Verify it's gone
        cursor = temp_db.conn.execute("SELECT COUNT(*) as count FROM applied_steps")
        assert cursor.fetchone()["count"] == 0

    def test_get_config_drift_summary(self, temp_db):
        """Test getting config drift summary."""
        # Apply some steps
        with temp_db.transaction("test", "user", "host") as tx:
            temp_db.record_applied_step(
                tx,
                operation_type="link",
                config={"op": "link", "src": "file1", "dst": "~/.file1"},
                dst_path="/home/user/.file1",
            )
            temp_db.record_applied_step(
                tx,
                operation_type="copy",
                config={"op": "copy", "src": "file2", "dst": "~/.file2"},
                dst_path="/home/user/.file2",
            )

        # Get summary
        summary = temp_db.get_config_drift_summary()

        assert summary["total_applied"] == 2
        assert "link" in summary["by_operation_type"]
        assert "copy" in summary["by_operation_type"]
        assert summary["by_operation_type"]["link"] == 1
        assert summary["by_operation_type"]["copy"] == 1
        assert len(summary["recent_operations"]) == 2
        assert "checked_at" in summary
