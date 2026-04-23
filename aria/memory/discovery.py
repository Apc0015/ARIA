"""Discovery queue helper."""

from __future__ import annotations

from typing import Any

from aria.memory.shared import SharedMemory


class DiscoveryBus:
    """Small helper for publishing and consuming discoveries."""

    def __init__(self, shared_memory: SharedMemory) -> None:
        self.shared_memory = shared_memory

    async def publish(self, discovery: dict[str, Any]) -> None:
        await self.shared_memory.post_discovery(discovery)

    async def consume_for(self, agent_name: str) -> list[dict[str, Any]]:
        return await self.shared_memory.get_discoveries_for_agent(agent_name)
