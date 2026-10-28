// 가짜 데이터 모드(NEXT_PUBLIC_MOCK=1). 백엔드 없이 화면을 개발 · 캡처하기 위한 고정 데이터.
// 모든 글은 가상 인물 "하늘"의 것(data/demo/universe-haneul.json 을 v8 모양으로 줄여 옮김). 실제 일기는 없다.
import ontology from "./ontology.json";
import type {
  Aspiration, AspirationState, ConfirmInput, Consent, ConsentInput, Conversation, DiaryInput, EntryResult, EntrySummary, Feedback, Me, Person,
  PersonThoughts, Prompt, Settings, StreamError, StreamHandlers, TalkProgress, Thought, Tone, Universe,
} from "./api";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const STEP_MS = 350;
const STEPS: [string, string][] = [
  ["safety", "글을 살펴보는 중"], ["names", "사람 이름을 가리는 중"], ["record", "생각을 나누는 중"],
  ["past", "지난 생각을 찾는 중"], ["observe", "이어진 생각을 살피는 중"], ["voice", "별지기가 한마디를 고르는 중"],
  ["save", "우주에 저장하는 중"],
];
// 위기 감지는 백엔드(app/service/safety) 몫. 여기서는 시험 단계 동작(평소 결과 + 위로 한마디 + 안부 한 줄)만 흉내 낸다.
const CRISIS = ["죽고 싶", "사라지고 싶", "자해", "끝내고 싶"];
const CHECK_IN = "요즘 많이 버거웠을 것 같아요. 괜찮은지 다음에 또 물어볼게요.";

/* ---------- 하늘의 우주 ---------- */
const P = (id: string, star_id: string, sun_id: string, day: string, title: string, order: number,
  extra: Partial<Universe["planets"][number]> = {}) =>
  ({ id, star_id, sun_id, written_at: `${day}T22:00:00+09:00`, title, order, ring: false, people: [], weather: null, ...extra });

