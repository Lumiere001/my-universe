// 문의 메일은 여기 한 곳에서만 읽는다(개인정보처리방침 · 이용약관 · 동의 화면).
// 서비스용 Gmail 을 만들면 화면 환경변수 NEXT_PUBLIC_CONTACT_EMAIL 에 넣고 다시 배포한다. 비어 있으면 '준비 중'.
const MAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL?.trim();

export default function Contact() {
  return MAIL ? <a href={`mailto:${MAIL}`}>{MAIL}</a> : <span data-testid="contact-pending">준비 중이에요(서비스용 메일을 곧 열어요)</span>;
}
