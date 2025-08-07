"""
Unit tests for drift detection functionality.
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from safety.drift import DriftDetector, DriftResult, DriftType, DriftReport, DriftSeverity
from safety.validator import ChecksumValidator


class TestDriftDetector:
    """Test DriftDetector functionality."""
    
    @pytest.fixture
    def mock_database(self):
        """Create a mock database."""
        mock_db = Mock()
        mock_db.get_current_applied_steps = Mock(return_value=[])
        mock_db.get_drift_history = Mock(return_value=[])
        mock_db.update_step_last_verified = Mock()
        mock_db.find_applied_step_by_path = Mock(return_value=None)
        mock_db.record_drift = Mock()
        mock_db.get_drift_summary = Mock(return_value=[])
        return mock_db
    
    @pytest.fixture
    def drift_detector(self, mock_database):
        """Create a DriftDetector instance with mock database."""
        return DriftDetector(mock_database)
    
    def test_check_all_managed_files_uses_get_current_applied_steps(self, drift_detector, mock_database):
        """Test that check_all_managed_files uses get_current_applied_steps method."""
        # Setup mock data
        mock_database.get_current_applied_steps.return_value = [
            {
                'id': 1,
                'dst_path': '~/test_file',
                'operation_type': 'link',
                'src_path': '/src/test_file'
            }
        ]
        
        # Run detection
        with patch.object(drift_detector, 'check_file_drift', return_value=[]):
            report = drift_detector.check_all_managed_files()
        
        # Verify the correct method was called
        mock_database.get_current_applied_steps.assert_called_once()
        assert report.total_files_checked == 1
    
    def test_check_all_managed_files_updates_last_verified(self, drift_detector, mock_database):
        """Test that check_all_managed_files updates last_verified timestamp when no drift found."""
        # Setup mock data
        mock_database.get_current_applied_steps.return_value = [
            {
                'id': 1,
                'dst_path': '~/test_file',
                'operation_type': 'link',
                'src_path': '/src/test_file'
            }
        ]
        
        # Run detection with no drift
        with patch.object(drift_detector, 'check_file_drift', return_value=[]):
            drift_detector.check_all_managed_files()
        
        # Verify update_step_last_verified was called
        mock_database.update_step_last_verified.assert_called_once_with(1)
    
    def test_check_specific_files_uses_find_applied_step_by_path(self, drift_detector, mock_database):
        """Test that check_specific_files uses find_applied_step_by_path method."""
        test_path = Path("/test/file.txt")
        
        # Setup mock data
        mock_database.find_applied_step_by_path.return_value = {
            'id': 1,
            'dst_path': str(test_path),
            'operation_type': 'copy',
            'src_path': '/src/file.txt'
        }
        
        # Run detection
        with patch.object(drift_detector, 'check_file_drift', return_value=[]):
            report = drift_detector.check_specific_files([test_path])
        
        # Verify the correct method was called
        mock_database.find_applied_step_by_path.assert_called_once()
        assert report.total_files_checked == 1
    
    def test_get_drift_history_uses_get_drift_history(self, drift_detector, mock_database):
        """Test that get_drift_history uses get_drift_history method with proper limit calculation."""
        # Setup mock return
        mock_history = [
            {'id': 1, 'file_path': '/test1', 'drift_type': 'modified'},
            {'id': 2, 'file_path': '/test2', 'drift_type': 'deleted'}
        ]
        mock_database.get_drift_history.return_value = mock_history
        
        # Test with days parameter
        result = drift_detector.get_drift_history(days=7)
        
        # Verify the correct method was called with calculated limit
        mock_database.get_drift_history.assert_called_once_with(limit=70)  # 7 days * 10
        assert result == mock_history
    
    def test_get_drift_history_default_limit(self, drift_detector, mock_database):
        """Test that get_drift_history uses default limit when days not specified."""
        mock_database.get_drift_history.return_value = []
        
        # Test without days parameter
        drift_detector.get_drift_history()
        
        # Verify default limit based on 30 days * 10 = 300
        mock_database.get_drift_history.assert_called_once_with(limit=300)
    
    def test_check_file_drift_missing_file(self, drift_detector, tmp_path):
        """Test drift detection for missing file."""
        test_file = tmp_path / "missing.txt"
        
        results = drift_detector.check_file_drift(
            applied_step_id=1,
            file_path=test_file,
            expected_config={'operation_type': 'link'}
        )
        
        assert len(results) == 1
        assert results[0].drift_type == DriftType.DELETED
        assert results[0].file_path == str(test_file)
    
    def test_check_file_drift_modified_content(self, drift_detector, tmp_path):
        """Test drift detection for modified file content."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("original content")
        
        # Mock expected checksum to be different
        expected_config = {
            'operation_type': 'copy',
            'checksum': 'different_checksum'
        }
        
        # Mock the ChecksumValidator calculate_sha256 method
        with patch.object(ChecksumValidator, 'calculate_sha256', return_value='current_checksum'):
            results = drift_detector.check_file_drift(
                applied_step_id=1,
                file_path=test_file,
                expected_config=expected_config
            )
        
        assert len(results) == 1
        assert results[0].drift_type == DriftType.MODIFIED
    
    def test_check_symlink_drift(self, drift_detector, tmp_path):
        """Test drift detection for symlinks."""
        source = tmp_path / "source.txt"
        source.write_text("content")
        link = tmp_path / "link.txt"
        link.symlink_to(source)
        
        # Test correct symlink
        expected_config = {
            'operation_type': 'link',
            'src_path': str(source),
            'file_type': 'symlink'  # Need to specify this to avoid TYPE_CHANGED drift
        }
        
        results = drift_detector.check_file_drift(
            applied_step_id=1,
            file_path=link,
            expected_config=expected_config
        )
        
        assert len(results) == 0  # No drift
        
        # Test wrong symlink target
        expected_config['src_path'] = '/wrong/path'
        results = drift_detector.check_file_drift(
            applied_step_id=1,
            file_path=link,
            expected_config=expected_config
        )
        
        assert len(results) == 1
        assert results[0].drift_type == DriftType.SYMLINK_TARGET


class TestDriftReport:
    """Test DriftReport functionality."""
    
    def test_drift_report_summary(self):
        """Test DriftReport summary generation."""
        report = DriftReport(total_files_checked=10)
        
        # Add some drift results
        report.drift_results.append(
            DriftResult(
                applied_step_id=1,
                file_path="/test1",
                drift_type=DriftType.DELETED,
                severity=DriftSeverity.HIGH,
                details={"info": "File not found"}
            )
        )
        report.drift_results.append(
            DriftResult(
                applied_step_id=2,
                file_path="/test2",
                drift_type=DriftType.MODIFIED,
                severity=DriftSeverity.MEDIUM,
                details={"info": "Content changed"}
            )
        )
        
        assert report.total_files_checked == 10
        assert len(report.drift_results) == 2
        assert report.has_drift is True
    
    def test_drift_report_no_drift(self):
        """Test DriftReport when no drift detected."""
        report = DriftReport(total_files_checked=5)
        
        assert report.has_drift is False
        assert len(report.drift_results) == 0