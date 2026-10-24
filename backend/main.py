import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.routes import recommendations

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="Mutual Fund Recommendation API", version="2.0.0")

# Comma-separated list, e.g. "https://mf-recommender.vercel.app,http://localhost:5173"
origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.include_router(recommendations.router, prefix="/api", tags=["recommendations"])


@app.get("/")
def root():
    return {"message": "Mutual Fund Recommendation API", "status": "active"}
