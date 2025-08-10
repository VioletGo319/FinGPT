# app/main.py
from fastapi import FastAPI
from app.routers.ask import router as ask_router

app = FastAPI(title="FinDocGPT")
app.include_router(ask_router, prefix="/ask")

@app.get("/health")
def health():
    return {"status": "ok"}