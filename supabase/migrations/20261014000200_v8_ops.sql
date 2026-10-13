-- 나의 우주 v8 운영 화면(WS22 — PRD §7 473 · §8.0 · §8.3 · §8.7, 결정 10 · 13). 덧붙이기만 한다.
-- 지금 배포된 코드는 아래 칸 · 역할 · 표를 모른 채 그대로 돈다(새 칸은 비어도 됨).

-- 1) 한마디에 다음 걸음 제안을 넣었는지 · 지난 한마디를 되풀이해 다시 만들었는지(원문 아님, 참/거짓 표시만).
--    제안 있음/없음의 다음 날 다시 쓴 비율 · 한마디 반복률(§8.3)을 원문을 풀지 않고 센다. 이 칸 전의 행은 비어 있음.
alter table messages
  add column suggested boolean,
  add column repeated boolean;

-- 2) 운영 화면 전용 역할 app_ops: 모든 사용자의 '평문 칸'(id · 종류 · 상태 · 숫자 · 시각)만 읽는다.
--    enc · steps_enc 같은 암호문 칸 · 작은 별 · 사람 · 해 이름 표에는 권한이 없어 이 역할로는 원문을 읽을 수 없다(원문 0건).
--    피드백 원문은 이 역할이 아니라, 운영자 열람에 동의한 사용자마다 그 사용자의 app_user 세션으로 따로 읽는다(app/repository/ops.py).
do $$
begin
  if not exists (select from pg_roles where rolname = 'app_ops') then
    create role app_ops nologin;
  end if;
end $$;
grant app_ops to postgres;
grant usage on schema public to app_ops;

grant select (user_id, created_at) on profiles to app_ops;
grant select (id, user_id, status, step, error_code, sun_id, source, confirmed, created_at) on entries to app_ops;
grant select (user_id, kind, certainty, value) on thoughts to app_ops;
grant select (user_id, entry_id, suggested, repeated, created_at) on messages to app_ops;
grant select (user_id, target, target_id, value, studio_config, created_at) on feedback to app_ops;
grant select (user_id, entry_id, step, ms, calls, est_usd, error_code, meta, studio_config, created_at) on runs to app_ops;
grant select (user_id, version, operator_read, created_at) on consents to app_ops;

do $$
declare t text;
begin
  foreach t in array array['profiles', 'entries', 'thoughts', 'messages', 'feedback', 'runs', 'consents'] loop
    execute format('create policy ops_read on %I for select to app_ops using (true)', t);
  end loop;
end $$;

-- 3) 운영자 열람 기록: 동의한 사용자의 피드백 원문을 운영 화면에서 풀어 볼 때마다 사용자별로 한 줄.
--    고치지 않는다. 그 사용자가 계정을 지우면 같이 지워진다(auth.users cascade).
create table ops_reads (
  id bigint generated always as identity primary key,
  admin_id uuid not null,                          -- 본 운영자(로그인한 auth 사용자 id)
  user_id uuid not null references auth.users on delete cascade,   -- 피드백을 남긴 사용자
  what text not null,                              -- feedback(원문 보기) · wrong(오답 모으기) · summarize(피드백 정리)
  items int not null default 0,                    -- 풀어 본 피드백 수
  created_at timestamptz not null default now()
);
create index ops_reads_user_created on ops_reads (user_id, created_at);

alter table ops_reads enable row level security;
create policy ops_log on ops_reads for all to app_ops using (true) with check (true);
revoke all on ops_reads from anon, authenticated, app_user;
grant select, insert on ops_reads to app_ops;       -- update · delete 없음(열람 기록은 고치지 않음)
grant usage on sequence ops_reads_id_seq to app_ops;
