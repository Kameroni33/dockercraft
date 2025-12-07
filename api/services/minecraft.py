from typing import List, Optional
from pathlib import Path
import logging
import yaml

from models import ServerInfo, ServerCreate, ServerStatus, ServerType
from services.docker_manager import DockerManager
from utils.rcon import RCONClient
from config import settings, setup_logging, load_config, save_config

setup_logging()
logger = logging.getLogger(__name__)

class MinecraftService:
    """Minecraft server management service"""
    
    def __init__(self):
        self.docker = DockerManager()
        self.config_path = Path("/config/servers.yml")
    
    def _get_container_name(self, server_id: str) -> str:
        """Get container name for server"""
        return f"dockercraft-minecraft-{server_id}"
    
    def _get_rcon_client(self, server_id: str) -> Optional[RCONClient]:
        """Get RCON client for server"""
        container_name = self._get_container_name(server_id)
        config = load_config("servers")
        
        if server_id not in config.get("instances", {}):
            return None
        
        instance = config["instances"][server_id]
        
        # Use container name as hostname in Docker network
        return RCONClient(
            host=container_name,
            password=settings.rcon_password,
            port=instance.get("rcon_port", 25575),
            timeout=settings.rcon_timeout
        )
    
    async def list_servers(self) -> List[ServerInfo]:
        """List all configured servers"""
        config = load_config("servers")
        servers = []
        
        for server_id, instance in config.get("instances", {}).items():
            container_name = self._get_container_name(server_id)
            container_status = self.docker.get_container_status(container_name)
            
            # Map Docker status to ServerStatus
            if container_status == "running":
                status = ServerStatus.RUNNING
            elif container_status in ["created", "restarting"]:
                status = ServerStatus.STARTING
            elif container_status == "exited":
                status = ServerStatus.STOPPED
            else:
                status = ServerStatus.ERROR
            
            # Get player count if running
            players_online = 0
            players_max = 20
            if status == ServerStatus.RUNNING:
                rcon = self._get_rcon_client(server_id)
                if rcon:
                    players_online, players_max = await rcon.get_player_count()
            
            servers.append(ServerInfo(
                id=server_id,
                name=instance.get("name", server_id),
                type=ServerType(instance.get("type", "paper")),
                version=instance.get("version", "unknown"),
                status=status,
                port=instance.get("port", 25565),
                rcon_port=instance.get("rcon_port", 25575),
                memory_min=instance.get("memory_min", "2G"),
                memory_max=instance.get("memory_max", "4G"),
                players_online=players_online,
                players_max=players_max,
                enabled=instance.get("enabled", True)
            ))
        
        return servers
    
    async def get_server(self, server_id: str) -> Optional[ServerInfo]:
        """Get specific server"""
        servers = await self.list_servers()
        for server in servers:
            if server.id == server_id:
                return server
        return None
    
    async def create_server(self, server: ServerCreate) -> ServerInfo:
        """Create new server instance"""
        config = load_config("servers")
        
        # Check if server already exists
        if server.id in config.get("instances", {}):
            raise ValueError(f"Server {server.id} already exists")
        
        # Create instance directory
        instance_path = settings.instances_path / server.id
        instance_path.mkdir(parents=True, exist_ok=True)
        
        # Create backup and log directories
        (settings.backups_path / server.id).mkdir(parents=True, exist_ok=True)
        (settings.logs_path / server.id).mkdir(parents=True, exist_ok=True)
        
        # Add to config
        if "instances" not in config:
            config["instances"] = {}
        
        config["instances"][server.id] = {
            "name": server.name,
            "type": server.type.value,
            "version": server.version,
            "memory_min": server.memory_min,
            "memory_max": server.memory_max,
            "port": server.port,
            "rcon_port": server.rcon_port,
            "enabled": True,
            "auto_backup": False
        }
        
        save_config("servers", config)
        
        # Create Docker container
        container_name = self._get_container_name(server.id)
        container_config = {
            "ports": {
                "25565/tcp": server.port,
                "25575/tcp": server.rcon_port
            },
            "volumes": {
                str(instance_path): {"bind": "/minecraft", "mode": "rw"}
            },
            "environment": {
                "MEMORY_MIN": server.memory_min,
                "MEMORY_MAX": server.memory_max,
                "RCON_PASSWORD": settings.rcon_password,
                "RCON_PORT": str(server.rcon_port)
            },
            "network": "dockercraft_dockercraft"
        }
        
        container = self.docker.create_container(container_name, container_config)
        if not container:
            raise RuntimeError("Failed to create Docker container")
        
        logger.info(f"Created server {server.id}")
        return await self.get_server(server.id)
    
    async def delete_server(self, server_id: str) -> bool:
        """Delete server instance"""
        config = load_config("servers")
        
        if server_id not in config.get("instances", {}):
            return False
        
        # Stop and remove container
        container_name = self._get_container_name(server_id)
        self.docker.stop_container(container_name)
        self.docker.remove_container(container_name)
        
        # Remove from config
        del config["instances"][server_id]
        save_config("servers", config)
        
        logger.info(f"Deleted server {server_id}")
        return True
    
    async def start_server(self, server_id: str) -> bool:
        """Start server"""
        container_name = self._get_container_name(server_id)
        return self.docker.start_container(container_name)
    
    async def stop_server(self, server_id: str) -> bool:
        """Stop server gracefully"""
        # Try graceful shutdown via RCON first
        rcon = self._get_rcon_client(server_id)
        if rcon:
            await rcon.execute("stop")
        
        # Then stop container
        container_name = self._get_container_name(server_id)
        return self.docker.stop_container(container_name)
    
    async def execute_command(self, server_id: str, command: str) -> Optional[str]:
        """Execute command on server"""
        rcon = self._get_rcon_client(server_id)
        if not rcon:
            return None
        return await rcon.execute(command)
    
    async def get_logs(self, server_id: str, lines: int = 100) -> str:
        """Get server logs"""
        log_file = settings.logs_path / server_id / "latest.log"
        if not log_file.exists():
            return "No logs available"
        
        try:
            with open(log_file) as f:
                all_lines = f.readlines()
                return "".join(all_lines[-lines:])
        except Exception as e:
            logger.error(f"Failed to read logs: {e}")
            return f"Error reading logs: {e}"