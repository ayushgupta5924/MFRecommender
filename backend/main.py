from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import recommendations
import logging
logging.basicConfig(level=logging.INFO)
app = FastAPI(title="Mutual Fund Recommendation API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(recommendations.router, prefix="/api", tags=["recommendations"])
@app.get("/")
async def root():
    return {"message": "Mutual Fund Recommendation API", "status": "active"}