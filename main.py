from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from config import settings
import httpx


app = FastAPI()
#hcheck health: checks if the app is running and returns the test_value from the .env file
@app.get("/health")
def health_check():
  return {"status": "ok", "test_value": settings.test_value}

#route #1: kicks off login, 302 redirect to github login page
@app.get("/auth/github")
def auth_github():
  url = f"https://github.com/login/oauth/authorize?client_id={settings.github_client_id}&redirect_uri={settings.github_redirect_uri}&scope=public_repo"
  return RedirectResponse(url)

#route #2: receives the code from GitHub, exchanges it for an access token
@app.get("/auth/callback")
def callback(code: str):
  response = httpx.post(
    "https://github.com/login/oauth/access_token",
    data={
      "client_id": settings.github_client_id,
      "client_secret": settings.github_client_secret,
      "code": code
    },
    headers={"Accept": "application/json"}
  )
  return {"access_token": response.json().get("access_token")}