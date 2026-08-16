import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.athletes import router as athletes_router
from app.routes.recommendations import router as recommendations_router

app = FastAPI(title="Adaptive Anti-Doping Defense Engine")

# Explicit origins rather than "*": browsers reject a reflected "*" when
# allow_credentials=True anyway, and an explicit list means the deployed
# Vercel domain is set via the CORS_ORIGINS env var (see render.yaml)
# instead of requiring a code change/redeploy later.
_DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "https://anti-doping-system.vercel.app",
]
_cors_origins_env = os.getenv("CORS_ORIGINS")
_cors_origins = (
    [origin.strip() for origin in _cors_origins_env.split(",") if origin.strip()]
    if _cors_origins_env
    else _DEFAULT_CORS_ORIGINS
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(athletes_router)
app.include_router(recommendations_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
