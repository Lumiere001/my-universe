-- 나의 우주 v8 기록 칸(WS11 — PRD §4.1 기록 속성 · §4.4 공통 기록 · §5.2 Classify · §8.2 G2 · §8.5 A · §8.7).
-- 덧붙이기만 한다: 새 칸은 비어도 되거나 기본값이 있어, 이 칸을 모르는 지금 배포 코드도 그대로 돈다.
-- 원문은 여기에도 두지 않는다. source_ref · content_hash 는 사용자별 HMAC(app/core/security.digest)이라 글을 되살릴 수 없다.

alter table entries
  add column source text not null default '텍스트',          -- 출처: 대화 / 텍스트 / 사진 / 지난 글 묶음
  add column source_ref text,                                 -- 가져온 원본 표시(게시물 · 파일)의 HMAC. 같은 글 두 번 가져오기 막기
  add column day date,                                        -- 글이 다루는 날. 비면 written_at 의 현지 날짜(이 칸 전의 행)
  add column day_basis text check (day_basis in ('확실', '추정')),
  add column confirmed text check (confirmed in ('확인 전', '확인됨')),   -- 대화에서 온 글만(요약 확인)
  add column record_type text,                                -- 글 유형(기록 Agent Classify 4갈래)
  add column content_hash text;                               -- HMAC(정규화한 제목 · 본문 + Studio 설정 번호). 같은 글 다시 보내지 않기

create unique index entries_user_source_ref on entries (user_id, source_ref) where source_ref is not null;
create index entries_user_content_hash on entries (user_id, content_hash) where content_hash is not null;

-- Studio 설정 번호('기록 판/관측 판', 예: 2/2). 반응 · 실행이 어느 설정에서 나왔는지(품질 루프 §8.5 · §8.7)
alter table feedback add column studio_config text;
alter table runs add column studio_config text;
