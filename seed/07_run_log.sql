-- synthetic run-log coverage
INSERT INTO run_log (id, run_type, user_id, track_id, started_at, ended_at, status, outcome_counts, error_detail, trigger_source) VALUES (1, 'search', 1, 1, '2026-09-21 08:00:00', '2026-09-21 08:02:00', 'success', '{"new_posts": 3}', NULL, 'manual');
-- synthetic run-log coverage
INSERT INTO run_log (id, run_type, user_id, track_id, started_at, ended_at, status, outcome_counts, error_detail, trigger_source) VALUES (2, 'search', 1, 2, '2026-09-21 08:03:00', '2026-09-21 08:05:00', 'partial', '{"new_posts": 1}', 'one fixture detail page was unavailable', 'manual');
-- synthetic run-log coverage
INSERT INTO run_log (id, run_type, user_id, track_id, started_at, ended_at, status, outcome_counts, error_detail, trigger_source) VALUES (3, 'apply', 1, NULL, '2026-09-21 09:00:00', '2026-09-21 09:03:00', 'success', '{"applied": 1, "cv_not_found": 1, "post_unavailable": 1, "questionnaire_required": 1, "unable_to_apply": 1}', NULL, 'manual');
-- synthetic run-log coverage
INSERT INTO run_log (id, run_type, user_id, track_id, started_at, ended_at, status, outcome_counts, error_detail, trigger_source) VALUES (4, 'apply', 1, NULL, '2026-09-21 09:04:00', '2026-09-21 09:05:00', 'failed', '{"cv_selector_error": 1}', 'RuntimeError: synthetic worker failure after 1 of 1 queued leads', 'manual');
-- synthetic run-log coverage
INSERT INTO run_log (id, run_type, user_id, track_id, started_at, ended_at, status, outcome_counts, error_detail, trigger_source) VALUES (5, 'search', 1, 1, '2026-09-21 10:00:00', NULL, 'running', '{"new_posts": 0}', NULL, 'manual');
-- synthetic run-log coverage
INSERT INTO run_log (id, run_type, user_id, track_id, started_at, ended_at, status, outcome_counts, error_detail, trigger_source) VALUES (6, 'search', 2, 7, '2026-09-21 11:00:00', '2026-09-21 11:02:00', 'success', '{"new_posts": 1}', NULL, 'scheduled');
-- synthetic run-log coverage
INSERT INTO run_log (id, run_type, user_id, track_id, started_at, ended_at, status, outcome_counts, error_detail, trigger_source) VALUES (7, 'apply', 1, NULL, '2026-09-21 09:10:00', '2026-09-21 09:12:00', 'success', '{"applied": 1, "invalid_input": 1, "post_closed": 1}', NULL, 'manual');
-- synthetic run-log coverage
INSERT INTO run_log (id, run_type, user_id, track_id, started_at, ended_at, status, outcome_counts, error_detail, trigger_source) VALUES (8, 'apply', 2, NULL, '2026-09-21 11:10:00', '2026-09-21 11:12:00', 'success', '{"applied": 1, "cv_not_found": 1}', NULL, 'manual');
