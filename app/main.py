from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from .db import Base, engine
from .routers import auth, domains, assessment, actions, evidence, dashboard, users, structure, reports, org

app = FastAPI(
    title="GVRM IEX API",
    version="1.0.0",
    description="Institutional Excellence & Transformation SaaS"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    from .seed_data import run_seed
    run_seed()

STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
def root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"product": "GVRM IEX", "status": "running", "docs": "/docs"}

app.include_router(auth.router)
app.include_router(domains.router)
app.include_router(assessment.router)
app.include_router(actions.router)
app.include_router(evidence.router)
app.include_router(dashboard.router)
app.include_router(users.router)
app.include_router(structure.router)
app.include_router(reports.router)
app.include_router(org.router)
