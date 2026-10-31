-- 나의 우주 v9 고른 시각 알림(PRD v9 Q8). 새 표만 덧붙인다(지금 배포된 코드는 이 표를 모른 채 그대로 돈다).
-- 구독(브라우저 알림 주소 · 키)은 enc 에만(AES-GCM, 사용자별 키, aad 'push_subs:<id>'). 평문 칸은 보낼 시각 · 마지막으로 보낸 날뿐.
-- 30분마다 도는 예약 작업(POST /push/due)이 app_ops 로 '지금 보낼 사람'만 고르고(평문 칸), 보내기는 그 사용자 세션에서 한다.
-- 계정 지우기(DELETE /me 의 diary.wipe, auth.users cascade)로 같이 지운다. 운영 반영은 동규 확인 뒤 동규가 실행.

create table push_subs (
  id text primary key,
  user_id uuid not null references auth.users on delete cascade,
  notify_at text not null check (notify_at ~ '^([01][0-9]|2[0-3]):(00|30)$'),   -- 한국 시각 'HH:MM'(30분 단위)
  last_sent date,                                  -- 하루 한 번만
  enc bytea not null,                              -- {endpoint, keys: {p256dh, auth}}
  created_at timestamptz not null default now()
);
create index push_subs_at on push_subs (notify_at);

alter table push_subs enable row level security;
create policy own_app on push_subs for all to app_user
  using (user_id = (select nullif(current_setting('app.user_id', true), '')::uuid))
  with check (user_id = (select nullif(current_setting('app.user_id', true), '')::uuid));
revoke all on push_subs from anon, authenticated;
revoke all on push_subs from app_user;
grant select, insert, update, delete on push_subs to app_user;

-- 예약 작업이 보낼 사람을 고를 때만(구독 원문은 못 읽음)
grant select (id, user_id, notify_at, last_sent) on push_subs to app_ops;
create policy ops_read on push_subs for select to app_ops using (true);
