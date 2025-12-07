from typing import List, Optional
from pathlib import Path
from datetime import datetime
import tarfile
import logging

from models import BackupInfo
from config import settings

logger = logging.getLogger(__name__)

class BackupService:
    """Backup management service"""
    
    async def list_backups(self, server_id: str) -> List[BackupInfo]:
        """List all backups for server"""
        backup_dir = settings.backups_path / server_id
        if not backup_dir.exists():
            return []
        
        backups = []
        for backup_file in sorted(backup_dir.glob("*.tar.gz"), reverse=True):
            stat = backup_file.stat()
            backups.append(BackupInfo(
                id=backup_file.stem,
                server_id=server_id,
                filename=backup_file.name,
                size=stat.st_size,
                created_at=datetime.fromtimestamp(stat.st_mtime)
            ))
        
        return backups
    
    async def create_backup(self, server_id: str, description: Optional[str] = None) -> BackupInfo:
        """Create new backup"""
        instance_dir = settings.instances_path / server_id
        if not instance_dir.exists():
            raise ValueError(f"Server {server_id} not found")
        
        backup_dir = settings.backups_path / server_id
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_filename = f"backup_{timestamp}.tar.gz"
        backup_path = backup_dir / backup_filename
        
        logger.info(f"Creating backup for {server_id}...")
        
        # Create compressed backup
        with tarfile.open(backup_path, "w:gz") as tar:
            for world_dir in ["world", "world_nether", "world_the_end"]:
                world_path = instance_dir / world_dir
                if world_path.exists():
                    tar.add(world_path, arcname=world_dir)
        
        stat = backup_path.stat()
        logger.info(f"Backup created: {backup_filename} ({stat.st_size} bytes)")
        
        return BackupInfo(
            id=backup_path.stem,
            server_id=server_id,
            filename=backup_filename,
            size=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_mtime)
        )
    
    async def restore_backup(self, backup_id: str) -> bool:
        """Restore from backup"""
        # TODO: Implement restore logic
        logger.warning("Restore not yet implemented")
        return False
    
    async def delete_backup(self, backup_id: str) -> bool:
        """Delete backup"""
        # Find backup file
        for server_dir in settings.backups_path.iterdir():
            if not server_dir.is_dir():
                continue
            
            for backup_file in server_dir.glob(f"{backup_id}.tar.gz"):
                backup_file.unlink()
                logger.info(f"Deleted backup: {backup_id}")
                return True
        
        return False
