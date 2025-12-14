import os
import yaml
from pydantic_settings import BaseSettings
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler


class Settings(BaseSettings):
    """Application settings"""
    
    # Paths
    data_path: Path = Path("/data")
    config_path: Path = Path("/config")
    instances_path: Path = data_path / "instances"
    backups_path: Path = data_path / "backups"
    logs_path: Path = data_path / "logs"

    # Logs
    log_file: str = "app.log"

    # Authentication
    admin_username: str = "admin"
    admin_password_hash: str = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5eBWXvqJ4Y9qi"  # "changeme"
    auth_enabled: bool = True
    
    # RCON
    rcon_password: str = "changeme"
    rcon_timeout: int = 10
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # Docker
    docker_socket: str = "/var/run/docker.sock"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()


def setup_logging() -> None:
    # Ensure logs directory exists
    os.makedirs(settings.logs_path, exist_ok=True)

    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    root_logger.setLevel(logging.INFO)

    # STDOUT handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)s | %(message)s'
    )
    console_handler.setFormatter(console_formatter)

    # File handler (rotating)
    file_handler = RotatingFileHandler(
        os.path.join(settings.logs_path, settings.log_file),
        maxBytes=5_000_000,   # 5 MB per file
        backupCount=5         # keep last 5 logs
    )
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(name)s:%(lineno)d | %(message)s'
    )
    file_handler.setFormatter(file_formatter)

    # Attach both handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


def initalize_config(config: str) -> None:
    """Initialize configuration YAML file"""
    config_path = Path(f"{settings.config_path}/{config}.yml")
    if not config_path.exists():
        with open(config_path) as file:
            yaml.dump({
            "instances": {},
            "settings": {
                "backup_retention_days": 30,
                "log_retention_days": 7,
                "max_backups_per_instance": 10,
                "rcon_timeout": 10,
            }
        }, file, default_flow_style=False)
    return None


def load_config(config: str) -> dict|None:
    """Load configurations from YAML file"""
    config_path = Path(f"{settings.config_path}/{config}.yml")
    if config_path.exists():
        with open(config_path) as file:
            return yaml.safe_load(file)
    return None


def save_config(config: str, contents: dict) -> None:
    """Save configuration to YAML file"""
    config_path = Path(f"{settings.config_path}/{config}.yml")
    with open(config_path, 'w') as file:
        yaml.dump(contents, file, default_flow_style=False)

