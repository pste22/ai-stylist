"""WebSocket client that drives a Mira live_server session like the web app."""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field

import websockets
from websockets.exceptions import ConnectionClosed


@dataclass
class TurnCapture:
    mira_text: str = ""
    products: list[dict] = field(default_factory=list)
    audio_bytes: int = 0
    latency_ms: float | None = None
    raw_events: list[dict] = field(default_factory=list)


class MiraSession:
    def __init__(
        self,
        ws_url: str = "ws://localhost:8765",
        *,
        text_mode: bool = True,
        user_name: str = "ShopperEval",
        turn_timeout: float = 45.0,
    ):
        self.ws_url = ws_url
        self.text_mode = text_mode
        self.user_name = user_name
        self.turn_timeout = turn_timeout
        self._ws = None
        self._inbox: asyncio.Queue = asyncio.Queue()
        self._reader_task: asyncio.Task | None = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *exc):
        await self.close()

    async def connect(self) -> None:
        self._ws = await websockets.connect(
            self.ws_url,
            max_size=16 * 1024 * 1024,
            open_timeout=15,
            ping_interval=20,
        )
        await self._ws.send(json.dumps({
            "type": "init",
            "name": self.user_name,
            "text_mode": self.text_mode,
            "style_vibe": "smart casual",
            "shopping_focus": "women",
            "budget": "mid",
        }))
        self._reader_task = asyncio.create_task(self._reader())
        # Wait for catalog bootstrap + Gemini Live session to come up.
        # text_input before sess exists is silently dropped on the server.
        await self._wait_ready(timeout=20.0)
        self._drain_inbox()

    async def _wait_ready(self, timeout: float = 20.0) -> None:
        """Block until startup products arrive, then give Gemini a settle window."""
        deadline = time.perf_counter() + timeout
        saw_products = False
        while time.perf_counter() < deadline:
            remaining = deadline - time.perf_counter()
            try:
                ev = await asyncio.wait_for(self._inbox.get(), timeout=min(1.0, remaining))
            except asyncio.TimeoutError:
                if saw_products:
                    break
                continue
            if ev.get("type") == "products":
                saw_products = True
            if ev.get("type") == "state":
                # any state means pumps are alive
                saw_products = saw_products or True
        # Extra settle — Live session often lags the first product push
        await asyncio.sleep(3.0)

    async def close(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def _reader(self) -> None:
        assert self._ws is not None
        try:
            async for msg in self._ws:
                if isinstance(msg, bytes):
                    await self._inbox.put({"type": "_audio", "nbytes": len(msg)})
                else:
                    try:
                        await self._inbox.put(json.loads(msg))
                    except json.JSONDecodeError:
                        await self._inbox.put({"type": "_raw", "text": msg})
        except ConnectionClosed:
            await self._inbox.put({"type": "_closed"})

    def _drain_inbox(self) -> None:
        while not self._inbox.empty():
            try:
                self._inbox.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def ask(self, text: str, *, retries: int = 1) -> TurnCapture:
        """Send a shopper text turn and wait for Mira's reply to complete."""
        capture = await self._ask_once(text)
        attempt = 0
        while not capture.mira_text.strip() and attempt < retries:
            attempt += 1
            await asyncio.sleep(2.0)
            capture = await self._ask_once(text)
        return capture

    async def _ask_once(self, text: str) -> TurnCapture:
        assert self._ws is not None
        self._drain_inbox()
        capture = TurnCapture()
        t0 = time.perf_counter()
        await self._ws.send(json.dumps({"type": "text_input", "text": text}))

        mira_chunks: list[str] = []
        saw_talking = False
        deadline = time.perf_counter() + self.turn_timeout
        # After first mira token, require quiet period before ending turn
        last_mira_at: float | None = None
        quiet_needed = 1.8

        while time.perf_counter() < deadline:
            timeout = max(0.1, deadline - time.perf_counter())
            try:
                ev = await asyncio.wait_for(self._inbox.get(), timeout=timeout)
            except asyncio.TimeoutError:
                if mira_chunks and last_mira_at and (time.perf_counter() - last_mira_at) >= quiet_needed:
                    break
                continue

            capture.raw_events.append(
                {k: v for k, v in ev.items() if k != "items"} | (
                    {"n_items": len(ev.get("items") or [])} if "items" in ev else {}
                )
            )

            et = ev.get("type")
            if et == "_closed":
                break
            if et == "_audio":
                capture.audio_bytes += int(ev.get("nbytes") or 0)
                if capture.latency_ms is None:
                    capture.latency_ms = (time.perf_counter() - t0) * 1000
                last_mira_at = time.perf_counter()
                continue
            if et == "transcript" and ev.get("who") == "mira":
                chunk = ev.get("text") or ""
                mira_chunks.append(chunk)
                last_mira_at = time.perf_counter()
                if capture.latency_ms is None:
                    capture.latency_ms = (time.perf_counter() - t0) * 1000
            if et == "products":
                for p in ev.get("items") or []:
                    if p.get("id") and not any(x.get("id") == p["id"] for x in capture.products):
                        capture.products.append(p)
            if et == "state":
                st = ev.get("state")
                if st == "talking":
                    saw_talking = True
                if st == "idle" and (saw_talking or mira_chunks):
                    await asyncio.sleep(0.7)
                    break

            if mira_chunks and last_mira_at and (time.perf_counter() - last_mira_at) >= quiet_needed:
                # Peek: if queue empty, turn is likely done
                if self._inbox.empty():
                    await asyncio.sleep(0.3)
                    if self._inbox.empty():
                        break

        capture.mira_text = "".join(mira_chunks).strip()
        return capture
