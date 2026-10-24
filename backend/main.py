import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.db import init_db
from app.routes import auth, recommendations, review

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Mutual Fund Recommendation API", version="3.0.0", lifespan=lifespan)

# Comma-separated list, e.g. "https://mf-recommender.vercel.app,http://localhost:5173"
origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.include_router(recommendations.router, prefix="/api", tags=["recommendations"])
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(review.router, prefix="/api", tags=["review"])


@app.middleware("http")
async def no_store(request: Request, call_next):
    # API responses are personal or time-sensitive; never let a proxy or CDN cache them.
    response = await call_next(request)
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def root():
    return {"message": "Mutual Fund Recommendation API", "status": "active"}