const universe: Universe = {
  suns: [
    { id: "d1", name: "삶의 성취", custom: false, planet_count: 8 },
    { id: "d2", name: "관계", custom: false, planet_count: 4 },
    { id: "d3", name: "건강", custom: false, planet_count: 3 },
    { id: "d4", name: "공동체", custom: false, planet_count: 2 },
    { id: "d5", name: "영성·신앙", custom: false, planet_count: 1 },
  ],
  stars: [
    { id: "s1", sun_id: "d1", name: "진로", planet_count: 5 },
    { id: "s2", sun_id: "d1", name: "배움과 기록", planet_count: 2 },
    { id: "s3", sun_id: "d2", name: "혼자와 함께", planet_count: 3 },
    { id: "s4", sun_id: "d2", name: "가족", planet_count: 1 },
    { id: "s5", sun_id: "d3", name: "아침 걷기", planet_count: 3 },
    { id: "s6", sun_id: "d4", name: "동아리 · 순모임", planet_count: 2 },
    { id: "s7", sun_id: "d5", name: "묵상", planet_count: 1 },
  ],
  planets: [
    P("e01", "s2", "d1", "2026-03-08", "3/8 일요일 독서노트", 0, { ring: true, ring_state: "열림", thought_count: 2, certainty: "단정" }),
    P("e02", "s1", "d1", "2026-03-14", "3/14 진로 상담", 0, { thought_count: 3, certainty: "단정" }),
    P("e03", "s5", "d3", "2026-03-20", "3/20 결심", 0, { ring: true, ring_state: "채워짐", thought_count: 1, certainty: "단정" }),
    P("e04", "s3", "d2", "2026-03-27", "3/27 금요일 일기", 0, { people: ["p1"], thought_count: 2, certainty: "고민 중" }),
    P("e05", "s3", "d2", "2026-04-05", "4/5 혼자 있는 시간", 1, { thought_count: 2, certainty: "고민 중" }),
    P("e06", "s5", "d3", "2026-04-08", "4/8 반성", 1, { weather: "흐림", thought_count: 3, certainty: "단정" }),
    P("e07", "s6", "d4", "2026-04-12", "4/12 순모임 후", 0, { thought_count: 1, certainty: "판단 보류" }),
    P("e08", "s6", "d4", "2026-05-15", "5/15 동아리 회의", 1, { ring: true, ring_state: "열림", thought_count: 2, certainty: "고민 중" }),
    P("e09", "s1", "d1", "2026-05-30", "5/30 선배와 대화", 1, { people: ["p1"], thought_count: 3, certainty: "고민 중", has_question: true }),
    P("e10", "s7", "d5", "2026-06-07", "6/7 시편 23편 묵상", 0, { weather: "구름 조금", thought_count: 1, certainty: "단정" }),
    P("e11", "s3", "d2", "2026-06-20", "6/20 혼자와 함께", 2, { thought_count: 4, certainty: "단정" }),
    P("e12", "s5", "d3", "2026-07-10", "7/10 걷기 2주째", 2, { weather: "맑음", thought_count: 2, certainty: "단정" }),
    P("e13", "s4", "d2", "2026-07-18", "7/18 가족 여행 2일차", 0, { people: ["p2", "p3"], weather: "맑음", thought_count: 1, certainty: "단정" }),
    P("e14", "s1", "d1", "2026-08-28", "8/28 막막함", 2, { weather: "안개", thought_count: 2, certainty: "판단 보류", has_question: true }),
    P("e15", "s1", "d1", "2026-09-12", "9/12 작은 회사 탐방", 3, { thought_count: 3, certainty: "고민 중" }),
    P("e16", "s1", "d1", "2026-09-20", "9/20 토요일 일기", 4, { ring: true, ring_state: "열림", people: ["p1"], thought_count: 5, certainty: "고민 중", has_question: true }),
    P("e17", "s2", "d1", "2026-08-08", "8/8 독서노트", 1, { thought_count: 2, certainty: "단정" }),
  ],
  links: [
    { id: "l1", from_planet: "e03", to_planet: "e06", type: "어긋남", line: "점선", cross_domain: false, needs_confirm: true, explanation: "매일 아침 걷기로 한 다짐 뒤에 사흘 만에 멈췄다는 반성이 왔어요.", from_quote: "매일 아침 30분씩 걷기로 했다", to_quote: "사흘 하고 멈췄다" },
    { id: "l2", from_planet: "e06", to_planet: "e12", type: "이어짐", line: "실선", cross_domain: false, needs_confirm: false, explanation: "멈췄던 걷기를 다시 시작해 2주째 이어 가고 있다고 직접 썼어요.", from_quote: "사흘 하고 멈췄다", to_quote: "걷기를 2주째 이어 가고 있다" },
    { id: "l3", from_planet: "e01", to_planet: "e17", type: "이어짐", line: "실선", cross_domain: false, needs_confirm: false, explanation: "'기록할 때 내 것이 된다'는 생각이 다시 나왔어요.", from_quote: "적을 때 비로소 내 것이 된다", to_quote: "기록하는 사람이 결국 배운다" },
    { id: "l4", from_planet: "e05", to_planet: "e11", type: "해소", line: "실선", cross_domain: false, needs_confirm: false, explanation: "혼자는 충전, 함께는 성장이라고 정리했어요.", from_quote: "혼자 있는 시간이 가장 편하다", to_quote: "혼자는 충전, 함께는 성장" },
    { id: "l5", from_planet: "e09", to_planet: "e15", type: "이어짐", line: "점선", cross_domain: false, needs_confirm: true, explanation: "선배에게 들은 작은 회사 이야기를 직접 보러 갔어요.", from_quote: "작은 회사에 가면 빨리 배운다고 했다", to_quote: "직접 가 보니 배우는 속도가 달랐다" },
    { id: "l6", from_planet: "e14", to_planet: "e16", type: "이어짐", line: "점선", cross_domain: false, needs_confirm: true, explanation: "취업이 막막하다는 마음이 진로를 다시 생각하는 글로 이어졌어요.", from_quote: "취업을 생각하면 막막하다", to_quote: "진로를 다시 생각해 보기로 했다" },
    { id: "l7", from_planet: "e07", to_planet: "e11", type: "이어짐", line: "점선", cross_domain: true, needs_confirm: true, explanation: "순모임에서 털어놓은 경험이 '함께하는 시간은 성장'이라는 생각으로 이어졌어요.", from_quote: "순모임에서 처음으로 고민을 털어놓았다", to_quote: "함께하는 시간은 나를 자라게 한다" },
    { id: "l9", from_planet: "e08", to_planet: "e16", type: "목표 충돌", line: "점선", cross_domain: true, needs_confirm: true, ended: true,
      explanation: "축제 부스 준비와 팀 찾기가 같은 주에 겹쳤는데, 부스 일을 마치며 충돌이 끝났어요.",
      from_quote: "축제 부스 준비를 맡았다", to_quote: "팀 세 곳을 직접 찾아보겠다" },
    { id: "l8", from_planet: "e10", to_planet: "e14", type: "긴장", line: "점선", cross_domain: true, needs_confirm: true, explanation: "'이미 충분하다'는 고백과 '준비가 안 됐다'는 막막함이 맞서 있어요.", from_quote: "이미 충분하다", to_quote: "아직 준비가 안 됐다" },
  ],
  twins: [
    { id: "w1", a_planet: "e04", b_planet: "e05", topic: "혼자 ↔ 함께", status: "해소" },
    { id: "w2", a_planet: "e02", b_planet: "e15", topic: "안정 ↔ 배움", status: "열림" },
  ],
  blackholes: [{ id: "b1", star_id: "s1", label: "큰 회사냐 작은 팀이냐", size: 3, planets: ["e09", "e14", "e16"] }],
  north_star: { text: "어디서든 배우며, 한 약속은 지키는 사람", values: ["성취", "규범"], reached_planets: ["e12"],
    reached: [{ entry_id: "e12", quote: "걷기를 2주째 이어 가고 있다", at: "2026-07-10T22:00:00+09:00" }] },
  people: [],
};

let people: Person[] = [
  { id: "p1", name: "민수", nickname: "민수 형", relation: "선배", auto: true, planets: ["e04", "e09", "e16"], forget_as: "선배" },
  { id: "p2", name: "지은", nickname: "", relation: "동생", auto: true, planets: ["e13"], forget_as: "동생" },
  { id: "p3", name: "엄마", nickname: "", relation: "엄마", auto: false, planets: ["e13"], forget_as: "부모" },
];

let settings: Settings = {
  tone: "다정하게", fact_bomb_ack: false, gentle_today: null, comfort_only_today: null,
  suggestions: "보통", cross_links: "눌렀을 때", weather_ask: true, keeper_name: "별지기", tone_note: "",
};

