import asyncio
from asyncio.events import AbstractEventLoop
from tinydb import TinyDB, Query
from typing import Any

from tinydb.queries import where
from ..utils import *


class Database:
    def __init__(self) -> None:
        self._db: TinyDB = TinyDB("tmp/tinydb.json")
        self.feed = self._db.table("feed")
        self.channels = self._db.table("channels")

    async def feed_insert(self, items: List[Any]) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.feed.insert_multiple, items)

    async def _feed_remove(self, item: Any) -> bool:
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                self.feed.remove,
                (
                    (where("username") == item["username"])
                    & (where("channel") == item["channel"])
                    & (where("type") == item["type"])
                ),
            )
        except:
            return False

        return True

    async def feed_remove(self, items: List[Any]) -> List[bool]:
        tasks = []
        for item in items:
            tasks.append(self._feed_remove(item))

        return await asyncio.gather(*tasks, return_exceptions=True)

    async def feed_get(self) -> List[Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.feed.all)

    async def channel_insert(self, items: List[Any]) -> None:
        loop = asyncio.get_event_loop()

        for item in items:
            for status in ["progress", "planning", "dropped", "paused"]:
                if not f"list_block_{status}" in item:
                    item[f"list_block_{status}"] = False

        await loop.run_in_executor(None, self.channels.insert_multiple, items)

    async def channel_update(self, id, item: Any) -> None:
        loop = asyncio.get_event_loop()

        for status in ["progress", "planning", "dropped", "paused"]:
            if not f"list_block_{status}" in item:
                item[f"list_block_{status}"] = False

        try:
            await loop.run_in_executor(
                None,
                self.channels.update,
                item,
                where("channel") == id,
            )
        except:
            return False

        return True

    async def _channel_remove(self, item: Any) -> bool:
        loop = asyncio.get_event_loop()

        for status in ["progress", "planning", "dropped", "paused"]:
            if not f"list_block_{status}" in item:
                item[f"list_block_{status}"] = False

        try:
            await loop.run_in_executor(
                None,
                self.channels.remove,
                (
                    (where("channel") == item["channel"])
                    & (where("list_block_progress") == item["list_block_progress"])
                    & (where("list_block_planning") == item["list_block_planning"])
                    & (where("list_block_dropped") == item["list_block_dropped"])
                    & (where("list_block_paused") == item["list_block_paused"])
                ),
            )
        except:
            return False

        return True

    async def channel_remove(self, items: List[Any]) -> List[bool]:
        tasks = []
        for item in items:
            tasks.append(self._channel_remove(item))

        return await asyncio.gather(*tasks, return_exceptions=True)

    async def channel_get(self) -> List[Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.channels.all)


database = Database()
