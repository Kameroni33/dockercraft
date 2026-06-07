"""SQLModel table models. Import all models here so init_db sees them."""

from api.models.backup import Backup
from api.models.instance import InstanceCreate, InstanceRead, Loader, ServerInstance
from api.models.mod import InstalledMod
from api.models.player import Player
from api.models.user import User

__all__ = [
    "Backup",
    "InstalledMod",
    "InstanceCreate",
    "InstanceRead",
    "Loader",
    "Player",
    "ServerInstance",
    "User",
]