let aspiration: AspirationState = {
  current: { id: "a2", said: "어디서든 배우며, 한 약속은 지키는 사람", values: ["성취", "규범"], obstacle: "바쁘면 미룬다",
    if_then: "바쁘다는 생각이 들면 10분만 먼저 하겠다", said_at: "2026-09-21T21:00:00+09:00",
    reached: [{ entry_id: "e12", quote: "걷기를 2주째 이어 가고 있다", at: "2026-07-10T22:00:00+09:00" }] },
  history: [{ id: "a1", said: "큰 회사에 들어가 인정받는 사람", values: ["성취", "안정"], obstacle: "자신감이 없다",
    if_then: "불안하면 공채 일정을 하나 확인하겠다", said_at: "2026-03-15T21:00:00+09:00", reached: [] }],
  ask: { should_ask: false, step: 1 },
};

/* ---------- 오늘 쓴 글의 결과(하늘의 10/3 일기) ---------- */
const MESSAGES: Record<Tone, string> = {
  다정하게: "큰 회사만 답이라던 3월의 생각에서, 오늘은 '배우고 있다는 느낌'으로 기준이 옮겨 갔네요. 그 변화를 스스로 알아챈 것도 오늘 한 일이에요. 다음 주엔 메일 한 통만 먼저 보내 볼까요? 쉬어 가도 괜찮아요.",
  담백하게: "기준이 '큰 회사'에서 '배우는 느낌'으로 바뀌었네요. 팀 찾기는 아직이고요. 다음 주에 메일 한 통, 어때요?",
  고양이처럼: "큰 회사만 답이라더니, 이제는 배우는 게 더 좋다고. 뭐, 그럴 줄 알았어. 다음 주엔 메일 한 통만 먼저 보내 볼래? 기지개 켜고 기다려 줄게.",
  팩폭: "팀 세 곳 찾기로 해 놓고 0곳이다. '바빠서'는 핑계고. 기준은 이미 네가 정했잖아. 다음 주 월요일, 메일 하나. 그거부터 해.",
  "직접 정하기": "기준이 '큰 회사'에서 '배우는 느낌'으로 바뀌었네! 그거 진짜 큰 변화야. 다음 주엔 메일 한 통만 먼저 보내 볼까? 🙂",
};
const COMFORT = "마음이 무거운 날엔 무거운 채로 있어도 괜찮아요. 오늘 생각을 이렇게 적어 둔 것만으로도 충분해요.";

