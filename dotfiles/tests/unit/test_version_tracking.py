"""
Unit tests for version tracking in StateDatabase.
"""

from pathlib import Path
import tempfile

from dotfiles_sync import __version__
from dotfiles_sync.state_database import StateDatabase


def test_version_stored_correctly():
    """Test that package version is stored correctly in system_info."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = StateDatabase(str(db_path))
        
        # Query system_info table
        cursor = db.conn.cursor()
        cursor.execute("SELECT dotfiles_version FROM system_info")
        result = cursor.fetchone()
        
        assert result is not None, "No system_info record found"
        stored_version = result[0]
        
        # Check that the stored version matches the package version
        assert stored_version == __version__, f"Version mismatch: stored={stored_version}, expected={__version__}"


def test_version_from_package_import():
    """Test that version is imported from package, not hardcoded."""
    # Verify that state_database imports __version__ from the package
    import dotfiles_sync.state_database as sd
    
    # Check that the module has imported __version__
    assert hasattr(sd, '__version__'), "state_database should import __version__"
    
    # Verify it matches the package version
    assert sd.__version__ == __version__, "Version should match package version"
    
    # Create a database to verify it uses the imported version
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = StateDatabase(str(db_path))
        
        # Check the stored version matches package version
        cursor = db.conn.cursor()
        cursor.execute("SELECT dotfiles_version FROM system_info")
        result = cursor.fetchone()
        
        assert result[0] == __version__, "Database should store package version"