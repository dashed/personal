"""
Pydantic models for the Dotfiles Management System.

This module defines all data models using Pydantic for validation,
serialization, and type safety.
"""

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings


# ============================================================================
# ENUMS
# ============================================================================

class OperationType(str, Enum):
    """Valid operation types for dotfile steps."""
    LINK = "link"
    COPY = "copy"
    SYNCDIR = "syncdir"
    APPEND = "append"
    PREPEND = "prepend"
    BREW_INSTALL = "brew_install"
    APT_INSTALL = "apt_install"
    DNF_INSTALL = "dnf_install"
    TEMPLATE = "template"
    SECRET_REF = "secret_ref"
    RUN = "run"
    RUN_ONCE = "run_once"


class Platform(str, Enum):
    """Supported platforms."""
    MACOS = "macos"
    LINUX = "linux"
    WINDOWS = "windows"
    ALL = "all"


class SecretProvider(str, Enum):
    """Supported secret providers."""
    ENVIRONMENT = "environment"
    KEYCHAIN = "keychain"
    ONEPASSWORD = "onepassword"
    LASTPASS = "lastpass"


class TransactionStatus(str, Enum):
    """Transaction status values."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class OperationStatus(str, Enum):
    """Operation status values."""
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"


# ============================================================================
# CONFIGURATION MODELS
# ============================================================================

class PackageConfig(BaseModel):
    """Package section of the configuration."""
    model_config = ConfigDict(frozen=True)
    
    name: str = Field(..., min_length=1, description="Package name")
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+", description="Semantic version")
    author: Optional[str] = Field(None, description="Author name and email")
    description: Optional[str] = Field(None, description="Package description")
    
    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate semantic version format."""
        parts = v.split(".")
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            raise ValueError(f"Version must be in format X.Y.Z, got: {v}")
        return v


class SafetyConfig(BaseModel):
    """Safety configuration section."""
    model_config = ConfigDict(frozen=True)
    
    dry_run_default: bool = Field(True, description="Default to dry-run mode")
    backup_before_modify: bool = Field(True, description="Create backups before modifications")
    backup_retention_days: int = Field(30, ge=0, description="Days to retain backups")
    verify_checksums: bool = Field(True, description="Verify file checksums")
    fail_on_error: bool = Field(True, description="Stop on first error")
    max_operations: int = Field(1000, ge=1, description="Maximum operations per transaction")
    require_confirmation: bool = Field(True, description="Require confirmation for destructive ops")
    
    @field_validator("backup_retention_days")
    @classmethod
    def validate_retention(cls, v: int) -> int:
        """Validate retention days is reasonable."""
        if v > 365:
            raise ValueError(f"Retention days too high: {v} (max 365)")
        return v


class SecurityConfig(BaseModel):
    """Security configuration section."""
    model_config = ConfigDict(frozen=True)
    
    whitelist_paths: List[str] = Field(
        default_factory=lambda: ["~/.config", "~/.local"],
        description="Paths allowed for modification"
    )
    blacklist_paths: List[str] = Field(
        default_factory=lambda: ["/etc", "/usr", "/System"],
        description="Paths that must never be modified"
    )
    secret_provider: SecretProvider = Field(
        SecretProvider.ENVIRONMENT,
        description="Secret management provider"
    )
    enable_command_whitelist: bool = Field(False, description="Enable command whitelisting")
    allowed_commands: List[str] = Field(
        default_factory=list,
        description="Whitelisted commands for run operations"
    )
    
    @model_validator(mode="after")
    def validate_paths(self) -> "SecurityConfig":
        """Ensure whitelist and blacklist don't overlap."""
        whitelist_set = set(self.whitelist_paths)
        blacklist_set = set(self.blacklist_paths)
        overlap = whitelist_set & blacklist_set
        if overlap:
            raise ValueError(f"Paths in both whitelist and blacklist: {overlap}")
        return self


class StepConfig(BaseModel):
    """Individual step configuration."""
    model_config = ConfigDict(extra="allow")  # Allow extra fields for operation-specific config
    
    op: OperationType = Field(..., description="Operation type")
    src: Optional[str] = Field(None, description="Source path")
    dst: Optional[str] = Field(None, description="Destination path")
    variants: List[str] = Field(default_factory=lambda: ["all"], description="Applicable variants")
    platforms: Optional[List[Platform]] = Field(None, description="Target platforms")
    description: Optional[str] = Field(None, description="Step description")
    
    # Operation-specific fields
    packages: Optional[List[str]] = Field(None, description="Packages to install")
    text: Optional[str] = Field(None, description="Text to append/prepend")
    command: Optional[str] = Field(None, description="Command to run")
    checksum: Optional[str] = Field(None, description="Checksum for run_once")
    vars: Optional[Dict[str, Any]] = Field(None, description="Template variables")
    key: Optional[str] = Field(None, description="Secret key")
    mode: Optional[str] = Field(None, description="File permissions")
    exclude: Optional[List[str]] = Field(None, description="Patterns to exclude")
    sudo: bool = Field(False, description="Requires sudo")
    marker: Optional[str] = Field(None, description="Marker for append/prepend")
    
    @model_validator(mode="after")
    def validate_required_fields(self) -> "StepConfig":
        """Validate operation-specific required fields."""
        op = self.op
        
        # Define required fields for each operation
        required_fields = {
            OperationType.LINK: ["src", "dst"],
            OperationType.COPY: ["src", "dst"],
            OperationType.SYNCDIR: ["src", "dst"],
            OperationType.APPEND: ["text", "dst"],
            OperationType.PREPEND: ["text", "dst"],
            OperationType.BREW_INSTALL: ["packages"],
            OperationType.APT_INSTALL: ["packages"],
            OperationType.DNF_INSTALL: ["packages"],
            OperationType.TEMPLATE: ["src", "dst", "vars"],
            OperationType.SECRET_REF: ["key", "dst"],
            OperationType.RUN: ["command"],
            OperationType.RUN_ONCE: ["command"],
        }
        
        if op in required_fields:
            for field in required_fields[op]:
                if getattr(self, field) is None:
                    raise ValueError(f"Operation {op.value} requires field: {field}")
        
        return self


