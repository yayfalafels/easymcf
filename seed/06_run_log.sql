-- synthetic run-log coverage
INSERT INTO run_log (id, run_type, track_id, started_at, ended_at, status, outcome_counts, error_detail) VALUES (1, 'search', 1, '2026-09-15 08:00:00', '2026-09-15 08:02:00', 'success', '{"new_posts": 3}', NULL);
-- synthetic run-log coverage
INSERT INTO run_log (id, run_type, track_id, started_at, ended_at, status, outcome_counts, error_detail) VALUES (2, 'search', 2, '2026-09-15 08:03:00', '2026-09-15 08:05:00', 'partial', '{"new_posts": 1}', 'one fixture detail page was unavailable');
-- synthetic run-log coverage
INSERT INTO run_log (id, run_type, track_id, started_at, ended_at, status, outcome_counts, error_detail) VALUES (3, 'apply', NULL, '2026-09-15 09:00:00', '2026-09-15 09:03:00', 'success', '{"applied": 1}', NULL);
-- synthetic run-log coverage
INSERT INTO run_log (id, run_type, track_id, started_at, ended_at, status, outcome_counts, error_detail) VALUES (4, 'apply', NULL, '2026-09-15 09:04:00', '2026-09-15 09:05:00', 'failed', '{"failed": 1}', 'synthetic failure fixture');
-- synthetic run-log coverage
INSERT INTO run_log (id, run_type, track_id, started_at, ended_at, status, outcome_counts, error_detail) VALUES (5, 'search', 1, '2026-09-15 10:00:00', NULL, 'running', '{"new_posts": 0}', NULL);
