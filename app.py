import io
import os
import secrets
import uuid
import zipfile
from pathlib import Path
from typing import List

import requests
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel

import db
import recraft_client as recraft
import metadata_client
import csv_export
import image_ops
from constants import STYLE_PRESETS

BASE_DIR = Path(__file__).parent
STORAGE_DIR = BASE_DIR / "storage" / "images"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

db.init_db()

app = FastAPI(title="Stock Image Studio")
app.mount("/images", StaticFiles(directory=STORAGE_DIR), name="images")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


APP_PASSWORD = os.environ.get("APP_PASSWORD")


@app.middleware("http")
async def require_password(request, call_next):
    if APP_PASSWORD and request.url.path != "/healthz":
        import base64

        auth = request.headers.get("authorization", "")
        ok = False
        if auth.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth[6:]).decode()
                _, _, password = decoded.partition(":")
                ok = secrets.compare_digest(password, APP_PASSWORD)
            except Exception:
                ok = False
        if not ok:
            from starlette.responses import Response

            return Response(
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Stock Image Studio"'},
            )
    return await call_next(request)


@app.middleware("http")
async def no_cache_static(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    return response


class GenerateRequest(BaseModel):
    prompt: str
    preset: str = "photo"
    n: int = 1


class UpscaleRequest(BaseModel):
    mode: str = "crisp"


class ResizeRequest(BaseModel):
    long_edge: int = 2000


class ExportRequest(BaseModel):
    ids: List[int]


def _download(url, dest_path):
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    dest_path.write_bytes(r.content)


def _get_or_404(image_id):
    row = db.get_image(image_id)
    if not row:
        raise HTTPException(404, "image not found")
    return row


def _call_recraft(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except requests.HTTPError as e:
        raise HTTPException(502, f"Recraft API error: {e.response.text}")
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/")
def root():
    static_dir = BASE_DIR / "static"
    html = (static_dir / "index.html").read_text(encoding="utf-8")
    css_v = int((static_dir / "style.css").stat().st_mtime)
    js_v = int((static_dir / "app.js").stat().st_mtime)
    html = html.replace("/static/style.css", f"/static/style.css?v={css_v}")
    html = html.replace("/static/app.js", f"/static/app.js?v={js_v}")
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@app.get("/api/presets")
def presets():
    return STYLE_PRESETS


@app.get("/api/suggest-topics")
def suggest_topics():
    try:
        return metadata_client.suggest_topics()
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"topic suggestion failed: {e}")


@app.post("/api/generate")
def generate(req: GenerateRequest):
    preset = STYLE_PRESETS.get(req.preset)
    if not preset:
        raise HTTPException(400, f"unknown preset '{req.preset}'")

    prompt = req.prompt
    if req.preset == "3d":
        prompt = f"{prompt}, 3D render, octane render style"

    data = _call_recraft(recraft.generate_image, prompt, model=preset["model"], style=preset["style"], n=req.n)

    is_vector = preset["model"].endswith("_vector")
    ext = "svg" if is_vector else "png"

    records = []
    for item in data:
        filename = f"{uuid.uuid4().hex[:12]}.{ext}"
        _download(item["url"], STORAGE_DIR / filename)
        row_id = db.insert_image(filename=filename, prompt=req.prompt, preset=req.preset, is_vector=int(is_vector))
        records.append(db.get_image(row_id))
    return records


@app.get("/api/images")
def list_images():
    return db.list_images()


@app.post("/api/images/{image_id}/remove-background")
def remove_background(image_id: int):
    row = _get_or_404(image_id)
    src = STORAGE_DIR / row["filename"]
    url = _call_recraft(recraft.remove_background, src)
    new_filename = f"{Path(row['filename']).stem}_nobg.png"
    _download(url, STORAGE_DIR / new_filename)
    db.update_image(image_id, filename=new_filename, status="bg_removed")
    return db.get_image(image_id)


@app.post("/api/images/{image_id}/upscale")
def upscale(image_id: int, req: UpscaleRequest):
    row = _get_or_404(image_id)
    src = STORAGE_DIR / row["filename"]
    url = _call_recraft(recraft.upscale, src, mode=req.mode)
    new_filename = f"{Path(row['filename']).stem}_upscaled.png"
    _download(url, STORAGE_DIR / new_filename)
    db.update_image(image_id, filename=new_filename, status="upscaled")
    return db.get_image(image_id)


@app.post("/api/images/{image_id}/vectorize")
def vectorize(image_id: int):
    row = _get_or_404(image_id)
    if row["is_vector"]:
        raise HTTPException(400, "already a vector image")
    src = STORAGE_DIR / row["filename"]
    url = _call_recraft(recraft.vectorize, src)
    new_filename = f"{Path(row['filename']).stem}.svg"
    _download(url, STORAGE_DIR / new_filename)
    db.update_image(image_id, filename=new_filename, is_vector=1, status="vectorized")
    return db.get_image(image_id)


@app.post("/api/images/{image_id}/resize")
def resize(image_id: int, req: ResizeRequest):
    row = _get_or_404(image_id)
    if row["is_vector"]:
        raise HTTPException(400, "vector images don't need resizing")
    src = STORAGE_DIR / row["filename"]
    new_filename = f"{Path(row['filename']).stem}_{req.long_edge}.png"
    image_ops.resize(src, STORAGE_DIR / new_filename, req.long_edge)
    db.update_image(image_id, filename=new_filename, status="resized")
    return db.get_image(image_id)


@app.post("/api/images/{image_id}/optimize")
def optimize(image_id: int):
    row = _get_or_404(image_id)
    if row["is_vector"]:
        raise HTTPException(400, "vector images don't need optimizing")
    src = STORAGE_DIR / row["filename"]
    before = src.stat().st_size
    new_filename = f"{Path(row['filename']).stem}_opt.png"
    image_ops.optimize(src, STORAGE_DIR / new_filename)
    after = (STORAGE_DIR / new_filename).stat().st_size
    db.update_image(image_id, filename=new_filename, status="optimized")
    row = db.get_image(image_id)
    row["size_before"] = before
    row["size_after"] = after
    return row


@app.post("/api/images/{image_id}/metadata")
def generate_metadata(image_id: int):
    row = _get_or_404(image_id)
    if row["is_vector"]:
        raise HTTPException(400, "generate metadata from a raster version (SVG not supported)")
    src = STORAGE_DIR / row["filename"]
    try:
        data = metadata_client.generate_metadata(src, prompt_hint=row["prompt"] or "")
    except Exception as e:
        raise HTTPException(502, f"metadata generation failed: {e}")
    db.update_image(
        image_id,
        title=data["title"],
        keywords=data["keywords"],
        keywords_ko=data.get("keywords_ko"),
        stock_category_id=data["category_id"],
        status="ready",
    )
    return db.get_image(image_id)


@app.post("/api/export-csv")
def export_csv(req: ExportRequest):
    rows = [r for r in (db.get_image(i) for i in req.ids) if r]
    if not rows:
        raise HTTPException(400, "no valid image ids")
    csv_text = csv_export.build_csv(rows)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=adobe_stock_metadata.csv"},
    )


@app.post("/api/export-zip")
def export_zip(req: ExportRequest):
    rows = [r for r in (db.get_image(i) for i in req.ids) if r]
    if not rows:
        raise HTTPException(400, "no valid image ids")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("metadata.csv", csv_export.build_csv(rows))
        for row in rows:
            zf.write(STORAGE_DIR / row["filename"], arcname=row["filename"])
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=stock-images.zip"},
    )
