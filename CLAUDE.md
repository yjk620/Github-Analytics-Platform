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
- GitHub OAuth login flow (hardest + most valuable piece — go slow)
- Session or JWT auth (pick one, don't build both)
- After login, call GitHub API once, on demand, for the user's repos
- Store in Postgres: `users` and `repositories` tables with a real foreign key
- Validate with Pydantic
- Dashboard listing the logged-in user's repos (name, language, stars, last commit)
- Done when: log in with GitHub, real repos appear on a deployed dashboard.
- Must be able to explain WHY the OAuth flow has the steps it does before moving on.

**Phase 2 — Commits + a real schema**
- Fetch commits per repo into a `commits` table (FK to `repositories`)
- First real encounter with GitHub rate limits — handle deliberately here
- Add indexes where queries need them; be able to explain why
- Dashboard gains: commit counts, language breakdown, activity over time
- Server-side filtering and pagination on the repo list
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
