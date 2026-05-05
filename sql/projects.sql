create table projects
(
    project_id  TEXT                  not null
        primary key,
    name        TEXT                  not null,
    description TEXT default '',
    status      TEXT default 'active' not null,
    created_by  TEXT default '',
    created_at  TEXT default CURRENT_TIMESTAMP,
    updated_at  TEXT default CURRENT_TIMESTAMP
);
