from fastapi import FastAPI

app = FastAPI()

@app.get("/ping")
async def ping():
    return {"pong": "hello from CultuLa API!"}
