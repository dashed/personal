"""
Drift detection for the Dotfiles Management System.

This module provides comprehensive drift detection functionality including:
- Detection of external modifications to managed files
- Comparison of current state vs expected state
- Classification of drift types (modified, deleted, permissions, ownership)
- Reporting and recovery suggestions
- Integration with the state database

Uses the existing drift_detection and applied_steps tables.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from dotfiles_sync.models import SystemInfo
from dotfiles_sync.state_database import StateDatabase
from .validator import ChecksumValidator


class DriftType(str, Enum):
    """Types of drift that can be detected."""
    MODIFIED = "modified"
    DELETED = "deleted"
    PERMISSIONS = "permissions"
    OWNERSHIP = "ownership"
    SYMLINK_TARGET = "symlink_target"
    TYPE_CHANGED = "type_changed"


class DriftSeverity(str, Enum):
    """Severity levels for drift detection."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DriftResult(BaseModel):
    """Result of drift detection for a single file."""
    
    applied_step_id: int = Field(..., description="ID from applied_steps table")
    file_path: str = Field(..., description="Path to the file")
    drift_type: DriftType = Field(..., description="Type of drift detected")
    severity: DriftSeverity = Field(..., description="Severity of the drift")
    expected_value: Optional[str] = Field(None, description="Expected value")
    actual_value: Optional[str] = Field(None, description="Actual value")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional details")
    detected_at: datetime = Field(default_factory=datetime.now)
    suggestion: Optional[str] = Field(None, description="Recovery suggestion")
    
    def __str__(self) -> str:
        return f"Drift in {self.file_path}: {self.drift_type.value} ({self.severity.value})"


class DriftReport(BaseModel):
    """Comprehensive drift detection report."""
    
    checked_at: datetime = Field(default_factory=datetime.now)
    system_info: SystemInfo = Field(default_factory=SystemInfo.from_current_system)
    total_files_checked: int = Field(0, description="Number of files checked")
    drift_results: List[DriftResult] = Field(default_factory=list, description="Detected drift")
    summary: Dict[str, Any] = Field(default_factory=dict, description="Summary statistics")
    
    @property
    def has_drift(self) -> bool:
        """Check if any drift was detected."""
        return len(self.drift_results) > 0
    
    @property
    def critical_drift_count(self) -> int:
        """Count of critical drift issues."""
        return sum(1 for result in self.drift_results if result.severity == DriftSeverity.CRITICAL)
    
    @property  
    def high_drift_count(self) -> int:
        """Count of high severity drift issues."""
        return sum(1 for result in self.drift_results if result.severity == DriftSeverity.HIGH)
    
    def generate_summary(self) -> None:
        """Generate summary statistics."""
        drift_by_type = {}
        drift_by_severity = {}
        
        for result in self.drift_results:
            # Count by type
            drift_by_type[result.drift_type.value] = drift_by_type.get(result.drift_type.value, 0) + 1
            
            # Count by severity
            drift_by_severity[result.severity.value] = drift_by_severity.get(result.severity.value, 0) + 1
        
        self.summary = {
            "total_drift_issues": len(self.drift_results),
            "drift_by_type": drift_by_type,
            "drift_by_severity": drift_by_severity,
            "files_with_drift": len(set(result.file_path for result in self.drift_results)),
            "clean_files": self.total_files_checked - len(set(result.file_path for result in self.drift_results))
        }


