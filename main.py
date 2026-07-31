###flow###
#Here's the actual flow:
#1. User clicks "Log in with GitHub" on your app.
#2. Your app redirects them to github.com itself — a page you don't control and never see.
#3. The user types their password there, on GitHub's site, not yours.
#4. GitHub redirects back to your app with a temporary code (not a password).
#. Your backend exchanges that code + your Client ID/Secret for an access token.
#6. That access token — a random string, not the user's password — is what gets stored in your DB, alongside basic profile info GitHub gives you (their GitHub user ID, username, avatar URL, etc.).



from fastapi import FastAPI
from config import settings

app = FastAPI()

@app.get("/health")

def health_check():
  return {"status": "ok", "test_value": settings.test_value}