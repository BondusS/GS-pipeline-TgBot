from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services.path_mapper import build_project_paths
from app.services.pipeline_builder import build_full_pipeline_steps
from app.services.pipeline_defaults import load_pipeline_defaults

logger = logging.getLogger(__name__)
app = FastAPI()

templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=templates_dir)


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/pipeline", response_class=HTMLResponse)
async def generate_pipeline(request: Request, windows_path: str = Form(...)):
    try:
        paths = build_project_paths(windows_path)
        defaults = load_pipeline_defaults()
        steps = build_full_pipeline_steps(paths=paths, defaults=defaults)
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "steps": steps,
                "dataset_path": paths.linux_path,
                "windows_path": windows_path,
            },
        )
    except Exception as e:
        logger.exception("pipeline build failed")
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "error": str(e), "windows_path": windows_path},
        )
