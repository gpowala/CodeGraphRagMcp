"""
Configuration Manager for C++ Graph-RAG MCP Server
Handles persistent storage of monitored directories and settings
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class ConfigManager:
    """
    Manages persistent configuration for the MCP server.
    
    Configuration is stored in a JSON file that persists across container restarts
    when using a mounted volume.
    """
    
    DEFAULT_CONFIG = {
        "monitored_paths": [],
        "base_path": "/host",
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "index_interval_seconds": 30,
        "max_file_size_mb": 10,
        "excluded_patterns": [
            "node_modules",
            "__pycache__",
            ".git",
            "build",
            "out",
            "bin",
            "obj",
            ".vs",
            "*.generated.*"
        ],
        "file_extensions": [
            ".cpp", ".cc", ".cxx",
            ".hpp", ".h", ".hxx",
            ".c", ".inl"
        ],
        "created_at": None,
        "updated_at": None
    }
    
    def __init__(self, config_path: Path):
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Path to the configuration directory
        """
        self.config_dir = Path(config_path)
        self.config_file = self.config_dir / "config.json"
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file or return defaults.
        
        Returns:
            Configuration dictionary
        """
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Merge with defaults to handle new fields
                    merged = {**self.DEFAULT_CONFIG, **config}
                    return merged
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load config file: {e}")
                return self.DEFAULT_CONFIG.copy()
        
        # Return default config if file doesn't exist
        return self.DEFAULT_CONFIG.copy()
    
    def save_config(self, config: Dict[str, Any]) -> bool:
        """
        Save configuration to file.
        
        Args:
            config: Configuration dictionary to save
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Load existing config and merge
            existing = self.load_config()
            merged = {**existing, **config}
            merged["updated_at"] = datetime.now().isoformat()
            
            if not merged.get("created_at"):
                merged["created_at"] = merged["updated_at"]
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(merged, f, indent=2)
            
            return True
        except IOError as e:
            print(f"Error saving config: {e}")
            return False
    
    def get_monitored_paths(self) -> List[str]:
        """Get list of monitored paths."""
        config = self.load_config()
        return config.get("monitored_paths", [])
    
    def set_monitored_paths(self, paths: List[str]) -> bool:
        """
        Set the list of monitored paths.
        
        Args:
            paths: List of paths to monitor
            
        Returns:
            True if saved successfully
        """
        return self.save_config({"monitored_paths": paths})
    
    def add_monitored_path(self, path: str) -> bool:
        """
        Add a path to the monitored list.
        
        Args:
            path: Path to add
            
        Returns:
            True if added successfully
        """
        paths = self.get_monitored_paths()
        if path not in paths:
            paths.append(path)
            return self.set_monitored_paths(paths)
        return True  # Already exists
    
    def remove_monitored_path(self, path: str) -> bool:
        """
        Remove a path from the monitored list.
        
        Args:
            path: Path to remove
            
        Returns:
            True if removed successfully
        """
        paths = self.get_monitored_paths()
        if path in paths:
            paths.remove(path)
            return self.set_monitored_paths(paths)
        return True  # Didn't exist
    
    def get_excluded_patterns(self) -> List[str]:
        """Get list of excluded patterns."""
        config = self.load_config()
        return config.get("excluded_patterns", self.DEFAULT_CONFIG["excluded_patterns"])
    
    def get_file_extensions(self) -> List[str]:
        """Get list of file extensions to index."""
        config = self.load_config()
        return config.get("file_extensions", self.DEFAULT_CONFIG["file_extensions"])
    
    def should_exclude(self, path: Path) -> bool:
        """
        Check if a path should be excluded from indexing.
        
        Args:
            path: Path to check
            
        Returns:
            True if the path should be excluded
        """
        path_str = str(path)
        patterns = self.get_excluded_patterns()
        
        for pattern in patterns:
            if pattern.startswith("*"):
                # Wildcard pattern
                if pattern[1:] in path_str:
                    return True
            else:
                # Directory name pattern
                if f"/{pattern}/" in path_str or f"\\{pattern}\\" in path_str:
                    return True
                if path_str.endswith(f"/{pattern}") or path_str.endswith(f"\\{pattern}"):
                    return True
        
        return False
    
    def is_valid_extension(self, path: Path) -> bool:
        """
        Check if a file has a valid extension for indexing.
        
        Args:
            path: Path to check
            
        Returns:
            True if the file should be indexed
        """
        extensions = self.get_file_extensions()
        return path.suffix.lower() in extensions
    
    def get_index_status_file(self) -> Path:
        """Get path to index status file."""
        return self.config_dir / "index_status.json"
    
    def save_index_status(self, status: Dict[str, Any]) -> bool:
        """
        Save indexing status for UI display.
        
        Args:
            status: Status dictionary
            
        Returns:
            True if saved successfully
        """
        try:
            status_file = self.get_index_status_file()
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump(status, f, indent=2)
            return True
        except IOError as e:
            print(f"Error saving index status: {e}")
            return False
    
    def load_index_status(self) -> Dict[str, Any]:
        """
        Load indexing status.
        
        Returns:
            Status dictionary
        """
        status_file = self.get_index_status_file()
        if status_file.exists():
            try:
                with open(status_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        
        return {
            "total_files": 0,
            "indexed_files": 0,
            "is_indexing": False,
            "last_indexed": None
        }


def get_config_manager() -> ConfigManager:
    """
    Factory function to get a ConfigManager instance.
    
    Returns:
        ConfigManager instance with path from environment
    """
    config_path = os.getenv("CONFIG_PATH", "/app/config")
    return ConfigManager(Path(config_path))
