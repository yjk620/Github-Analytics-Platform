from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from config import settings
import psycopg
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
  token = response.json().get("access_token")

  profile_data = httpx.get(
    "https://api.github.com/user",
    headers={"Authorization": f"Bearer {token}"}
  )
  profile = profile_data.json()

  conn = psycopg.connect(settings.database_url)
  cur = conn.cursor()
  cur.execute(
    """
      INSERT INTO users (github_id, login, name, avatar_url, bio, access_token)
      VALUES (%s, %s, %s, %s, %s, %s)
      ON CONFLICT (github_id) DO UPDATE SET 
        login = EXCLUDED.login, 
        name = EXCLUDED.name, 
        avatar_url = EXCLUDED.avatar_url, 
        bio = EXCLUDED.bio, 
        access_token = EXCLUDED.access_token,
        updated_at = NOW()
    """,
    (
      profile["id"],
      profile["login"],
      profile["name"],
      profile["avatar_url"],
      profile["bio"],
      token
    )
  )
  conn.commit()
  conn.close()

  return {"profile": profile}

  
