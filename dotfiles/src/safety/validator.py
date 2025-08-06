"""
Path and permission validation for the Dotfiles Management System.

This module provides comprehensive validation functionality including:
- Path security validation (whitelist/blacklist)
- Permission checking before operations
- Checksum verification for file integrity
- Command whitelisting for run operations
- Path traversal attack prevention

Integrates with SecurityConfig and SafetyConfig from the models.
"""

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from dotfiles_sync.models import SecurityConfig, SafetyConfig, ExecutionContext


class ValidationResult(BaseModel):
    """Result of a validation check."""
    
    valid: bool = Field(..., description="Whether validation passed")
    message: str = Field(..., description="Human-readable validation message")
    error_code: Optional[str] = Field(None, description="Machine-readable error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional validation details")


class PathValidator:
    """
    Validates paths against security policies.
    
    Provides comprehensive path validation including:
    - Whitelist/blacklist checking
    - Path traversal prevention
    - Permission verification
    - File system safety checks
    """
    
    def __init__(self, security_config: Optional[SecurityConfig] = None):
        """
        Initialize path validator.
        
        Args:
            security_config: Security configuration with path policies
        """
        self.security_config = security_config or SecurityConfig()
        self._whitelist_patterns = self._compile_patterns(self.security_config.whitelist_paths)
        self._blacklist_patterns = self._compile_patterns(self.security_config.blacklist_paths)
        
    def _compile_patterns(self, patterns: List[str]) -> Set[str]:
        """
        Compile glob patterns for efficient matching.
        
        Args:
            patterns: List of glob patterns
            
        Returns:
            Set of normalized patterns
        """
        compiled = set()
        for pattern in patterns:
            # Expand environment variables and ~ in patterns
            expanded = os.path.expanduser(os.path.expandvars(pattern))
            compiled.add(expanded)
        return compiled
    
    def _path_matches_patterns(self, path: Path, patterns: Set[str]) -> bool:
        """
        Check if path matches any of the patterns.
        
        Args:
            path: Path to check
            patterns: Set of patterns to match against
            
        Returns:
            True if path matches any pattern
        """
        # Use absolute() instead of resolve() for pattern matching
        # This preserves the logical path structure without following symlinks
        # Important for macOS where /tmp -> /private/tmp and other system symlinks exist
        path_str = str(path.absolute())
        
        for pattern in patterns:
            # Simple glob matching - could be enhanced with fnmatch for complex patterns
            if pattern.endswith("/**"):
                # Directory and all subdirectories
                base = pattern[:-3]
                if path_str.startswith(base):
                    return True
            elif pattern.endswith("/*"):
                # Direct children only
                base = pattern[:-2]
                parent = str(path.absolute().parent)
                if parent == base:
                    return True
            else:
                # Exact match
                if path_str == pattern or str(path) == pattern:
                    return True
                    
        return False
    
    def validate_destination_path(self, dst_path: Path) -> ValidationResult:
        """
        Validate a destination path against security policies.
        
        Args:
            dst_path: Destination path to validate
            
        Returns:
            ValidationResult indicating if path is allowed
        """
        try:
            # Get absolute path for pattern matching (preserves logical structure)
            absolute_path = dst_path.absolute()
            
            # Also resolve path for security checks (follows symlinks, prevents traversal)
            resolved_path = dst_path.resolve()
            
            # Check blacklist first (takes precedence) - use absolute path for pattern matching
            if self._path_matches_patterns(absolute_path, self._blacklist_patterns):
                return ValidationResult(
                    valid=False,
                    message=f"Path {absolute_path} is in blacklist",
                    error_code="PATH_BLACKLISTED",
                    details={"path": str(absolute_path), "blacklist": list(self._blacklist_patterns)}
                )
            
            # Check whitelist - use absolute path for pattern matching
            if self._whitelist_patterns and not self._path_matches_patterns(absolute_path, self._whitelist_patterns):
                return ValidationResult(
                    valid=False,
                    message=f"Path {absolute_path} not in whitelist",
                    error_code="PATH_NOT_WHITELISTED", 
                    details={"path": str(absolute_path), "whitelist": list(self._whitelist_patterns)}
                )
            
            # Check for dangerous paths using resolved path for security
            # Be more specific to avoid false positives on macOS where user paths
            # can resolve to /System/Volumes/Data/...
            dangerous_paths = [
                "/.ssh/authorized_keys",
                "/etc/passwd",
                "/etc/shadow",
                "/System/Library/",
                "/usr/bin/",
                "/usr/sbin/",
                "/bin/",
                "/sbin/"
            ]
            
            # Use resolved path for security checks
            resolved_str = str(resolved_path)
            for dangerous in dangerous_paths:
                # Check for exact path matches or if the path is within these directories
                if dangerous in resolved_str:
                    # Special case: /System/Volumes/Data is macOS firmlink, not system files
                    if dangerous == "/System/Library/" and "/System/Volumes/Data/" in resolved_str:
                        continue
                    return ValidationResult(
                        valid=False,
                        message=f"Path {absolute_path} resolves to dangerous location: {dangerous}",
                        error_code="PATH_DANGEROUS",
                        details={"path": str(absolute_path), "resolved": str(resolved_path), "indicator": dangerous}
                    )
            
            # Check for path traversal attempts
            if ".." in str(dst_path):
                # Ensure the resolved path is still within allowed directories
                if not self._path_matches_patterns(resolved_path, self._whitelist_patterns):
                    return ValidationResult(
                        valid=False,
                        message=f"Path traversal detected: {dst_path} resolves outside whitelist",
                        error_code="PATH_TRAVERSAL",
                        details={"path": str(dst_path), "resolved": str(resolved_path)}
                    )
            
            return ValidationResult(
                valid=True,
                message=f"Path {absolute_path} is valid",
                details={"path": str(absolute_path), "resolved": str(resolved_path)}
            )
            
        except Exception as e:
            return ValidationResult(
                valid=False,
                message=f"Path validation failed: {e}",
                error_code="PATH_VALIDATION_ERROR",
                details={"error": str(e)}
            )
    
    def validate_source_path(self, src_path: Path) -> ValidationResult:
        """
        Validate a source path exists and is readable.
        
        Args:
            src_path: Source path to validate
            
        Returns:
            ValidationResult indicating if source is valid
        """
        try:
            resolved_path = src_path.resolve()
            
            if not resolved_path.exists():
                return ValidationResult(
                    valid=False,
                    message=f"Source path {resolved_path} does not exist",
                    error_code="SOURCE_NOT_FOUND",
                    details={"path": str(resolved_path)}
                )
            
            if not os.access(resolved_path, os.R_OK):
                return ValidationResult(
                    valid=False,
                    message=f"Source path {resolved_path} is not readable",
                    error_code="SOURCE_NOT_READABLE",
                    details={"path": str(resolved_path)}
                )
            
            return ValidationResult(
                valid=True,
                message=f"Source path {resolved_path} is valid",
                details={"path": str(resolved_path)}
            )
            
        except Exception as e:
            return ValidationResult(
                valid=False,
                message=f"Source validation failed: {e}",
                error_code="SOURCE_VALIDATION_ERROR",
                details={"error": str(e)}
            )


