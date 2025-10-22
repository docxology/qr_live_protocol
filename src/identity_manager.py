"""
Identity Manager module for QRLP.

Handles user identity creation, management, and cryptographic hashing
for QR code verification and authenticity.
"""

import os
import hashlib
import platform
import uuid
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, asdict

from .config import IdentitySettings


@dataclass
class IdentityInfo:
    """Identity information structure."""
    identity_hash: str
    creation_time: datetime
    system_info: Dict[str, Any]
    file_hashes: Dict[str, str]
    custom_data: Dict[str, Any]
    version: str = "1.0"


class IdentityManager:
    """
    Identity management for QRLP.
    
    Creates and manages user identity hashes based on files, system information,
    and custom data to provide unique identification for QR codes.
    """
    
    def __init__(self, settings: IdentitySettings):
        """
        Initialize identity manager with settings.
        
        Args:
            settings: IdentitySettings configuration object
        """
        self.settings = settings
        self.identity_info: Optional[IdentityInfo] = None
        self.cached_hash: Optional[str] = None
        self.last_hash_time = 0
        
        # Statistics
        self.hash_generations = 0
        self.file_reads = 0
        self.system_info_queries = 0
        
        # Initialize identity
        self._initialize_identity()
    
    def get_identity_hash(self) -> str:
        """
        Get current identity hash.
        
        Returns:
            SHA-256 hash string representing current identity
        """
        # Return cached hash if recent and no settings require updates
        current_time = time.time()
        if (self.cached_hash and 
            current_time - self.last_hash_time < 60 and  # Cache for 1 minute
            not self._identity_changed()):
            return self.cached_hash
        
        # Generate new hash
        self.cached_hash = self._generate_identity_hash()
        self.last_hash_time = current_time
        self.hash_generations += 1
        
        return self.cached_hash
    
    def get_identity_info(self) -> Optional[IdentityInfo]:
        """Get complete identity information."""
        return self.identity_info
    
    def update_custom_data(self, key: str, value: Any) -> None:
        """
        Update custom data in identity.
        
        Args:
            key: Data key
            value: Data value
        """
        if not self.identity_info:
            self._initialize_identity()
        
        if self.identity_info:
            self.identity_info.custom_data[key] = value
            # Invalidate cached hash
            self.cached_hash = None
    
    def add_file_to_identity(self, file_path: str, alias: Optional[str] = None) -> bool:
        """
        Add a file hash to the identity.
        
        Args:
            file_path: Path to file to include in identity
            alias: Optional alias for the file
            
        Returns:
            True if file was successfully added
        """
        try:
            if not os.path.exists(file_path):
                return False
            
            file_hash = self._calculate_file_hash(file_path)
            key = alias or os.path.basename(file_path)
            
            if not self.identity_info:
                self._initialize_identity()
            
            if self.identity_info:
                self.identity_info.file_hashes[key] = file_hash
                # Invalidate cached hash
                self.cached_hash = None
                self.file_reads += 1
                return True
            
            return False
            
        except Exception as e:
            print(f"Error adding file to identity: {e}")
            return False
    
    def remove_file_from_identity(self, file_key: str) -> bool:
        """
        Remove a file from identity.
        
        Args:
            file_key: Key of file to remove
            
        Returns:
            True if file was removed
        """
        if self.identity_info and file_key in self.identity_info.file_hashes:
            del self.identity_info.file_hashes[file_key]
            self.cached_hash = None
            return True
        return False
    
    def export_identity(self, file_path: str) -> bool:
        """
        Export identity information to file.
        
        Args:
            file_path: Path to save identity file
            
        Returns:
            True if export was successful
        """
        try:
            if not self.identity_info:
                return False
            
            # Convert to JSON-serializable format
            export_data = asdict(self.identity_info)
            export_data['creation_time'] = self.identity_info.creation_time.isoformat()
            
            with open(file_path, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Error exporting identity: {e}")
            return False
    
    def import_identity(self, file_path: str) -> bool:
        """
        Import identity information from file.
        
        Args:
            file_path: Path to identity file
            
        Returns:
            True if import was successful
        """
        try:
            if not os.path.exists(file_path):
                return False
            
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Reconstruct identity info
            self.identity_info = IdentityInfo(
                identity_hash=data['identity_hash'],
                creation_time=datetime.fromisoformat(data['creation_time']),
                system_info=data['system_info'],
                file_hashes=data['file_hashes'],
                custom_data=data['custom_data'],
                version=data.get('version', '1.0')
            )
            
            # Invalidate cached hash
            self.cached_hash = None
            return True
            
        except Exception as e:
            print(f"Error importing identity: {e}")
            return False
    
    def get_statistics(self) -> Dict:
        """Get identity manager statistics."""
        return {
            "hash_generations": self.hash_generations,
            "file_reads": self.file_reads,
            "system_info_queries": self.system_info_queries,
            "has_identity": self.identity_info is not None,
            "cached_hash": self.cached_hash is not None,
            "last_hash_time": self.last_hash_time,
            "file_count": len(self.identity_info.file_hashes) if self.identity_info else 0
        }
    
    def _initialize_identity(self) -> None:
        """Initialize identity information."""
        # Try to load from file if specified
        if (self.settings.identity_file and 
            os.path.exists(self.settings.identity_file)):
            if self.import_identity(self.settings.identity_file):
                return
        
        # Create new identity if auto-generate is enabled
        if self.settings.auto_generate:
            self._create_new_identity()
        else:
            self.identity_info = None
    
    def _create_new_identity(self) -> None:
        """Create a new identity."""
        system_info = {}
        file_hashes = {}
        
        # Collect system information if enabled
        if self.settings.include_system_info:
            system_info = self._collect_system_info()
        
        # Include identity file hash if specified
        if (self.settings.include_file_hash and 
            self.settings.identity_file and 
            os.path.exists(self.settings.identity_file)):
            file_hashes['identity_file'] = self._calculate_file_hash(self.settings.identity_file)
        
        # Create identity info
        self.identity_info = IdentityInfo(
            identity_hash="",  # Will be calculated
            creation_time=datetime.now(timezone.utc),
            system_info=system_info,
            file_hashes=file_hashes,
            custom_data={}
        )
        
        # Generate the actual hash
        self.cached_hash = self._generate_identity_hash()
        self.identity_info.identity_hash = self.cached_hash
        self.last_hash_time = time.time()
        self.hash_generations += 1
    
    def _generate_identity_hash(self) -> str:
        """Generate cryptographic hash of identity."""
        if not self.identity_info:
            return ""
        
        # Collect all identity components
        components = []
        
        # Add system info
        if self.identity_info.system_info:
            system_str = json.dumps(self.identity_info.system_info, sort_keys=True)
            components.append(f"system:{system_str}")
        
        # Add current file hashes (recalculate from actual files)
        if self.identity_info.file_hashes:
            current_file_hashes = {}
            for filename, stored_hash in self.identity_info.file_hashes.items():
                # Determine the actual file path
                file_path = None
                if (filename == 'identity_file' and
                    self.settings.identity_file and
                    os.path.exists(self.settings.identity_file)):
                    file_path = self.settings.identity_file
                elif (self.settings.identity_file and
                      filename == os.path.basename(self.settings.identity_file)):
                    file_path = self.settings.identity_file
                elif os.path.exists(filename):
                    file_path = filename

                if file_path and os.path.exists(file_path):
                    current_file_hashes[filename] = self._calculate_file_hash(file_path)
                else:
                    current_file_hashes[filename] = stored_hash  # Keep stored hash if file not found

            files_str = json.dumps(current_file_hashes, sort_keys=True)
            components.append(f"files:{files_str}")
        
        # Add custom data
        if self.identity_info.custom_data:
            custom_str = json.dumps(self.identity_info.custom_data, sort_keys=True)
            components.append(f"custom:{custom_str}")
        
        # Add creation time
        components.append(f"created:{self.identity_info.creation_time.isoformat()}")
        
        # Combine and hash
        combined = "|".join(components)
        
        if self.settings.hash_algorithm == "sha256":
            return hashlib.sha256(combined.encode('utf-8')).hexdigest()
        elif self.settings.hash_algorithm == "sha512":
            return hashlib.sha512(combined.encode('utf-8')).hexdigest()
        elif self.settings.hash_algorithm == "md5":
            return hashlib.md5(combined.encode('utf-8')).hexdigest()
        else:
            # Default to SHA-256
            return hashlib.sha256(combined.encode('utf-8')).hexdigest()
    
    def _collect_system_info(self) -> Dict[str, Any]:
        """Collect system information for identity."""
        self.system_info_queries += 1
        
        try:
            info = {
                "platform": platform.platform(),
                "system": platform.system(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
                "hostname": platform.node(),
                "username": os.getenv('USER') or os.getenv('USERNAME') or 'unknown',
                "mac_address": ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff) 
                                       for ele in range(0,8*6,8)][::-1])
            }
            
            # Add working directory
            info["working_directory"] = os.getcwd()
            
            # Add environment variables (selective)
            env_vars = ['PATH', 'HOME', 'USERPROFILE', 'COMPUTERNAME', 'HOSTNAME']
            info["environment"] = {
                var: os.getenv(var, '') for var in env_vars if os.getenv(var)
            }
            
            return info
            
        except Exception as e:
            return {"error": str(e)}
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate hash of a file."""
        try:
            hash_obj = hashlib.new(self.settings.hash_algorithm)
            
            with open(file_path, 'rb') as f:
                # Read file in chunks to handle large files
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_obj.update(chunk)
            
            return hash_obj.hexdigest()
            
        except Exception as e:
            return f"error:{str(e)}"
    
    def _identity_changed(self) -> bool:
        """Check if identity components have changed."""
        if not self.identity_info:
            return True

        # Check all tracked files for changes
        for filename, stored_hash in self.identity_info.file_hashes.items():
            # Determine the actual file path to check
            file_path = None

            # If it's the identity_file from settings
            if (filename == 'identity_file' and
                self.settings.identity_file and
                os.path.exists(self.settings.identity_file)):
                file_path = self.settings.identity_file
            # If it's an alias that matches the identity file basename
            elif (self.settings.identity_file and
                  filename == os.path.basename(self.settings.identity_file)):
                file_path = self.settings.identity_file
            # If the filename itself is a valid path
            elif os.path.exists(filename):
                file_path = filename

            if file_path and os.path.exists(file_path):
                current_hash = self._calculate_file_hash(file_path)
                if current_hash != stored_hash:
                    return True

        return False 