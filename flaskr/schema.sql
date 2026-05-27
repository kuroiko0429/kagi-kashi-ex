DROP TABLE IF EXISTS clubs;
DROP TABLE IF EXISTS members;
DROP TABLE IF EXISTS borrow_records;
DROP TABLE IF EXISTS activity_reports;
DROP TABLE IF EXISTS favorites;

CREATE TABLE clubs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL,
  room_number TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'locked', -- 'locked' (施錠中), 'active' (活動中), 'temp_locked' (一時施錠中)
  message TEXT,
  icon_color TEXT NOT NULL, -- e.g., '#10b981'
  key_number TEXT NOT NULL
);

CREATE TABLE members (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id TEXT NOT NULL,
  name TEXT NOT NULL,
  club_id INTEGER NOT NULL,
  registered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, -- 新規追加: サークル登録日 (退部制限用)
  FOREIGN KEY (club_id) REFERENCES clubs (id)
);

CREATE TABLE borrow_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  club_id INTEGER NOT NULL,
  student_id TEXT NOT NULL,
  student_name TEXT NOT NULL,
  key_number TEXT NOT NULL,
  borrowed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  returned_at TIMESTAMP,
  FOREIGN KEY (club_id) REFERENCES clubs (id)
);

CREATE TABLE activity_reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  club_id INTEGER NOT NULL,
  reporter_name TEXT NOT NULL,
  student_id TEXT NOT NULL,
  report_date TEXT NOT NULL,
  description TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (club_id) REFERENCES clubs (id)
);

CREATE TABLE favorites (
  student_id TEXT NOT NULL,
  club_id INTEGER NOT NULL,
  PRIMARY KEY (student_id, club_id),
  FOREIGN KEY (club_id) REFERENCES clubs (id)
);
