"""
File storage utilities for managing uploaded materials.
"""

import os
from pathlib import Path
from typing import Tuple
from app.config import config


def get_storage_path(university: str, major: str, course: str, week: str, filename: str) -> Tuple[Path, str]:
    """
    Generate storage path for uploaded file.
    
    Returns:
        Tuple of (full_path, relative_path)
    """
    # Sanitize components
    university = sanitize_path_component(university)
    major = sanitize_path_component(major)
    course = sanitize_path_component(course)
    week = sanitize_path_component(week)
    filename = sanitize_filename(filename)
    
    # Build path
    relative_path = Path(university) / major / course / week / filename
    full_path = config.STORAGE_ROOT / relative_path
    
    return full_path, str(relative_path)


def ensure_directory(path: Path) -> None:
    """Ensure directory exists, create if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)


def save_uploaded_file(file_content: bytes, filepath: Path) -> bool:
    """
    Save uploaded file to disk.
    
    Args:
        file_content: Binary file content
        filepath: Full path where to save
        
    Returns:
        True if successful, False otherwise
    """
    try:
        ensure_directory(filepath)
        with open(filepath, 'wb') as f:
            f.write(file_content)
        return True
    except Exception as e:
        print(f"Error saving file: {e}")
        return False


def sanitize_path_component(component: str) -> str:
    """Sanitize path component to prevent directory traversal."""
    # Remove any path separators and special characters
    component = component.replace('/', '_').replace('\\', '_')
    component = component.replace('..', '_')
    # Remove leading/trailing spaces
    component = component.strip()
    # Replace spaces with underscores
    component = component.replace(' ', '_')
    return component


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to be filesystem-safe."""
    # Keep extension
    name, ext = os.path.splitext(filename)
    name = sanitize_path_component(name)
    # Limit length
    if len(name) > 200:
        name = name[:200]
    return f"{name}{ext}"


def get_file_path(relative_path: str) -> Path:
    """Get full path from relative storage path."""
    return config.STORAGE_ROOT / relative_path


def file_exists(relative_path: str) -> bool:
    """Check if file exists in storage."""
    full_path = get_file_path(relative_path)
    return full_path.exists() and full_path.is_file()
