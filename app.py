from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from photo_search_engine import engine

BASE_DIR = Path(__file__).parent.resolve()

app = FastAPI(title="Photo Search API", version="1.0.0")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def load_resources():
    engine.load()


@app.get("/api/stats")
def get_stats():
    return engine.stats()


@app.post("/api/reload")
@app.get("/api/reload")
def reload_index():
    try:
        return engine.reload_index()
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/search")
def search(
    q: str = Query(..., min_length=1, description="Natural language search query"),
    k: int = Query(20, ge=1, le=200, description="Number of results to return"),
    threshold: float = Query(0.0, ge=0.0, le=1.0, description="Minimum score filter")
):
    try:
        return engine.search(query=q, count=k, threshold=threshold)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/image")
def serve_image(path: str = Query(..., description="Absolute file path to image")):
    img_path = Path(path).resolve()

    if not img_path.exists() or not img_path.is_file():
        raise HTTPException(status_code=404, detail=f"Image file not found: {path}")

    # Basic extension validation
    if img_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}:
        raise HTTPException(status_code=400, detail="Invalid image extension")

    return FileResponse(
        path=img_path,
        headers={"Cache-Control": "public, max-age=86400"},
    )


# Serve Static Assets & Main Web UI
static_dir = BASE_DIR / "static"
static_dir.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def index():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h2>Photo Search API is running. UI loading...</h2>")
