create table settings
(
    key         TEXT                        not null
        primary key,
    value       TEXT      default ''        not null,
    value_type  TEXT      default 'str'     not null,
    description TEXT      default '',
    category    TEXT      default 'general' not null,
    updated_at  TIMESTAMP default CURRENT_TIMESTAMP
);