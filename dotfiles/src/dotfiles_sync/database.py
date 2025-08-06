"""
Database interface wrapper for the Dotfiles Management System.

This module provides a simplified interface to the state database,
wrapping the comprehensive StateDatabase implementation and using
Pydantic models for data validation.
"""

import logging
from pathlib import Path
from typing import Optional

# Import the comprehensive database implementation
from dotfiles_sync.state_database import StateDatabase as _StateDatabase

# Import Pydantic models for database operations
from dotfiles_sync.models import (
    TransactionContext,
    OperationResult,
)

logger = logging.getLogger(__name__)

# Re-export the main database class
StateDatabase = _StateDatabase

# Re-export Pydantic models for database operations
__all__ = [
    "StateDatabase",
    "TransactionContext", 
    "OperationResult",
    "get_default_db_path",
    "init_database",
    "check_database_exists",
]


def get_default_db_path() -> Path:
    """Get the default database path following XDG conventions.
    
    Returns:
        Path to the default state database
    """
    return Path.home() / ".local" / "state" / "dotfiles" / "state.db"


def init_database(db_path: Optional[Path] = None) -> StateDatabase:
    """Initialize and return a database connection.
    
    Args:
        db_path: Optional custom database path
        
    Returns:
        Initialized StateDatabase instance
    """
    if db_path is None:
        db_path = get_default_db_path()
    
    logger.info(f"Initializing database at {db_path}")
    return StateDatabase(db_path)


def check_database_exists(db_path: Optional[Path] = None) -> bool:
    """Check if the state database exists.
    
    Args:
        db_path: Optional custom database path
        
    Returns:
        True if database file exists
    """
    if db_path is None:
        db_path = get_default_db_path()
    
    return db_path.exists()