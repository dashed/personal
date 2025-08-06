"""
Configuration loader and validator for dotfiles.toml using Pydantic.

This module handles parsing and validation of the TOML configuration file
using Pydantic models for type safety and validation.
"""

import logging
import tomllib
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from dotfiles_sync.models import (
    DotfilesConfig,
    Platform,
    StepConfig,
)

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


class ConfigLoader:
    """Loads and validates dotfiles.toml configuration using Pydantic."""
    
    def __init__(self, config_path: Path):
        """Initialize configuration loader.
        
        Args:
            config_path: Path to the dotfiles.toml file
        """
        self.config_path = Path(config_path) if isinstance(config_path, str) else config_path
        self._config: Optional[DotfilesConfig] = None
        self._raw_data: Optional[Dict[str, Any]] = None
    
    def load(self) -> DotfilesConfig:
        """Load and validate the TOML configuration file.
        
        Returns:
            Validated DotfilesConfig model
            
        Raises:
            ConfigValidationError: If file cannot be loaded or validated
        """
        try:
            # Load TOML file
            with open(self.config_path, "rb") as f:
                self._raw_data = tomllib.load(f)
            
            # Parse and validate with Pydantic
            self._config = DotfilesConfig.from_toml(self._raw_data)
            
            logger.debug(f"Loaded configuration from {self.config_path}")
            logger.info(f"Configuration loaded: {self._config.package.name} v{self._config.package.version}")
            
            return self._config
            
        except FileNotFoundError:
            raise ConfigValidationError(f"Configuration file not found: {self.config_path}")
        except tomllib.TOMLDecodeError as e:
            raise ConfigValidationError(f"Invalid TOML syntax: {e}")
        except ValidationError as e:
            # Format Pydantic validation errors nicely
            errors = []
            for err in e.errors():
                loc = " -> ".join(str(l) for l in err["loc"])
                msg = err["msg"]
                errors.append(f"  {loc}: {msg}")
            
            error_msg = "Configuration validation failed:\n" + "\n".join(errors)
            raise ConfigValidationError(error_msg)
        except Exception as e:
            raise ConfigValidationError(f"Failed to load configuration: {e}")
    
    def validate(self, config: Optional[DotfilesConfig] = None) -> None:
        """Validate the configuration (already validated by Pydantic on load).
        
        Args:
            config: Optional configuration to validate (uses loaded config if None)
            
        Raises:
            ConfigValidationError: If validation fails
        """
        if config is None:
            config = self._config
        
        if config is None:
            raise ConfigValidationError("No configuration loaded")
        
        # Pydantic already validates on instantiation, but we can add custom checks here
        self._validate_custom_rules(config)
        
        logger.info("Configuration validation successful")
    
    def _validate_custom_rules(self, config: DotfilesConfig) -> None:
        """Apply custom validation rules beyond Pydantic's built-in validation.
        
        Args:
            config: Configuration to validate
            
        Raises:
            ConfigValidationError: If custom validation fails
        """
        # Check for duplicate destinations in steps
        destinations = []
        for step in config.step:
            if step.dst:
                if step.dst in destinations:
                    logger.warning(f"Duplicate destination found: {step.dst}")
                destinations.append(step.dst)
        
        # Warn if no steps defined
        if not config.step:
            logger.warning("No steps defined in configuration")
        
        # Check safety settings
        if not config.safety.dry_run_default:
            logger.warning("Safety: dry_run_default is disabled - operations will apply by default!")
        
        if not config.safety.backup_before_modify:
            logger.warning("Safety: backup_before_modify is disabled - no automatic backups!")
    
    def filter_steps_by_variant(
        self, 
        variant: str,
        config: Optional[DotfilesConfig] = None
    ) -> List[StepConfig]:
        """Filter steps by the specified variant.
        
        Args:
            variant: Variant name to filter by
            config: Optional configuration (uses loaded config if None)
            
        Returns:
            List of steps applicable to the variant
        """
        if config is None:
            config = self._config
        
        if config is None:
            raise ConfigValidationError("No configuration loaded")
        
        filtered_steps = config.filter_steps_by_variant(variant)
        logger.debug(f"Filtered {len(filtered_steps)} steps for variant '{variant}'")
        
        return filtered_steps
    
    def filter_steps_by_platform(
        self,
        platform: Platform,
        config: Optional[DotfilesConfig] = None
    ) -> List[StepConfig]:
        """Filter steps by the specified platform.
        
        Args:
            platform: Platform to filter by
            config: Optional configuration (uses loaded config if None)
            
        Returns:
            List of steps applicable to the platform
        """
        if config is None:
            config = self._config
        
        if config is None:
            raise ConfigValidationError("No configuration loaded")
        
        filtered_steps = config.filter_steps_by_platform(platform)
        logger.debug(f"Filtered {len(filtered_steps)} steps for platform '{platform.value}'")
        
        return filtered_steps
    
    def get_safety_settings(self, config: Optional[DotfilesConfig] = None) -> Dict[str, Any]:
        """Get safety settings as a dictionary.
        
        Args:
            config: Optional configuration (uses loaded config if None)
            
        Returns:
            Safety settings dictionary
        """
        if config is None:
            config = self._config
        
        if config is None:
            raise ConfigValidationError("No configuration loaded")
        
        return config.safety.model_dump()
    
    def get_raw_data(self) -> Optional[Dict[str, Any]]:
        """Get the raw TOML data before Pydantic parsing.
        
        Returns:
            Raw configuration dictionary or None
        """
        return self._raw_data
    
    def reload(self) -> DotfilesConfig:
        """Reload the configuration from disk.
        
        Returns:
            Newly loaded configuration
            
        Raises:
            ConfigValidationError: If reload fails
        """
        self._config = None
        self._raw_data = None
        return self.load()