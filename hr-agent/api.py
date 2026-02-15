"""
FastAPI wrapper around the HR LangGraph agent.
Exposes POST /ask for question answering and GET /health for liveness.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agent import ask

app = FastAPI(title="HR Agent API", version="1.0.0")


class QuestionRequest(BaseModel):
    question: str


class AnswerResponse(BaseModel):
    answer: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask", response_model=AnswerResponse)
async def ask_question(req: QuestionRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")
    answer = await ask(req.question)
    return AnswerResponse(answer=answer)
