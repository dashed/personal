"""
Impact analysis for the Dotfiles Management System.

This module provides comprehensive impact analysis for operations before execution,
including risk assessment, dependency analysis, and conflict detection.

Phase 4: Safety Features & Confirmation implementation.
"""

import hashlib
import os
import re
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from pydantic import BaseModel, Field

from dotfiles_sync.models import StepConfig, OperationType, ExecutionContext
from dotfiles_sync.context import OperationContext


class ImpactLevel(str, Enum):
    """Impact severity levels for operations."""
    
    LOW = "low"           # Safe operations (copy, read-only)
    MEDIUM = "medium"     # Reversible operations (link, template)
    HIGH = "high"         # Destructive operations (overwrite, delete)
    CRITICAL = "critical" # System-level operations (commands, secrets)


class ImpactType(str, Enum):
    """Types of impacts an operation can have."""
    
    FILE_CREATE = "file_create"
    FILE_MODIFY = "file_modify" 
    FILE_DELETE = "file_delete"
    DIRECTORY_CREATE = "directory_create"
    PERMISSION_CHANGE = "permission_change"
    COMMAND_EXECUTION = "command_execution"
    DEPENDENCY_BREAK = "dependency_break"
    CONFLICT_DETECTED = "conflict_detected"


class ImpactDetail(BaseModel):
    """Detailed information about a specific impact."""
    
    type: ImpactType
    level: ImpactLevel
    path: Optional[str] = None
    description: str
    reversible: bool = Field(True, description="Whether this impact can be undone")
    dependencies: List[str] = Field(default_factory=list, description="Files that depend on this change")
    conflicts: List[str] = Field(default_factory=list, description="Conflicting operations or files")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional impact metadata")


class ImpactReport(BaseModel):
    """Comprehensive impact analysis report for an operation."""
    
    operation_type: str
    operation_id: int = 0
    src_path: Optional[str] = None
    dst_path: Optional[str] = None
    overall_level: ImpactLevel
    impacts: List[ImpactDetail] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    
    def add_impact(self, impact: ImpactDetail) -> None:
        """Add an impact detail to the report."""
        self.impacts.append(impact)
        self._update_overall_level(impact.level)
    
    def add_warning(self, message: str) -> None:
        """Add a warning message to the report."""
        self.warnings.append(message)
    
    def add_error(self, message: str) -> None:
        """Add an error message to the report."""
        self.errors.append(message)
    
    def add_recommendation(self, message: str) -> None:
        """Add a recommendation to the report."""
        self.recommendations.append(message)
    
    def _update_overall_level(self, new_level: ImpactLevel) -> None:
        """Update overall impact level based on new impact."""
        levels = {
            ImpactLevel.LOW: 1,
            ImpactLevel.MEDIUM: 2, 
            ImpactLevel.HIGH: 3,
            ImpactLevel.CRITICAL: 4
        }
        
        current_score = levels.get(self.overall_level, 0)
        new_score = levels.get(new_level, 0)
        
        if new_score > current_score:
            self.overall_level = new_level
    
    @property
    def is_destructive(self) -> bool:
        """Check if the operation has destructive impacts."""
        return self.overall_level in [ImpactLevel.HIGH, ImpactLevel.CRITICAL]
    
    @property
    def has_conflicts(self) -> bool:
        """Check if there are any conflicts detected."""
        return any(impact.type == ImpactType.CONFLICT_DETECTED for impact in self.impacts)
    
    @property
    def requires_confirmation(self) -> bool:
        """Check if this operation should require user confirmation."""
        return self.is_destructive or self.has_conflicts or len(self.errors) > 0


