import os
import openai
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


openai.api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI()

@app.get("/ping")
async def ping():
    return {"pong": "hello from CultuLa API!"}

class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
async def chat(req: ChatRequest):
    user_msg = req.message
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are AI先生, a friendly Japanese teacher and cultural guide."},
                {"role": "user",   "content": user_msg}
            ]
        )
        reply = resp.choices[0].message.content
        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

