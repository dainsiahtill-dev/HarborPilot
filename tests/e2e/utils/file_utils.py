"""
File utilities for HarborPilot E2E tests
"""

import os
import shutil
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from loguru import logger


class FileUtils:
    """Utility class for file operations"""
    
    @staticmethod
    def ensure_directory(path: Union[str, Path]) -> Path:
        """
        Ensure directory exists, create if it doesn't
        
        Args:
            path: Directory path
            
        Returns:
            Path object
        """
        path_obj = Path(path)
        path_obj.mkdir(parents=True, exist_ok=True)
        return path_obj
    
    @staticmethod
    def create_file(path: Union[str, Path], content: str = "", encoding: str = "utf-8") -> Path:
        """
        Create file with content
        
        Args:
            path: File path
            content: File content
            encoding: File encoding
            
        Returns:
            Path object
        """
        path_obj = Path(path)
        FileUtils.ensure_directory(path_obj.parent)
        
        with open(path_obj, 'w', encoding=encoding) as f:
            f.write(content)
        
        logger.debug(f"Created file: {path_obj}")
        return path_obj
    
    @staticmethod
    def read_file(path: Union[str, Path], encoding: str = "utf-8") -> str:
        """
        Read file content
        
        Args:
            path: File path
            encoding: File encoding
            
        Returns:
            File content
        """
        path_obj = Path(path)
        
        if not path_obj.exists():
            raise FileNotFoundError(f"File not found: {path_obj}")
        
        with open(path_obj, 'r', encoding=encoding) as f:
            content = f.read()
        
        logger.debug(f"Read file: {path_obj}")
        return content
    
    @staticmethod
    def read_json_file(path: Union[str, Path], encoding: str = "utf-8") -> Dict[str, Any]:
        """
        Read JSON file
        
        Args:
            path: File path
            encoding: File encoding
            
        Returns:
            Parsed JSON data
        """
        content = FileUtils.read_file(path, encoding)
        return json.loads(content)
    
    @staticmethod
    def write_json_file(path: Union[str, Path], data: Dict[str, Any], indent: int = 2, encoding: str = "utf-8") -> None:
        """
        Write JSON file
        
        Args:
            path: File path
            data: JSON data
            indent: JSON indentation
            encoding: File encoding
        """
        path_obj = Path(path)
        FileUtils.ensure_directory(path_obj.parent)
        
        with open(path_obj, 'w', encoding=encoding) as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        
        logger.debug(f"Wrote JSON file: {path_obj}")
    
    @staticmethod
    def append_to_file(path: Union[str, Path], content: str, encoding: str = "utf-8") -> None:
        """
        Append content to file
        
        Args:
            path: File path
            content: Content to append
            encoding: File encoding
        """
        path_obj = Path(path)
        FileUtils.ensure_directory(path_obj.parent)
        
        with open(path_obj, 'a', encoding=encoding) as f:
            f.write(content)
        
        logger.debug(f"Appended to file: {path_obj}")
    
    @staticmethod
    def delete_file(path: Union[str, Path]) -> bool:
        """
        Delete file
        
        Args:
            path: File path
            
        Returns:
            True if deleted, False if didn't exist
        """
        path_obj = Path(path)
        
        if path_obj.exists():
            path_obj.unlink()
            logger.debug(f"Deleted file: {path_obj}")
            return True
        
        return False
    
    @staticmethod
    def delete_directory(path: Union[str, Path], ignore_errors: bool = False) -> bool:
        """
        Delete directory and all contents
        
        Args:
            path: Directory path
            ignore_errors: Whether to ignore errors during deletion
            
        Returns:
            True if deleted, False if didn't exist
        """
        path_obj = Path(path)
        
        if path_obj.exists():
            shutil.rmtree(path_obj, ignore_errors=ignore_errors)
            logger.debug(f"Deleted directory: {path_obj}")
            return True
        
        return False
    
    @staticmethod
    def copy_file(src: Union[str, Path], dst: Union[str, Path]) -> Path:
        """
        Copy file
        
        Args:
            src: Source file path
            dst: Destination file path
            
        Returns:
            Destination path object
        """
        src_obj = Path(src)
        dst_obj = Path(dst)
        
        if not src_obj.exists():
            raise FileNotFoundError(f"Source file not found: {src_obj}")
        
        FileUtils.ensure_directory(dst_obj.parent)
        shutil.copy2(src_obj, dst_obj)
        
        logger.debug(f"Copied file: {src_obj} -> {dst_obj}")
        return dst_obj
    
    @staticmethod
    def copy_directory(src: Union[str, Path], dst: Union[str, Path]) -> Path:
        """
        Copy directory
        
        Args:
            src: Source directory path
            dst: Destination directory path
            
        Returns:
            Destination path object
        """
        src_obj = Path(src)
        dst_obj = Path(dst)
        
        if not src_obj.exists():
            raise FileNotFoundError(f"Source directory not found: {src_obj}")
        
        if dst_obj.exists():
            FileUtils.delete_directory(dst_obj)
        
        shutil.copytree(src_obj, dst_obj)
        
        logger.debug(f"Copied directory: {src_obj} -> {dst_obj}")
        return dst_obj
    
    @staticmethod
    def move_file(src: Union[str, Path], dst: Union[str, Path]) -> Path:
        """
        Move file
        
        Args:
            src: Source file path
            dst: Destination file path
            
        Returns:
            Destination path object
        """
        src_obj = Path(src)
        dst_obj = Path(dst)
        
        if not src_obj.exists():
            raise FileNotFoundError(f"Source file not found: {src_obj}")
        
        FileUtils.ensure_directory(dst_obj.parent)
        shutil.move(str(src_obj), str(dst_obj))
        
        logger.debug(f"Moved file: {src_obj} -> {dst_obj}")
        return dst_obj
    
    @staticmethod
    def get_file_size(path: Union[str, Path]) -> int:
        """
        Get file size in bytes
        
        Args:
            path: File path
            
        Returns:
            File size in bytes
        """
        path_obj = Path(path)
        
        if not path_obj.exists():
            raise FileNotFoundError(f"File not found: {path_obj}")
        
        return path_obj.stat().st_size
    
    @staticmethod
    def get_file_modified_time(path: Union[str, Path]) -> float:
        """
        Get file modification time
        
        Args:
            path: File path
            
        Returns:
            Modification timestamp
        """
        path_obj = Path(path)
        
        if not path_obj.exists():
            raise FileNotFoundError(f"File not found: {path_obj}")
        
        return path_obj.stat().st_mtime
    
    @staticmethod
    def list_files(directory: Union[str, Path], pattern: str = "*", recursive: bool = False) -> List[Path]:
        """
        List files in directory
        
        Args:
            directory: Directory path
            pattern: File pattern (glob)
            recursive: Whether to search recursively
            
        Returns:
            List of file paths
        """
        dir_obj = Path(directory)
        
        if not dir_obj.exists():
            raise FileNotFoundError(f"Directory not found: {dir_obj}")
        
        if recursive:
            files = list(dir_obj.rglob(pattern))
        else:
            files = list(dir_obj.glob(pattern))
        
        # Filter only files (not directories)
        return [f for f in files if f.is_file()]
    
    @staticmethod
    def list_directories(directory: Union[str, Path], pattern: str = "*", recursive: bool = False) -> List[Path]:
        """
        List directories in directory
        
        Args:
            directory: Directory path
            pattern: Directory pattern (glob)
            recursive: Whether to search recursively
            
        Returns:
            List of directory paths
        """
        dir_obj = Path(directory)
        
        if not dir_obj.exists():
            raise FileNotFoundError(f"Directory not found: {dir_obj}")
        
        if recursive:
            dirs = list(dir_obj.rglob(pattern))
        else:
            dirs = list(dir_obj.glob(pattern))
        
        # Filter only directories
        return [d for d in dirs if d.is_dir()]
    
    @staticmethod
    def find_files_by_extension(directory: Union[str, Path], extensions: List[str], recursive: bool = True) -> List[Path]:
        """
        Find files by extension
        
        Args:
            directory: Directory path
            extensions: List of file extensions (with or without dot)
            recursive: Whether to search recursively
            
        Returns:
            List of file paths
        """
        # Normalize extensions (ensure they start with dot)
        normalized_extensions = []
        for ext in extensions:
            if not ext.startswith('.'):
                ext = '.' + ext
            normalized_extensions.append(ext)
        
        all_files = []
        for ext in normalized_extensions:
            pattern = f"*{ext}"
            files = FileUtils.list_files(directory, pattern, recursive)
            all_files.extend(files)
        
        # Remove duplicates and sort
        return sorted(list(set(all_files)))
    
    @staticmethod
    def create_temp_directory(prefix: str = "harborpilot_test_") -> Path:
        """
        Create temporary directory
        
        Args:
            prefix: Directory name prefix
            
        Returns:
            Temporary directory path
        """
        temp_dir = Path(tempfile.mkdtemp(prefix=prefix))
        logger.debug(f"Created temp directory: {temp_dir}")
        return temp_dir
    
    @staticmethod
    def create_temp_file(content: str = "", prefix: str = "harborpilot_test_", suffix: str = ".tmp") -> Path:
        """
        Create temporary file
        
        Args:
            content: File content
            prefix: File name prefix
            suffix: File name suffix
            
        Returns:
            Temporary file path
        """
        with tempfile.NamedTemporaryFile(mode='w', prefix=prefix, suffix=suffix, delete=False) as f:
            f.write(content)
            temp_file = Path(f.name)
        
        logger.debug(f"Created temp file: {temp_file}")
        return temp_file
    
    @staticmethod
    def file_exists(path: Union[str, Path]) -> bool:
        """
        Check if file exists
        
        Args:
            path: File path
            
        Returns:
            True if file exists
        """
        return Path(path).is_file()
    
    @staticmethod
    def directory_exists(path: Union[str, Path]) -> bool:
        """
        Check if directory exists
        
        Args:
            path: Directory path
            
        Returns:
            True if directory exists
        """
        return Path(path).is_dir()
    
    @staticmethod
    def get_relative_path(path: Union[str, Path], base: Union[str, Path]) -> Path:
        """
        Get relative path
        
        Args:
            path: Target path
            base: Base path
            
        Returns:
            Relative path
        """
        path_obj = Path(path).resolve()
        base_obj = Path(base).resolve()
        
        try:
            return path_obj.relative_to(base_obj)
        except ValueError:
            # If not relative, return absolute path
            return path_obj
    
    @staticmethod
    def join_paths(*paths) -> Path:
        """
        Join paths
        
        Args:
            *paths: Path components
            
        Returns:
            Joined path
        """
        return Path(*paths)
    
    @staticmethod
    def get_file_extension(path: Union[str, Path]) -> str:
        """
        Get file extension
        
        Args:
            path: File path
            
        Returns:
            File extension (with dot)
        """
        return Path(path).suffix
    
    @staticmethod
    def get_file_stem(path: Union[str, Path]) -> str:
        """
        Get file stem (name without extension)
        
        Args:
            path: File path
            
        Returns:
            File stem
        """
        return Path(path).stem
    
    @staticmethod
    def change_extension(path: Union[str, Path], new_extension: str) -> Path:
        """
        Change file extension
        
        Args:
            path: File path
            new_extension: New extension (with or without dot)
            
        Returns:
            Path with new extension
        """
        if not new_extension.startswith('.'):
            new_extension = '.' + new_extension
        
        return Path(path).with_suffix(new_extension)
    
    @staticmethod
    def count_lines_in_file(path: Union[str, Path]) -> int:
        """
        Count lines in file
        
        Args:
            path: File path
            
        Returns:
            Number of lines
        """
        path_obj = Path(path)
        
        if not path_obj.exists():
            raise FileNotFoundError(f"File not found: {path_obj}")
        
        with open(path_obj, 'r', encoding='utf-8') as f:
            return sum(1 for _ in f)
    
    @staticmethod
    def is_text_file(path: Union[str, Path], sample_size: int = 1024) -> bool:
        """
        Check if file is text file
        
        Args:
            path: File path
            sample_size: Number of bytes to sample
            
        Returns:
            True if text file
        """
        path_obj = Path(path)
        
        if not path_obj.exists():
            raise FileNotFoundError(f"File not found: {path_obj}")
        
        try:
            with open(path_obj, 'rb') as f:
                sample = f.read(sample_size)
            
            # Try to decode as UTF-8
            sample.decode('utf-8')
            return True
        except UnicodeDecodeError:
            return False


# Convenience functions
def ensure_directory(path: Union[str, Path]) -> Path:
    """Ensure directory exists"""
    return FileUtils.ensure_directory(path)


def create_file(path: Union[str, Path], content: str = "") -> Path:
    """Create file with content"""
    return FileUtils.create_file(path, content)


def read_file(path: Union[str, Path]) -> str:
    """Read file content"""
    return FileUtils.read_file(path)


def read_json_file(path: Union[str, Path]) -> Dict[str, Any]:
    """Read JSON file"""
    return FileUtils.read_json_file(path)


def write_json_file(path: Union[str, Path], data: Dict[str, Any]) -> None:
    """Write JSON file"""
    return FileUtils.write_json_file(path, data)


def delete_directory(path: Union[str, Path]) -> bool:
    """Delete directory"""
    return FileUtils.delete_directory(path)


def create_temp_directory(prefix: str = "harborpilot_test_") -> Path:
    """Create temporary directory"""
    return FileUtils.create_temp_directory(prefix)
