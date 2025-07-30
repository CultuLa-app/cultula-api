import os
import cloudinary.uploader
from fastapi import FastAPI, HTTPException, File, UploadFile
from pydantic import BaseModel
from openai import OpenAI
import base64
import json
from google.oauth2 import service_account
from google.cloud import texttospeech

_creds_json = base64.b64decode(os.environ["GOOGLE_CREDENTIALS_BASE64"])
_sa_info = json.loads(_creds_json)

credentials = service_account.Credentials.from_service_account_info(_sa_info)
tts_client = texttospeech.TextToSpeechClient(credentials=credentials)

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
    try:
        audio.file.seek(0)

        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio.file,
            response_format="json"
        )
        return {"text": result["text"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class TTSRequest(BaseModel):
    text: str
    voice: str = "ja-JP-Wavenet-A"
    speed: float = 1.0

@app.post("/tts")
async def tts(req: TTSRequest):
    synthesis_input = texttospeech.SynthesisInput(text=req.text)
    voice_params = texttospeech.VoiceSelectionParams(
        language_code="ja-JP", name=req.voice
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=req.speed
    )

    try:
        resp = tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS error: {e}")

    upload = cloudinary.uploader.upload(
        resp.audio_content,
        resource_type="raw",
        public_id=f"tts/{abs(hash(req.text))}"
    )

    return {"url": upload["secure_url"]}

