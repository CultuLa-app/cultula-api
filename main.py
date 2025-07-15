from fastapi import FastAPI, HTTPException
from mangum import Mangum
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
    # echo for now; later replace with OpenAI calls
    return {"reply": f"You said: {user_msg}"}

handler = Mangum(app)
