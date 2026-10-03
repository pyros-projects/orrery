"""ComfyUI's server keeps answering while a route waits for the language model (#165): the slow routes run in
a thread. Needs aiohttp, which ComfyUI's environment has (no GPU, no model):

    PYTHONPATH=src /path/to/comfy-ui/.venv/bin/python experiments/api-llm/nonblocking.py
"""

import asyncio
import tempfile
import time

from aiohttp import ClientSession, web

from orrery import endpoint, webapi


def slow_check(base_url, key, model):  # a model that takes its time
    time.sleep(3)
    return {"ok": True, "models": [], "seconds": 3.0}


async def main():
    endpoint.check = slow_check
    app, routes = web.Application(), web.RouteTableDef()  # as ComfyUI's PromptServer.instance.routes
    webapi.register(routes, web)
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    home = tempfile.mkdtemp(prefix="orrery-nb-")
    async with ClientSession() as http:
        start = time.monotonic()
        slow = asyncio.create_task(http.post(f"http://127.0.0.1:{port}/orrery/llm/check", json={"home": home, "model": "m"}))
        await asyncio.sleep(0.2)
        fast = await http.get(f"http://127.0.0.1:{port}/orrery/home", params={"home": home})
        fast_at = time.monotonic() - start
        await (await slow).json()
        slow_at = time.monotonic() - start
    await runner.cleanup()
    print(f"fast route answered at {fast_at:.2f} s (status {fast.status}), the slow check at {slow_at:.2f} s")
    assert fast_at < 1 < slow_at, "the slow route blocked the server"


asyncio.run(main())
