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
  access_token_response = httpx.post(
    "https://github.com/login/oauth/access_token",
    data={
      "client_id": settings.github_client_id,
      "client_secret": settings.github_client_secret,
      "code": code
    },
    headers={"Accept": "application/json"}
  )
  access_token = access_token_response.json().get("access_token")

  profile_data = httpx.get(
    "https://api.github.com/user",
    headers={"Authorization": f"Bearer {access_token}"}
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
      access_token
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

#================ sessions ========================
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
#1. grab the sessions table with name s
#2. join the users table, u, on the condition that the github_id in sessions matches the github_id in users
#3. check if session_id matches the provided session_id and that the session has not expired
#4. retrieve informations in users table
#5. set row to result of the query

  #no row means the cookie is missing, fake, or expired
  if row is None:
    conn.close()
    return {"error": "Not Logged In"}

#label the values in the row for easier access later
  github_id, login, name, avatar_url, bio, access_token = row




#================== repositories ==========================
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

  for repo in repos:
    commit_response = httpx.get(
      f"https://api.github.com/repos/{login}/{repo['name']}/commits?per_page=100",
      headers={"Authorization": f"Bearer {access_token}"}
    )
    comms = commit_response.json()

    for comm in comms:
      cur.execute( 
        """
          INSERT INTO commits (
            sha, repo_github_id, message, author_name, 
            committed_at, html_url)
          VALUES (%s, %s, %s, %s, %s, %s)
          ON CONFLICT (sha) DO NOTHING
        """,
        (
          comm["sha"],
          repo["id"],
          comm["commit"]["message"],
          comm["commit"]["author"]["name"],
          comm["commit"]["author"]["date"],
          comm["html_url"]
        )
      )
  conn.commit()

#create rows by repo containing all of its commits
  cur.execute (
    """
      SELECT r.name, r.language, r.stars_count, r.html_url, r.pushed_at, COUNT(c.sha) AS commit_count
      FROM repositories r
      LEFT JOIN commits c ON r.repo_github_id = c.repo_github_id
      WHERE r.owner_github_id = %s
      GROUP BY r.name, r.language, r.stars_count, r.html_url, r.pushed_at
      ORDER BY commit_count DESC
    """,
    (github_id,)
  )
  repo_rows = cur.fetchall()

  #1. FROM, call repostitories, r, creating (repos_count) # of rows
  #2. LEFT JOIN, call commits as c and find commits with matching repo_github_id and expand rows
  #   -> (repo_count) # of rows -> (commit_count) # of rows
  #    **  if a repo have no matching commit KEEP IT (THIS IS WHAT 'LEFT' DO)
  #3. WHERE, filter out rows that are NOT the current user's github_id
  #4. GROUP BY, sort the rows into buckets
  #5. SELECT, with the sorted buckets emit one row per bucket, making (commit_count) # of rows back into (repo_count) # of rows
  #6. ORDER, order the rows by commit_count descending orders

#language breakdown: how many repos use each language
  cur.execute(
    """
      SELECT r.language, COUNT(*) AS repo_count
      FROM repositories r
      WHERE r.owner_github_id = %s AND r.language IS NOT NULL
      GROUP BY r.language
      ORDER BY repo_count DESC
    """,
    (github_id,)
  )
  language_rows = cur.fetchall()

  #1. FROM, only repositories this time - no JOIN needed since language lives here
  #2. WHERE, this user's repos only, and skip repos with no language
  #    ** empty repos have language = NULL. grouping would make a "NULL" bucket,
  #       which isn't a language, so filter those rows out before grouping
  #3. GROUP BY, one bucket per distinct language
  #4. SELECT, COUNT(*) is safe here (unlike COUNT(c.sha) above) because there is
  #    no LEFT JOIN creating phantom rows - every row in a bucket is a real repo
  #5. ORDER, most-used language first

  conn.close()

  return {
    "login": login,
    "name": name,
    "avatar_url": avatar_url,
    "bio": bio,
    "repos": [
      {
        "name": r[0],
        "language": r[1],
        "stars": r[2],
        "url": r[3],
        "pushed_at": r[4],
        "commit_count": r[5]
      }
      for r in repo_rows
    ],
    "languages": [
      {
        "language": l[0],
        "repo_count": l[1]
      }
      for l in language_rows
    ]
  }

