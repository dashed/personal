"""
Template processing verb implementation.

This module provides Jinja2 template processing functionality with
variable substitution and security protections against template injection.
"""

import os
from pathlib import Path
from typing import Any, Dict, List

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateSyntaxError
    from jinja2.sandbox import SandboxedEnvironment

    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False

from dotfiles_sync.models import StepConfig, OperationResult
from dotfiles_sync.context import OperationContext

from .base import Verb


class TemplateVerb(Verb):
    """
    Process Jinja2 templates with variable substitution.

    Features:
    - Jinja2 template processing
    - Variable substitution from config and environment
    - Sandboxed execution for security
    - Template injection prevention
    - Support for custom filters
    - File permission setting
    """

    def __init__(self) -> None:
        """Initialize the template verb."""
        super().__init__("template")
        self._env = None

    def validate(self, step: StepConfig, context: OperationContext) -> List[str]:
        """
        Validate template operation.

        Args:
            step: Step configuration
            context: Operation context

        Returns:
            List of validation error messages
        """
        errors = []

        # Check if Jinja2 is available
        if not JINJA2_AVAILABLE:
            errors.append("Jinja2 is not installed - required for template operations")
            return errors

        # Check required fields
        if not step.src:
            errors.append("Source template path is required for template operation")
        if not step.dst:
            errors.append("Destination path is required for template operation")
        if not step.vars:
            errors.append("Template variables (vars) are required for template operation")

        # Validate paths using base class
        errors.extend(self._validate_paths(step, context))

        # Check if source template exists
        src_path = context.get_src_path()
        if src_path and not src_path.exists():
            errors.append(f"Template file does not exist: {src_path}")
        elif src_path and not src_path.is_file():
            errors.append(f"Template source is not a file: {src_path}")

        # Validate template variables
        if step.vars and not isinstance(step.vars, dict):
            errors.append("Template variables must be a dictionary")

        # Try to validate template syntax if possible
        if src_path and src_path.exists() and step.vars:
            try:
                env = self._get_template_environment(src_path.parent)
                template_content = src_path.read_text(encoding="utf-8")
                env.from_string(template_content)
            except TemplateSyntaxError as e:
                errors.append(f"Template syntax error in {src_path}: {e}")
            except Exception as e:
                errors.append(f"Error loading template {src_path}: {e}")

        return errors

    def apply(self, step: StepConfig, context: OperationContext) -> OperationResult:
        """
        Apply template operation.

        Args:
            step: Step configuration
            context: Operation context

        Returns:
            Operation result
        """
        try:
            src_path = context.get_src_path()
            dst_path = context.get_dst_path()

            if not src_path or not dst_path:
                return OperationResult(
                    success=False,
                    operation_id=0,
                    operation_type="template",
                    message="Source or destination path not available",
                )

            # Create backup if destination exists
            backup_path = None
            original_exists = dst_path.exists()
            original_content = None

            if original_exists:
                original_content = (
                    dst_path.read_text(encoding="utf-8") if dst_path.is_file() else None
                )
                backup_path = self._backup_file(dst_path, context)

            # Load and render template
            env = self._get_template_environment(src_path.parent)
            template = env.get_template(src_path.name)

            # Prepare template variables
            template_vars = self._prepare_template_vars(step.vars or {}, context)

            # Render template
            rendered_content = template.render(**template_vars)

            # Create parent directories if needed
            if step.create_parent_dirs and dst_path.parent:
                dst_path.parent.mkdir(parents=True, exist_ok=True)

                # Set parent directory permissions if specified
                if step.parent_dir_mode:
                    try:
                        mode = int(step.parent_dir_mode, 8)  # Convert octal string to int
                        dst_path.parent.chmod(mode)
                    except (ValueError, OSError) as e:
                        self.logger.warning(f"Failed to set parent directory permissions: {e}")

            # Write rendered content to destination
            dst_path.write_text(rendered_content, encoding="utf-8")

            # Set file permissions if specified
            if step.mode:
                try:
                    mode = int(step.mode, 8)  # Convert octal string to int
                    dst_path.chmod(mode)
                except (ValueError, OSError) as e:
                    self.logger.warning(f"Failed to set file permissions: {e}")

            # Prepare rollback data
            rollback_data = self._prepare_rollback_data(
                step,
                context,
                backup_path=backup_path,
                original_state={
                    "existed": original_exists,
                    "content": original_content,
                    "template_vars": template_vars,
                },
            )

            message = f"Template rendered: {src_path.name} -> {dst_path}"
            if backup_path:
                message += f" (backup: {backup_path})"

            return OperationResult(
                success=True,
                operation_id=0,
                operation_type="template",
                message=message,
                rollback_data=rollback_data,
            )

        except Exception as e:
            self.logger.error(f"Template operation failed: {e}")
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type="template",
                message=f"Operation failed: {str(e)}",
            )

    def rollback(
        self, step: StepConfig, context: OperationContext, rollback_data: Dict[str, Any]
    ) -> bool:
        """
        Rollback template operation.

        Args:
            step: Step configuration
            context: Operation context
            rollback_data: Data from the original operation

        Returns:
            True if rollback succeeded, False otherwise
        """
        try:
            dst_path = context.get_dst_path()
            if not dst_path:
                return False

            original_state = rollback_data.get("original_state", {})
            backup_path_str = rollback_data.get("backup_path")

            if original_state.get("existed", False):
                # File existed before, restore from backup or original content
                if backup_path_str and Path(backup_path_str).exists():
                    # Restore from backup
                    import shutil

                    shutil.copy2(backup_path_str, dst_path)
                    self.logger.info(f"Restored {dst_path} from backup")
                elif original_state.get("content"):
                    # Restore from saved content
                    dst_path.write_text(original_state["content"], encoding="utf-8")
                    self.logger.info(f"Restored {dst_path} from saved content")
                else:
                    self.logger.warning(f"Could not restore original content for {dst_path}")
                    return False
            else:
                # File didn't exist before, remove it
                if dst_path.exists():
                    dst_path.unlink()
                    self.logger.info(f"Removed {dst_path} (didn't exist before)")

            return True

        except Exception as e:
            self.logger.error(f"Template rollback failed: {e}")
            return False

    def dry_run(self, step: StepConfig, context: OperationContext) -> OperationResult:
        """
        Perform a dry run of template operation.

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
                operation_type="template",
                message=f"Validation failed: {'; '.join(validation_errors)}",
                dry_run=True,
            )

        try:
            src_path = context.get_src_path()
            dst_path = context.get_dst_path()

            if not src_path or not dst_path:
                return OperationResult(
                    success=False,
                    operation_id=0,
                    operation_type="template",
                    message="Source or destination path not available",
                    dry_run=True,
                )

            # Try to render template to validate it works
            env = self._get_template_environment(src_path.parent)
            template = env.get_template(src_path.name)
            template_vars = self._prepare_template_vars(step.vars or {}, context)

            # Test render (don't save the result)
            rendered_content = template.render(**template_vars)

            message = f"Would render template: {src_path.name} -> {dst_path}"
            message += f" ({len(rendered_content)} characters)"

            if dst_path.exists():
                message += " (would overwrite existing file)"

            return OperationResult(
                success=True,
                operation_id=0,
                operation_type="template",
                message=message,
                dry_run=True,
            )

        except Exception as e:
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type="template",
                message=f"Dry run failed: {str(e)}",
                dry_run=True,
            )

    # Private helper methods

    def _get_template_environment(self, template_dir: Path) -> Environment:
        """Get or create a Jinja2 environment."""
        if self._env is None:
            # Use sandboxed environment for security
            self._env = SandboxedEnvironment(
                loader=FileSystemLoader(str(template_dir)),
                autoescape=select_autoescape(["html", "xml"]),
                # Security settings
                enable_async=False,
            )

            # Add custom filters
            self._env.filters["basename"] = lambda path: Path(path).name
            self._env.filters["dirname"] = lambda path: str(Path(path).parent)
            self._env.filters["expanduser"] = lambda path: str(Path(path).expanduser())
            self._env.filters["abspath"] = lambda path: str(Path(path).absolute())

        return self._env

    def _prepare_template_vars(
        self, config_vars: Dict[str, Any], context: OperationContext
    ) -> Dict[str, Any]:
        """
        Prepare template variables by merging config vars with system info.

        Args:
            config_vars: Variables from step configuration
            context: Operation context

        Returns:
            Dictionary with all template variables
        """
        template_vars = {}

        # Add system information
        system_info = context.execution_context.system_info
        template_vars.update(
            {
                "platform": system_info.platform,
                "hostname": system_info.hostname,
                "username": system_info.username,
                "home": str(Path.home()),
                "variant": context.execution_context.variant,
            }
        )

        # Add environment variables with 'env' prefix
        template_vars["env"] = dict(os.environ)

        # Add configuration variables (these take precedence)
        template_vars.update(config_vars)

        # Filter out potentially dangerous variables
        template_vars = self._sanitize_template_vars(template_vars)

        return template_vars

    def _sanitize_template_vars(self, template_vars: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize template variables to prevent security issues.

        Args:
            template_vars: Raw template variables

        Returns:
            Sanitized template variables
        """
        sanitized = {}

        # List of potentially dangerous keys to exclude
        dangerous_keys = {
            "__builtins__",
            "__import__",
            "__loader__",
            "__spec__",
            "eval",
            "exec",
            "compile",
            "open",
            "file",
            "input",
            "raw_input",
        }

        for key, value in template_vars.items():
            if key in dangerous_keys:
                self.logger.warning(f"Skipping potentially dangerous template variable: {key}")
                continue

            # Convert values to safe types
            if isinstance(value, (str, int, float, bool, list, dict)):
                sanitized[key] = value
            else:
                # Convert other types to strings
                sanitized[key] = str(value)

        return sanitized
