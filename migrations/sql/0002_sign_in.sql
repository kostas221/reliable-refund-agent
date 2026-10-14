-- Sign-in for the HTTP layer (plan section 7): a password hash per user and server-side sessions.

-- An argon2 hash, never the password. NULL: the user cannot sign in.
ALTER TABLE users ADD COLUMN password_hash text;

-- A session lives in the database, so it survives a restart and a sign-out really ends it. The browser holds a
-- random token in an HttpOnly cookie; this table keeps only its SHA-256, so reading the table does not let anyone
-- sign in.
CREATE TABLE sessions (
    id text PRIMARY KEY,
    user_id text NOT NULL REFERENCES users (id),
    -- Sent back by the screens in a header with every change (synchronizer token against CSRF).
    csrf_token text NOT NULL,
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    CHECK (expires_at > created_at)
);

GRANT SELECT, INSERT ON sessions TO refund_app;
GRANT UPDATE (revoked_at) ON sessions TO refund_app;
