"""
In-memory WebSocket connection manager for driver real-time notifications.
Single-server solution — for multi-server scale, replace with Redis pub/sub fanout.
"""
import asyncio
from typing import Dict, Set
from fastapi import WebSocket
import structlog

logger = structlog.get_logger()


class DriverWSManager:
    def __init__(self):
        # driver_id (str) → WebSocket
        self._connections: Dict[str, WebSocket] = {}

    async def connect(self, driver_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[driver_id] = ws
        logger.info("driver_ws_connected", driver_id=driver_id, total=len(self._connections))

    def disconnect(self, driver_id: str) -> None:
        self._connections.pop(driver_id, None)
        logger.info("driver_ws_disconnected", driver_id=driver_id, total=len(self._connections))

    @property
    def connected_ids(self) -> Set[str]:
        return set(self._connections.keys())

    async def send(self, driver_id: str, payload: dict) -> bool:
        ws = self._connections.get(driver_id)
        if not ws:
            return False
        try:
            await ws.send_json(payload)
            return True
        except Exception:
            self.disconnect(driver_id)
            return False

    async def broadcast_new_order(self, order_payload: dict, available_driver_ids: Set[str]) -> int:
        """Send new-order notification to all connected available drivers."""
        targets = set(self._connections.keys()) & available_driver_ids
        if not targets:
            return 0
        tasks = [self.send(did, {"type": "new_order", "order": order_payload}) for did in targets]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        sent = sum(1 for r in results if r is True)
        logger.info("driver_order_broadcast", sent=sent, targets=len(targets))
        return sent


# Singleton shared across the app
driver_ws = DriverWSManager()
