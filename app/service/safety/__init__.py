"""안전: 위기 감지, 가명 처리, 사람 판정 문장 검사. 모두 순수 함수(DB · 네트워크 없음). 단 detect_crisis(llm=True)만 가명 처리한 글로 Solar 를 부른다."""
from app.service.safety.crisis import detect_crisis
from app.service.safety.judge import judged
from app.service.safety.pseudonym import (RealNameLeak, assert_no_real_names, find_new_names, forget, mask,
                                          unmask)
