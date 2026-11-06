-- 고른 시각 알림 예약을 Supabase 안에서(2026-11-06 동규).
-- GitHub Actions 의 */30 예약(.github/workflows/push.yml)은 36시간에 7번만 돌아 21:00 을 고른 구독에 한 번도 못 보냈다.
-- pg_cron 이 정확히 :00 · :30 에 POST /push/due 를 부른다(pg_net). 같은 날 두 번 보내지 않는 것은 서버가 last_sent 로 막으므로
-- GitHub 예약은 예비로 그대로 둔다.
--
-- 먼저 Vault 에 'cron_secret'(백엔드 CRON_SECRET 과 같은 값)이 있어야 한다. 값은 저장소에 두지 않는다:
--   select vault.create_secret('<CRON_SECRET>', 'cron_secret', 'POST /push/due 의 X-Cron-Secret');
-- 끄기: select cron.unschedule('push-due');

create extension if not exists pg_cron with schema pg_catalog;
create extension if not exists pg_net with schema extensions;

select cron.schedule('push-due', '*/30 * * * *', $$
  select net.http_post(
    url := 'https://my-universe-api.vercel.app/push/due',
    headers := jsonb_build_object('X-Cron-Secret', (select decrypted_secret from vault.decrypted_secrets where name = 'cron_secret')),
    timeout_milliseconds := 60000
  );
$$);
