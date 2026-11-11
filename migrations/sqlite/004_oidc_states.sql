-- Chorus pilot: estados OIDC (PKCE) pendientes de callback.
CREATE TABLE oidc_states (
    state TEXT PRIMARY KEY,
    verifier TEXT NOT NULL,
    nonce TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX idx_oidc_states_created ON oidc_states (created_at);
