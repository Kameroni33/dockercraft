from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from enum import Enum
from datetime import datetime

class ServerStatus(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    STARTING = "starting"
    STOPPING = "stopping"
    ERROR = "error"

class ServerType(str, Enum):
    VANILLA = "vanilla"
    PAPER = "paper"
    FABRIC = "fabric"
    FORGE = "forge"
    SPIGOT = "spigot"

class ServerInfo(BaseModel):
    """Server instance information"""
    id: str
    name: str
    type: ServerType
    version: str
    status: ServerStatus
    port: int
    rcon_port: int
    memory_min: str
    memory_max: str
    players_online: int = 0
    players_max: int = 20
    enabled: bool = True

class ServerCreate(BaseModel):
    """Create new server instance"""
    id: str = Field(..., description="Unique server ID")
    name: str
    type: ServerType = ServerType.PAPER
    version: str = "1.21"
    memory_min: str = "2G"
    memory_max: str = "4G"
    port: int = 25565
    rcon_port: int = 25575

class CommandRequest(BaseModel):
    """Execute server command"""
    command: str

class CommandResponse(BaseModel):
    """Command execution response"""
    success: bool
    response: str
    timestamp: datetime

class BackupInfo(BaseModel):
    """Backup information"""
    id: str
    server_id: str
    filename: str
    size: int
    created_at: datetime

class BackupCreate(BaseModel):
    """Create backup request"""
    server_id: str
    description: Optional[str] = None

class ModInfo(BaseModel):
    """Mod information from Modrinth"""
    slug: str
    title: str
    description: str
    downloads: int
    icon_url: Optional[str]
    versions: List[str]

class ModInstall(BaseModel):
    """Install mod request"""
    server_id: str
    mod_slug: str
    version: str