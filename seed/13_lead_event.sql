-- synthetic activity fixture
INSERT INTO lead_event (id, lead_id, event_type, detail, occurred_at) VALUES (1, 1, 'stage_change', 'seed stage fixture', '2026-09-19 07:00:00');
-- synthetic activity fixture
INSERT INTO lead_event (id, lead_id, event_type, detail, occurred_at) VALUES (2, 2, 'stage_change', 'seed stage fixture', '2026-09-19 07:00:00');
-- synthetic activity fixture
INSERT INTO lead_event (id, lead_id, event_type, detail, occurred_at) VALUES (3, 3, 'stage_change', 'seed stage fixture', '2026-09-19 07:00:00');
-- synthetic activity fixture
INSERT INTO lead_event (id, lead_id, event_type, detail, occurred_at) VALUES (4, 4, 'stage_change', 'seed stage fixture', '2026-09-19 07:00:00');
-- synthetic activity fixture
INSERT INTO lead_event (id, lead_id, event_type, detail, occurred_at) VALUES (5, 5, 'stage_change', 'seed stage fixture', '2026-09-19 07:00:00');
-- synthetic note-history coverage
INSERT INTO lead_event (id, lead_id, event_type, detail, occurred_at) VALUES (101, 5, 'note_edited', 'note added', '2026-09-19 07:00:00');
-- synthetic activity fixture
INSERT INTO lead_event (id, lead_id, event_type, detail, occurred_at) VALUES (6, 6, 'stage_change', 'seed stage fixture', '2026-09-19 07:00:00');
-- synthetic activity fixture
INSERT INTO lead_event (id, lead_id, event_type, detail, occurred_at) VALUES (7, 7, 'stage_change', 'seed stage fixture', '2026-09-19 07:00:00');
-- synthetic activity fixture
INSERT INTO lead_event (id, lead_id, event_type, detail, occurred_at) VALUES (8, 8, 'stage_change', 'seed stage fixture', '2026-09-19 07:00:00');
-- synthetic activity fixture
INSERT INTO lead_event (id, lead_id, event_type, detail, occurred_at) VALUES (9, 9, 'stage_change', 'seed stage fixture', '2026-09-19 07:00:00');
-- synthetic activity fixture
INSERT INTO lead_event (id, lead_id, event_type, detail, occurred_at) VALUES (10, 10, 'stage_change', 'seed stage fixture', '2026-09-19 07:00:00');
-- synthetic activity fixture
INSERT INTO lead_event (id, lead_id, event_type, detail, occurred_at) VALUES (11, 11, 'stage_change', 'seed stage fixture', '2026-09-19 07:00:00');
-- synthetic activity fixture
INSERT INTO lead_event (id, lead_id, event_type, detail, occurred_at) VALUES (12, 12, 'stage_change', 'seed stage fixture', '2026-09-19 07:00:00');
-- synthetic activity fixture
INSERT INTO lead_event (id, lead_id, event_type, detail, occurred_at) VALUES (13, 13, 'stage_change', 'seed stage fixture', '2026-09-19 07:00:00');
-- synthetic contact-log coverage
INSERT INTO lead_event (id, lead_id, event_type, detail, occurred_at) VALUES (201, 4, 'contact_logged', 'last_contact_date: None -> 2026-09-19', '2026-09-19 07:40:00');
-- synthetic deadline-refresh coverage
INSERT INTO lead_event (id, lead_id, event_type, detail, occurred_at) VALUES (202, 4, 'deadline_changed', 'deadline: 2026-09-19 -> 2026-10-17', '2026-09-19 07:41:00');
-- synthetic field-edit coverage
INSERT INTO lead_event (id, lead_id, event_type, detail, occurred_at) VALUES (200, 2, 'field_edited', 'company_override: None -> Seed Co', '2026-09-19 07:30:00');