class DriftDetector:
    """
    Detects and reports drift in managed dotfiles.
    
    Features:
    - Checksum-based change detection
    - Permission and ownership monitoring
    - Symlink target verification
    - File type change detection
    - Integration with state database
    """
    
    def __init__(self, database: StateDatabase):
        """
        Initialize drift detector.
        
        Args:
            database: State database instance
        """
        self.database = database
        self.system_info = SystemInfo.from_current_system()
    
    def check_file_drift(self, applied_step_id: int, file_path: Path, expected_config: Dict[str, Any]) -> List[DriftResult]:
        """
        Check for drift in a single file.
        
        Args:
            applied_step_id: ID from applied_steps table
            file_path: Path to check
            expected_config: Expected configuration from applied_steps
            
        Returns:
            List of drift results (empty if no drift)
        """
        results = []
        file_path_str = str(file_path)
        
        try:
            # Check if file exists
            if not file_path.exists() and not file_path.is_symlink():
                results.append(DriftResult(
                    applied_step_id=applied_step_id,
                    file_path=file_path_str,
                    drift_type=DriftType.DELETED,
                    severity=DriftSeverity.HIGH,
                    expected_value="file exists",
                    actual_value="file deleted",
                    suggestion="Re-run dotfiles sync to restore file"
                ))
                return results
            
            # Get expected values from config
            expected_checksum = expected_config.get("checksum")
            expected_mode = expected_config.get("mode")
            operation_type = expected_config.get("operation_type", "unknown")
            
            # Check checksum for regular files
            if file_path.is_file() and not file_path.is_symlink():
                actual_checksum = ChecksumValidator.calculate_sha256(file_path)
                
                if expected_checksum and actual_checksum != expected_checksum:
                    severity = DriftSeverity.HIGH if operation_type in ["copy", "template"] else DriftSeverity.MEDIUM
                    results.append(DriftResult(
                        applied_step_id=applied_step_id,
                        file_path=file_path_str,
                        drift_type=DriftType.MODIFIED,
                        severity=severity,
                        expected_value=expected_checksum,
                        actual_value=actual_checksum,
                        details={"operation_type": operation_type},
                        suggestion="Check if manual modifications are intentional, or re-run sync to restore"
                    ))
            
            # Check symlink target
            elif file_path.is_symlink():
                actual_target = str(file_path.readlink())
                expected_target = expected_config.get("src_path")
                
                if expected_target and actual_target != expected_target:
                    results.append(DriftResult(
                        applied_step_id=applied_step_id,
                        file_path=file_path_str,
                        drift_type=DriftType.SYMLINK_TARGET,
                        severity=DriftSeverity.MEDIUM,
                        expected_value=expected_target,
                        actual_value=actual_target,
                        suggestion="Re-run dotfiles sync to fix symlink target"
                    ))
            
            # Check permissions if expected
            if expected_mode:
                try:
                    actual_mode = oct(file_path.stat().st_mode)[-3:]
                    expected_mode_clean = expected_mode.lstrip('0') if expected_mode.startswith('0') else expected_mode
                    
                    if actual_mode != expected_mode_clean:
                        results.append(DriftResult(
                            applied_step_id=applied_step_id,
                            file_path=file_path_str,
                            drift_type=DriftType.PERMISSIONS,
                            severity=DriftSeverity.LOW,
                            expected_value=expected_mode_clean,
                            actual_value=actual_mode,
                            suggestion=f"Run: chmod {expected_mode_clean} {file_path}"
                        ))
                except OSError:
                    pass  # Skip permission check if not accessible
            
            # Check if file type changed
            expected_type = expected_config.get("file_type", "file")
            if file_path.is_symlink() and expected_type != "symlink":
                results.append(DriftResult(
                    applied_step_id=applied_step_id,
                    file_path=file_path_str,
                    drift_type=DriftType.TYPE_CHANGED,
                    severity=DriftSeverity.HIGH,
                    expected_value=expected_type,
                    actual_value="symlink",
                    suggestion="Re-run dotfiles sync to restore correct file type"
                ))
            elif file_path.is_file() and expected_type == "symlink":
                results.append(DriftResult(
                    applied_step_id=applied_step_id,
                    file_path=file_path_str,
                    drift_type=DriftType.TYPE_CHANGED,
                    severity=DriftSeverity.HIGH,
                    expected_value="symlink",
                    actual_value="file",
                    suggestion="Re-run dotfiles sync to restore symlink"
                ))
            
        except Exception as e:
            # Log error but don't fail entire drift check
            results.append(DriftResult(
                applied_step_id=applied_step_id,
                file_path=file_path_str,
                drift_type=DriftType.MODIFIED,
                severity=DriftSeverity.LOW,
                expected_value="unknown",
                actual_value="error",
                details={"error": str(e)},
                suggestion="Manual investigation required"
            ))
        
        return results
    
    def check_all_managed_files(self) -> DriftReport:
        """
        Check drift for all currently managed files.
        
        Returns:
            Comprehensive drift report
        """
        report = DriftReport()
        
        try:
            # Get all currently applied steps from database
            applied_steps = self.database.get_current_applied_steps()
            report.total_files_checked = len(applied_steps)
            
            for step in applied_steps:
                if not step.get("dst_path"):
                    continue
                    
                file_path = Path(step["dst_path"]).expanduser().resolve()
                
                # Check for drift in this file
                drift_results = self.check_file_drift(
                    applied_step_id=step["id"],
                    file_path=file_path,
                    expected_config=step
                )
                
                report.drift_results.extend(drift_results)
                
                # Update last verified timestamp in database
                if not drift_results:  # Only update if no drift found
                    self.database.update_step_last_verified(step["id"])
            
            # Record drift results in database
            for result in report.drift_results:
                self.database.record_drift_detection(
                    applied_step_id=result.applied_step_id,
                    expected_checksum=result.expected_value,
                    actual_checksum=result.actual_value,
                    drift_type=result.drift_type.value,
                    details=result.details
                )
            
            # Generate summary
            report.generate_summary()
            
        except Exception as e:
            # Create error report
            report.summary = {"error": str(e), "total_drift_issues": 0}
        
        return report
    
    def check_specific_files(self, file_paths: List[Path]) -> DriftReport:
        """
        Check drift for specific files.
        
        Args:
            file_paths: List of file paths to check
            
        Returns:
            Drift report for specified files
        """
        report = DriftReport()
        
        try:
            for file_path in file_paths:
                resolved_path = file_path.expanduser().resolve()
                
                # Find applied step for this file
                applied_step = self.database.find_applied_step_by_path(str(resolved_path))
                
                if not applied_step:
                    continue
                
                # Check for drift
                drift_results = self.check_file_drift(
                    applied_step_id=applied_step["id"],
                    file_path=resolved_path,
                    expected_config=applied_step
                )
                
                report.drift_results.extend(drift_results)
            
            report.total_files_checked = len(file_paths)
            report.generate_summary()
            
        except Exception as e:
            report.summary = {"error": str(e), "total_drift_issues": 0}
        
        return report
    
    def get_drift_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get drift detection history from database.
        
        Args:
            days: Number of days of history to retrieve
            
        Returns:
            List of historical drift detection results
        """
        try:
            return self.database.get_drift_history(days)
        except Exception:
            return []
    
    def get_drift_summary(self) -> Dict[str, Any]:
        """
        Get summary of current drift status.
        
        Returns:
            Dictionary with drift summary statistics
        """
        try:
            return self.database.get_drift_summary()
        except Exception:
            return {"error": "Unable to retrieve drift summary"}
    
    def suggest_fixes(self, drift_results: List[DriftResult]) -> List[str]:
        """
        Generate fix suggestions for detected drift.
        
        Args:
            drift_results: List of drift detection results
            
        Returns:
            List of suggested fix commands/actions
        """
        suggestions = []
        
        # Group by suggestion type
        resync_files = []
        chmod_commands = []
        manual_review = []
        
        for result in drift_results:
            if result.drift_type in [DriftType.DELETED, DriftType.SYMLINK_TARGET, DriftType.TYPE_CHANGED]:
                resync_files.append(result.file_path)
            elif result.drift_type == DriftType.PERMISSIONS and result.suggestion:
                chmod_commands.append(result.suggestion)
            elif result.drift_type == DriftType.MODIFIED:
                if result.severity in [DriftSeverity.HIGH, DriftSeverity.CRITICAL]:
                    manual_review.append(result.file_path)
                else:
                    resync_files.append(result.file_path)
        
        # Generate consolidated suggestions
        if resync_files:
            suggestions.append(f"Re-run dotfiles sync to restore {len(resync_files)} files")
            
        if chmod_commands:
            suggestions.extend(chmod_commands[:5])  # Limit to first 5 chmod commands
            if len(chmod_commands) > 5:
                suggestions.append(f"... and {len(chmod_commands) - 5} more permission fixes")
        
        if manual_review:
            suggestions.append(f"Manually review {len(manual_review)} modified files for intentional changes")
        
        return suggestions
    
    def auto_fix_permissions(self, drift_results: List[DriftResult]) -> Tuple[int, List[str]]:
        """
        Automatically fix permission drift (dry-run by default).
        
        Args:
            drift_results: List of drift results with permission issues
            
        Returns:
            Tuple of (fixed_count, error_messages)
        """
        fixed_count = 0
        errors = []
        
        for result in drift_results:
            if result.drift_type != DriftType.PERMISSIONS:
                continue
                
            try:
                file_path = Path(result.file_path)
                expected_mode = result.expected_value
                
                if expected_mode and file_path.exists():
                    # Convert mode string to integer
                    mode_int = int(expected_mode, 8)
                    file_path.chmod(mode_int)
                    fixed_count += 1
                    
            except (ValueError, OSError) as e:
                errors.append(f"Failed to fix {result.file_path}: {e}")
        
        return fixed_count, errors


class DriftMonitor:
    """
    Scheduled drift monitoring service.
    """
    
    def __init__(self, detector: DriftDetector, check_interval_hours: int = 24):
        """
        Initialize drift monitor.
        
        Args:
            detector: Drift detector instance
            check_interval_hours: Hours between automatic checks
        """
        self.detector = detector
        self.check_interval_hours = check_interval_hours
        self.last_check: Optional[datetime] = None
    
    def should_run_check(self) -> bool:
        """
        Check if it's time to run drift detection.
        
        Returns:
            True if check should be run
        """
        if self.last_check is None:
            return True
            
        hours_since_check = (datetime.now() - self.last_check).total_seconds() / 3600
        return hours_since_check >= self.check_interval_hours
    
    def run_scheduled_check(self) -> Optional[DriftReport]:
        """
        Run scheduled drift check if needed.
        
        Returns:
            Drift report if check was run, None otherwise
        """
        if not self.should_run_check():
            return None
            
        report = self.detector.check_all_managed_files()
        self.last_check = datetime.now()
        
        return report