from fastapi import APIRouter, HTTPException
from typing import List
import logging

from models import BackupInfo, BackupCreate
from services.backup_service import BackupService

router = APIRouter()
logger = logging.getLogger(__name__)

backup_service = BackupService()

@router.get("/{server_id}", response_model=List[BackupInfo])
async def list_backups(server_id: str):
    """List all backups for server"""
    return await backup_service.list_backups(server_id)

@router.post("/", response_model=BackupInfo)
async def create_backup(backup: BackupCreate):
    """Create new backup"""
    try:
        return await backup_service.create_backup(backup.server_id, backup.description)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{backup_id}/restore")
async def restore_backup(backup_id: str):
    """Restore from backup"""
    try:
        success = await backup_service.restore_backup(backup_id)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to restore backup")
        return {"message": "Backup restored successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{backup_id}")
async def delete_backup(backup_id: str):
    """Delete backup"""
    success = await backup_service.delete_backup(backup_id)
    if not success:
        raise HTTPException(status_code=404, detail="Backup not found")
    return {"message": "Backup deleted"}