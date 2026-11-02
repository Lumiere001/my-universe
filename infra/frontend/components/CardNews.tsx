"use client";
// 홈 화면 앱을 처음 열면 보는 카드뉴스(2026-11-02 동규 「설명이 친절하게 카드뉴스 형식, 화면이 꽉 차도록」).
// 한 장 = 화면 하나. 옆으로 밀거나 '다음', 끝에서 '시작하기'(= Landing 시작 화면). 본 기기는 Landing 이 기억한다. 주소에 ?cards 면 다시 보임.
import { useRef, useState } from "react";

const CARDS: { pic: string; round?: boolean; title: string; text: string }[] = [
  { pic: "/keeper/planet.svg", round: true, title: "반가워요, 나는 별지기예요", text: "오늘 하루를 같이 이야기하고, 그 이야기를 일기로 정리해 주는 친구예요." },
  { pic: "/landing/talk.jpg", title: "오늘 하루를 말해 주세요", text: "편하게 말하듯 적으면 별지기가 묻고 들어요. 쓰고 싶은 날엔 직접 써도 돼요." },
  { pic: "/landing/write.jpg", title: "내 말 그대로 일기 한 편", text: "대화를 마치면 별지기가 내 말로 일기를 정리해요. 맞는지 보고 저장하면 끝이에요." },
  { pic: "/landing/universe-mobile.jpg", title: "생각이 별이 돼요", text: "일기 속 생각이 별이 되어 비슷한 생각끼리 이어져요. 한 갈래 이야기가 10편 쌓이면 새 해가 떠요." },
  { pic: "", title: "내 일기는 나만 봐요", text: "일기는 나만 여는 열쇠로 잠가 두고, AI에는 사람 이름을 가명으로 바꿔 보내요." },
];

export default function CardNews({ onDone }: { onDone: () => void }) {
  const track = useRef<HTMLOListElement>(null);
  const [at, setAt] = useState(0);
  const last = at === CARDS.length - 1;
  const go = (n: number) => track.current?.scrollTo({ left: n * track.current.clientWidth,
    behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
  return (
    <div className="cnews" role="dialog" aria-modal="true" aria-label="나의 우주 소개">
      <button className="cn-skip" onClick={onDone}>건너뛰기</button>
      <ol ref={track} className="cn-track" onScroll={(e) => setAt(Math.round(e.currentTarget.scrollLeft / e.currentTarget.clientWidth))}>
        {CARDS.map((c, i) => (
          <li key={c.title} aria-label={`${i + 1} / ${CARDS.length}`} aria-hidden={i !== at}>
            <div className={"cn-pic" + (c.round ? " round" : "")}>
              {c.pic ? <img src={c.pic} alt="" /> : <Lock />}
            </div>
            <h2>{c.title}</h2>
            <p>{c.text}</p>
          </li>
        ))}
      </ol>
      <div className="cn-foot">
        <div className="cn-dots" aria-hidden>{CARDS.map((c, i) => <i key={c.title} data-on={i === at || undefined} />)}</div>
        <button className="primary wide" onClick={() => (last ? onDone() : go(at + 1))}>{last ? "시작하기" : "다음"}</button>
      </div>
    </div>
  );
}

function Lock() {
  return (
    <svg viewBox="0 0 64 64" width="132" height="132" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
      <rect x="14" y="28" width="36" height="26" rx="6" />
      <path d="M22 28v-7a10 10 0 0 1 20 0v7" />
      <circle cx="32" cy="40" r="3" fill="currentColor" stroke="none" />
      <path d="M32 43v4" />
    </svg>
  );
}