class DependencyAnalyzer:
    """Analyzes file dependencies and references."""
    
    def __init__(self):
        """Initialize the dependency analyzer."""
        self._reference_patterns = {
            # Shell scripts and config files
            'source': re.compile(r'(?:source|\.)\s+["\']?([^"\'\s]+)["\']?'),
            'include': re.compile(r'(?:include|require)\s+["\']?([^"\'\s]+)["\']?'),
            # Import statements
            'import': re.compile(r'import\s+["\']?([^"\'\s]+)["\']?'),
            # Path references
            'path': re.compile(r'["\']([~/][^"\']+)["\']'),
        }
    
    def find_dependencies(self, file_path: Path) -> List[str]:
        """
        Find files that the given file depends on.
        
        Args:
            file_path: Path to analyze for dependencies
            
        Returns:
            List of file paths this file depends on
        """
        dependencies = []
        
        if not file_path.exists() or not file_path.is_file():
            return dependencies
        
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            
            for pattern_name, pattern in self._reference_patterns.items():
                matches = pattern.findall(content)
                for match in matches:
                    # Resolve relative paths
                    dep_path = self._resolve_path(match, file_path.parent)
                    if dep_path and dep_path.exists():
                        dependencies.append(str(dep_path))
        
        except Exception:
            # Ignore errors reading files
            pass
        
        return dependencies
    
    def find_dependents(self, file_path: Path, search_paths: List[Path] = None) -> List[str]:
        """
        Find files that depend on the given file.
        
        Args:
            file_path: Path to find dependents for
            search_paths: Paths to search for dependents
            
        Returns:
            List of file paths that depend on this file
        """
        if search_paths is None:
            # Default search paths
            search_paths = [
                Path.home() / '.config',
                Path.home() / '.local',
                Path.home(),
            ]
        
        dependents = []
        target_str = str(file_path)
        
        for search_path in search_paths:
            if not search_path.exists():
                continue
                
            try:
                # Search for files that reference this path
                for candidate in search_path.rglob('*'):
                    if candidate.is_file() and candidate != file_path:
                        deps = self.find_dependencies(candidate)
                        if target_str in deps:
                            dependents.append(str(candidate))
            except Exception:
                # Ignore permission errors, etc.
                continue
        
        return dependents
    
    def _resolve_path(self, path_str: str, base_dir: Path) -> Optional[Path]:
        """Resolve a path string relative to a base directory."""
        try:
            if path_str.startswith('~/'):
                return Path(path_str).expanduser()
            elif path_str.startswith('/'):
                return Path(path_str)
            else:
                return base_dir / path_str
        except Exception:
            return None


