create table llm_providers
(
    id          TEXT
        primary key,
    name        TEXT                       not null,
    auth_type   TEXT      default 'bearer' not null,
    api_url     TEXT      default ''       not null,
    api_key     TEXT      default ''       not null,
    model       TEXT      default ''       not null,
    api_version TEXT      default ''       not null,
    max_tokens  INTEGER   default 4096     not null,
    temperature REAL      default 0.7      not null,
    timeout     INTEGER   default 120      not null,
    is_active   INTEGER   default 0        not null,
    created_at  TIMESTAMP default CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP default CURRENT_TIMESTAMP
);

INSERT INTO llm_providers (id, name, auth_type, api_url, api_key, model, api_version, max_tokens, temperature, timeout, is_active, created_at, updated_at) VALUES ('d14010f4', 'Ollama', 'OpenAI', 'http://localhost:11434/v1', '', 'qwen3:4b', '', 40960, 0.7, 120, 0, '2026-04-25 12:56:26', '2026-05-01 05:56:18');