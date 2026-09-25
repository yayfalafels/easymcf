-- synthetic apply outcome coverage
INSERT INTO application (id, lead_id, cv_id, status, error_detail, attempted_at, run_id) VALUES (1, 3, 1, 'applied', NULL, '2026-09-21 09:00:00', 3);
-- synthetic apply outcome coverage
INSERT INTO application (id, lead_id, cv_id, status, error_detail, attempted_at, run_id) VALUES (2, 1, 1, 'questionnaire_required', 'synthetic questionnaire_required fixture', '2026-09-21 09:00:00', 4);
-- synthetic apply outcome coverage
INSERT INTO application (id, lead_id, cv_id, status, error_detail, attempted_at, run_id) VALUES (3, 1, 1, 'cv_selector_error', 'synthetic cv_selector_error fixture', '2026-09-21 09:00:00', 4);
-- synthetic apply outcome coverage
INSERT INTO application (id, lead_id, cv_id, status, error_detail, attempted_at, run_id) VALUES (4, 1, 1, 'unable_to_apply', 'synthetic unable_to_apply fixture', '2026-09-21 09:00:00', 4);
-- synthetic apply outcome coverage
INSERT INTO application (id, lead_id, cv_id, status, error_detail, attempted_at, run_id) VALUES (5, 12, 1, 'post_unavailable', 'synthetic post_unavailable fixture', '2026-09-21 09:00:00', 4);
-- synthetic apply outcome coverage
INSERT INTO application (id, lead_id, cv_id, status, error_detail, attempted_at, run_id) VALUES (6, 1, 1, 'cv_not_found', 'synthetic cv_not_found fixture', '2026-09-21 09:00:00', 4);
-- synthetic apply outcome coverage
INSERT INTO application (id, lead_id, cv_id, status, error_detail, attempted_at, run_id) VALUES (7, 12, 1, 'post_closed', 'synthetic post_closed fixture', '2026-09-21 09:00:00', 4);
-- synthetic apply outcome coverage
INSERT INTO application (id, lead_id, cv_id, status, error_detail, attempted_at, run_id) VALUES (8, 1, 1, 'invalid_input', 'synthetic invalid_input fixture', '2026-09-21 09:00:00', 4);
-- synthetic retry pair
INSERT INTO application (id, lead_id, cv_id, status, error_detail, attempted_at, run_id) VALUES (9, 3, 1, 'applied', NULL, '2026-09-21 09:01:00', 3);
-- synthetic retry pair
INSERT INTO application (id, lead_id, cv_id, status, error_detail, attempted_at, run_id) VALUES (10, 3, 1, 'applied', NULL, '2026-09-21 09:02:00', 3);
-- second user apply attempt
INSERT INTO application (id, lead_id, cv_id, status, error_detail, attempted_at, run_id) VALUES (11, 16, 3, 'applied', NULL, '2026-09-21 11:01:00', 6);
