import docker
from docker.models.containers import Container
from typing import Optional, List, Dict
import logging

from config import settings, setup_logging

setup_logging()
logger = logging.getLogger(__name__)

class DockerManager:
    """Manage Docker containers"""
    
    def __init__(self):
        try:
            self.client = docker.from_env()
            logger.info("Docker client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            self.client = None
    
    def get_container(self, name: str) -> Optional[Container]:
        """Get container by name"""
        try:
            return self.client.containers.get(name)
        except docker.errors.NotFound:
            return None
        except Exception as e:
            logger.error(f"Error getting container {name}: {e}")
            raise None
    
    def list_containers(self, prefix: str = "dockercraft-minecraft") -> List[Container]:
        """List all minecraft containers"""
        try:
            return self.client.containers.list(
                all=True,
                filters={"name": prefix}
            )
        except Exception as e:
            logger.error(f"Error listing containers: {e}")
            return []
    
    def create_container(self, name: str, config: Dict) -> Optional[Container]:
        """Create new container"""
        try:
            container = self.client.containers.create(
                image="dockercraft-minecraft:latest",
                name=name,
                detach=True,
                **config
            )
            logger.info(f"Container {name} created")
            return container
        except Exception as e:
            logger.error(f"Failed to create container {name}: {e}")
            return None
    
    def start_container(self, name: str) -> bool:
        """Start container"""
        container = self.get_container(name)
        if container:
            try:
                container.start()
                logger.info(f"Container {name} started")
                return True
            except Exception as e:
                logger.error(f"Failed to start container {name}: {e}")
        return False
    
    def stop_container(self, name: str) -> bool:
        """Stop container"""
        container = self.get_container(name)
        if container:
            try:
                container.stop(timeout=30)
                logger.info(f"Container {name} stopped")
                return True
            except Exception as e:
                logger.error(f"Failed to stop container {name}: {e}")
        return False
    
    def remove_container(self, name: str) -> bool:
        """Remove container"""
        container = self.get_container(name)
        if container:
            try:
                container.remove(force=True)
                logger.info(f"Container {name} removed")
                return True
            except Exception as e:
                logger.error(f"Failed to remove container {name}: {e}")
        return False
    
    def get_container_status(self, name: str) -> str:
        """Get container status"""
        container = self.get_container(name)
        if container:
            return container.status
        return "not_found"
