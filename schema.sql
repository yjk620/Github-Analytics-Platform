CREATE TABLE IF NOT EXISTS users (
    github_id BIGINT PRIMARY KEY,
    login TEXT NOT NULL,
    name TEXT,
    avatar_url TEXT NOT NULL,
    bio TEXT,
    access_token TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY,
  github_id BIGINT NOT NULL REFERENCES users(github_id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '7 days'
);

CREATE TABLE IF NOT EXISTS repositories (
    repo_github_id BIGINT PRIMARY KEY,
    owner_github_id BIGINT NOT NULL REFERENCES users(github_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    language TEXT,
    stars_count INT NOT NULL,
    html_url TEXT NOT NULL,
    fork BOOLEAN NOT NULL,
    fork_count INT NOT NULL,
    pushed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);