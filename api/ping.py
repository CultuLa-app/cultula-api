from fastapi import FastAPI
from mangum import Mangum

app = FastAPI()

@app.get("/ping")
async def ping():
    return {"pong": "hello from CultuLa API!"}

handler = Mangum(app)
