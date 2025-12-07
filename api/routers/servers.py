from fastapi import APIRouter, HTTPException, status
from typing import List
import logging

from models import ServerInfo, ServerCreate, CommandRequest, CommandResponse, ServerStatus
from services.docker_manager import DockerManager
from services.minecraft import MinecraftService
from datetime import datetime

router = APIRouter()
logger = logging.getLogger(__name__)

docker_manager = DockerManager()
minecraft_service = MinecraftService()

@router.get("", response_model=List[ServerInfo])
async def list_servers():
    """List all server instances"""
    return await minecraft_service.list_servers()

@router.get("/{server_id}", response_model=ServerInfo)
async def get_server(server_id: str):
    """Get server details"""
    server = await minecraft_service.get_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server

@router.post("", response_model=ServerInfo, status_code=status.HTTP_201_CREATED)
async def create_server(server: ServerCreate):
    """Create new server instance"""
    try:
        return await minecraft_service.create_server(server)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(server_id: str):
    """Delete server instance"""
    success = await minecraft_service.delete_server(server_id)
    if not success:
        raise HTTPException(status_code=404, detail="Server not found")

@router.post("/{server_id}/start")
async def start_server(server_id: str):
    """Start server"""
    success = await minecraft_service.start_server(server_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to start server")
    return {"message": f"Server {server_id} starting"}

@router.post("/{server_id}/stop")
async def stop_server(server_id: str):
    """Stop server gracefully"""
    success = await minecraft_service.stop_server(server_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to stop server")
    return {"message": f"Server {server_id} stopping"}

@router.post("/{server_id}/restart")
async def restart_server(server_id: str):
    """Restart server"""
    await minecraft_service.stop_server(server_id)
    await minecraft_service.start_server(server_id)
    return {"message": f"Server {server_id} restarting"}

@router.post("/{server_id}/command", response_model=CommandResponse)
async def execute_command(server_id: str, cmd: CommandRequest):
    """Execute server command via RCON"""
    response = await minecraft_service.execute_command(server_id, cmd.command)
    if response is None:
        raise HTTPException(status_code=400, detail="Failed to execute command")
    
    return CommandResponse(
        success=True,
        response=response,
        timestamp=datetime.now()
    )

@router.get("/{server_id}/logs")
async def get_logs(server_id: str, lines: int = 100):
    """Get server logs"""
    logs = await minecraft_service.get_logs(server_id, lines)
    return {"logs": logs}