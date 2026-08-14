from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.athletes import router as athletes_router

app = FastAPI(title="Adaptive Anti-Doping Defense Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(athletes_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
