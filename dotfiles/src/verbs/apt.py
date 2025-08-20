"""
APT package management verb implementation.

This module provides APT package installation functionality with
version pinning, sudo handling, and idempotent operations for Debian/Ubuntu systems.
"""

import subprocess
import shutil
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from dotfiles_sync.models import StepConfig, OperationResult
from dotfiles_sync.context import OperationContext

from .base import Verb


class AptVerb(Verb):
    """
    Install packages using APT (Advanced Package Tool).

    Features:
    - Package installation with version pinning
    - Idempotent operations (won't reinstall existing packages)
    - Automatic sudo handling
    - Package cache updates
    - Support for custom repositories/PPAs
    """

    def __init__(self) -> None:
        """Initialize the apt verb."""
        super().__init__("apt_install")
        self.apt_path = None

    def validate(self, step: StepConfig, context: OperationContext) -> List[str]:
        """
        Validate apt_install operation.

        Args:
            step: Step configuration
            context: Operation context

        Returns:
            List of validation error messages
        """
        errors = []

        # Check basic requirements
        if not step.packages:
            errors.append("Packages list is required for apt_install operation")
        elif not isinstance(step.packages, list) or len(step.packages) == 0:
            errors.append("Packages must be a non-empty list")

        # Validate platform - APT works on Debian-based systems
        if context.execution_context.system_info.platform != 'linux':
            errors.append(f"APT not supported on platform: {context.execution_context.system_info.platform}")

        # Check if APT is available
        if not self._find_apt():
            errors.append("APT not found - this system may not be Debian/Ubuntu based")

        # Check for sudo access if needed
        if step.sudo and not self._can_use_sudo():
            errors.append("Sudo access required but not available")

        return errors

    def apply(self, step: StepConfig, context: OperationContext) -> OperationResult:
        """
        Apply apt_install operation.

        Args:
            step: Step configuration
            context: Operation context

        Returns:
            Operation result
        """
        try:
            # Find APT
            if not self._find_apt():
                return OperationResult(
                    success=False,
                    operation_id=0,
                    operation_type="apt_install",
                    message="APT not found on this system",
                )

            packages = step.packages or []
            use_sudo = step.sudo

            # Update package cache if needed
            if not self._update_cache_if_needed(use_sudo):
                self.logger.warning("Failed to update APT cache, proceeding anyway")

            installed_packages = []
            failed_packages = []
            already_installed = []

            for package in packages:
                try:
                    # Parse package specification (package=version)
                    package_info = self._parse_package_spec(package)
                    
                    # Check if already installed
                    if self._is_package_installed(package_info):
                        already_installed.append(package)
                        continue

                    # Install the package
                    if self._install_package(package_info, use_sudo):
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
                operation_type="apt_install",
                message=message,
                rollback_data=rollback_data,
            )

        except Exception as e:
            self.logger.error(f"APT install operation failed: {e}")
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type="apt_install",
                message=f"Operation failed: {str(e)}",
            )

    def rollback(self, step: StepConfig, context: OperationContext, rollback_data: Dict[str, Any]) -> bool:
        """
        Rollback apt_install operation by uninstalling packages that were installed.

        Args:
            step: Step configuration
            context: Operation context
            rollback_data: Data from the original operation

        Returns:
            True if rollback succeeded, False otherwise
        """
        try:
            # Find APT
            if not self._find_apt():
                self.logger.warning("APT not found - cannot rollback package installations")
                return False

            # Get packages that were installed during apply
            original_state = rollback_data.get("original_state", {})
            installed_packages = original_state.get("installed_packages", [])

            if not installed_packages:
                self.logger.info("No packages to uninstall during rollback")
                return True

            use_sudo = step.sudo
            success = True

            for package in installed_packages:
                try:
                    package_info = self._parse_package_spec(package)
                    if not self._uninstall_package(package_info, use_sudo):
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
        Perform a dry run of apt_install operation.

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
                operation_type="apt_install",
                message=f"Validation failed: {'; '.join(validation_errors)}",
                dry_run=True,
            )

        packages = step.packages or []
        if not packages:
            return OperationResult(
                success=True,
                operation_id=0,
                operation_type="apt_install",
                message="No packages to install",
                dry_run=True,
            )

        # Check which packages would be installed
        would_install = []
        already_installed = []
        
        if self._find_apt():
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
            would_install = packages  # All packages would be installed if apt missing

        message_parts = []
        if would_install:
            message_parts.append(f"Would install: {', '.join(would_install)}")
        if already_installed:
            message_parts.append(f"Already installed: {', '.join(already_installed)}")

        message = "; ".join(message_parts) if message_parts else "No changes needed"

        return OperationResult(
            success=True,
            operation_id=0,
            operation_type="apt_install",
            message=message,
            dry_run=True,
        )

    # Private helper methods

    def _find_apt(self) -> Optional[str]:
        """Find the APT executable."""
        if self.apt_path:
            return self.apt_path

        # Look for apt-get (primary) or apt (newer interface)
        for command in ["apt-get", "apt"]:
            path = shutil.which(command)
            if path:
                self.apt_path = path
                return path

        return None

    def _can_use_sudo(self) -> bool:
        """Check if sudo is available and can be used."""
        try:
            # Check if sudo exists
            if not shutil.which("sudo"):
                return False
                
            # Check if we can use sudo (won't prompt for password in non-interactive mode)
            result = subprocess.run(
                ["sudo", "-n", "true"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            return result.returncode == 0
            
        except Exception:
            return False

    def _update_cache_if_needed(self, use_sudo: bool) -> bool:
        """Update APT package cache if it's stale."""
        if not self.apt_path:
            return False

        try:
            # Check if cache needs updating (older than 1 hour)
            cache_file = Path("/var/cache/apt/pkgcache.bin")
            if cache_file.exists():
                import time
                age_hours = (time.time() - cache_file.stat().st_mtime) / 3600
                if age_hours < 1:
                    return True  # Cache is fresh

            # Update cache
            cmd = []
            if use_sudo:
                cmd.append("sudo")
            
            cmd.extend([self.apt_path, "update"])
            
            self.logger.info("Updating APT package cache...")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes
            )
            
            if result.returncode == 0:
                self.logger.info("APT cache updated successfully")
                return True
            else:
                self.logger.warning(f"APT cache update failed: {result.stderr}")
                return False

        except Exception as e:
            self.logger.warning(f"Error updating APT cache: {e}")
            return False

    def _parse_package_spec(self, package_spec: str) -> Dict[str, Any]:
        """
        Parse package specification string.
        
        Supports formats:
        - package_name
        - package_name=version
        """
        package_info = {
            "name": package_spec,
            "version": None,
            "original_spec": package_spec
        }

        # Check for version specification
        if "=" in package_spec:
            name, version = package_spec.split("=", 1)
            package_info["name"] = name
            package_info["version"] = version

        return package_info

    def _is_package_installed(self, package_info: Dict[str, Any]) -> bool:
        """Check if a package is installed."""
        try:
            # Use dpkg to check if package is installed
            result = subprocess.run(
                ["dpkg", "-l", package_info["name"]],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # dpkg -l returns 0 if package is installed
            if result.returncode == 0:
                # Check if the package is actually installed (not just known)
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.startswith("ii"):  # "ii" means installed
                        if package_info["name"] in line:
                            # If version specified, check if it matches
                            if package_info["version"]:
                                return package_info["version"] in line
                            return True
            
            return False

        except Exception as e:
            self.logger.debug(f"Error checking if {package_info['name']} is installed: {e}")
            return False

    def _install_package(self, package_info: Dict[str, Any], use_sudo: bool) -> bool:
        """Install a package using APT."""
        if not self.apt_path:
            return False

        try:
            cmd = []
            if use_sudo:
                cmd.append("sudo")
                
            cmd.extend([
                self.apt_path, "install", "-y",  # -y for non-interactive
                package_info["original_spec"]
            ])
            
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

    def _uninstall_package(self, package_info: Dict[str, Any], use_sudo: bool) -> bool:
        """Uninstall a package using APT."""
        if not self.apt_path:
            return False

        try:
            cmd = []
            if use_sudo:
                cmd.append("sudo")
                
            cmd.extend([
                self.apt_path, "remove", "-y",
                package_info["name"]
            ])
            
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