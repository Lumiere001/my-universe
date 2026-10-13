-- 나의 우주 v8 대화(WS19 · WS20). 새 표만 덧붙인다(지금 배포된 코드는 이 표를 모른 채 그대로 돈다).
-- 대화 턴 원문은 서버에 둔다(2026-10-13 동규: 다른 기기에서 이어 하기). 원문(턴 · 지금까지 정리 · 초안)은 enc 에만
-- (AES-GCM, 사용자별 키, aad 'conversations:<id>'). 평문 칸은 id · 턴 수 · 시각 · 초안 기록 id 뿐이다.
-- 확인하고 저장하면 그 대화 행을 지운다(확인한 정리본 = entries 만 남김). 확인 전 대화는 사용자가 지우거나
-- 계정 지우기(DELETE /me 의 diary.wipe, auth.users cascade)로 같이 지운다.

create table conversations (
  id text primary key,
  user_id uuid not null references auth.users on delete cascade,
  entry_id text,                                   -- '대화 마치고 정리하기'로 만든 확인 전 초안 기록(지워졌을 수 있어 FK 없음)
  turn_count int not null default 0 check (turn_count >= 0),   -- 사용자 턴 수(운영 지표: 대화 턴 수 · 그만둔 지점)
  enc bytea,                                       -- {turns, summary, from_entry, draft, crisis …}
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index conversations_user_updated on conversations (user_id, updated_at desc);

alter table conversations enable row level security;
create policy own_app on conversations for all to app_user
  using (user_id = (select nullif(current_setting('app.user_id', true), '')::uuid))
  with check (user_id = (select nullif(current_setting('app.user_id', true), '')::uuid));
revoke all on conversations from anon, authenticated;
revoke all on conversations from app_user;
grant select, insert, update, delete on conversations to app_user;
