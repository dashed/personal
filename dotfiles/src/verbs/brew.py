"""
Homebrew package management verb implementation.

This module provides Homebrew package installation functionality with
version pinning, cask support, and idempotent operations.
"""

import subprocess
import json
import shutil
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from dotfiles_sync.models import StepConfig, OperationResult
from dotfiles_sync.context import OperationContext

from .base import Verb


class BrewVerb(Verb):
    """
    Install packages using Homebrew.

    Features:
    - Formula and cask installation
    - Version pinning with package@version syntax
    - Idempotent operations (won't reinstall existing packages)
    - Homebrew installation if missing
    - Support for custom taps
    """

    def __init__(self) -> None:
        """Initialize the brew verb."""
        super().__init__("brew_install")
        self.brew_path = None

    def validate(self, step: StepConfig, context: OperationContext) -> List[str]:
        """
        Validate brew_install operation.

        Args:
            step: Step configuration
            context: Operation context

        Returns:
            List of validation error messages
        """
        errors = []

        # Check basic requirements
        if not step.packages:
            errors.append("Packages list is required for brew_install operation")
        elif not isinstance(step.packages, list) or len(step.packages) == 0:
            errors.append("Packages must be a non-empty list")

        # Validate platform - Homebrew works on macOS and Linux
        if context.execution_context.system_info.platform not in ['darwin', 'linux']:
            errors.append(f"Homebrew not supported on platform: {context.execution_context.system_info.platform}")

        # Check if Homebrew is available or can be installed
        if not self._find_brew():
            if not self._can_install_brew():
                errors.append("Homebrew not found and cannot be automatically installed")

        return errors

    def apply(self, step: StepConfig, context: OperationContext) -> OperationResult:
        """
        Apply brew_install operation.

        Args:
            step: Step configuration
            context: Operation context

        Returns:
            Operation result
        """
        try:
            # Ensure Homebrew is available
            if not self._ensure_brew_installed():
                return OperationResult(
                    success=False,
                    operation_id=0,
                    operation_type="brew_install",
                    message="Failed to install or locate Homebrew",
                )

            packages = step.packages or []
            installed_packages = []
            failed_packages = []
            already_installed = []

            for package in packages:
                try:
                    # Parse package specification (package@version, cask:package, etc.)
                    package_info = self._parse_package_spec(package)
                    
                    # Check if already installed
                    if self._is_package_installed(package_info):
                        already_installed.append(package)
                        continue

                    # Install the package
                    if self._install_package(package_info):
                        installed_packages.append(package)
                    else:
                        failed_packages.append(package)

                except Exception as e:
                    self.logger.error(f"Error processing package {package}: {e}")
                    failed_packages.append(package)

            # Create result message
            message_parts = []
            if installed_packages:
                message_parts.append(f"Installed: {', '.join(installed_packages)}")
            if already_installed:
                message_parts.append(f"Already installed: {', '.join(already_installed)}")
            if failed_packages:
                message_parts.append(f"Failed: {', '.join(failed_packages)}")

            success = len(failed_packages) == 0
            message = "; ".join(message_parts) if message_parts else "No packages processed"

            # Prepare rollback data
            rollback_data = self._prepare_rollback_data(
                step, context, original_state={"installed_packages": installed_packages}
            )

            return OperationResult(
                success=success,
                operation_id=0,
                operation_type="brew_install",
                message=message,
                rollback_data=rollback_data,
            )

        except Exception as e:
            self.logger.error(f"Brew install operation failed: {e}")
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type="brew_install",
                message=f"Operation failed: {str(e)}",
            )

    def rollback(self, step: StepConfig, context: OperationContext, rollback_data: Dict[str, Any]) -> bool:
        """
        Rollback brew_install operation by uninstalling packages that were installed.

        Args:
            step: Step configuration
            context: Operation context
            rollback_data: Data from the original operation

        Returns:
            True if rollback succeeded, False otherwise
        """
        try:
            # Find Homebrew
            if not self._find_brew():
                self.logger.warning("Homebrew not found - cannot rollback package installations")
                return False

            # Get packages that were installed during apply
            original_state = rollback_data.get("original_state", {})
            installed_packages = original_state.get("installed_packages", [])

            if not installed_packages:
                self.logger.info("No packages to uninstall during rollback")
                return True

            success = True
            for package in installed_packages:
                try:
                    package_info = self._parse_package_spec(package)
                    if not self._uninstall_package(package_info):
                        success = False
                        self.logger.error(f"Failed to uninstall {package}")
                except Exception as e:
                    success = False
                    self.logger.error(f"Error uninstalling {package}: {e}")

            return success

        except Exception as e:
            self.logger.error(f"Rollback failed: {e}")
            return False

    def dry_run(self, step: StepConfig, context: OperationContext) -> OperationResult:
        """
        Perform a dry run of brew_install operation.

        Args:
            step: Step configuration  
            context: Operation context

        Returns:
            Operation result for dry run
        """
        validation_errors = self.validate(step, context)
        if validation_errors:
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type="brew_install",
                message=f"Validation failed: {'; '.join(validation_errors)}",
                dry_run=True,
            )

        packages = step.packages or []
        if not packages:
            return OperationResult(
                success=True,
                operation_id=0,
                operation_type="brew_install",
                message="No packages to install",
                dry_run=True,
            )

        # Check which packages would be installed
        would_install = []
        already_installed = []
        
        if self._find_brew():
            for package in packages:
                try:
                    package_info = self._parse_package_spec(package)
                    if self._is_package_installed(package_info):
                        already_installed.append(package)
                    else:
                        would_install.append(package)
                except Exception:
                    would_install.append(package)  # Assume would install if can't check
        else:
            would_install = packages  # All packages would be installed if brew missing

        message_parts = []
        if would_install:
            message_parts.append(f"Would install: {', '.join(would_install)}")
        if already_installed:
            message_parts.append(f"Already installed: {', '.join(already_installed)}")

        message = "; ".join(message_parts) if message_parts else "No changes needed"

        return OperationResult(
            success=True,
            operation_id=0,
            operation_type="brew_install",
            message=message,
            dry_run=True,
        )

    # Private helper methods

    def _find_brew(self) -> Optional[str]:
        """Find the Homebrew executable."""
        if self.brew_path:
            return self.brew_path

        # Common locations for brew
        possible_paths = [
            "/opt/homebrew/bin/brew",  # Apple Silicon Mac
            "/usr/local/bin/brew",     # Intel Mac
            "/home/linuxbrew/.linuxbrew/bin/brew",  # Linux
            shutil.which("brew"),      # In PATH
        ]

        for path in possible_paths:
            if path and Path(path).exists():
                self.brew_path = path
                return path

        return None

    def _can_install_brew(self) -> bool:
        """Check if Homebrew can be automatically installed."""
        # We can install Homebrew on macOS and Linux
        try:
            # Check for curl which is needed for Homebrew installation
            return shutil.which("curl") is not None
        except Exception:
            return False

    def _ensure_brew_installed(self) -> bool:
        """Ensure Homebrew is installed."""
        if self._find_brew():
            return True

        # Try to install Homebrew
        self.logger.info("Homebrew not found, attempting to install...")
        try:
            install_cmd = [
                "bash", "-c",
                "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            ]
            
            result = subprocess.run(
                install_cmd, 
                capture_output=True, 
                text=True, 
                timeout=600  # 10 minutes
            )
            
            if result.returncode == 0:
                # Try to find brew again after installation
                self.brew_path = None  # Reset cache
                return self._find_brew() is not None
            else:
                self.logger.error(f"Homebrew installation failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error installing Homebrew: {e}")
            return False

    def _parse_package_spec(self, package_spec: str) -> Dict[str, Any]:
        """
        Parse package specification string.
        
        Supports formats:
        - package_name
        - package_name@version
        - cask:package_name
        - tap/package_name
        """
        package_info = {
            "name": package_spec,
            "version": None,
            "is_cask": False,
            "tap": None,
            "original_spec": package_spec
        }

        # Check for cask prefix
        if package_spec.startswith("cask:"):
            package_info["is_cask"] = True
            package_spec = package_spec[5:]  # Remove "cask:" prefix
            package_info["name"] = package_spec

        # Check for version specification
        if "@" in package_spec and not package_spec.startswith("@"):
            name, version = package_spec.rsplit("@", 1)
            package_info["name"] = name
            package_info["version"] = version

        # Check for tap specification
        if "/" in package_info["name"] and not package_info["name"].startswith("/"):
            package_info["tap"] = package_info["name"]

        return package_info

    def _is_package_installed(self, package_info: Dict[str, Any]) -> bool:
        """Check if a package is installed."""
        if not self.brew_path:
            return False

        try:
            if package_info["is_cask"]:
                # Check cask installation
                result = subprocess.run(
                    [self.brew_path, "list", "--cask", package_info["name"]],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            else:
                # Check formula installation
                result = subprocess.run(
                    [self.brew_path, "list", package_info["name"]],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            
            return result.returncode == 0

        except Exception as e:
            self.logger.debug(f"Error checking if {package_info['name']} is installed: {e}")
            return False

    def _install_package(self, package_info: Dict[str, Any]) -> bool:
        """Install a package using Homebrew."""
        if not self.brew_path:
            return False

        try:
            cmd = [self.brew_path, "install"]
            
            if package_info["is_cask"]:
                cmd.append("--cask")
            
            # Use the original spec to preserve version/tap information
            cmd.append(package_info["original_spec"].replace("cask:", ""))
            
            self.logger.info(f"Installing {package_info['original_spec']} with command: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minutes per package
            )
            
            if result.returncode == 0:
                self.logger.info(f"Successfully installed {package_info['name']}")
                return True
            else:
                self.logger.error(f"Failed to install {package_info['name']}: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout installing {package_info['name']}")
            return False
        except Exception as e:
            self.logger.error(f"Error installing {package_info['name']}: {e}")
            return False

    def _uninstall_package(self, package_info: Dict[str, Any]) -> bool:
        """Uninstall a package using Homebrew."""
        if not self.brew_path:
            return False

        try:
            cmd = [self.brew_path, "uninstall"]
            
            if package_info["is_cask"]:
                cmd.append("--cask")
            
            cmd.append(package_info["name"])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes
            )
            
            return result.returncode == 0

        except Exception as e:
            self.logger.error(f"Error uninstalling {package_info['name']}: {e}")
            return False