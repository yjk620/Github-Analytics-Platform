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

#Boolean flag variable, if redirect_uri -> True (cookie secure), else False (cookie not secure)
COOKIE_SECURE = settings.github_redirect_uri.startswith("https://")

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

#access token error case
  if not access_token:
    return {"error": "GitHub login failed"}

  profile_data = httpx.get(
    "https://api.github.com/user",
    headers={"Authorization": f"Bearer {access_token}"}
  )
  profile = profile_data.json()

  conn = psycopg.connect(settings.database_url)

  #finally runs on every exit path, including an exception partway through. without
  #it a crash leaks the connection, and postgres stops accepting new ones at 100.
  try:
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

    conn.commit()
  finally:
    conn.close()

  #create a redirect response to dashboard
  session_response = RedirectResponse(url="/dashboard")
  session_response.set_cookie( #attach cookie to the response
    key="session_id", #label cookie as session_id so that the browser can send it back to the server on future requests
    value=session_id,  #the real cookie data
    httponly=True,     #Disable JS accessing the cookie, which blocks XSS attacks
    secure=COOKIE_SECURE,  #sends cookie only when COOKIE_SECURE is True
    samesite="lax"     #restricts requests from other sites
  )

  return session_response

#route #3: protected page. reads the session cookie, fetches the user's repos
#from GitHub, stores them, and returns the user plus their repo list
@app.get("/dashboard")
def dashboard(session_id: str = Cookie(None), page: int=1, per_page: int=20, language: str=None): #default Cookie to none if empty cookie
  conn = psycopg.connect(settings.database_url)
  #same reason as in callback: every return below, and every crash, still closes.
  try:
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
      return {"error": "Not Logged In"}

  #label the values in the row for easier access later
    github_id, login, name, avatar_url, bio, access_token = row




  #================== repositories ==========================
    #fetch this user's repos from GitHub. returns a JSON array, not a single object
    repos_response = httpx.get(
      "https://api.github.com/user/repos?per_page=100&affiliation=owner",
      headers={"Authorization": f"Bearer {access_token}"}
    )

    #GitHub only sends a list of repos on 200. every other status sends an error msg
    if repos_response.status_code != 200:
      return {"error": f"Could not fetch repos from GitHub (HTTP {repos_response.status_code})"}

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
      #find the latest commit date for current repo
      cur.execute("SELECT MAX(committed_at) FROM commits WHERE repo_github_id = %s", (repo["id"],))
      latest_commit_date = cur.fetchone()[0]

      #fetch the currnet etag
      cur.execute("SELECT etag FROM repositories WHERE repo_github_id = %s", (repo["id"],))
      etag = cur.fetchone()[0]

      if latest_commit_date is None: 
        since = "1970-01-01T00:00:00Z" #if no commits, set to epoch time
      else: since = latest_commit_date.isoformat() #convert datetime to ISO 8601 string
      since_param = f"since={since}"

      #initialize header for commit request
      commit_header = {"Authorization": f"Bearer {access_token}"}

      #if etag exists replace with etag, if not keep it as it is
      if etag:
        commit_header = {"Authorization": f"Bearer {access_token}", "If-None-Match": etag}
      else:
        commit_header = {"Authorization": f"Bearer {access_token}"}


      commit_response = httpx.get(
        f"https://api.github.com/repos/{repo['owner']['login']}/{repo['name']}/commits?per_page=100&{since_param}",
        headers=commit_header
      )

      #if no change has been made since last load Github returns 304, so no data to update -> continue
      if commit_response.status_code == 304:
        continue

      #if repo is empty/rate limited, skip and print error code
      #409 = empty repo, 403 = rate limited
      if commit_response.status_code != 200:
        print(f"skipped {repo['name']}: HTTP {commit_response.status_code}")
        continue

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
      #update the new etag from server to db
      cur.execute(
        "UPDATE repositories SET etag = %s WHERE repo_github_id = %s",
        (commit_response.headers.get("etag"), repo["id"])
      )

    conn.commit()



    #create rows by repo containing all of its commits
    #pagination 20 repos per page
    #filter by language
    offset=(page-1)*per_page

    sql = """
      SELECT r.name, r.language, r.stars_count, r.html_url, r.pushed_at, COUNT(c.sha) AS commit_count
      FROM repositories r
      LEFT JOIN commits c ON r.repo_github_id = c.repo_github_id
      WHERE r.owner_github_id = %s
    """
    params = [github_id]

    repo_count_sql = "SELECT COUNT(*) FROM repositories r WHERE r.owner_github_id = %s"
    repo_count_params = [github_id]

    if language:
      sql+=" AND language = %s"
      repo_count_sql+=" AND language = %s"
      params.append(language)
      repo_count_params.append(language)

    cur.execute(repo_count_sql, repo_count_params)
    repo_count = cur.fetchone()[0] #the [0] only returns the first colum of the tuple, which is the count
    has_next = repo_count > page*per_page

    sql+="""
      GROUP BY r.name, r.language, r.stars_count, r.html_url, r.pushed_at
      ORDER BY commit_count DESC
      LIMIT %s OFFSET %s
    """
    params.append(per_page)
    params.append(offset)

    cur.execute(sql, params)
    repo_rows = cur.fetchall()

    #1. initialize SQL query
      #1.1 FROM, call repostitories r
      #1.2. LEFT JOIN, call commits as c and find commits with matching repo_github_id and expand rows
        #   -> (repo_count) # of rows -> (commit_count) # of rows
        #    **  if a repo have no matching commit KEEP IT (THIS IS WHAT 'LEFT' DO)
      #1.3. WHERE, filter out rows that are NOT the current user's github_id
    #2. language filter: if lanague is provided, add the filter to the query and update params
    #3. execute the repo_count query to get total number of repos and check if there is a next page (pagnination)
    #4. After filtering add query that groups the rows by same repos
      #4.1. GROUP BY, sort the rows into buckets
      #4.2. ORDER, order the rows by commit_count descending orders
      #4.3. LIMIT, limit the number of rows returned to per_page
    #5. update the main SQL query params
    #6. execute the main SQL query and fetch all rows

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

    #1. FROM, call repository r
    #2. WHERE, this user's repos only, and skip repos with no language
    #3. GROUP BY, one bucket per distinct language
    #4. SELECT, count each bucket as repo_count
    #5. ORDER, sort by descending repo_count



    #commit activiy overtime
    cur.execute (
      """
        SELECT DATE_TRUNC('month', c.committed_at) AS month, COUNT(*) AS commit_count
        FROM commits c
        JOIN repositories r ON c.repo_github_id = r.repo_github_id
        WHERE r.owner_github_id = %s
        GROUP BY month
        ORDER BY month DESC
      """,
      (github_id,)
    )
    activity_rows = cur.fetchall()

    #1. FROM, call commits c
    #2. JOIN, call repository r, matching by repo_github_id on each commit and repo
    #3. WHERE, keep only commits belonging to this user's repos
    #4. GROUP BY, put all rows in same month into same bucket
    #5. SELECT, emit one row per month with COUNT(*) of the commits in that bucket
    #6. ORDER, newest month first

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
      ],

      "activities": [
        {
          "month": a[0],
          "commit_count": a[1]
        }
        for a in activity_rows
      ],

      "pagination": {
        "page": page,
        "per_page": per_page,
        "total": repo_count,
        "has_next": has_next
      }
    }
  finally:
    conn.close()
