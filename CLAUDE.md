# GitHub Analytics Platform

Backend portfolio project for 2027 summer internship applications. Built by a
3rd-year CS student rebuilding backend depth (strong JS/React background, a
finance-tracker project already built, limited backend experience, no prior
internships).

**One-line story:** "I built a platform that connects to your GitHub, syncs your
repos and commits in the background, and shows you analytics about your coding
activity."

## How Claude should work on this project

- **The user wants to LEARN this, not have it built for them.**
- Explain concepts before writing code — the "why," not just commands.
- When there's a design decision, present options + tradeoffs and let the user
  choose. Don't just pick and move on.
- The user writes the first draft of anything they'll need to explain in an
  interview. Review and improve their code rather than generating it wholesale.
  If they can't explain a piece of this project in an interview, it shouldn't be
  in the project.
- Keep it simple: one clear implementation, no speculative abstractions, no
  "backup" mechanisms, no unrequested features. Smallest change that correctly
  does the thing.
- Nudge the user to restate concepts in their own words at key moments — that's
  how they learn.
- Prefer diagrams and concrete examples over walls of abstract text.
- Call out commit points: whenever a logical, working unit is done, say so and
  give a conventional-commit message.
- Ask "why do you think we're doing this?" before explaining, when it's a good
  teaching moment.
- Gently correct mixed-up terminology (e.g. they've said "commitments" for
  "commits").
- Hold the user to finishing and understanding the current step before jumping
  ahead.

## Scope discipline

This project is deliberately scoped DOWN from a bigger feature list (Redis,
webhooks, AI summaries, health scores, notifications, dev comparisons) that would
be un-finishable and un-defendable at this stage. **Do not re-expand scope.** If
asked to add something from "out of scope" below, remind the user why it was cut
and make sure the core is done first.

**Out of scope until Phase 3 is genuinely done + there's time:**
- Redis caching (only once a query is genuinely slow enough to justify it)
- GitHub webhooks (real-time updates instead of scheduled sync — stretch goal)
- "Wrapped"-style summary view (pure frontend on data already fetched)

**Never for this project:** AI features, health scores, notifications, dev
comparisons.

## Tech stack (decided)

| Layer            | Choice                                                          |
|------------------|------------------------------------------------------------------|
| Language         | Python 3.11+                                                     |
| Web framework    | FastAPI                                                           |
| Server           | uvicorn (ASGI server running the FastAPI app)                    |
| Database         | PostgreSQL                                                        |
| DB access        | psycopg (raw SQL, to see the SQL) — SQLAlchemy only if an ORM is deliberately chosen |
| Validation       | Pydantic (built into FastAPI)                                     |
| Background jobs  | APScheduler (or cron + a script)                                  |
| External calls   | httpx or requests                                                 |
| Auth             | GitHub OAuth + session or JWT (pick ONE)                          |
| Tests            | pytest                                                             |
| Deployment       | Railway or Render (free tier)                                     |
| Frontend         | React + Vite — minimal; the backend is the point                 |

**Why FastAPI over Flask/Django:** built-in Pydantic validation, automatic
`/docs`, async-native (useful given heavy external GitHub API calls), modern
Python backend standard. Flask needs bolted-on validation; Django's ORM/admin/
templates are overkill since the frontend is separate React.

**Mental model already internalized:** request flows `browser → uvicorn →
FastAPI app` and back. Uvicorn moves raw HTTP both directions and does no
business logic. FastAPI (with Pydantic inside it) does the real work: validate
input, call GitHub, query Postgres, shape the response.

## Roadmap

Every phase must end with a WORKING, DEPLOYED app before moving to the next one.
A polished earlier phase beats a broken later one.

**Phase 0 — Foundation**
- [x] Empty repo, first commit
- [x] Python venv, dependencies pinned in `requirements.txt`
- [x] `.gitignore` (Python template — protects `venv/` and `.env`)
- [x] FastAPI app with a `/health` route
- [x] Env var loading via `.env` (chose Pydantic Settings over python-dotenv,
      for validation + fail-loudly-at-startup behavior)
- [x] Postgres running locally via Docker (plain `docker run`, not
      docker-compose — deliberately kept simple for a single-service setup).
      Container name `postgres`, db `github_analytics`, confirmed reachable
      from Python via `psycopg` (`SELECT 1` round-trip proved the connection).
- [x] Deployed to Railway as hello-world. Two-service confusion resolved along
      the way (env vars must be set per-service, not shared automatically
      within a Railway project); start command `uvicorn main:app --host
      0.0.0.0 --port $PORT`; public domain generated via Settings → Networking.
