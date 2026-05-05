create table memory_entries
(
    memory_id        TEXT
        primary key,
    level            TEXT      not null,
    scope_id         TEXT      not null,
    content          TEXT      not null,
    metadata_json    TEXT    default '{}',
    created_at       TIMESTAMP not null,
    last_accessed_at TIMESTAMP not null,
    access_count     INTEGER default 0,
    retention        REAL    default 1.0,
    is_archived      INTEGER default 0,
    summary          TEXT
);

create index idx_memory_retention
    on memory_entries (retention);

create index idx_memory_scope
    on memory_entries (level, scope_id);