class DotfilesConfig(BaseModel):
    """Complete dotfiles configuration."""
    model_config = ConfigDict(frozen=True)
    
    package: PackageConfig
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    security: Optional[SecurityConfig] = None
    step: List[StepConfig] = Field(default_factory=list, description="Configuration steps")
    
    @classmethod
    def from_toml(cls, data: Dict[str, Any]) -> "DotfilesConfig":
        """Create configuration from TOML data."""
        return cls(**data)
    
    def filter_steps_by_variant(self, variant: str) -> List[StepConfig]:
        """Filter steps applicable to a specific variant."""
        return [
            step for step in self.step
            if variant in step.variants or "all" in step.variants
        ]
    
    def filter_steps_by_platform(self, platform: Platform) -> List[StepConfig]:
        """Filter steps applicable to a specific platform."""
        return [
            step for step in self.step
            if step.platforms is None or platform in step.platforms or Platform.ALL in step.platforms
        ]


# ============================================================================
# CONTEXT MODELS
# ============================================================================

class SystemInfo(BaseModel):
    """System information model."""
    model_config = ConfigDict(frozen=True)
    
    hostname: str
    username: str
    platform: Platform
    arch: str
    python_version: str
    
    @classmethod
    def from_current_system(cls) -> "SystemInfo":
        """Create SystemInfo from current system."""
        import platform as platform_lib
        import getpass
        
        system = platform_lib.system().lower()
        if system == "darwin":
            platform_val = Platform.MACOS
        elif system == "windows":
            platform_val = Platform.WINDOWS
        else:
            platform_val = Platform.LINUX
        
        arch = platform_lib.machine()
        if arch in ("x86_64", "AMD64"):
            arch = "x86_64"
        elif arch in ("aarch64", "arm64"):
            arch = "arm64"
        
        return cls(
            hostname=platform_lib.node(),
            username=getpass.getuser(),
            platform=platform_val,
            arch=arch,
            python_version=platform_lib.python_version()
        )
    
    def matches_platform(self, platforms: List[Platform]) -> bool:
        """Check if current platform matches any in the list."""
        return self.platform in platforms or Platform.ALL in platforms


class ExecutionContext(BaseModel):
    """Execution context for operations."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    config_path: Path
    variant: str = "default"
    dry_run: bool = True
    force: bool = False
    system_info: SystemInfo = Field(default_factory=SystemInfo.from_current_system)
    config: Optional[DotfilesConfig] = None
    transaction_id: Optional[str] = None
    
    @field_validator("config_path", mode="before")
    @classmethod
    def convert_path(cls, v: Any) -> Path:
        """Convert string to Path."""
        if isinstance(v, str):
            return Path(v).expanduser().resolve()
        elif isinstance(v, Path):
            return v.expanduser().resolve()
        return v
    
    def expand_path(self, path: str) -> Path:
        """Expand a path with home directory and make absolute."""
        expanded = Path(path).expanduser()
        if not expanded.is_absolute():
            # Make relative to config file directory
            expanded = self.config_path.parent / expanded
        return expanded.resolve()


# ============================================================================
# DATABASE MODELS
# ============================================================================

class TransactionContext(BaseModel):
    """Database transaction context."""
    model_config = ConfigDict(frozen=True)
    
    id: str = Field(..., min_length=1)
    variant: str
    user: str
    hostname: str
    dry_run: bool = False
    metadata: Optional[Dict[str, Any]] = None
    status: TransactionStatus = TransactionStatus.PENDING


class OperationResult(BaseModel):
    """Result of a single operation."""
    model_config = ConfigDict(frozen=True)
    
    success: bool
    operation_id: int
    message: str
    rollback_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ============================================================================
# SETTINGS (using pydantic-settings)
# ============================================================================

class AppSettings(BaseSettings):
    """Application settings from environment variables."""
    model_config = ConfigDict(
        env_prefix="DOTFILES_",
        env_nested_delimiter="__",
        frozen=True
    )
    
    # Database settings
    db_path: Optional[Path] = None
    
    # Logging settings
    log_level: str = "INFO"
    log_format: str = "rich"  # "rich" or "plain"
    
    # CLI settings
    default_config: Path = Path("dotfiles.toml")
    default_variant: str = "default"
    
    # Safety overrides (for CI/CD)
    force_apply: bool = False
    skip_confirmation: bool = False
    
    # Development settings
    debug: bool = False
    profile: bool = False
    
    @field_validator("db_path", "default_config", mode="before")
    @classmethod
    def expand_paths(cls, v: Any) -> Optional[Path]:
        """Expand and resolve paths."""
        if v is None:
            return None
        if isinstance(v, str):
            return Path(v).expanduser().resolve()
        return v