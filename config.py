import os
from typing import Dict, Any
from dataclasses import dataclass
from pathlib import Path

@dataclass
class APIConfig:
    """API configuration settings"""
    base_url: str
    timeout: int = 30
    retry_attempts: int = 3
    api_key_header: str = "X-API-Key"
    content_type: str = "application/json"

@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    host: str
    port: int
    database: str
    username: str
    password: str
    connection_pool_size: int = 10

@dataclass
class LoggingConfig:
    """Logging configuration settings"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: str = "logs/app.log"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5

@dataclass
class AppConfig:
    """Main application configuration"""
    name: str = "Anubis Forensics"
    version: str = "1.0.0"
    debug: bool = False
    data_dir: str = "data"
    temp_dir: str = "temp"
    max_file_size: int = 100 * 1024 * 1024  # 100MB

class Config:
    """Centralized configuration management"""
    
    def __init__(self):
        self._load_environment()
        self._setup_directories()
    
    def _load_environment(self):
        """Load configuration from environment variables"""
        # API Configuration
        self.api = APIConfig(
            base_url=os.getenv("API_BASE_URL", "http://localhost:8000/api/v1"),
            timeout=int(os.getenv("API_TIMEOUT", "30")),
            retry_attempts=int(os.getenv("API_RETRY_ATTEMPTS", "3")),
            api_key_header=os.getenv("API_KEY_HEADER", "X-API-Key"),
            content_type=os.getenv("API_CONTENT_TYPE", "application/json")
        )
        
        # Database Configuration
        self.database = DatabaseConfig(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "anubis_forensics"),
            username=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
            connection_pool_size=int(os.getenv("DB_POOL_SIZE", "10"))
        )
        
        # Logging Configuration
        self.logging = LoggingConfig(
            level=os.getenv("LOG_LEVEL", "INFO"),
            format=os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
            file_path=os.getenv("LOG_FILE", "logs/app.log"),
            max_file_size=int(os.getenv("LOG_MAX_SIZE", str(10 * 1024 * 1024))),
            backup_count=int(os.getenv("LOG_BACKUP_COUNT", "5"))
        )
        
        # Application Configuration
        self.app = AppConfig(
            name=os.getenv("APP_NAME", "Anubis Forensics"),
            version=os.getenv("APP_VERSION", "1.0.0"),
            debug=os.getenv("DEBUG", "False").lower() == "true",
            data_dir=os.getenv("DATA_DIR", "data"),
            temp_dir=os.getenv("TEMP_DIR", "temp"),
            max_file_size=int(os.getenv("MAX_FILE_SIZE", str(100 * 1024 * 1024)))
        )
    
    def _setup_directories(self):
        """Create necessary directories"""
        directories = [
            self.app.data_dir,
            self.app.temp_dir,
            os.path.dirname(self.logging.file_path)
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def get_api_endpoint(self, endpoint: str) -> str:
        """Get full API endpoint URL"""
        return f"{self.api.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "api": {
                "base_url": self.api.base_url,
                "timeout": self.api.timeout,
                "retry_attempts": self.api.retry_attempts,
                "api_key_header": self.api.api_key_header,
                "content_type": self.api.content_type
            },
            "database": {
                "host": self.database.host,
                "port": self.database.port,
                "database": self.database.database,
                "username": self.database.username,
                "connection_pool_size": self.database.connection_pool_size
            },
            "logging": {
                "level": self.logging.level,
                "format": self.logging.format,
                "file_path": self.logging.file_path,
                "max_file_size": self.logging.max_file_size,
                "backup_count": self.logging.backup_count
            },
            "app": {
                "name": self.app.name,
                "version": self.app.version,
                "debug": self.app.debug,
                "data_dir": self.app.data_dir,
                "temp_dir": self.app.temp_dir,
                "max_file_size": self.app.max_file_size
            }
        }

# Global configuration instance
config = Config() 