function result(id: string, input: DiaryInput): EntryResult {
  const heavy = !!ontology.weather.find((w) => w.name === input.weather && "comfort_only" in w);
  const crisis = CRISIS.some((w) => input.text.includes(w));
  const comfort = heavy || crisis || settings.comfort_only_today === today();
  const tone: Tone = crisis && (settings.tone === "팩폭" || settings.tone === "직접 정하기") ? "다정하게" : settings.tone; // 위기 글이면 팩폭 · 직접 정하기도 그 글만 다정하게
  const written = input.written_at ?? "2026-10-03T22:40:00+09:00";
  const head = `${input.title ?? ""} ${input.text.split("\n")[0]}`;
  const twoDays = /\d{1,2}\/\d{1,2}\s*~\s*\d{1,2}\/\d{1,2}/.test(head); // 날짜가 둘(3/27~3/29) → 날짜 확인 필요(서버 G2 흉내)
  return {
    id, status: "done", step: "save", written_at: written, source: "텍스트",
    day: input.day ?? written.slice(0, 10), day_basis: input.day ? "확실" : "추정", day_check: !input.day && twoDays,
    title: input.title || "10/3 토요일 일기", weather: input.weather ?? null, crisis,
    info: { summary: "관심 있는 팀 세 곳을 찾아보기로 했지만 한 곳도 못 찾아봤고, 대신 일하는 곳보다 배우는 느낌이 중요하다는 쪽으로 생각이 정리됐다.",
      addressee: "나", addressee_person: null, events: ["팀 찾기를 미룸", "부모님께 아직 말하지 못함"] },
    thoughts: [
      { id: "t1", text: "바쁘다는 핑계로 팀 찾기를 또 미뤘다.", kind: "자기평가(부정)", grateful: false, certainty: "단정", value: "성취",
        quote: "바쁘다는 핑계로 또 미뤘다.", self_change: null, topic: "진로", star_id: "s1", sun_id: "d1", people: [], other: null, state: null },
      { id: "t2", text: "어디서 일하든 배우고 있다는 느낌이 더 중요하다.", kind: "신념·원칙", grateful: false, certainty: "단정", value: "자율",
        quote: "이제는 어디서 일하든 내가 배우고 있다는 느낌이 더 중요하다는 걸 알겠다.",
        self_change: "예전에는 큰 회사에 들어가야만 인정받는다고 생각했다", topic: "진로", star_id: "s1", sun_id: "d1", people: [], other: null,
        state: { type: "바뀜", status: "확정", mistake: false } },
      { id: "t3", text: "다음 주에 한 곳이라도 먼저 메일을 보낸다.", kind: "다짐", grateful: false, certainty: "고민 중", value: null,
        quote: "다음 주에는 한 곳이라도 먼저 메일을 보내 보고 싶다.", self_change: null, topic: "진로", star_id: "s1", sun_id: "d1", people: [], other: null,
        state: { type: "다짐", status: "열림", mistake: false } },
      { id: "t4", text: "민수 형한테 물어보려다 말았다.", kind: "기타", grateful: false, certainty: "판단 보류", value: null,
        quote: "저녁에 민수 형한테 연락할까 하다가 말았다.", self_change: null, topic: "진로", star_id: "s1", sun_id: "d1", people: ["p1"], other: "망설임", state: null },
    ],
    relations: [
      { id: "r1", from: "t9", to: "t2", from_entry: "e02", to_entry: id, type: "바뀜", group: "판단형", line: "실선", cross_domain: false,
        needs_confirm: false, explanation: "3월에는 큰 회사가 맞다고 했는데, 오늘은 배우는 느낌이 더 중요하다고 직접 썼어요.", quote: "큰 회사에 들어가는 게 맞다." },
      { id: "r2", from: "t8", to: "t1", from_entry: "e16", to_entry: id, type: "어긋남", group: "판단형", line: "점선", cross_domain: false,
        needs_confirm: true, explanation: "9/20에 팀 세 곳을 찾아보기로 한 다짐 뒤에, 오늘 한 곳도 못 찾았다는 반성이 왔어요.", quote: null },
      { id: "r3", from: "t7", to: "t2", from_entry: "e09", to_entry: id, type: "이어짐", group: "영향형", line: "점선", cross_domain: false,
        needs_confirm: true, explanation: "선배에게 들은 '작은 팀에서 빨리 배운다'는 이야기와 같은 방향이에요.", quote: null },
    ],
    past: [
      { thought_id: "t9", entry_id: "e02", text: "큰 회사에 들어가는 게 맞다.", written_at: "2026-03-14T21:00:00+09:00" },
      { thought_id: "t8", entry_id: "e16", text: "관심 있는 팀 세 곳을 직접 찾아보겠다.", written_at: "2026-09-20T22:00:00+09:00" },
      { thought_id: "t7", entry_id: "e09", text: "작은 팀에서는 배우는 속도가 빠르다더라.", written_at: "2026-05-30T22:00:00+09:00" },
    ],
    reached: [{ aspiration_id: "a2", quote: "어디서 일하든 내가 배우고 있다는 느낌이 더 중요하다",
      message: "'어디서든 배우는 사람'에 한 걸음 닿은 문장이에요." }],
    message: { text: comfort ? COMFORT : MESSAGES[tone], tone, mode: comfort ? "comfort" : "normal", check_in: crisis ? CHECK_IN : null },
    next_question: comfort ? { kind: "none", text: "" } : { kind: "free", text: "부모님께는 어떤 말부터 꺼내고 싶어요?" },
    people_questions: [{ id: "q1", name: "민수 형", question: "글에 나온 '민수 형'은(는) 사람 목록에 있는 누군가를 부르는 다른 이름인가요?",
      options: ["같은 사람", "다른 사람", "사람 이름 아님"] }],
    // 관측 보고서(WS15)
    observation: { state: "바뀜", limits: ["생각을 나눈 것과 이어진 선은 AI가 원문 인용을 근거로 추정한 것이라 틀릴 수 있어요.",
      "지난 생각 2개와만 비교했어요. 같은 세부 주제와 뜻이 가까운 것을 골랐고, 이 글을 정리할 때 이미 있던 기록만 봤어요.",
      "점선은 글에 직접 쓰지 않은 연결이에요. 맞는지 알려 주세요."] },
  };
}

const entries = new Map<string, EntryResult>();
const today = () => new Date().toISOString().slice(0, 10);

