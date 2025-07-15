from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

@app.get("/ping")
async def ping():
    return {"pong": "hello from CultuLa API!"}

class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
async def chat(req: ChatRequest):
    user_msg = req.message
    return {"reply": f"You said: {user_msg}"}

