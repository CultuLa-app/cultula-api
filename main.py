import os
import io
import time
import requests
import cloudinary.uploader
from fastapi import FastAPI, HTTPException, File, UploadFile
from pydantic import BaseModel
from openai import OpenAI
import base64
import json
from google.oauth2 import service_account
from google.cloud import texttospeech

# ---------- Google TTS setup ----------
_creds_json = base64.b64decode(os.environ["GOOGLE_CREDENTIALS_BASE64"])
_sa_info = json.loads(_creds_json)
credentials = service_account.Credentials.from_service_account_info(_sa_info)
tts_client = texttospeech.TextToSpeechClient(credentials=credentials)

# ---------- OpenAI setup ----------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------- D-ID setup ----------
DID_API_KEY = os.getenv("DID_API_KEY")
DID_BASE = "https://api.d-id.com"

app = FastAPI()

@app.get("/ping")
async def ping():
    return {"pong": "hello from CultuLa API!"}

# ---- Chat ----
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

# ---- Speech-to-text (Whisper) ----
@app.post("/listen")
async def listen(audio: UploadFile = File(...)):
    try:
        contents = await audio.read()
        buffer = io.BytesIO(contents)
        buffer.name = audio.filename or "audio.wav"
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=buffer,
            response_format="json"
        )
        # new SDK: result.text is correct
        return {"text": result.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---- Text-to-speech (Google TTS -> Cloudinary) ----
class TTSRequest(BaseModel):
    text: str
    voice: str = "ja-JP-Wavenet-A"
    speed: float = 1.0

@app.post("/tts")
async def tts(req: TTSRequest):
    synthesis_input = texttospeech.SynthesisInput(text=req.text)
    voice_params = texttospeech.VoiceSelectionParams(
        language_code="ja-JP",
        name=req.voice
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

    # Upload MP3 bytes to Cloudinary as video
    try:
        upload = cloudinary.uploader.upload(
            io.BytesIO(resp.audio_content),
            resource_type="video",
            public_id=f"tts/{abs(hash(req.text))}"
            format="mp3"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cloudinary upload error: {e}")

    return {"url": upload["secure_url"]}

# ---- Combined: TTS -> Cloudinary -> D-ID (returns final video_url) ----
class TalkFromTTSRequest(TTSRequest):
    # presenter portrait URL (Cloudinary image you want to speak)
    image_url: str
    # output resolution (depends on plan): "360p" | "720p" | "1080p"
    resolution: str = "720p"

@app.post("/avatar/talk_from_tts")
async def talk_from_tts(req: TalkFromTTSRequest):
    if not DID_API_KEY:
        raise HTTPException(status_code=500, detail="Missing DID_API_KEY in environment")

    # 1) Google TTS -> MP3
    try:
        synthesis_input = texttospeech.SynthesisInput(text=req.text)
        voice = texttospeech.VoiceSelectionParams(language_code="ja-JP", name=req.voice)
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=req.speed,
        )
        tts_resp = tts_client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS error: {e}")

    # 2) Upload MP3 to Cloudinary
    try:
        up = cloudinary.uploader.upload(
            io.BytesIO(tts_resp.audio_content),
            resource_type="video",
            public_id=f"tts/{abs(hash(req.text))}"
            format="mp3"
        )
        audio_url = up["secure_url"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cloudinary upload error: {e}")

    # 3) Call D-ID (create talk)
    headers = {
        "Authorization": f"Basic {DID_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "source_url": req.image_url,                 # presenter portrait
        "script": {"type": "audio", "audio_url": audio_url},
        "config": {"result_format": "mp4", "stitch": True},
        "resolution": req.resolution,
    }

    try:
        r = requests.post(f"{DID_BASE}/talks", json=payload, headers=headers, timeout=60)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"D-ID create request failed: {e}")
    if r.status_code >= 300:
        raise HTTPException(status_code=400, detail=f"D-ID create error: {r.text}")

    talk = r.json()
    talk_id = talk.get("id")
    if not talk_id:
        raise HTTPException(status_code=500, detail=f"Unexpected D-ID response: {talk}")

    # 4) Poll until video is ready -> return final video_url
    for _ in range(60):  # ~120s max (60 * 2s)
        g = requests.get(f"{DID_BASE}/talks/{talk_id}", headers=headers, timeout=30)
        if g.status_code >= 300:
            raise HTTPException(status_code=400, detail=f"D-ID status error: {g.text}")
        data = g.json()
        result_url = data.get("result_url")
        status = data.get("status")
        if result_url:
            return {"video_url": result_url, "status": status, "id": talk_id}
        time.sleep(2)

    raise HTTPException(status_code=504, detail="Timed out waiting for D-ID result")
