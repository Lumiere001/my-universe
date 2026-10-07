-- 나의 우주 v8 보안(docs/security-review-v8.md H1 · M5 · M9 · L3).
-- 1) Data API(PostgREST · GraphQL)로 표를 직접 읽고 쓰지 못하게 anon · authenticated 의 권한을 모두 거둔다.
--    화면(supabase-js)은 로그인만 쓰고, 표는 백엔드만 DB 에 직접 붙어 쓴다.
-- 2) 백엔드는 PostgREST 가 모르는 역할 app_user 로 트랜잭션을 열고(set local role), RLS 는 그 역할에 건다(두 겹).
--    사용자 id 는 트랜잭션마다 app.user_id 설정으로 넘긴다(app/repository/tables.py pg_session).
-- 3) 마음 상태 표시(entries.crisis · messages.mode)는 enc 안으로 옮기고 평문 칸을 지운다. profiles 설정도 enc 로.
-- 4) 실행 잠금(entries.locked_until): 인스턴스가 여러 개여도 같은 기록을 두 번 돌리지 않게 조건부 update 로 잡는다.

revoke all on all tables in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;
revoke all on all functions in schema public from anon, authenticated, public;
alter default privileges for role postgres in schema public revoke all on tables from anon, authenticated;
alter default privileges for role postgres in schema public revoke all on sequences from anon, authenticated;
alter default privileges for role postgres in schema public revoke all on functions from anon, authenticated, public;

do $$
begin
  if not exists (select from pg_roles where rolname = 'app_user') then
    create role app_user nologin;
  end if;
end $$;
grant app_user to postgres;
grant usage on schema public to app_user;
grant select, insert, update, delete on all tables in schema public to app_user;
grant usage on all sequences in schema public to app_user;
alter default privileges for role postgres in schema public grant select, insert, update, delete on tables to app_user;
alter default privileges for role postgres in schema public grant usage on sequences to app_user;

do $$
declare t text;
begin
  foreach t in array array['profiles', 'entries', 'suns', 'stars', 'thoughts', 'people', 'thought_people',
                           'people_questions', 'relations', 'states', 'aspirations', 'aspiration_reached',
                           'messages', 'feedback', 'runs'] loop
    execute format('create policy own_app on %I for all to app_user '
                   'using (user_id = (select nullif(current_setting(''app.user_id'', true), '''')::uuid)) '
                   'with check (user_id = (select nullif(current_setting(''app.user_id'', true), '''')::uuid))', t);
  end loop;
end $$;

-- 비용 상한이 runs 합계라 음수를 막는다
alter table runs add constraint runs_nonneg check (est_usd >= 0 and calls >= 0 and coalesce(ms, 0) >= 0);

-- runs.meta: 상황 이름(무거운 날 …)은 남기지 않고, voice 검사는 문제 개수만
update runs set meta = case when jsonb_typeof(meta -> 'checks') = 'array'
                            then jsonb_build_object('checks', jsonb_array_length(meta -> 'checks')) else '{}' end
where meta <> '{}';

-- 위기 · 돌봄 표시는 enc 로(이미 있는 평문 값은 옮길 수 없어 지운다: 암호화 키가 DB 밖에 있음)
alter table entries drop column crisis;
alter table messages drop column mode;
alter table profiles add column enc bytea;            -- {settings, onboarding} (오늘은 위로만 · 살살 날짜 등)
alter table entries add column locked_until timestamptz;
