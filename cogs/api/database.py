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


database = Database()