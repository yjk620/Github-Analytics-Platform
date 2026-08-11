CREATE TABLE users (
    github_id BIGINT PRIMARY KEY,
    login TEXT NOT NULL,
    name TEXT,
    avatar_url TEXT NOT NULL,
    bio TEXT,
    access_token TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE sessions (
  session_id TEXT PRIMARY KEY,
  github_id BIGINT NOT NULL REFERENCES users(github_id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '7 days'
);