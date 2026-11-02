"""
tools/make_common_words.py

이름 글자(pseudonym.GIVEN) 둘로 된 보통 낱말 목록(app/service/safety/common_words.txt)을 다시 만든다.
'설명 · 대신 · 준비'처럼 이름 글자로만 된 낱말을 이름으로 잡던 것을 막는다(2026-11-03 동규 「오타나 낱말을 사람 이름으로 잡음」).
Kiwi(Apache-2.0)는 서버에 넣지 않고(모델 104MB) 여기서만 쓴다:
    uv run --with kiwipiepy python tools/make_common_words.py
"""

import re
from pathlib import Path

from kiwipiepy import Kiwi

SRC = Path(__file__).resolve().parents[1] / "app/service/safety/pseudonym.py"
OUT = SRC.with_name("common_words.txt")
HEAD = """# 이름 글자 둘로 된 보통 낱말(이름처럼 보여도 이름이 아닌 말). app/service/safety/pseudonym.py 의 _name_like 가 뺀다.
# 만든 법: Kiwi 형태소 분석기(kiwipiepy 0.24 · kiwipiepy_model 0.24, Apache-2.0, github.com/bab2min/Kiwi)에
# GIVEN 글자 두 개의 모든 짝을 넣어, 사전이 아는 보통 명사(NNG 한 덩어리, 점수 -13.5 위) · 동사 줄기만 남겼다(2026-11-03).
# 서버에는 Kiwi 를 넣지 않는다(모델 104MB). GIVEN 을 바꾸면 다시 만든다(tools/make_common_words.py).
"""

# pseudonym 을 불러오면 openai 까지 따라와서, GIVEN 글자만 글에서 읽는다
given = sorted(set("".join(re.findall(r'"([^"]*)"', re.search(r"GIVEN = set\(((?:\"[^\"]*\"\s*)+)\)", SRC.read_text()).group(1)))))
kiwi = Kiwi()
words = []
for w in (a + b for a in given for b in given):
    t = kiwi.tokenize(w)
    # 아는 보통 명사(모르는 글자 짝은 점수가 -18 아래) 또는 동사 · 형용사 줄기(만나 · 두라)
    if (len(t) == 1 and t[0].form == w and t[0].tag == "NNG" and t[0].score > -13.5) or (t and t[0].form == w and t[0].tag in ("VV", "VA")):
        words.append(w)
OUT.write_text(HEAD + "\n".join(words) + "\n")
print(f"{len(words)} words → {OUT}")
