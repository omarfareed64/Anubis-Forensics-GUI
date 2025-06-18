import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional
from config import config

class Logger:
    """Centralized logging utility"""
    
    _loggers = {}
    
    @classmethod
    def get_logger(cls, name: str = "anubis") -> logging.Logger:
        """Get or create a logger instance"""
        if name not in cls._loggers:
            cls._loggers[name] = cls._create_logger(name)
        return cls._loggers[name]
    
    @classmethod
    def _create_logger(cls, name: str) -> logging.Logger:
        """Create a new logger instance"""
        logger = logging.getLogger(name)
        
        # Avoid duplicate handlers
        if logger.handlers:
            return logger
        
        # Set log level
        logger.setLevel(getattr(logging, config.logging.level.upper()))
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            fmt=config.logging.format,
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        simple_formatter = logging.Formatter(
            fmt="%(levelname)s - %(message)s"
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        logger.addHandler(console_handler)
        
        # File handler with rotation
        log_file = Path(config.logging.file_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=config.logging.max_file_size,
            backupCount=config.logging.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)
        
        # Error file handler
        error_log_file = log_file.parent / f"{log_file.stem}_error{log_file.suffix}"
        error_handler = logging.handlers.RotatingFileHandler(
            filename=error_log_file,
            maxBytes=config.logging.max_file_size,
            backupCount=config.logging.backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        logger.addHandler(error_handler)
        
        return logger
    
    @classmethod
    def setup_qt_logging(cls):
        """Setup logging for PyQt5"""
        qt_logger = cls.get_logger("PyQt5")
        
        # Redirect Qt messages to our logger
        def qt_message_handler(message_type, context, message):
            if message_type == 0:  # QtInfoMsg
                qt_logger.info(f"Qt Info: {message}")
            elif message_type == 1:  # QtWarningMsg
                qt_logger.warning(f"Qt Warning: {message}")
            elif message_type == 2:  # QtCriticalMsg
                qt_logger.error(f"Qt Critical: {message}")
            elif message_type == 3:  # QtFatalMsg
                qt_logger.critical(f"Qt Fatal: {message}")
        
        # Install Qt message handler
        try:
            from PyQt5.QtCore import qInstallMessageHandler
            qInstallMessageHandler(qt_message_handler)
        except ImportError:
            pass

# Convenience functions
def get_logger(name: str = "anubis") -> logging.Logger:
    """Get a logger instance"""
    return Logger.get_logger(name)

def log_function_call(func):
    """Decorator to log function calls"""
    def wrapper(*args, **kwargs):
        logger = get_logger()
        logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
        try:
            result = func(*args, **kwargs)
            logger.debug(f"{func.__name__} returned {result}")
            return result
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
            raise
    return wrapper

def log_exceptions(logger_name: str = "anubis"):
    """Decorator to log exceptions"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_logger(logger_name)
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Exception in {func.__name__}: {e}", exc_info=True)
                raise
        return wrapper
    return decorator 