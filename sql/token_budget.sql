create table token_budget
(
    id             INTEGER
        primary key autoincrement,
    daily_budget   REAL      default 10.0,
    monthly_budget REAL      default 300.0,
    alert_email    TEXT,
    updated_at     TIMESTAMP default CURRENT_TIMESTAMP
);