/* ---------- API 흉내 ---------- */
async function run(id: string, input: DiaryInput, from: number, h: StreamHandlers): Promise<EntryResult> {
  for (let i = from; i < STEPS.length; i++) {
    await sleep(STEP_MS);
    // "[끊김]"이 든 글은 세 번째 단계에서 한 번 끊어 "이어서 하기"를 흉내 낸다
    if (i === 3 && input.text.includes("[끊김]") && from === 0) {
      entries.set(id, { ...result(id, input), status: "failed", step: STEPS[2][0] });
      throw { entry_id: id, code: "disconnected", message: "연결이 끊겼어요.", resumable: true } as StreamError;
    }
    h.onProgress({ entry_id: id, step: STEPS[i][0], label: STEPS[i][1], done: i + 1, total: STEPS.length });
  }
  const r = result(id, input);
  entries.set(id, r);
  prompt = { kind: r.next_question?.kind === "free" ? "free" : "none", text: r.next_question?.text ?? "",
    vow: r.message?.mode === "comfort" ? null : { thought_id: "t3", text: r.thoughts[2].text, overdue: false } };
  if (!universe.planets.find((p) => p.id === id)) {
    universe.planets.push(P(id, "s1", "d1", "2026-10-03", r.title, universe.planets.filter((p) => p.star_id === "s1").length,
      { ring: true, ring_state: "열림", people: ["p1"], weather: input.weather ?? null, thought_count: r.thoughts.length, certainty: "단정" }));
    universe.links.push(
      { id: "r1", from_planet: "e02", to_planet: id, type: "바뀜", line: "실선", cross_domain: false, needs_confirm: false, explanation: r.relations[0].explanation,
        from_quote: r.relations[0].quote ?? "", to_quote: r.thoughts[1].quote },
      { id: "r2", from_planet: "e16", to_planet: id, type: "어긋남", line: "점선", cross_domain: false, needs_confirm: true, explanation: r.relations[1].explanation,
        from_quote: "팀 세 곳을 직접 찾아보겠다", to_quote: r.thoughts[0].quote });
  }
  return r;
}
const inputs = new Map<string, DiaryInput>();
let seq = 18;
export async function writeDiary(input: DiaryInput, h: StreamHandlers) {
  const same = [...inputs].find(([i, x]) => entries.get(i)?.status === "done" && x.text === input.text && (x.title ?? "") === (input.title ?? ""));
  if (same) { await sleep(STEP_MS); return { ...entries.get(same[0])!, duplicate: true }; } // 같은 글은 다시 정리하지 않음
  const id = "e" + seq++;
  inputs.set(id, input);
  return run(id, input, 0, h);
}
export function resumeDiary(id: string, h: StreamHandlers) {
  return run(id, inputs.get(id) ?? { text: "" }, 3, h);
}
export async function getDiary(id: string): Promise<EntryResult> {
  await sleep(120);
  const e = entries.get(id);
  if (e) return e;
  const p = universe.planets.find((x) => x.id === id);
  const base = result(id, { text: "", title: p?.title, written_at: p?.written_at, weather: p?.weather });
  // 지난 기록은 요약만 보여 준다(가짜 데이터에는 지난 글의 생각 목록이 없다)
  return { ...base, info: { ...base.info!, summary: SUMMARY[id] ?? base.info!.summary, events: [] },
    thoughts: PAST_THOUGHTS[id] ?? [], relations: [], past: [], people_questions: [], reached: [], next_question: null, message: null };
}
// 지난 글의 생각은 행성 카드 · 사람별 생각에 쓰는 몇 개만
const T = (id: string, text: string, kind: string, certainty: string, quote: string, star_id: string, sun_id: string, people: string[] = []): Thought =>
  ({ id, text, kind, grateful: kind === "감정", certainty, value: null, quote, self_change: null, topic: "", star_id, sun_id, people, other: null, state: null });
const PAST_THOUGHTS: Record<string, Thought[]> = {
  e04: [T("t04a", "형이 먼저 안부를 물어봐 줘서 힘이 됐다.", "감정", "단정", "형이 먼저 안부를 물어봐 줬다", "s3", "d2", ["p1"])],
  e09: [T("t09a", "작은 팀에서는 배우는 속도가 빠르다더라.", "해석", "고민 중", "작은 회사에 가면 빨리 배운다고 했다", "s1", "d1", ["p1"])],
  e11: [T("t11a", "혼자는 충전, 함께는 성장이다.", "신념·원칙", "단정", "혼자는 충전, 함께는 성장", "s3", "d2"),
    T("t11b", "함께하는 시간이 나를 자라게 한다.", "해석", "단정", "함께하는 시간은 나를 자라게 한다", "s3", "d2")],
  e16: [T("t16a", "민수 형 말처럼 작은 팀도 직접 알아보고 싶다.", "소망", "고민 중", "형 말처럼 작은 팀도 알아보고 싶다", "s1", "d1", ["p1"])],
};
const SUMMARY: Record<string, string> = {
  e01: "『배움의 기술』을 읽고 그날 바로 세 줄로 적어 보니 확실히 달랐다. 매주 일요일 독서노트를 쓰기로 했다.",
  e02: "진로 상담 뒤, 직장은 안정이 제일이고 큰 회사에 들어가는 게 맞다고 정리했다.",
  e03: "몸이 무거워 내일부터 매일 아침 30분씩 걷기로 했다.",
  e04: "형이 먼저 안부를 물어봐 준 일이 큰 힘이 됐다.",
  e05: "주말 내내 혼자 지내며 혼자 있는 시간이 가장 편하다고 느꼈다.",
  e06: "걷기를 사흘 하다 멈춘 일을 돌아보며 핑계를 반성했다.",
  e07: "순모임에서 처음으로 고민을 털어놓았다.",
  e08: "축제 부스 준비를 맡았고 시험과 함께 해낼 수 있을지 걱정했다.",
  e09: "졸업한 선배에게 작은 회사에서 빨리 배운다는 이야기를 들었다.",
  e10: "'부족함이 없다'를 '이미 충분하다'는 고백으로 읽었다.",
  e11: "혼자는 충전, 함께는 성장이라고 생각이 정리됐다.",
  e12: "아침 걷기를 2주째 이어 가고 있다. 이번엔 습관이 된 것 같다.",
  e13: "가족과 바다에 가고 저녁엔 노래방에 갔다.",
  e14: "졸업을 한 학기 앞두고 취업을 생각하면 막막하다.",
  e15: "작은 스타트업을 방문해 배우는 속도와 안정 사이를 비교했다.",
  e16: "선배와 이야기한 뒤 큰 회사의 안정과 작은 팀의 배움 사이에서 진로를 다시 생각했다. 팀 세 곳을 찾아보기로 했다.",
  e17: "『생각의 탄생』을 읽고 기록하는 사람이 결국 배운다는 말을 3월의 느낌과 이었다.",
};
export async function listDiary(): Promise<{ entries: EntrySummary[] }> {
  await sleep(120);
  const sun = (id: string) => universe.suns.find((s) => s.id === id)?.name ?? null;
  const star = (id: string) => universe.stars.find((s) => s.id === id)?.name ?? null;
  return { entries: [...universe.planets].sort((a, b) => b.written_at.localeCompare(a.written_at)).map((p) => ({
    id: p.id, written_at: p.written_at, title: p.title, summary: entries.get(p.id)?.info?.summary ?? SUMMARY[p.id] ?? "",
    day: entries.get(p.id)?.day ?? p.written_at.slice(0, 10), day_check: entries.get(p.id)?.day_check ?? false,
    weather: p.weather, status: "done", sun: sun(p.sun_id), star: star(p.star_id) })) };
}
export async function getUniverse(): Promise<Universe> {
  await sleep(150);
  return structuredClone({ ...universe, people: people.map(({ id, name, relation, planets }) => ({ id, name, relation, planets })) });
}
export async function sendFeedback(f: Feedback) {
  await sleep(150);
  if (f.value === "오늘은 살살") settings = { ...settings, gentle_today: today() };
  if (f.value === "오늘은 위로만") settings = { ...settings, comfort_only_today: today() };
  if (f.value === "날씨 건너뜀") settings = { ...settings, weather_ask: false };
  if (f.target === "vow" && f.target_id) closedVows.add(f.target_id);
  if (f.target === "relation" && f.target_id) {
    const l = universe.links.find((x) => x.id === f.target_id);
    if (l && f.value === "맞아요") Object.assign(l, { line: "실선", needs_confirm: false });
    if (l && f.value === "아니에요") universe.links = universe.links.filter((x) => x !== l);
  }
  return { ok: true, state: null };
}
/* ---------- 쓰기 화면 말풍선 · 날짜 고치기 · 지우기(WS13) ---------- */
let prompt: Prompt = { kind: "weather", text: "오늘 마음 날씨는 어디에 가까워요? 맑음 · 구름 조금 · 흐림 · 비 · 천둥 · 안개",
  vow: { thought_id: "t8", text: "관심 있는 팀 세 곳을 직접 찾아보겠다.", overdue: true } };