class PermissionValidator:
    """
    Validates file system permissions and ownership.
    """
    
    @staticmethod
    def check_write_permission(path: Path) -> ValidationResult:
        """
        Check if we have write permission to a path.
        
        Args:
            path: Path to check
            
        Returns:
            ValidationResult indicating if writable
        """
        try:
            if path.exists():
                # Check if we can write to existing file/directory
                writable = os.access(path, os.W_OK)
            else:
                # Check if we can write to parent directory
                parent = path.parent
                parent.mkdir(parents=True, exist_ok=True)
                writable = os.access(parent, os.W_OK)
            
            if not writable:
                return ValidationResult(
                    valid=False,
                    message=f"No write permission for {path}",
                    error_code="PERMISSION_DENIED",
                    details={"path": str(path)}
                )
            
            return ValidationResult(
                valid=True,
                message=f"Write permission available for {path}",
                details={"path": str(path)}
            )
            
        except Exception as e:
            return ValidationResult(
                valid=False,
                message=f"Permission check failed: {e}",
                error_code="PERMISSION_CHECK_ERROR",
                details={"error": str(e)}
            )
    
    @staticmethod
    def validate_file_mode(path: Path, expected_mode: str) -> ValidationResult:
        """
        Validate file permissions match expected mode.
        
        Args:
            path: Path to check
            expected_mode: Expected mode (e.g., "0600", "0755")
            
        Returns:
            ValidationResult indicating if mode matches
        """
        try:
            if not path.exists():
                return ValidationResult(
                    valid=False,
                    message=f"Cannot check mode of non-existent file {path}",
                    error_code="FILE_NOT_FOUND"
                )
            
            current_mode = oct(path.stat().st_mode)[-3:]
            expected = expected_mode.lstrip('0')
            
            if current_mode != expected:
                return ValidationResult(
                    valid=False,
                    message=f"File mode {current_mode} does not match expected {expected}",
                    error_code="MODE_MISMATCH",
                    details={"path": str(path), "current": current_mode, "expected": expected}
                )
            
            return ValidationResult(
                valid=True,
                message=f"File mode {current_mode} matches expected",
                details={"path": str(path), "mode": current_mode}
            )
            
        except Exception as e:
            return ValidationResult(
                valid=False,
                message=f"Mode validation failed: {e}",
                error_code="MODE_VALIDATION_ERROR",
                details={"error": str(e)}
            )


