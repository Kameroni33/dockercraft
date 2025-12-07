from mcrcon import MCRcon
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class RCONClient:
    """RCON client wrapper"""
    
    def __init__(self, host: str, password: str, port: int = 25575, timeout: int = 10):
        self.host = host
        self.password = password
        self.port = port
        self.timeout = timeout
    
    async def execute(self, command: str) -> Optional[str]:
        """Execute RCON command"""
        try:
            with MCRcon(self.host, self.password, port=self.port, timeout=self.timeout) as mcr:
                response = mcr.command(command)
                logger.info(f"RCON command '{command}' executed successfully")
                return response
        except Exception as e:
            logger.error(f"RCON command failed: {e}")
            return None
    
    async def get_player_count(self) -> tuple[int, int]:
        """Get online and max players"""
        try:
            response = await self.execute("list")
            if response:
                # Parse "There are X of a max of Y players online"
                parts = response.split()
                if len(parts) >= 8:
                    online = int(parts[2])
                    max_players = int(parts[6])
                    return online, max_players
        except Exception as e:
            logger.error(f"Failed to get player count: {e}")
        return 0, 20