create table strategy_performance
(
    strategy_name         TEXT
        primary key,
    total_decisions       INTEGER default 0,
    success_rate          REAL,
    avg_confidence        REAL,
    avg_execution_time_ms REAL,
    feedback_correct_rate REAL,
    weight                REAL    default 1.0
);

