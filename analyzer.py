"""Claude API로 이력서 분석.

입력: JD + 지원자 자료(이력서·포트폴리오·자소서 텍스트)
출력: JSON 구조 (메타정보 + 핵심역량/경험요약 + 매칭도 점수)
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from anthropic import Anthropic

MODEL = "claude-haiku-4-5"  # 비용 효율적이고 충분히 똑똑


def _client() -> Anthropic:
    api_key = ""
    try:
        import streamlit as st
        api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        pass
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY 환경변수 또는 secrets에 없음")
    return Anthropic(api_key=api_key)


SYSTEM_PROMPT = """당신은 채용 담당자를 돕는 시니어 HR 매니저입니다.
주어진 채용 공고(JD)와 지원자 자료(이력서·포트폴리오·자소서)를 분석해서 다음 JSON 형식으로 응답하세요.

```json
{
  "기본정보": {
    "이름": "...",
    "이메일": "... 또는 빈 문자열",
    "연락처": "... 또는 빈 문자열",
    "나이": "... 또는 빈 문자열",
    "최종학력": "... (학교명/전공/졸업여부)",
    "경력연수": "X년 또는 신입 (인턴·교육 제외 정직원·계약직 합계)"
  },
  "경력사항": [
    {
      "회사명": "회사명",
      "역할": "직무/역할/팀",
      "기간": "2021-03 ~ 2023-08 또는 자유 형식",
      "재직개월": 29,
      "구분": "정규직"
    }
  ],
  "핵심역량": ["...", "...", "..."],
  "주요기술스택": ["Python", "PyTorch", "..."],
  "경험요약": "3~5줄로 핵심 경험을 자연어로 요약. 어떤 프로젝트/역할을 했고 어떤 임팩트를 냈는지.",
  "자격및기타": ["관련 자격증·수상·논문·공모전·기타"],
  "매칭도": {
    "점수": 0,
    "장점": ["JD 자격요건·우대사항과 회사 인재상 기준 강점 3~5개. 각 항목 끝에 출처 표기 [JD] 또는 [인재상]"],
    "약점": ["JD 자격요건·우대사항과 회사 인재상 기준 약점/우려점 2~3개. 각 항목 끝에 출처 표기 [JD] 또는 [인재상]"],
    "한줄평": "최종 인상 한 줄"
  }
}
```

규칙:
- 매칭도 점수: 0~100 정수. JD의 자격요건·우대사항·주요업무 + (있다면) **회사 인재상 부합도**를 종합 평가.
  - JD 기술/경험 적합도와 회사 인재상 부합도를 균형 있게 고려
  - 회사 인재상에 명시된 가치/태도/도메인 적합성도 매칭도에 반영
- 장점·약점은 JD와 인재상 둘 다 보고 작성:
  - JD의 자격요건/우대사항/주요업무 기준 항목 → 끝에 [JD] 표기
  - 회사 인재상의 가치/태도/도메인 기준 항목 → 끝에 [인재상] 표기
  - 인재상이 있으면 장점·약점 각각에 인재상 항목을 최소 1개 이상 포함
- 인재상이 비어있으면 [JD]만 사용.
- **경력사항**:
  - 회사 단위 직장 경력만 포함 (인턴·체험형·해외연수·학원/교육과정·프로젝트는 제외)
  - "구분"은 "정규직"·"계약직"·"프리랜서"·"인턴"·"기타" 중 하나 (인턴은 가급적 제외하되 명시되어 있으면 표시)
  - "재직개월"은 시작일~종료일 기준 개월 수 정수. 모를 경우 "기간" 문자열만 채우고 0으로.
  - 같은 회사를 여러 번 다녔으면 별도 항목으로 분리
  - 정직원/계약직 경력이 없으면 빈 배열
- "경력연수"는 인턴·교육·학원 제외한 정직원·계약직 재직개월 합계로 산정 (1년=12개월). 소수점 1자리까지.
- 정보 없는 필드는 빈 문자열/빈 배열. 추측 금지.
- 응답은 위 JSON 한 객체만. 다른 텍스트 X.
- 한국어로 작성.
"""


def analyze_applicant(
    jd_text: str,
    applicant_name: str,
    documents: dict[str, str],  # {파일명: 텍스트}
    ideal_profile: str = "",  # 회사 인재상 (포지션별 + 공통)
) -> dict[str, Any]:
    """지원자 1명 분석 → JSON dict."""
    client = _client()

    docs_section = ""
    for fname, text in documents.items():
        truncated = text[:25000]
        docs_section += f"\n\n=== {fname} ===\n{truncated}"

    profile_section = ""
    if ideal_profile.strip():
        profile_section = (
            f"\n\n# 회사 인재상 / 우대 인재 (JD와 함께 종합 평가)\n"
            f"{ideal_profile.strip()}"
        )

    user_message = (
        f"# 채용 공고 (JD)\n{jd_text}"
        f"{profile_section}\n\n"
        f"# 지원자: {applicant_name}\n"
        f"# 제출 자료{docs_section}"
    )

    msg = client.messages.create(
        model=MODEL,
        max_tokens=2500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    text = msg.content[0].text.strip()
    # JSON 블록 추출 (모델이 코드 블록 감쌀 수도 있음)
    m = re.search(r'\{[\s\S]*\}', text)
    if not m:
        return {"error": "JSON 파싱 실패", "raw": text}
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return {"error": f"JSON 파싱 실패: {e}", "raw": text}

    data["_model"] = MODEL
    data["_tokens"] = {"input": msg.usage.input_tokens, "output": msg.usage.output_tokens}
    return data