class ChecksumValidator:
    """
    Validates file integrity using checksums.
    """
    
    @staticmethod
    def calculate_sha256(path: Path) -> Optional[str]:
        """
        Calculate SHA256 checksum of a file.
        
        Args:
            path: File path
            
        Returns:
            SHA256 hex digest or None if calculation fails
        """
        try:
            if not path.exists() or not path.is_file():
                return None
                
            hash_obj = hashlib.sha256()
            with open(path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
            
        except Exception:
            return None
    
    @classmethod
    def verify_checksum(cls, path: Path, expected_checksum: str) -> ValidationResult:
        """
        Verify file checksum matches expected value.
        
        Args:
            path: File to verify
            expected_checksum: Expected SHA256 checksum
            
        Returns:
            ValidationResult indicating if checksum matches
        """
        actual_checksum = cls.calculate_sha256(path)
        
        if actual_checksum is None:
            return ValidationResult(
                valid=False,
                message=f"Could not calculate checksum for {path}",
                error_code="CHECKSUM_CALCULATION_FAILED",
                details={"path": str(path)}
            )
        
        if actual_checksum != expected_checksum:
            return ValidationResult(
                valid=False,
                message=f"Checksum mismatch for {path}",
                error_code="CHECKSUM_MISMATCH",
                details={
                    "path": str(path),
                    "expected": expected_checksum,
                    "actual": actual_checksum
                }
            )
        
        return ValidationResult(
            valid=True,
            message=f"Checksum verified for {path}",
            details={"path": str(path), "checksum": actual_checksum}
        )


class CommandValidator:
    """
    Validates commands against security policies.
    """
    
    def __init__(self, security_config: Optional[SecurityConfig] = None):
        """
        Initialize command validator.
        
        Args:
            security_config: Security configuration with command policies
        """
        self.security_config = security_config or SecurityConfig()
    
    def validate_command(self, command: str) -> ValidationResult:
        """
        Validate a command against the whitelist.
        
        Args:
            command: Command to validate
            
        Returns:
            ValidationResult indicating if command is allowed
        """
        if not self.security_config.enable_command_whitelist:
            return ValidationResult(
                valid=True,
                message="Command whitelisting disabled",
                details={"command": command}
            )
        
        # Check if command is in whitelist
        for allowed_cmd in self.security_config.allowed_commands:
            if command.startswith(allowed_cmd):
                return ValidationResult(
                    valid=True,
                    message=f"Command allowed by whitelist: {allowed_cmd}",
                    details={"command": command, "matched_pattern": allowed_cmd}
                )
        
        return ValidationResult(
            valid=False,
            message=f"Command not in whitelist: {command}",
            error_code="COMMAND_NOT_WHITELISTED",
            details={"command": command, "whitelist": self.security_config.allowed_commands}
        )


class SafetyValidator:
    """
    Comprehensive safety validator combining all validation components.
    """
    
    def __init__(
        self, 
        security_config: Optional[SecurityConfig] = None,
        safety_config: Optional[SafetyConfig] = None
    ):
        """
        Initialize safety validator.
        
        Args:
            security_config: Security configuration
            safety_config: Safety configuration
        """
        self.security_config = security_config or SecurityConfig()
        self.safety_config = safety_config or SafetyConfig()
        
        self.path_validator = PathValidator(self.security_config)
        self.command_validator = CommandValidator(self.security_config)
    
    def validate_operation(
        self, 
        operation_type: str,
        src_path: Optional[Path] = None,
        dst_path: Optional[Path] = None,
        command: Optional[str] = None,
        expected_checksum: Optional[str] = None
    ) -> List[ValidationResult]:
        """
        Validate an operation comprehensively.
        
        Args:
            operation_type: Type of operation (link, copy, run, etc.)
            src_path: Source path if applicable
            dst_path: Destination path if applicable
            command: Command if applicable
            expected_checksum: Expected checksum if applicable
            
        Returns:
            List of validation results
        """
        results = []
        
        # Validate source path if provided
        if src_path:
            results.append(self.path_validator.validate_source_path(src_path))
        
        # Validate destination path if provided
        if dst_path:
            results.append(self.path_validator.validate_destination_path(dst_path))
            results.append(PermissionValidator.check_write_permission(dst_path))
        
        # Validate command if provided
        if command:
            results.append(self.command_validator.validate_command(command))
        
        # Validate checksum if provided and required
        if expected_checksum and src_path and self.safety_config.verify_checksums:
            results.append(ChecksumValidator.verify_checksum(src_path, expected_checksum))
        
        return results
    
    def validate_pre_flight(self, execution_context: ExecutionContext) -> List[ValidationResult]:
        """
        Perform pre-flight validation before operation execution.
        
        Args:
            execution_context: Execution context with configuration
            
        Returns:
            List of validation results
        """
        results = []
        
        if not execution_context.config:
            results.append(ValidationResult(
                valid=False,
                message="No configuration provided in execution context",
                error_code="NO_CONFIG"
            ))
            return results
        
        # Validate configuration structure
        try:
            # Check if we have required safety configuration
            if not execution_context.config.safety:
                results.append(ValidationResult(
                    valid=False,
                    message="Safety configuration missing",
                    error_code="NO_SAFETY_CONFIG"
                ))
            
            # Validate all steps in configuration
            for i, step in enumerate(execution_context.config.step):
                # Properly expand paths using ExecutionContext
                src_path = execution_context.expand_path(step.src) if step.src else None
                dst_path = execution_context.expand_path(step.dst) if step.dst else None
                
                step_results = self.validate_operation(
                    operation_type=step.op.value,
                    src_path=src_path,
                    dst_path=dst_path,
                    command=step.command,
                    expected_checksum=step.checksum
                )
                
                # Add step context to results
                for result in step_results:
                    if result.details is None:
                        result.details = {}
                    result.details["step_index"] = i
                    result.details["operation_type"] = step.op.value
                
                results.extend(step_results)
            
        except Exception as e:
            results.append(ValidationResult(
                valid=False,
                message=f"Pre-flight validation failed: {e}",
                error_code="PREFLIGHT_ERROR",
                details={"error": str(e)}
            ))
        
        return results


class ValidationError(Exception):
    """Exception raised for validation failures."""
    
    def __init__(self, message: str, validation_results: List[ValidationResult]):
        super().__init__(message)
        self.validation_results = validation_results