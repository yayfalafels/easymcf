-- no real cookie payload is ever seeded; a seeded row must not claim an authenticated session
INSERT INTO mcf_session (id, user_id, status, uploaded_at, cookie_ref, confirmed_account_email, confirmed_at) VALUES (1, 1, 'missing', NULL, NULL, '{{INITIAL_USER_EMAIL}}', '2026-09-21 12:00:00');
-- no real cookie payload is ever seeded; a seeded row must not claim an authenticated session
INSERT INTO mcf_session (id, user_id, status, uploaded_at, cookie_ref, confirmed_account_email, confirmed_at) VALUES (2, 2, 'missing', NULL, NULL, NULL, NULL);
