-- 나의 우주 v8 스키마(WS5). 원문(본문 · 제목 · 생각 · 인용 · 이름 …)은 enc(bytea, AES-GCM, 사용자별 키)에만 둔다.
-- 평문 칸은 보기 값(종류 · 상태 …) · id · 시각 · 숫자뿐이다. 모든 표: user_id(auth.users, cascade) + RLS(user_id = auth.uid()).

create table profiles (
  user_id uuid primary key references auth.users on delete cascade,
  settings jsonb not null default '{}',
  onboarding jsonb not null default '{}',          -- 되고 싶은 모습 묻기 단계 · 거절, 날씨 질문 건너뜀
  created_at timestamptz not null default now()
);

create table entries (
  id text primary key,
  user_id uuid not null references auth.users on delete cascade,
  written_at timestamptz not null,
  weather text,
  status text not null default 'processing' check (status in ('processing', 'done', 'failed')),
  step text,                                       -- 마지막으로 끝난 단계
  crisis boolean not null default false,
  addressee text,
  star_id text,
  sun_id text,
  enc bytea,                                       -- {title, text, summary, events, addressee_person}
  steps_enc bytea,                                 -- 단계별 저장값(끊긴 뒤 이어 하기)
  error_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index entries_user_written on entries (user_id, written_at desc);

create table suns (
  id text primary key,
  user_id uuid not null references auth.users on delete cascade,
  name text not null,                              -- 삶의 영역 이름(기준 축 · 사용자가 추가한 해)
  custom boolean not null default false,
  created_at timestamptz not null default now(),
  unique (user_id, name)
);

create table stars (
  id text primary key,
  user_id uuid not null references auth.users on delete cascade,
  sun_id text references suns on delete set null,
  enc bytea not null,                              -- {name} (사람 이름이 작은 별이 될 수 있어 가린다)
  created_at timestamptz not null default now()
);

create table thoughts (
  id text primary key,
  user_id uuid not null references auth.users on delete cascade,
  entry_id text not null references entries on delete cascade,
  star_id text references stars on delete set null,
  sun_id text references suns on delete set null,
  position int not null default 0,
  kind text not null,
  certainty text not null,
  value text,
  grateful boolean not null default false,
  enc bytea not null,                              -- {text, quote, self_change, other, topic}
  created_at timestamptz not null default now()
);
create index thoughts_user_entry on thoughts (user_id, entry_id);

create table people (
  id text primary key,
  user_id uuid not null references auth.users on delete cascade,
  relation text not null default '',
  auto boolean not null default false,             -- 글에서 자동 등록
  enc bytea not null,                              -- {name, nicknames}
  created_at timestamptz not null default now()
);

create table thought_people (
  user_id uuid not null references auth.users on delete cascade,
  thought_id text not null references thoughts on delete cascade,
  person_id text not null references people on delete cascade,
  primary key (thought_id, person_id)
);

create table people_questions (
  id text primary key,
  user_id uuid not null references auth.users on delete cascade,
  entry_id text references entries on delete cascade,
  reason text not null,                            -- 동명이인 · 별명 · 이름인지 낱말인지
  enc bytea not null,                              -- {name}
  answer text,
  created_at timestamptz not null default now()
);

create table relations (
  id text primary key,                             -- '옛생각id>새생각id'
  user_id uuid not null references auth.users on delete cascade,
  from_thought text not null references thoughts on delete cascade,
  to_thought text not null references thoughts on delete cascade,
  from_entry text not null references entries on delete cascade,
  to_entry text not null references entries on delete cascade,
  type text not null,
  grp text not null,
  line text not null check (line in ('실선', '점선')),
  cross_domain boolean not null default false,
  needs_confirm boolean not null default false,
  vow_kept boolean not null default false,
  enc bytea not null,                              -- {explanation, quote, axis, topic, notes}
  created_at timestamptz not null default now()
);

create table states (
  user_id uuid not null references auth.users on delete cascade,
  key text not null,                               -- 생각 id(다짐 · 질문) · 관계 id(바뀜) · '긴장:<관계 id>'
  kind text not null,
  state text,
  enc bytea not null,                              -- 상태 전체와 이력(rules.states 모양)
  updated_at timestamptz not null default now(),
  primary key (user_id, key)
);

create table aspirations (
  id text primary key,
  user_id uuid not null references auth.users on delete cascade,
  version int not null,                            -- 판(바뀌면 새 판, 이력 보존)
  "values" text[] not null default '{}',
  enc bytea not null,                              -- {now, said, obstacle, if_then}
  said_at timestamptz not null default now()
);

create table aspiration_reached (
  id text primary key,
  user_id uuid not null references auth.users on delete cascade,
  aspiration_id text not null references aspirations on delete cascade,
  entry_id text not null references entries on delete cascade,
  thought_id text references thoughts on delete cascade,
  enc bytea not null,                              -- {quote, note, message}
  at timestamptz not null default now()
);

create table messages (
  id text primary key,
  user_id uuid not null references auth.users on delete cascade,
  entry_id text not null references entries on delete cascade,
  tone text,
  mode text not null,
  next_kind text,
  enc bytea not null,                              -- {text, next_question} (반복 검사용 지난 한마디)
  created_at timestamptz not null default now()
);

create table feedback (
  id text primary key,
  user_id uuid not null references auth.users on delete cascade,
  target text not null,
  target_id text,
  value text not null,
  enc bytea,                                       -- {text} 불편한 점 한 줄일 때만
  created_at timestamptz not null default now()
);

create table runs (                                -- 원문 없는 실행 기록
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users on delete cascade,
  entry_id text,
  step text not null,
  ms int,
  calls int not null default 0,
  est_usd numeric(10, 5) not null default 0,
  error_code text,
  meta jsonb not null default '{}',               -- 이름만(voice checks · situations)
  created_at timestamptz not null default now()
);
create index runs_user_created on runs (user_id, created_at);

do $$
declare t text;
begin
  foreach t in array array['profiles', 'entries', 'suns', 'stars', 'thoughts', 'people', 'thought_people',
                           'people_questions', 'relations', 'states', 'aspirations', 'aspiration_reached',
                           'messages', 'feedback', 'runs'] loop
    execute format('alter table %I enable row level security', t);
    execute format('create policy own on %I for all to authenticated using (user_id = (select auth.uid())) '
                   'with check (user_id = (select auth.uid()))', t);
    execute format('grant select, insert, update, delete on %I to authenticated', t);
    execute format('revoke all on %I from anon', t);
  end loop;
end $$;
