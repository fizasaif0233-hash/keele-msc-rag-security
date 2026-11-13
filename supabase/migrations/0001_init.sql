-- RAG Security Evaluation Platform
-- Apply this script in the Supabase SQL editor after enabling the vector extension.
-- It is safe to run more than once. It does not delete existing rows.
--
-- The embedding column is vector(1536), matching app/constants.py.
-- Changing the embedding model dimension requires a new migration.

create extension if not exists vector;
create extension if not exists pgcrypto;

create table if not exists public.profiles (
    id uuid primary key references auth.users (id) on delete cascade,
    email text not null unique,
    role text not null default 'employee' check (role in ('admin', 'employee', 'researcher')),
    created_at timestamptz not null default now()
);

create table if not exists public.documents (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid not null references public.profiles (id),
    title text not null,
    file_path text not null,
    document_type text not null,
    access_level text not null check (access_level in ('public', 'employee', 'hr', 'confidential', 'admin')),
    processing_status text not null default 'pending' check (
        processing_status in ('pending', 'processing', 'ready', 'failed')
    ),
    content_hash text,
    extracted_text text,
    error_message text,
    protected_markers text[] not null default '{}',
    chunk_count integer not null default 0,
    created_at timestamptz not null default now(),
    unique (owner_id, content_hash)
);

create table if not exists public.document_permissions (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null references public.documents (id) on delete cascade,
    user_id uuid not null references public.profiles (id) on delete cascade,
    permission text not null default 'read' check (permission in ('read')),
    created_at timestamptz not null default now(),
    unique (document_id, user_id)
);

create table if not exists public.document_chunks (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null references public.documents (id) on delete cascade,
    chunk_index integer not null,
    content text not null,
    embedding vector(1536),
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (document_id, chunk_index)
);

create table if not exists public.chat_sessions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.profiles (id) on delete cascade,
    title text not null default 'New chat',
    configuration text not null default 'secured' check (configuration in ('baseline', 'secured')),
    created_at timestamptz not null default now()
);

