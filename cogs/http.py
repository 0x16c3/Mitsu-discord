import aiohttp
import json


class AsyncRequest:
    def __init__(self, _loop):
        self.loop = _loop
        self.session = aiohttp.ClientSession(loop=self.loop)

    async def _request(self, url: str, **kwargs):
        async with self.session as session:
            status_code = -1
            response = None

            if not "type" in kwargs:
                kwargs["type"] = "get"

            if not "headers" in kwargs:
                kwargs["headers"] = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.106 Safari/537.36",
                    "Content-Type": "application/json;charset=UTF-8",
                }

            if kwargs["type"].lower() == "get":
                del kwargs["type"]
                status_code, response = await self._fetch(session, url, **kwargs)

            elif kwargs["type"].lower() == "post":
                del kwargs["type"]
                if "json" in kwargs:
                    kwargs["data"] = json.dumps(
                        kwargs.pop("json"), separators=(",", ":"), ensure_ascii=True
                    )

                status_code, response = await self._send(session, url, **kwargs)

        if status_code not in [200, 201]:
            return status_code, None

        return status_code, response

    async def _fetch(self, session: aiohttp.ClientSession, url, **kwargs):
        async with session.get(url, **kwargs) as response:
            return response.status, await response.read()

    async def _send(self, session: aiohttp.ClientSession, url, **kwargs):
        async with session.post(url, **kwargs) as response:
            return response.status, await response.read()