const closedVows = new Set<string>();
export async function getPrompt(): Promise<Prompt> {
  await sleep(100);
  const skip = prompt.kind === "weather" && !settings.weather_ask;
  return { ...prompt, ...(skip && { kind: "none", text: "" }), vow: prompt.vow && !closedVows.has(prompt.vow.thought_id) ? prompt.vow : null };
}
export async function setEntryDay(id: string, day: string): Promise<EntryResult> {
  await sleep(120);
  const r = { ...(entries.get(id) ?? (await getDiary(id))), day, day_basis: "확실" as const, day_check: false };
  entries.set(id, r);
  return r;
}
export async function deleteDiary(id: string) {
  await sleep(120);
  entries.delete(id);
  universe.planets = universe.planets.filter((p) => p.id !== id);
  universe.links = universe.links.filter((l) => l.from_planet !== id && l.to_planet !== id);
}
export async function getPersonThoughts(id: string): Promise<PersonThoughts> {
  await sleep(100);
  const p = people.find((x) => x.id === id);
  if (!p) throw new Error("이 사람을 찾지 못했어요. 화면을 새로 고쳐 주세요.");
  const when = (eid: string) => universe.planets.find((x) => x.id === eid)!;
  const past = Object.entries(PAST_THOUGHTS).flatMap(([eid, ts]) => ts.filter((t) => t.people.includes(id))
    .map((t) => ({ ...t, entry_id: eid, written_at: when(eid).written_at, title: when(eid).title })));
  const mine = [...entries.values()].flatMap((e) => e.thoughts.filter((t) => t.people.includes(id))
    .map((t) => ({ ...t, entry_id: e.id, written_at: e.written_at, title: e.title })));
  return { person: { id, name: p.name, relation: p.relation },
    thoughts: [...past, ...mine].sort((a, b) => a.written_at.localeCompare(b.written_at)) };
}
// ponytail: 가족 말 묶음(엄마 → 부모)은 서버(pseudonym.forget_word)만 안다. 가짜 데이터는 관계 말 · '그 사람'만
const forgetAs = (p: { name: string; relation: string }) => (p.relation && p.relation !== p.name ? p.relation : "그 사람");
export async function listPeople() { await sleep(100); return { people: structuredClone(people) }; }
export async function addPerson(p: { name: string; nickname: string; relation: string }) {
  const n: Person = { id: "p" + (people.length + 10), ...p, auto: false, planets: [], forget_as: forgetAs(p) };
  people = [...people, n];
  return n;
}
export async function updatePerson(id: string, p: Partial<Person>) {
  people = people.map((x) => (x.id === id ? { ...x, ...p, forget_as: forgetAs({ ...x, ...p }) } : x));
  return people.find((x) => x.id === id)!;
}
export async function deletePerson(id: string) {
  const replaced = people.find((x) => x.id === id)?.planets.length ?? 0;
  people = people.filter((x) => x.id !== id);
  return { ok: true, replaced };
}
export async function getAspiration() { await sleep(100); return structuredClone(aspiration); }
export async function saveAspiration(a: { now: string; want: string; obstacle: string; if_then: string; values: string[] }) {
  const n: Aspiration = { id: "a" + (aspiration.history.length + 3), said: a.want, values: a.values, obstacle: a.obstacle,
    if_then: a.if_then, said_at: new Date().toISOString(), reached: [] };
  aspiration = { ...aspiration, current: n, history: aspiration.current ? [aspiration.current, ...aspiration.history] : aspiration.history };
  universe.north_star = { text: n.said, values: n.values, reached_planets: [], reached: [] };
  return n;
}
export async function getMe(): Promise<Me> {
  await sleep((globalThis as { __slowMe?: number }).__slowMe ?? 100);   // 시험: /me 가 /universe 보다 늦게 오는 경우
  return { user: { id: "mock", email: "haneul@example.com" }, settings: { ...settings },
    onboarding: { entries: universe.planets.length, aspiration: "set", weather_asked: true } };
}
export async function patchSettings(s: Partial<Settings>) {
  // 백엔드와 같은 규칙: 팩폭은 경고 확인 뒤에만
  if (s.tone === "팩폭" && !(s.fact_bomb_ack ?? settings.fact_bomb_ack)) throw new Error("팩폭은 경고를 확인한 뒤에 고를 수 있어요.");
  const note = s.tone_note === undefined ? settings.tone_note : s.tone_note.replace(/\s+/g, " ").trim();
  if ((s.tone ?? settings.tone) === "직접 정하기" && !note) throw new Error("원하는 말투를 한 줄 적어 주세요.");
  settings = { ...settings, ...s, tone_note: note };
  return { ...settings };
}

