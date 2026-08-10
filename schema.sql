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