from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import logging

from services.minecraft import MinecraftService

router = APIRouter()
logger = logging.getLogger(__name__)

minecraft_service = MinecraftService()

@router.websocket("/console/{server_id}")
async def websocket_console(websocket: WebSocket, server_id: str):
    """WebSocket endpoint for live console"""
    await websocket.accept()
    
    try:
        # Send initial logs
        logs = await minecraft_service.get_logs(server_id, lines=50)
        await websocket.send_json({
            "type": "logs",
            "data": logs
        })
        
        # Keep connection alive and handle commands
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "command":
                command = data.get("command", "")
                response = await minecraft_service.execute_command(server_id, command)
                
                await websocket.send_json({
                    "type": "response",
                    "command": command,
                    "response": response or "No response"
                })
            
            # Sleep briefly to prevent tight loop
            await asyncio.sleep(0.1)
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for server {server_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")