// 동의: 가짜 데이터 모드는 이미 동의한 사용자(시험 계정과 같음).
// localStorage "mock-consent" 가 "none" 이면 아직 동의하지 않은 사용자(e2e 동의 화면 시험).
const CONSENT_V = "2026-10-13";
const consentRead = () => { try { return localStorage.getItem("mock-consent"); } catch { return null; } };
export async function getConsent(): Promise<Consent> {
  const v = consentRead();
  if (v === "none") return { version: CONSENT_V, needed: true, agreed: null };
  return { version: CONSENT_V, needed: false, agreed: { version: CONSENT_V, operator_read: v === "operator_read", at: "2026-10-13T09:00:00+09:00" } };
}
export async function saveConsent(c: ConsentInput): Promise<Consent> {
  if (!c.age14) throw new Error("만 14세 미만은 지금 쓸 수 없어요.");
  if (!c.required || !c.sensitive) throw new Error("필수 동의가 빠졌어요. 필수 항목 둘과 나이를 골라 주세요.");
  localStorage.setItem("mock-consent", c.operator_read ? "operator_read" : "ok");
  return getConsent();
}

/* ---------- 대화 · 요약 확인 (WS19 · WS20) ---------- */
// 별지기 답은 고정 문장 몇 개를 돌려 쓴다(백엔드는 Solar + 말 검사). 위기 말이면 위로 + 안부 한 줄, 질문 없음.
const talks = new Map<string, Conversation>();
const REPLIES = ["그랬군요. 그때 마음은 어땠어요?", "지난 9/20에 '팀 세 곳을 직접 찾아보겠다'고 하셨는데, 오늘 이야기와 이어지네요. 요즘은 어때요?",
  "이야기해 줘서 고마워요. 그다음엔 어떻게 됐어요?"];
