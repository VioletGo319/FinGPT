# app/routers/ask.py
from fastapi import APIRouter
from pydantic import BaseModel
from app.services.rag import search_and_answer 

router = APIRouter()

class AskIn(BaseModel):
    question: str
    ticker: str | None = None

@router.post("/")
def ask(payload: AskIn):
    answer, sources = search_and_answer(payload.question)
    return {"answer": answer, "sources": sources, "meta": {"ticker": payload.ticker}}
