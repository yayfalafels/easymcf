-- no real cookie payload is ever seeded, cookie_ref names a file this seed never creates
INSERT INTO mcf_session (id, user_id, status, uploaded_at, cookie_ref, confirmed_account_email, confirmed_at) VALUES (1, 1, 'valid', '2026-09-21 12:00:00', 'mcf_session_1.json', 'yayfalafels@gmail.com', '2026-09-21 12:00:00');
-- no real cookie payload is ever seeded, cookie_ref names a file this seed never creates
INSERT INTO mcf_session (id, user_id, status, uploaded_at, cookie_ref, confirmed_account_email, confirmed_at) VALUES (2, 2, 'missing', NULL, NULL, NULL, NULL);
