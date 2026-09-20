-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (1, 1, 'stage_change', 'promoted to TOAPPLY', NULL, 'TOAPPLY', '2026-09-19 07:00:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (2, 2, 'stage_change', 'added manually at APPLIED', NULL, 'APPLIED', '2026-09-19 07:00:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (3, 3, 'stage_change', 'promoted to TOAPPLY', NULL, 'TOAPPLY', '2026-09-19 07:00:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (4, 3, 'stage_change', NULL, 'TOAPPLY', 'APPLIED', '2026-09-19 07:01:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (5, 3, 'stage_change', NULL, 'APPLIED', 'CALLBACK', '2026-09-19 07:02:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (6, 4, 'stage_change', 'promoted to TOAPPLY', NULL, 'TOAPPLY', '2026-09-19 07:00:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (7, 4, 'stage_change', NULL, 'TOAPPLY', 'APPLIED', '2026-09-19 07:01:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (8, 4, 'stage_change', NULL, 'APPLIED', 'CALLBACK', '2026-09-19 07:02:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (9, 4, 'stage_change', NULL, 'CALLBACK', 'INTERVIEW', '2026-09-19 07:03:00');
-- synthetic note-history coverage
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (10, 4, 'note_edited', 'note added', 'INTERVIEW', 'INTERVIEW', '2026-09-19 07:30:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (11, 5, 'stage_change', 'promoted to TOAPPLY', NULL, 'TOAPPLY', '2026-09-19 07:00:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (12, 5, 'stage_change', NULL, 'TOAPPLY', 'APPLIED', '2026-09-19 07:01:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (13, 5, 'stage_change', NULL, 'APPLIED', 'CALLBACK', '2026-09-19 07:02:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (14, 5, 'stage_change', NULL, 'CALLBACK', 'INTERVIEW', '2026-09-19 07:03:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (15, 5, 'stage_change', NULL, 'INTERVIEW', 'OFFER', '2026-09-19 07:04:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (16, 5, 'stage_change', 'close_reason: None -> rejected', 'OFFER', 'CLOSED', '2026-09-19 07:05:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (17, 5, 'stage_change', 're-opened from an offer', 'CLOSED', 'INTERVIEW', '2026-09-19 07:06:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (18, 5, 'stage_change', NULL, 'INTERVIEW', 'OFFER', '2026-09-19 07:07:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (19, 6, 'stage_change', 'promoted to TOAPPLY', NULL, 'TOAPPLY', '2026-09-19 07:00:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (20, 6, 'stage_change', NULL, 'TOAPPLY', 'APPLIED', '2026-09-19 07:01:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (21, 6, 'stage_change', NULL, 'APPLIED', 'CALLBACK', '2026-09-19 07:02:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (22, 6, 'stage_change', NULL, 'CALLBACK', 'INTERVIEW', '2026-09-19 07:03:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (23, 6, 'stage_change', NULL, 'INTERVIEW', 'OFFER', '2026-09-19 07:04:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (24, 6, 'stage_change', 'close_reason: None -> offer_accepted', 'OFFER', 'CLOSED', '2026-09-19 07:05:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (25, 7, 'stage_change', 'promoted to TOAPPLY', NULL, 'TOAPPLY', '2026-09-19 07:00:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (26, 7, 'stage_change', NULL, 'TOAPPLY', 'APPLIED', '2026-09-19 07:01:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (27, 7, 'stage_change', 'close_reason: None -> rejected', 'APPLIED', 'CLOSED', '2026-09-19 07:02:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (28, 8, 'stage_change', 'promoted to TOAPPLY', NULL, 'TOAPPLY', '2026-09-19 07:00:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (29, 8, 'stage_change', NULL, 'TOAPPLY', 'APPLIED', '2026-09-19 07:01:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (30, 8, 'stage_change', 'close_reason: None -> withdrawn', 'APPLIED', 'CLOSED', '2026-09-19 07:02:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (31, 9, 'stage_change', 'promoted to TOAPPLY', NULL, 'TOAPPLY', '2026-09-19 07:00:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (32, 9, 'stage_change', NULL, 'TOAPPLY', 'APPLIED', '2026-09-19 07:01:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (33, 9, 'stage_change', 'close_reason: None -> expired', 'APPLIED', 'CLOSED', '2026-09-19 07:02:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (34, 10, 'stage_change', 'promoted to TOAPPLY', NULL, 'TOAPPLY', '2026-09-19 07:00:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (35, 10, 'stage_change', 'close_reason: None -> cancelled', 'TOAPPLY', 'CLOSED', '2026-09-19 07:01:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (36, 11, 'stage_change', 'promoted to TOAPPLY', NULL, 'TOAPPLY', '2026-09-19 07:00:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (37, 11, 'stage_change', 'close_reason: None -> duplicate', 'TOAPPLY', 'CLOSED', '2026-09-19 07:01:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (38, 12, 'stage_change', 'promoted to TOAPPLY', NULL, 'TOAPPLY', '2026-09-19 07:00:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (39, 12, 'stage_change', 'close_reason: None -> apply_failed', 'TOAPPLY', 'CLOSED', '2026-09-19 07:01:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (40, 13, 'stage_change', 'promoted to TOAPPLY', NULL, 'TOAPPLY', '2026-09-19 07:00:00');
-- synthetic stage history
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (41, 13, 'stage_change', 'close_reason: None -> dropped', 'TOAPPLY', 'CLOSED', '2026-09-19 07:01:00');
-- synthetic event coverage
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (42, 1, 'field_edited', 'company_override: None -> Seed Co', 'TOAPPLY', 'TOAPPLY', '2026-09-19 07:31:00');
-- synthetic event coverage
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (43, 3, 'contact_logged', 'last_contact_date: None -> 2026-09-19', 'CALLBACK', 'CALLBACK', '2026-09-19 07:40:00');
-- synthetic event coverage
INSERT INTO lead_event (id, lead_id, event_type, detail, stage_from, stage_to, occurred_at) VALUES (44, 3, 'deadline_changed', 'deadline: 2026-09-19 -> 2026-10-17', 'CALLBACK', 'CALLBACK', '2026-09-19 07:41:00');
