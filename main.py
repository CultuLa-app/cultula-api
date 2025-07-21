import os
import cloudinary.uploader
from fastapi import FastAPI, HTTPException, File, UploadFile
from pydantic import BaseModel
from openai import OpenAI


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

@app.get("/ping")
async def ping():
    return {"pong": "hello from CultuLa API!"}

class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        resp = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are AI先生, a friendly Japanese teacher and cultural guide."},
                {"role": "user",   "content": req.message}
            ]
        )
        reply = resp.choices[0].message.content
        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/listen")
async def listen(audio: UploadFile = File(...)):
    content = await audio.read()
    try:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=content,
            response_format="json"
        )
        return {"text": result["text"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