class ImpactAnalyzer:
    """
    Analyzes the impact of operations before execution.
    
    Provides comprehensive impact analysis including risk assessment,
    dependency analysis, conflict detection, and safety recommendations.
    """
    
    def __init__(self, dependency_analyzer: Optional[DependencyAnalyzer] = None):
        """
        Initialize the impact analyzer.
        
        Args:
            dependency_analyzer: Optional dependency analyzer instance
        """
        self.dependency_analyzer = dependency_analyzer or DependencyAnalyzer()
    
    def analyze_operation(
        self, 
        step: StepConfig, 
        context: OperationContext,
        operation_id: int = 0
    ) -> ImpactReport:
        """
        Analyze the impact of a single operation.
        
        Args:
            step: Step configuration to analyze
            context: Operation context
            operation_id: Unique identifier for this operation
            
        Returns:
            Comprehensive impact analysis report
        """
        report = ImpactReport(
            operation_type=step.op.value,
            operation_id=operation_id,
            src_path=step.src,
            dst_path=step.dst,
            overall_level=ImpactLevel.LOW
        )
        
        # Analyze based on operation type
        if step.op == OperationType.LINK:
            self._analyze_link_operation(step, context, report)
        elif step.op == OperationType.COPY:
            self._analyze_copy_operation(step, context, report)
        elif step.op == OperationType.SYNCDIR:
            self._analyze_syncdir_operation(step, context, report)
        elif step.op == OperationType.TEMPLATE:
            self._analyze_template_operation(step, context, report)
        elif step.op == OperationType.SECRET_REF:
            self._analyze_secret_operation(step, context, report)
        elif step.op in [OperationType.APPEND, OperationType.PREPEND]:
            self._analyze_text_operation(step, context, report)
        elif step.op in [OperationType.RUN, OperationType.RUN_ONCE]:
            self._analyze_command_operation(step, context, report)
        elif step.op in [OperationType.BREW_INSTALL, OperationType.APT_INSTALL]:
            self._analyze_package_operation(step, context, report)
        
        # Add general safety recommendations
        self._add_safety_recommendations(report)
        
        return report
    
    def _analyze_link_operation(
        self, 
        step: StepConfig, 
        context: OperationContext, 
        report: ImpactReport
    ) -> None:
        """Analyze symlink operation impact."""
        src_path = context.get_src_path() if hasattr(context, 'get_src_path') else None
        dst_path = context.get_dst_path() if hasattr(context, 'get_dst_path') else None
        
        if not src_path or not dst_path:
            report.add_error("Cannot analyze link operation: missing source or destination path")
            return
        
        # Check if destination exists
        if dst_path.exists():
            if dst_path.is_symlink():
                current_target = dst_path.readlink()
                if current_target == src_path:
                    # No change needed
                    report.add_impact(ImpactDetail(
                        type=ImpactType.FILE_MODIFY,
                        level=ImpactLevel.LOW,
                        path=str(dst_path),
                        description=f"Symlink already points to {src_path}",
                        reversible=True
                    ))
                else:
                    # Will change symlink target
                    report.add_impact(ImpactDetail(
                        type=ImpactType.FILE_MODIFY,
                        level=ImpactLevel.MEDIUM,
                        path=str(dst_path),
                        description=f"Will change symlink from {current_target} to {src_path}",
                        reversible=True
                    ))
            else:
                # Will replace regular file with symlink
                report.add_impact(ImpactDetail(
                    type=ImpactType.FILE_DELETE,
                    level=ImpactLevel.HIGH,
                    path=str(dst_path),
                    description=f"Will replace existing file with symlink to {src_path}",
                    reversible=True  # Reversible via backup
                ))
                report.add_warning(f"Existing file at {dst_path} will be replaced")
        else:
            # Creating new symlink
            report.add_impact(ImpactDetail(
                type=ImpactType.FILE_CREATE,
                level=ImpactLevel.LOW,
                path=str(dst_path),
                description=f"Will create symlink to {src_path}",
                reversible=True
            ))
        
        # Check source file exists
        if not src_path.exists():
            report.add_error(f"Source file does not exist: {src_path}")
        
        # Analyze dependencies
        if dst_path.exists():
            dependents = self.dependency_analyzer.find_dependents(dst_path)
            if dependents:
                report.add_warning(f"File is referenced by {len(dependents)} other files")
                report.add_impact(ImpactDetail(
                    type=ImpactType.DEPENDENCY_BREAK,
                    level=ImpactLevel.MEDIUM,
                    path=str(dst_path),
                    description="May affect dependent files",
                    reversible=True,
                    dependencies=dependents
                ))
    
    def _analyze_copy_operation(
        self, 
        step: StepConfig, 
        context: OperationContext, 
        report: ImpactReport
    ) -> None:
        """Analyze file copy operation impact."""
        src_path = context.get_src_path() if hasattr(context, 'get_src_path') else None
        dst_path = context.get_dst_path() if hasattr(context, 'get_dst_path') else None
        
        if not src_path or not dst_path:
            report.add_error("Cannot analyze copy operation: missing source or destination path")
            return
        
        # Check source exists
        if not src_path.exists():
            report.add_error(f"Source file does not exist: {src_path}")
            return
        
        # Check destination impact
        if dst_path.exists():
            # Check if files are different
            try:
                src_content = src_path.read_bytes()
                dst_content = dst_path.read_bytes()
                
                if src_content == dst_content:
                    report.add_impact(ImpactDetail(
                        type=ImpactType.FILE_MODIFY,
                        level=ImpactLevel.LOW,
                        path=str(dst_path),
                        description="File content is already up to date",
                        reversible=True
                    ))
                else:
                    report.add_impact(ImpactDetail(
                        type=ImpactType.FILE_MODIFY,
                        level=ImpactLevel.MEDIUM,
                        path=str(dst_path),
                        description=f"Will overwrite existing file with content from {src_path}",
                        reversible=True
                    ))
                    
                    # Check for local modifications
                    if self._has_local_modifications(dst_path):
                        report.add_warning("Destination file appears to have local modifications")
                        report.add_impact(ImpactDetail(
                            type=ImpactType.CONFLICT_DETECTED,
                            level=ImpactLevel.HIGH,
                            path=str(dst_path),
                            description="Local modifications will be lost",
                            reversible=True,
                            conflicts=["local_modifications"]
                        ))
            
            except Exception as e:
                report.add_warning(f"Could not compare file contents: {e}")
        else:
            # Creating new file
            report.add_impact(ImpactDetail(
                type=ImpactType.FILE_CREATE,
                level=ImpactLevel.LOW,
                path=str(dst_path),
                description=f"Will create new file from {src_path}",
                reversible=True
            ))
            
            # Check if parent directory needs creation
            if not dst_path.parent.exists():
                report.add_impact(ImpactDetail(
                    type=ImpactType.DIRECTORY_CREATE,
                    level=ImpactLevel.LOW,
                    path=str(dst_path.parent),
                    description="Will create parent directory",
                    reversible=True
                ))
    
    def _analyze_template_operation(
        self, 
        step: StepConfig, 
        context: OperationContext, 
        report: ImpactReport
    ) -> None:
        """Analyze template processing operation impact."""
        if not step.vars:
            report.add_error("Template operation requires variables")
            return
        
        dst_path = context.get_dst_path() if hasattr(context, 'get_dst_path') else None
        if not dst_path:
            report.add_error("Cannot analyze template operation: missing destination path")
            return
        
        if dst_path.exists():
            report.add_impact(ImpactDetail(
                type=ImpactType.FILE_MODIFY,
                level=ImpactLevel.MEDIUM,
                path=str(dst_path),
                description="Will render template and replace existing file",
                reversible=True
            ))
            
            # Template operations can have unpredictable content changes
            report.add_warning("Template output may vary based on variables and environment")
        else:
            report.add_impact(ImpactDetail(
                type=ImpactType.FILE_CREATE,
                level=ImpactLevel.MEDIUM,
                path=str(dst_path),
                description="Will create file from template",
                reversible=True
            ))
    
    def _analyze_secret_operation(
        self, 
        step: StepConfig, 
        context: OperationContext, 
        report: ImpactReport
    ) -> None:
        """Analyze secret management operation impact."""
        dst_path = context.get_dst_path() if hasattr(context, 'get_dst_path') else None
        if not dst_path:
            report.add_error("Cannot analyze secret operation: missing destination path")
            return
        
        # Secret operations are always critical due to security implications
        report.add_impact(ImpactDetail(
            type=ImpactType.FILE_CREATE if not dst_path.exists() else ImpactType.FILE_MODIFY,
            level=ImpactLevel.CRITICAL,
            path=str(dst_path),
            description="Will write secret data to file with secure permissions",
            reversible=True
        ))
        
        # Additional security considerations
        report.add_warning("Secret will be written to disk - ensure secure storage")
        report.add_recommendation("Verify file permissions are restrictive (600)")
        
        if dst_path.exists():
            report.add_warning("Existing file will be overwritten with secret data")
    
    def _analyze_command_operation(
        self, 
        step: StepConfig, 
        context: OperationContext, 
        report: ImpactReport
    ) -> None:
        """Analyze command execution operation impact."""
        if not step.command:
            report.add_error("Command operation requires a command")
            return
        
        # Command operations are inherently risky
        report.add_impact(ImpactDetail(
            type=ImpactType.COMMAND_EXECUTION,
            level=ImpactLevel.CRITICAL,
            description=f"Will execute command: {step.command}",
            reversible=False  # Commands cannot be automatically undone
        ))
        
        # Analyze command safety
        dangerous_patterns = [
            'rm ', 'delete', 'format', 'mkfs',
            'sudo rm', 'sudo del', '>>', '> ',
            'curl.*|.*sh', 'wget.*|.*sh'
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, step.command, re.IGNORECASE):
                report.add_error(f"Command contains potentially dangerous pattern: {pattern}")
                break
        
        report.add_warning("Command execution cannot be automatically reversed")
        report.add_recommendation("Review command carefully before execution")
    
    def _analyze_package_operation(
        self, 
        step: StepConfig, 
        context: OperationContext, 
        report: ImpactReport
    ) -> None:
        """Analyze package manager operation impact."""
        if not step.packages:
            report.add_error("Package operation requires package list")
            return
        
        # Package operations modify system state
        report.add_impact(ImpactDetail(
            type=ImpactType.COMMAND_EXECUTION,
            level=ImpactLevel.HIGH,
            description=f"Will install packages: {', '.join(step.packages)}",
            reversible=True  # Can be uninstalled
        ))
        
        # System-level changes
        report.add_warning("Package installation modifies system state")
        report.add_recommendation("Packages can be uninstalled if needed")
        
        if step.sudo:
            report.add_impact(ImpactDetail(
                type=ImpactType.PERMISSION_CHANGE,
                level=ImpactLevel.HIGH,
                description="Operation requires sudo privileges",
                reversible=True
            ))
    
    def _analyze_text_operation(
        self, 
        step: StepConfig, 
        context: OperationContext, 
        report: ImpactReport
    ) -> None:
        """Analyze text append/prepend operation impact."""
        dst_path = context.get_dst_path() if hasattr(context, 'get_dst_path') else None
        if not dst_path:
            report.add_error("Cannot analyze text operation: missing destination path")
            return
        
        if dst_path.exists():
            # Check for marker to avoid duplicates
            if step.marker:
                try:
                    content = dst_path.read_text(encoding='utf-8')
                    if step.marker in content:
                        report.add_impact(ImpactDetail(
                            type=ImpactType.FILE_MODIFY,
                            level=ImpactLevel.LOW,
                            path=str(dst_path),
                            description=f"Text with marker '{step.marker}' already present",
                            reversible=True
                        ))
                        return
                except Exception:
                    pass
            
            report.add_impact(ImpactDetail(
                type=ImpactType.FILE_MODIFY,
                level=ImpactLevel.MEDIUM,
                path=str(dst_path),
                description=f"Will {step.op.value} text to existing file",
                reversible=True
            ))
        else:
            report.add_impact(ImpactDetail(
                type=ImpactType.FILE_CREATE,
                level=ImpactLevel.LOW,
                path=str(dst_path),
                description=f"Will create file and {step.op.value} text",
                reversible=True
            ))
    
    def _analyze_syncdir_operation(
        self, 
        step: StepConfig, 
        context: OperationContext, 
        report: ImpactReport
    ) -> None:
        """Analyze directory sync operation impact."""
        src_path = context.get_src_path() if hasattr(context, 'get_src_path') else None
        dst_path = context.get_dst_path() if hasattr(context, 'get_dst_path') else None
        
        if not src_path or not dst_path:
            report.add_error("Cannot analyze syncdir operation: missing source or destination path")
            return
        
        if not src_path.exists():
            report.add_error(f"Source directory does not exist: {src_path}")
            return
        
        # Directory sync can affect many files
        report.add_impact(ImpactDetail(
            type=ImpactType.DIRECTORY_CREATE if not dst_path.exists() else ImpactType.FILE_MODIFY,
            level=ImpactLevel.HIGH,
            path=str(dst_path),
            description="Will synchronize entire directory tree",
            reversible=True
        ))
        
        # Count files that would be affected
        try:
            file_count = sum(1 for _ in src_path.rglob('*') if _.is_file())
            if file_count > 100:
                report.add_warning(f"Operation will affect {file_count} files")
                report.add_recommendation("Consider selective synchronization for large directories")
        except Exception:
            pass
        
        report.add_warning("Directory sync may create, modify, or delete multiple files")
    
    def _has_local_modifications(self, file_path: Path) -> bool:
        """Check if a file appears to have local modifications."""
        # This is a heuristic - in a real implementation, you might:
        # 1. Compare with backup versions
        # 2. Check against known checksums
        # 3. Compare modification times
        # For now, we'll use a simple heuristic
        try:
            stat = file_path.stat()
            # If file was modified in the last 24 hours, consider it potentially modified
            import time
            return (time.time() - stat.st_mtime) < 86400
        except Exception:
            return False
    
    def _add_safety_recommendations(self, report: ImpactReport) -> None:
        """Add general safety recommendations based on impact analysis."""
        if report.is_destructive:
            report.add_recommendation("Create backup before proceeding")
            report.add_recommendation("Test in dry-run mode first")
        
        if report.has_conflicts:
            report.add_recommendation("Resolve conflicts before proceeding")
        
        if any(impact.level == ImpactLevel.CRITICAL for impact in report.impacts):
            report.add_recommendation("Review operation carefully - critical system impact")
        
        if len(report.impacts) > 10:
            report.add_recommendation("Consider breaking operation into smaller steps")