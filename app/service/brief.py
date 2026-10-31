"""
app/service/brief.py

흐름 요약(PRD v9 ⑥ · Q10) · 내 일기에 묻기(Q11). 둘 다 이미 있는 원문 재료로만 Solar 가 짧게 쓰고,
문장마다 출처(재료 번호 → 기록 · 날짜)를 붙인다. 출처가 없거나 재료에 없는 번호를 단 문장은 버린다(지어낸 말 막기).
사람을 판정 · 진단하지 않는다(tone_rules): 그런 생각이 나온 날의 원문만 비춘다.
"""

import json
import re
from datetime import date, timedelta

MIN_RECORDS = 3   # 이보다 적으면 요약하지 않고 '아직 모으는 중'(짐작)
MAX_REFS = 40     # '처음부터'가 길어지면 작은 별마다 처음 · 마지막만 넘기고, 그래도 많으면 앞에서 자름

SECTIONS = ("한눈에", "영역", "영역을 넘어 이어진 생각", "되고 싶은 모습 쪽으로")
JUDGE = re.compile(r"당신은|너는 .*사람|성격|문제가 있|해야 (합|해)|하세요")


def since(period, today):
    """기간 칩 → 시작 날(이 날 포함). week = 이번 주 월요일부터, month = 이번 달 1일부터, all = None."""
    today = today if isinstance(today, date) else date.fromisoformat(str(today))
    return {"week": today - timedelta(days=today.weekday()), "month": today.replace(day=1)}.get(period)


def material(ins, reached=()):
    """rules.insight 결과 → (재료 글, refs{번호: {entry_id, day}}). 번호는 R1, R2 …"""
    refs, lines = {}, []

    def ref(e):
        k = f"R{len(refs) + 1}"
        refs[k] = {"entry_id": e["record_id"], "day": e["day"]}
        return f"[{k} {e['day']}] “{e.get('quote', '')}”"

    for sun in ins.get("suns", []):
        lines.append(f"## {sun['name']} (기록 {sun['records']}편)")
        for k in sun["kept"]:
            lines.append(f"- 이어 온 생각 · {k['star']} {k['times']}번: 처음 {ref(k['from'])} → 마지막 {ref(k['to'])}")
        for name, key in (("바뀐 생각", "changed"), ("맞서는 생각", "open"), ("정리된 생각", "settled")):
            for p in sun[key]:
                frm = p.get("froms") or [p["from"]]
                to = p.get("tos") or [p["to"]]
                lines.append(f"- {name} · {p.get('star', '')}: 그때 {ref(frm[0])} → 지금 {ref(to[-1])}")
    for a in ins.get("across", []):
        lines.append(f"- 영역을 넘어 이어진 생각 · {a['type']} {' ↔ '.join(a['suns'])}: {ref(a['from'])} → {ref(a['to'])}")
    for r in reached:
        lines.append(f"- 되고 싶은 모습에 닿은 날: {ref(r)}")
        if len(refs) >= MAX_REFS:
            break
    return "\n".join(lines[:MAX_REFS * 2]), refs


def brief_messages(text, period_label, suns):
    sys = ("너는 일기장 '나의 우주'의 흐름 요약을 쓴다. 아래 재료(사용자가 쓴 원문 인용과 날짜)만으로, 이 기간에 생각이 어디에 머물고 "
           "어떻게 이어지고 바뀌었는지 짧게 비춰 준다. 재료에 없는 일을 지어내지 않는다. 사람을 판정 · 진단 · 평가하지 않고 조언하지 않는다"
           "('당신은 ~한 사람' 금지). 바뀐 생각을 잘못처럼 말하지 않는다. 문장마다 근거가 된 재료 번호(R1 같은)를 sources 에 하나 이상 단다.\n"
           f"소제목은 순서대로 '한눈에'(2~3문장), 영역마다 그 이름({', '.join(suns)}), 재료에 있을 때만 '영역을 넘어 이어진 생각' · "
           "'되고 싶은 모습 쪽으로'. 영역마다 1~3문장.\n"
           'JSON 하나만: {"sections": [{"title": 소제목, "sentences": [{"text": 문장, "sources": ["R1"]}]}]}')
    return [{"role": "system", "content": sys}, {"role": "user", "content": f"기간: {period_label}\n\n재료:\n{text}"}]


def ask_messages(question, refs_text):
    sys = ("너는 일기장 '나의 우주'에서 사용자가 자기 일기에 묻는 말에 답한다. 아래 찾은 원문(번호 · 날짜 · 인용)만으로 짧게 답한다. "
           "원문에 없는 일을 지어내지 않고, 사람을 판정 · 진단 · 해석하지 않으며 조언하지 않는다. '나는 왜 이럴까' 같은 물음에도 이유를 "
           "짐작하지 않고, 그런 생각이 나온 날의 원문을 비춰 준다. 문장마다 근거 번호를 sources 에 하나 이상 단다. 1~4문장.\n"
           'JSON 하나만: {"found": 찾은 원문으로 답할 수 있으면 true, "sentences": [{"text": 문장, "sources": ["R1"]}]}')
    return [{"role": "system", "content": sys}, {"role": "user", "content": f"물음: {question}\n\n찾은 원문:\n{refs_text}"}]


def parse(raw, refs, unmask=lambda s: s):
    """→ [{"title", "sentences": [{"text", "sources": [{entry_id, day}]}]}]. 출처 없는 문장 · 판정하는 문장은 버린다."""
    m = re.search(r"\{.*\}", raw or "", re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        d = {}
    secs = d.get("sections") if isinstance(d.get("sections"), list) else [{"title": "", "sentences": d.get("sentences") or []}]
    out = []
    for sec in secs:
        sents = []
        for x in sec.get("sentences") or [] if isinstance(sec, dict) else []:
            src = [refs[k] for k in dict.fromkeys(x.get("sources") or []) if k in refs] if isinstance(x, dict) else []
            text = unmask(str(x.get("text") or "").strip()) if isinstance(x, dict) else ""
            if text and src and not JUDGE.search(text):
                sents.append({"text": text, "sources": src})
        if sents:
            out.append({"title": unmask(str(sec.get("title") or "")), "sentences": sents})
    return out, d.get("found")


if __name__ == "__main__":
    assert since("week", date(2026, 11, 5)) == date(2026, 11, 2) and since("month", date(2026, 11, 5)) == date(2026, 11, 1)
    refs = {"R1": {"entry_id": "e1", "day": "2026-10-01"}}
    raw = '{"sections": [{"title": "한눈에", "sentences": [{"text": "진로 생각이 이어졌어요.", "sources": ["R1"]},' \
          '{"text": "근거 없는 말", "sources": ["R9"]}, {"text": "당신은 성실한 사람이에요.", "sources": ["R1"]}]}]}'
    secs, _ = parse(raw, refs)
    assert [s["text"] for s in secs[0]["sentences"]] == ["진로 생각이 이어졌어요."]
    print("ok")
