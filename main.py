from fastapi import FastAPI
from config import settings

app = FastAPI()

@app.get("/health")

def health_check():
  return {"status": "ok", "test_value": settings.test_value}