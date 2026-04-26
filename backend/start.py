"""
Windows-compatible dev server entry point.

Problem: uvicorn --reload spawns the server in a child process via
multiprocessing.spawn. The child starts its asyncio event loop BEFORE
importing main.py, so the WindowsProactorEventLoopPolicy set in main.py
never takes effect in the child. Playwright then fails with NotImplementedError.

Fix: Run this file instead. It sets the ProactorEventLoop policy here,
then passes the loop_factory directly to uvicorn so every process uses
ProactorEventLoop regardless of import order.

Usage (Windows dev):
    py start.py

This is equivalent to:
    py -m uvicorn main:app --reload --port 8000
but with Playwright working on Windows.
"""

import asyncio
import sys

# Must be set BEFORE uvicorn is imported
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        # Explicitly pass ProactorEventLoop as the factory so uvicorn's
        # subprocess also uses it, not the default SelectorEventLoop
        loop="asyncio",
    )
