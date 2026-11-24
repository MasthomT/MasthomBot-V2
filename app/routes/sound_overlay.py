"""Overlay OBS « audio seul » : /overlay/sons — aucun visuel, joue les sons des automatisations.

À mettre UNE fois dans OBS (source navigateur, dans une scène présente partout) : contrairement au widget
« Alertes des commandes » intégré à chaque scène composée, il ne disparaît pas au changement de scène.
Une seule connexion SSE (celle de cette source) ; les sons arrivent par automation_service.sound_listeners.
"""
import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from app.services import automation_service as A

router = APIRouter(tags=["overlay-sons"])

PAGE = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><title>Sons des automatisations</title>
<style>html,body{margin:0;background:transparent;overflow:hidden}</style></head>
<body><script>
(function () {
  var es;
  function connect() {
    es = new EventSource('/overlay/sons/stream?t=' + Date.now());
    es.onmessage = function (e) {
      try {
        var d = JSON.parse(e.data);
        if (d.type === 'sound' && d.file) { var a = new Audio('/static/commands/sounds/' + encodeURIComponent(d.file)); a.volume = 1; a.play().catch(function () {}); }
      } catch (err) {}
    };
    es.onerror = function () { es.close(); setTimeout(connect, 3000); };
  }
  connect();
})();
</script></body></html>"""


@router.get("/overlay/sons", response_class=HTMLResponse)
async def sound_overlay_page():
    return HTMLResponse(PAGE, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})


@router.get("/overlay/sons/stream")
async def sound_overlay_stream(request: Request):
    async def gen():
        q: asyncio.Queue = asyncio.Queue()
        A.sound_listeners.append(q)
        try:
            yield ": ok\n\n"
            while not await request.is_disconnected():
                try:
                    d = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(d, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"          # garde la connexion ouverte
        finally:
            if q in A.sound_listeners:
                A.sound_listeners.remove(q)
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})