- **Phase 0 complete.** Live URL confirmed returning `{"status":"ok","test_value":"succeed"}`.

**Phase 1 — Auth + first real data (the spine)**
- [x] GitHub OAuth login flow — works end to end locally
- [x] Sessions (chose DB-backed sessions over JWT, for instant revocation)
- [x] Fetch repos from GitHub — happens on dashboard load, deliberately, so the
      cost of per-request fetching is felt before Phase 3 moves it to a job
- [x] `users`, `sessions`, `repositories` tables with real foreign keys
- [x] Dashboard listing the logged-in user's repos
- [x] **Deployed and working** — real login, real repos, live URL
- **Phase 1 complete (2026-08-15).**

**Deployment notes:**
- Two GitHub OAuth apps: dev (localhost callback) and prod (Railway callback).
  Prod credentials live only in Railway's Variables, never in `.env`.
- Tables are created by `init_db()` in `main.py`, which runs `schema.sql` at
  startup against `settings.database_url` — the same connection string the rest
  of the app uses. This was the fix for a long debugging session where the schema
  had been loaded into a *different* Postgres instance than the app connected to
  (same db name `railway` and user `postgres`, different host, so the strings
  looked identical). Letting the app provision its own tables removes the
  possibility of the two disagreeing.
- Limitation to remember: `init_db()` only CREATEs tables, it cannot ALTER them.
  Adding a column to an existing table still needs a manual ALTER on each
  environment. Migration tooling (Alembic) is the real answer if the schema
  starts changing often — worth reaching for in Phase 2 if it becomes painful.
- Railway's auto-deploy did not fire on push twice; deploys had to be triggered
  manually. Check Settings → Source if this continues.
- Debugging lesson worth keeping: staged ≠ committed ≠ pushed ≠ deployed. When
  local and production disagree, verify what is *actually running* (e.g. have an
  endpoint report its own state) before suspecting the code.

**Phase 2 — Commits + a real schema**
- [x] `commits` table (FK to `repositories`), fetched per repo on dashboard load
- [x] Dashboard analytics, all computed in SQL rather than Python:
      commit counts per repo (LEFT JOIN + GROUP BY), language breakdown
      (GROUP BY on repositories), activity over time (DATE_TRUNC by month)
- [x] Server-side pagination (LIMIT/OFFSET) and optional language filter, with
      the WHERE clause built by concatenation so filters compose
- [x] **Indexes — deliberately none.** Measured, not assumed:
      - Current volume (5 repos, 83 commits): Seq Scan, ~0.05ms. An index would
        be ignored entirely.
      - Benchmarked at 1000 repos / 200k commits: dashboard query took ~52ms,
        and adding an index on `commits.repo_github_id` only moved it to ~39ms —
        Postgres still chose a Seq Scan. **Indexes help queries that skip most
        rows; they don't help queries that need all of them.** This query
        aggregates every commit, so there is nothing to skip.
      - Same data, single-repo lookup (`WHERE repo_github_id = 42`, 200 of 200k
        rows): 5.2ms → 0.57ms with the index, and the planner used it. That is
        the shape of query an index is for.
      - So the real fix at scale is restructuring — paginate to the current
        page's repos *before* aggregating — not adding an index.
      - Primary keys (`sessions.session_id` etc.) are indexed automatically.
- [ ] Rate limit handling — the one Phase 2 item still open
- Done when: dashboard shows commit analytics, repo list filters/paginates
  server-side. **This is the point the project becomes resume-worthy.**

**Phase 3 — Background sync**
- Move GitHub fetching out of the request path into a scheduled job (APScheduler)
- Re-sync repos and commits on a schedule
- Dashboard reads from the database, never GitHub directly
- Incremental sync (only fetch what changed)
- Done when: log in, close the app, data keeps updating on its own.
- Build only after feeling the pain of per-request fetching in Phases 1–2.

## Timing

~6–8 weeks before internship applications open. LeetCode (NeetCode 75) and the
finance tracker come first — this project runs part-time alongside them. Realistic
pace: Phase 0–1 in the first week or two, Phase 2 is where it becomes
resume-worthy. Don't rush to Phase 3.

## Git workflow

- Commit at each logical, working checkpoint, as you go — never reconstructed
  after the fact.
- Conventional commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`.
  Imperative mood, ~50 char subject.
- One concern per commit — if the message needs "and," it's probably two commits.
- Feature branches, merge to main, even solo.
- Never fake history (no backdating, no artificial splitting).
- `.gitignore` must keep `venv/`, `__pycache__/`, and especially `.env` out of the
  repo — `.env` will hold the GitHub OAuth client secret and DB credentials and
  must never be committed.
