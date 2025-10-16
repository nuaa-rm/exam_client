import threading
import time
import io
from typing import Optional
import os

from fastapi import FastAPI, Response, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import mss
from PIL import Image

from .range_response import RangeResponse
from .auth import JWTAuthMiddleware
from capture.service import get_recorder_names, get_recorder
from utils.logger import getLogger


logger = getLogger("server.app")
MEDIA_ROOT = os.path.abspath('./media')

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exempt health and screenshot endpoints from JWT auth so they can be called without cookie
app.add_middleware(JWTAuthMiddleware, exempt_paths=["/screenshot/latest"])


# Thread-safe container for latest screenshot bytes
_screenshot_lock = threading.Lock()
_screenshot_png: Optional[bytes] = None


def _screenshot_worker(interval: float = 10.0):
    """Background worker that captures the primary monitor every `interval` seconds
    and stores PNG bytes in `_screenshot_png` guarded by `_screenshot_lock`.
    """
    global _screenshot_png
    if mss is None or Image is None:
        logger.error("mss or Pillow not available; screenshot worker will not run")
        return

    sct = mss.mss()
    logger.info("Screenshot worker started, interval=%s seconds", interval)
    while True:
        try:
            monitor = sct.monitors[0]  # primary monitor
            img = sct.grab(monitor)
            # convert to PNG bytes via PIL for cross-platform consistency
            img_pil = Image.frombytes("RGB", img.size, img.rgb)
            buf = io.BytesIO()
            img_pil.save(buf, format="PNG")
            png = buf.getvalue()
            with _screenshot_lock:
                _screenshot_png = png
            logger.debug("Captured screenshot (%d bytes)", len(png))
        except Exception as e:
            logger.exception("Exception in screenshot worker: %s", e)
        time.sleep(interval)


# start background thread (daemon)
_worker_thread = threading.Thread(target=_screenshot_worker, args=(10.0,), daemon=True)
_worker_thread.start()
logger.info("Background screenshot worker thread started")


@app.get("/screenshot")
async def latest_screenshot():
    """Return latest screenshot PNG captured by background thread.

    Returns 204 if no screenshot is available yet.
    """
    with _screenshot_lock:
        png = _screenshot_png
    logger.info("/screenshot/latest requested; available=%s", bool(png))
    if not png:
        return Response(status_code=204)
    return Response(content=png, media_type="image/png")


@app.get("/recorder/list")
async def list_recorders():
    """List active recorders."""
    return get_recorder_names()


@app.get("/recorder/live/{name}.m3u8")
async def live_recorder(name: str):
    """Stub endpoint for future live streaming of recorder by name."""
    recorder = get_recorder(name)
    if not recorder:
        return JSONResponse(status_code=404, content={"error": "Recorder not found"})
    return Response(content=recorder.generate_live_m3u8(), media_type="application/vnd.apple.mpegurl")


def _is_safe_media_path(rel_path: str) -> bool:
    """Return True if the provided relative path points to a file inside MEDIA_ROOT
    and has an allowed extension. This prevents path traversal attacks.
    """
    # normalize and resolve
    requested = os.path.normpath(rel_path)
    # disallow absolute paths
    if os.path.isabs(requested):
        return False
    # join and resolve
    full_path = os.path.abspath(os.path.join(MEDIA_ROOT, requested))
    if not full_path.startswith(MEDIA_ROOT + os.sep) and full_path != MEDIA_ROOT:
        return False
    # allow only .ts and .m3u8
    _, ext = os.path.splitext(full_path)
    if ext.lower() not in ('.ts', '.m3u8'):
        return False
    # must exist and be a file
    if not os.path.isfile(full_path):
        return False
    return True


@app.get("/recorder/file/{path:path}")
async def get_media_file(request: Request, path: str):
    """Serve a media file from the media directory. Path is treated as a
    relative path and validated to prevent traversal. Returns 404 if invalid.
    """
    if not _is_safe_media_path(path):
        logger.warning("Attempt to access invalid media path: %s", path)
        return JSONResponse(status_code=404, content={"error": "File not found"})
    full_path = os.path.abspath(os.path.join(MEDIA_ROOT, os.path.normpath(path)))
    _, ext = os.path.splitext(full_path)
    ext = ext.lower()
    if ext == '.m3u8':
        media_type = "application/vnd.apple.mpegurl"
    elif ext == '.ts':
        media_type = "video/mp2t"
    else:
        media_type = "application/octet-stream"
    return RangeResponse(request, full_path, content_type=media_type)