create table if not exists public.chat_messages (
    id uuid primary key default gen_random_uuid(),
    session_id uuid not null references public.chat_sessions (id) on delete cascade,
    role text not null check (role in ('user', 'assistant', 'system')),
    content text not null,
    latency_ms integer,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.test_datasets (
    id uuid primary key default gen_random_uuid(),
    name text not null unique,
    description text not null default '',
    created_by uuid references public.profiles (id),
    created_at timestamptz not null default now()
);

create table if not exists public.test_cases (
    id uuid primary key default gen_random_uuid(),
    dataset_id uuid not null references public.test_datasets (id) on delete cascade,
    category text not null check (
        category in (
            'benign',
            'direct_prompt_injection',
            'indirect_prompt_injection',
            'unauthorised_disclosure',
            'input_validation'
        )
    ),
    title text not null,
    description text not null default '',
    input text not null,
    expected_outcome text not null,
    evaluation_criteria jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.experiments (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    configuration text not null check (configuration in ('baseline', 'secured')),
    dataset_id uuid not null references public.test_datasets (id),
    repetitions integer not null check (repetitions between 1 and 20),
    status text not null default 'pending' check (status in ('pending', 'running', 'completed', 'failed', 'cancelled')),
    parameters jsonb not null default '{}'::jsonb,
    comparison_group uuid,
    created_by uuid references public.profiles (id),
    started_at timestamptz,
    completed_at timestamptz,
    progress_completed integer not null default 0,
    progress_total integer not null default 0,
    error_message text,
    created_at timestamptz not null default now()
);

create table if not exists public.test_results (
    id uuid primary key default gen_random_uuid(),
    experiment_id uuid not null references public.experiments (id) on delete cascade,
    test_case_id uuid not null references public.test_cases (id),
    repetition_number integer not null check (repetition_number >= 1),
    actual_outcome text not null,
    attack_success boolean not null default false,
    information_disclosed boolean not null default false,
    legitimate_task_success boolean not null default false,
    response_latency_ms integer,
    evaluation_details jsonb not null default '{}'::jsonb,
    error_message text,
    created_at timestamptz not null default now(),
    unique (experiment_id, test_case_id, repetition_number)
);

create table if not exists public.security_logs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references public.profiles (id),
    event_type text not null,
    severity text not null,
    outcome text not null,
    configuration text,
    experiment_id uuid,
    test_case_id uuid,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.app_settings (
    key text primary key,
    value jsonb not null,
    updated_at timestamptz not null default now()
);

create index if not exists documents_owner_idx on public.documents (owner_id);
create index if not exists documents_access_idx on public.documents (access_level);
create index if not exists chunks_document_idx on public.document_chunks (document_id);
create index if not exists chat_sessions_user_idx on public.chat_sessions (user_id);
create index if not exists chat_messages_session_idx on public.chat_messages (session_id, created_at);
create index if not exists test_cases_dataset_idx on public.test_cases (dataset_id);
create index if not exists experiments_dataset_idx on public.experiments (dataset_id, status);
create index if not exists test_results_experiment_idx on public.test_results (experiment_id);
create index if not exists security_logs_created_idx on public.security_logs (created_at desc);
create index if not exists document_chunks_embedding_idx
    on public.document_chunks using hnsw (embedding vector_cosine_ops);

-- A null or empty allow-list returns no rows. The API always passes an explicit list.
create or replace function public.match_document_chunks(
    query_embedding vector(1536),
    match_count integer,
    similarity_threshold double precision,
    allowed_document_ids uuid[]
)
returns table (
    chunk_id uuid,
    document_id uuid,
    title text,
    access_level text,
    chunk_index integer,
    content text,
    similarity double precision
)
language sql
stable
as $$
    select
        c.id,
        c.document_id,
        d.title,
        d.access_level,
        c.chunk_index,
        c.content,
        (1 - (c.embedding <=> query_embedding))::double precision as similarity
    from public.document_chunks c
    join public.documents d on d.id = c.document_id
    where d.processing_status = 'ready'
      and c.embedding is not null
      and allowed_document_ids is not null
      and d.id = any(allowed_document_ids)
      and (1 - (c.embedding <=> query_embedding)) >= similarity_threshold
    order by c.embedding <=> query_embedding
    limit greatest(coalesce(match_count, 0), 0);
$$;

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.profiles (id, email, role)
    values (new.id, coalesce(new.email, ''), 'employee')
    on conflict (id) do update set email = excluded.email;
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();

alter table public.profiles enable row level security;
alter table public.documents enable row level security;
alter table public.document_permissions enable row level security;
alter table public.document_chunks enable row level security;
alter table public.chat_sessions enable row level security;
alter table public.chat_messages enable row level security;
alter table public.test_datasets enable row level security;
alter table public.test_cases enable row level security;
alter table public.experiments enable row level security;
alter table public.test_results enable row level security;
alter table public.security_logs enable row level security;
alter table public.app_settings enable row level security;

-- The API connects as the database owner, which bypasses RLS.
-- These statements close the public Data API. Users cannot change their own role there.
revoke all on table public.profiles from anon, authenticated;
revoke all on table public.documents from anon, authenticated;
revoke all on table public.document_permissions from anon, authenticated;
revoke all on table public.document_chunks from anon, authenticated;
revoke all on table public.chat_sessions from anon, authenticated;
revoke all on table public.chat_messages from anon, authenticated;
revoke all on table public.test_datasets from anon, authenticated;
revoke all on table public.test_cases from anon, authenticated;
revoke all on table public.experiments from anon, authenticated;
revoke all on table public.test_results from anon, authenticated;
revoke all on table public.security_logs from anon, authenticated;
revoke all on table public.app_settings from anon, authenticated;

grant select on table public.profiles to authenticated;

drop policy if exists profiles_select_own on public.profiles;
create policy profiles_select_own
    on public.profiles
    for select
    to authenticated
    using (id = auth.uid());
