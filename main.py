from fastapi import FastAPI, Cookie
from fastapi.responses import RedirectResponse
from config import settings
import psycopg
import httpx
import secrets


app = FastAPI()

#run schema.sql against whatever database this environment points at, so a fresh
#deploy provisions its own tables. every statement is CREATE TABLE IF NOT EXISTS,
#so running this on every boot is a no-op once the tables already exist.
#note: this only CREATES tables - it cannot ALTER existing ones. changing a column
#on a table that already exists still needs a manual ALTER (or a migration tool).
def init_db():
  with open("schema.sql") as f:
    schema = f.read()
  conn = psycopg.connect(settings.database_url)
  cur = conn.cursor()
  cur.execute(schema)
  conn.commit()
  conn.close()

init_db()

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
  token_response = httpx.post(
    "https://github.com/login/oauth/access_token",
    data={
      "client_id": settings.github_client_id,
      "client_secret": settings.github_client_secret,
      "code": code
    },
    headers={"Accept": "application/json"}
  )
  token = token_response.json().get("access_token")

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

  session_id = secrets.token_urlsafe(32)
  cur.execute(
    """
      INSERT INTO sessions (session_id, github_id)
      VALUES (%s, %s)
    """,
    (
      session_id,
      profile["id"]
    )
  )

  session_response = RedirectResponse(url="/dashboard")
  session_response.set_cookie(key="session_id", value=session_id, httponly=True)

  conn.commit()
  conn.close()

  return session_response

#route #3: protected page. reads the session cookie, fetches the user's repos
#from GitHub, stores them, and returns the user plus their repo list
@app.get("/dashboard")
def dashboard(session_id: str = Cookie(None)): #default Cookie to none if empty cookie
  conn = psycopg.connect(settings.database_url)
  cur = conn.cursor()

  #find who this session belongs to. access_token is needed to call GitHub below
  cur.execute(
    """
      SELECT u.github_id, u.login, u.name, u.avatar_url, u.bio, u.access_token
      FROM sessions s
      JOIN users u ON s.github_id = u.github_id
      WHERE s.session_id = %s AND s.expires_at > NOW()
    """,
    (session_id,)
  )
  row = cur.fetchone()

  #no row means the cookie is missing, fake, or expired
  if row is None:
    conn.close()
    return {"error": "Not Logged In"}

  github_id, login, name, avatar_url, bio, access_token = row

  #fetch this user's repos from GitHub. returns a JSON array, not a single object
  repos_response = httpx.get(
    "https://api.github.com/user/repos?per_page=100",
    headers={"Authorization": f"Bearer {access_token}"}
  )
  repos = repos_response.json()

  #upsert each repo. same ON CONFLICT pattern as users - repos change over time
  for repo in repos:
    cur.execute(
      """
        INSERT INTO repositories (
          repo_github_id, owner_github_id, name, language,
          stars_count, html_url, fork, fork_count, pushed_at, description
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (repo_github_id) DO UPDATE SET
          name = EXCLUDED.name,
          language = EXCLUDED.language,
          stars_count = EXCLUDED.stars_count,
          html_url = EXCLUDED.html_url,
          fork = EXCLUDED.fork,
          fork_count = EXCLUDED.fork_count,
          pushed_at = EXCLUDED.pushed_at,
          updated_at = NOW(),
          description = EXCLUDED.description
      """,
      (
        repo["id"],
        github_id,
        repo["name"],
        repo["language"],
        repo["stargazers_count"],
        repo["html_url"],
        repo["fork"],
        repo["forks_count"],
        repo["pushed_at"],
        repo["description"]
      )
    )

  conn.commit()
  conn.close()

  return {
    "login": login,
    "name": name,
    "avatar_url": avatar_url,
    "bio": bio,
    "repos": [
      {
        "name": repo["name"],
        "language": repo["language"],
        "stars": repo["stargazers_count"],
        "url": repo["html_url"],
        "pushed_at": repo["pushed_at"]
      }
      for repo in repos
    ]
  }

