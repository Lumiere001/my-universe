-- 나의 우주 v8 첫 로그인 동의(WS24). 새 표만 덧붙인다(지금 배포된 코드는 이 표를 모른 채 그대로 돈다).
-- 동의할 때마다 한 줄(판 번호 · 시각 · 선택 동의). 가장 최근 줄이 지금 동의다. 문구 판(version)이 바뀌면 다시 묻는다.
-- 필수 셋(필수 · 민감정보 · 만 14세 이상)은 모두 참인 줄만 들어간다. 줄은 고치지 않는다(동의 기록).
-- 계정 지우기(DELETE /me 의 diary.wipe)와 auth.users cascade 로 같이 지워진다.

create table consents (
  id text primary key,
  user_id uuid not null references auth.users on delete cascade,
  version text not null,                           -- 동의 문구 판(app/api/consent.py VERSION)
  required boolean not null,                       -- 이용약관 · 개인정보 수집 · 이용 · 외부 처리(국외 이전 포함)
  sensitive boolean not null,                      -- 민감정보(건강 · 신앙 등) 따로
  age14 boolean not null,                          -- 만 14세 이상
  operator_read boolean not null default false,    -- 선택: 운영자가 내 피드백과 그 대상 문장을 읽을 수 있음
  created_at timestamptz not null default now(),
  constraint consents_required check (required and sensitive and age14)
);
create index consents_user_created on consents (user_id, created_at desc);

alter table consents enable row level security;
create policy own_app on consents for all to app_user
  using (user_id = (select nullif(current_setting('app.user_id', true), '')::uuid))
  with check (user_id = (select nullif(current_setting('app.user_id', true), '')::uuid));
revoke all on consents from anon, authenticated;
revoke all on consents from app_user;
grant select, insert, delete on consents to app_user;   -- update 없음(동의 기록은 고치지 않음), delete 는 계정 지우기
