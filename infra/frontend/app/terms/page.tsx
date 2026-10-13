// 이용약관(짧게). 로그인 없이 보인다(Shell 의 PUBLIC). 문구를 바꾸면 시행일과 백엔드 app/api/consent.py VERSION 을 같이 올린다.
// 위기 대응 안내(단체 · 번호)는 넣지 않는다(시험 단계 방침, 2026-10-08 동규).
import type { Metadata } from "next";
import Link from "next/link";
import Contact from "@/components/Contact";

export const metadata: Metadata = { title: "이용약관 · 나의 우주" };

const UL = { margin: 0, paddingLeft: 20 } as const;

export default function TermsPage() {
  return (
    <main>
      <h1>나의 우주 이용약관</h1>
      <p className="sub">시행일 2026년 10월 13일</p>

      <section className="card">
        <h2>1. 어떤 서비스인가요</h2>
        <p style={{ margin: 0 }}>나의 우주는 일기를 생각 단위로 나눠 우주로 보여 주고, 별지기가 원문에 근거해 말을 거는 일기장이에요.
          나의 우주 팀(전남대 LLMOps 5조)이 <b>무료 시험 운영</b>으로 열어 두었어요. 구글 계정이 있는 만 14세 이상이면 누구나 쓸 수 있어요.</p>
      </section>

      <section className="card">
        <h2>2. 의료 · 상담 서비스가 아니에요</h2>
        <ul style={UL}>
          <li>나의 우주는 의료 · 심리 상담 서비스가 아니에요. 별지기 한마디와 정리 결과는 AI가 만든 것이라 틀릴 수 있고, 진단 · 치료 · 상담을 대신하지 않아요.</li>
          <li>별지기는 사람을 판정하지 않아요. 결과가 내 생각과 다르면 &apos;아니에요&apos; · &apos;불편한 점 한 줄&apos;로 알려 주세요.</li>
        </ul>
      </section>

      <section className="card">
        <h2>3. 시험 운영이라서</h2>
        <ul style={UL}>
          <li>기능 · 화면 · 문구가 자주 바뀌고, 고치는 동안 잠시 멈출 수 있어요. 큰 변경이나 서비스를 닫을 때는 미리 알려요.</li>
          <li>동의 문구가 바뀌면 다음에 들어올 때 다시 동의를 받아요.</li>
          <li>잘 지키려고 하지만 기록이 사라지지 않는다고 보장하지는 못해요. 소중한 글은 따로도 남겨 두세요.</li>
        </ul>
      </section>

      <section className="card">
        <h2>4. 쓰는 사람이 지킬 것</h2>
        <ul style={UL}>
          <li>내 계정으로 나만 써요. 남의 계정으로 들어가거나, 서비스를 망가뜨리거나, 일부러 많은 요청을 보내지 않아요.</li>
          <li>일기 속 다른 사람의 이야기는 꼭 필요한 만큼만 써요(<Link href="/privacy">개인정보처리방침</Link>).</li>
        </ul>
      </section>

      <section className="card">
        <h2>5. 지우기와 그만 쓰기</h2>
        <ul style={UL}>
          <li><b>사람 한 명 지우기</b>: 사람 화면에서. 글 속 그 이름이 관계 말(&quot;친구&quot; 같은)로 바뀌어요.</li>
          <li><b>계정과 모든 기록 지우기</b>: 설정 맨 아래에서 &apos;지우기&apos;를 입력하면 기록 · 벡터 · 동의 기록 · 로그인 계정이 함께 지워져요. 되돌릴 수 없어요.</li>
          <li><b>선택 동의 거두기</b>: 설정의 &apos;동의 내용 보기 · 바꾸기&apos;에서 언제든.</li>
          <li>그만 쓰고 싶으면 위처럼 계정을 지우면 돼요. 따로 알릴 필요는 없어요.</li>
        </ul>
      </section>

      <section className="card">
        <h2>6. 문의</h2>
        <p style={{ margin: 0 }}>문의 · 요청: <Contact /></p>
      </section>
    </main>
  );
}