let talkSeq = 1;
const now = () => new Date().toISOString();
export async function listTalks() { await sleep(100); return { conversations: [...talks.values()].reverse().map((c) => structuredClone(c)) }; }
export async function startTalk(from?: string): Promise<Conversation> {
  await sleep(150);
  for (const [k, c] of talks) if (!c.turn_count) talks.delete(k);
  const p = from && universe.planets.find((x) => x.id === from);
  const text = p ? `${p.written_at.slice(0, 10)}에 쓴 '${p.title}' 이야기를 이어 해 볼까요? 그 뒤로 어떻게 지냈어요?`
    : prompt.vow ? `지난번에 적은 다짐, '${prompt.vow.text}' 요즘은 어때요? 떠오르는 만큼 편하게 들려줘요.` : "오늘 하루는 어땠어요? 떠오르는 것부터 편하게 이야기해 줘요.";
  const c: Conversation = { id: "c" + talkSeq++, created_at: now(), updated_at: now(), summary: "", from_entry: p ? from! : null,
    entry_id: null, turn_count: 0, wrap: false, turns: [{ role: "keeper", kind: p ? "continue" : prompt.vow ? "vow" : "free", text, at: now() }] };
  talks.set(c.id, c);
  return structuredClone(c);
}
export async function getTalk(id: string) {
  const c = talks.get(id);
  if (!c) throw new Error("이 대화를 찾지 못했어요. 지워졌을 수 있어요. '새 대화 시작'을 눌러 주세요.");
  return structuredClone(c);
}
export async function deleteTalk(id: string) { talks.delete(id); }
export async function sayTalk(id: string, text: string, onProgress: (p: TalkProgress) => void, via: "text" | "voice" = "text"): Promise<Conversation> {
  const c = talks.get(id);
  if (!c) throw { entry_id: null, code: "not_found", message: "이 대화를 찾지 못했어요. 지워졌을 수 있어요. '새 대화 시작'을 눌러 주세요.", resumable: false } as StreamError;
  for (const [step, label] of [["safety", "말을 살펴보는 중"], ["past", "지난 기록을 찾는 중"], ["reply", "별지기가 답을 고르는 중"]]) {
    onProgress({ conversation_id: id, step, label });
    await sleep(STEP_MS);
  }
  const crisis = CRISIS.some((w) => text.includes(w)), wrap = /그만|여기까지|잘게/.test(text) && !crisis;
  const reply = crisis ? "많이 힘들었겠어요. 이렇게 털어놓아 줘서 고마워요. 저는 여기 있을게요."
    : wrap ? "오늘은 진로 이야기를 차분히 꺼내 줬네요.\n여기까지 정리해 둘까요? '대화 마치고 정리하기'를 누르면 오늘 이야기를 일기로 정리해요."
    : REPLIES[c.turn_count % REPLIES.length];
  c.turns.push({ role: "user", text, at: now(), via },
    { role: "keeper", kind: wrap ? "wrap" : "reply", text: reply, mode: crisis ? "comfort" : "normal", tone: settings.tone, check_in: crisis ? CHECK_IN : null, at: now() });
  c.turn_count += 1; c.wrap = wrap; c.updated_at = now();
  if (c.turn_count % 3 === 0 || text.length >= 300) c.summary = c.turns.filter((t) => t.role === "user").map((t) => t.text).join(" ").slice(0, 200);
  return structuredClone(c);
}
export async function finishTalk(id: string, h: StreamHandlers): Promise<EntryResult> {
  const c = talks.get(id)!;
  const text = c.turns.filter((t) => t.role === "user").map((t) => t.text).join("\n");
  h.onProgress({ entry_id: "", step: "draft", label: "대화를 일기로 정리하는 중", done: 0, total: STEPS.length });
  const eid = "e" + seq++;
  for (let i = 0; i < STEPS.length - 1; i++) {
    await sleep(STEP_MS);
    h.onProgress({ entry_id: eid, step: STEPS[i][0], label: STEPS[i][1], done: i + 1, total: STEPS.length });
  }
  const r: EntryResult = { ...result(eid, { text, title: "오늘의 이야기" }), status: "confirm", step: "voice", source: "대화",
    day_basis: "확실", confirmed: "확인 전", message: null, next_question: null, reached: [], people_questions: [] };
  entries.set(eid, r);
  c.entry_id = eid;
  return structuredClone(r);
}
export async function confirmDiary(id: string, x: ConfirmInput): Promise<EntryResult> {
  await sleep(300);
  const r = entries.get(id);
  if (!r || r.status !== "confirm") throw new Error("이미 저장했거나 확인할 수 없는 정리예요. 화면을 새로 고쳐 주세요.");
  const gone = new Set(x.fixes.filter((f) => f.remove).map((f) => f.id));
  const kind = new Map(x.fixes.filter((f) => f.kind).map((f) => [f.id, f.kind!]));
  const done: EntryResult = { ...result(id, { text: "", title: r.title }), source: "대화", confirmed: "확인됨", day_basis: "확실",
    info: { ...r.info!, summary: x.summary ?? r.info!.summary },
    thoughts: r.thoughts.filter((t) => !gone.has(t.id)).map((t) => ({ ...t, kind: kind.get(t.id) ?? t.kind })) };
  entries.set(id, done);
  for (const [k, c] of talks) if (c.entry_id === id) talks.delete(k);
  return structuredClone(done);
}

/* ---------- 말로 쓰기 · 읽어 주기 (WS21) ---------- */
// 가상 인물 하늘이 말한 것처럼 조각마다 한 문장. e2e 가 조각 크기 · 읽어 준 글을 보도록 window 에 남긴다.
const SAID = ["오늘은 아침 일찍 동네 공원을 천천히 걸었어요.", "바람이 차가웠는데 걷고 나니 머리가 맑아졌어요.",
  "점심엔 동생이랑 김밥을 먹으면서 진로 이야기를 했어요.", "아직 정한 건 없지만 이번 주엔 포트폴리오를 한 장이라도 고쳐 보려고요.",
  "오후엔 도서관에서 디자인 책을 두 권 빌렸어요.", "읽다 보니 예전에 그림 그리던 때가 생각나서 조금 설렜어요.",
  "저녁엔 엄마가 끓여 준 된장찌개를 먹고 일찍 씻었어요.", "내일은 오늘보다 삼십 분 일찍 일어나 보고 싶어요.",
  "요즘 밤에 휴대폰을 오래 보는 게 마음에 걸려요.", "그래서 열한 시가 되면 휴대폰을 책상 위에 두고 자기로 했어요.",
  "동생이 그 말을 듣고 자기도 같이 해 보겠다고 해서 웃었어요.", "작은 거라도 하나씩 해 보면 조금은 달라질 것 같아요."];
type VoiceLog = { __voicePieces?: number[]; __spoken?: string[] };
export async function transcribe(piece: Blob): Promise<{ text: string; seconds: number }> {
  const w = window as unknown as VoiceLog;
  const n = (w.__voicePieces ??= []).push(piece.size);
  await sleep(STEP_MS);
  const seconds = Math.round(Math.max(0, piece.size - 44) / 32000);   // 16kHz 모노 WAV 조각 기준
  const at = ((n - 1) * 6) % SAID.length;
  return { text: seconds >= 60 ? SAID.slice(at, at + 6).join(" ") : SAID[(n - 1) % SAID.length], seconds };   // 긴 조각은 긴 이야기
}
export async function speak(text: string): Promise<Blob> {
  ((window as unknown as VoiceLog).__spoken ??= []).push(text);
  return new Blob([new Uint8Array(44)], { type: "audio/wav" });
}
