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
FALLBACK_MODEL = "claude-sonnet-4-6"  # JSON 파싱 실패 시 자동 fallback (더 강한 모델)


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
      "구분": "정규직",
      "퇴사사유": "이력서·자소서에 명시된 사유 (예: 계약만료, 조직개편, 이직, 학업, 결혼/육아, 개인사정 등). 명시 없으면 빈 문자열."
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
  - "퇴사사유": 이력서·자소서·경력기술서에 명시된 사유만 기재 (예: 계약만료·조직개편·이직·학업·결혼/육아·개인사정·회사 사정·프로젝트 종료 등). 명시되지 않으면 반드시 빈 문자열. 절대 추측 금지.
  - 같은 회사를 여러 번 다녔으면 별도 항목으로 분리
  - 정직원/계약직 경력이 없으면 빈 배열
- "경력연수"는 인턴·교육·학원 제외한 정직원·계약직 재직개월 합계로 산정 (1년=12개월). 소수점 1자리까지.
- 정보 없는 필드는 빈 문자열/빈 배열. 추측 금지.
- 응답은 위 JSON 한 객체만. 다른 텍스트 X.
- 한국어로 작성.
"""


LEARN_PROFILE_PROMPT = """당신은 채용 담당 시니어 HR 매니저입니다.
주어진 채용 공고(JD)와 지원자들의 자료(이력서·포트폴리오·자소서)를 분석해서,
이 회사가 어떤 인재상을 **우대**했는지(긍정 사례) 그리고 어떤 패턴을 **회피**했는지(부정 사례, 있을 경우)
**추상화된 패턴**으로 추출하세요.

## 입력 라벨
지원자들은 다음 라벨로 그룹화되어 제공됩니다:
- **[POSITIVE]** = 합격자 또는 면접 단계까지 진출한 지원자 (우대 패턴)
- **[NEGATIVE]** = 탈락한 지원자 (회피 패턴)

## 🔒 개인정보 보호 규칙 (절대 준수)
출력 어디에도 **개인 식별 정보를 절대 포함하지 마세요**:
- ❌ 지원자 본인 이름, 영문명, 이니셜
- ❌ 지원자가 다닌 구체적 회사명 (예: "OO기업", "OO스타트업" 같은 익명 표기로)
- ❌ 지원자가 다닌 구체적 학교명·전공 (예: "주요 대학", "공학 전공" 같은 일반화)
- ❌ 구체적 프로젝트명·서비스명·제품명 (기능 설명으로 일반화)
- ❌ 구체적 자격증·수상 이력의 고유명
- ❌ 구체적 직책 (시니어·주니어·리더 같은 추상 수준만)
- ❌ 구체적 도메인(헬스케어, 광고, 핀테크 등 산업 카테고리 수준만, 회사 이름 X)

대신 **역량·태도·기술 스택·경험 유형**의 추상화된 표현만 사용하세요.
예: "Ruby on Rails 시니어 백엔드 경력" (O) / "OO기업에서 11년 RoR 개발" (X)

## 출력 JSON 형식
```json
{
  "인재상_요약": "JD와 POSITIVE 그룹 패턴 + NEGATIVE 그룹 회피 패턴을 종합한 자연어 인재상 텍스트. 인재상 관리 페이지에 그대로 붙여넣을 수 있는 형식. 다음 두 섹션을 포함하세요:\n\n## 우대 인재상 (POSITIVE 패턴)\n- 8~12줄: 합격·면접 진출자에게서 공통으로 보이는 역량·태도·경험 유형\n\n## 회피 패턴 (NEGATIVE 패턴 — 탈락자 자료가 있을 때만)\n- 4~7줄: 탈락자에게서 반복적으로 보이는 약점·미스매치 패턴 (지원자 비난 X, 채용 기준 관점에서 서술)\n\n**모든 개인정보/회사명/학교명/프로젝트명 제외, 역량·태도·경험 유형만 표현.**"
}
```

규칙:
- 한국어로 작성.
- **POSITIVE 그룹**에서 공통적·반복적으로 보이는 추상화된 패턴 위주. 한 명에게만 있는 특수 경험은 제외.
- **NEGATIVE 그룹**이 비어있거나 1명뿐이면 "회피 패턴" 섹션은 생략.
- NEGATIVE에서 "이 사람은 별로다" 식 표현 금지. "OO 경험이 부족한 지원자가 탈락하는 경향" 같이 채용 관점으로.
- 추측 금지. 자료에 근거한 분석만.
- 응답은 위 JSON 한 객체만. 다른 텍스트 X.
- **다시 강조**: 출력 어디에도 지원자 이름·회사명·학교명·프로젝트명 등장 절대 금지.
"""


def learn_ideal_profile(
    jd_text: str,
    hired_examples: list[dict],  # [{name, documents}] — POSITIVE 그룹 (호환성 유지)
    negative_examples: list[dict] | None = None,  # [{name, documents}] — NEGATIVE (탈락자)
) -> dict[str, Any]:
    """POSITIVE(합격/면접진출) + NEGATIVE(탈락) 자료로 인재상 텍스트 자동 생성.

    기존 호출 시그니처(positional positive only)는 그대로 동작.
    """
    client = _client()

    def _format_group(label: str, examples: list[dict]) -> str:
        if not examples:
            return ""
        section = f"\n\n# {label} 그룹 ({len(examples)}명)"
        for ex in examples:
            section += f"\n\n=== [{label}] {ex['name']} ===\n"
            for fname, text in ex.get('documents', {}).items():
                section += f"\n--- {fname} ---\n{text[:15000]}\n"
        return section

    positive_section = _format_group("POSITIVE", hired_examples)
    negative_section = _format_group("NEGATIVE", negative_examples or [])

    user_message = (
        f"# 채용 공고 (JD)\n{jd_text}"
        f"{positive_section}"
        f"{negative_section}"
    )

    msg = client.messages.create(
        model=FALLBACK_MODEL,  # 인재상 학습은 정확도 중요 → sonnet 사용
        max_tokens=3000,
        system=LEARN_PROFILE_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    text = msg.content[0].text.strip()
    m = re.search(r'\{[\s\S]*\}', text)
    if not m:
        return {"error": "JSON 파싱 실패", "raw": text}
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return {"error": f"JSON 파싱 실패: {e}", "raw": text}
    data["_model"] = FALLBACK_MODEL
    data["_tokens"] = {"input": msg.usage.input_tokens, "output": msg.usage.output_tokens}
    data["_positive_count"] = len(hired_examples)
    data["_negative_count"] = len(negative_examples or [])
    return data


def analyze_applicant(
    jd_text: str,
    applicant_name: str,
    documents: dict[str, str],  # {파일명: 텍스트}
    ideal_profile: str = "",
    hired_reference: str = "",
    vision_items: list[dict] | None = None,  # [{type: 'pdf'|'image', media_type, data: bytes, name}]
) -> dict[str, Any]:
    """지원자 1명 분석 → JSON dict.

    vision_items가 있으면 Claude vision/document content block 사용 (sonnet 모델).
    디자이너 포트폴리오·이미지·zip 내부 자료 평가 시 활용.
    """
    import base64
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

    hired_section = ""
    if hired_reference.strip():
        hired_section = (
            f"\n\n# 과거 합격자 reference (Few-shot — 이런 사람들이 우리 회사에 합격했습니다)\n"
            f"{hired_reference.strip()}\n"
            f"\n매칭도 평가 시 이 합격자들과 얼마나 패턴이 비슷한지도 함께 고려하세요."
        )

    vision_section = ""
    if vision_items:
        vision_section = (
            f"\n\n# 시각 자료 ({len(vision_items)}개)\n"
            f"아래 첨부된 포트폴리오 PDF · 디자인 이미지 등 시각 자료를 직접 검토해서 "
            f"디자인 품질·일관성·표현력·컨셉을 평가에 반영하세요. "
            f"디자이너 포지션 평가 시 시각 자료 비중을 높게 두세요."
        )

    user_text = (
        f"# 채용 공고 (JD)\n{jd_text}"
        f"{profile_section}"
        f"{hired_section}"
        f"{vision_section}\n\n"
        f"# 지원자: {applicant_name}\n"
        f"# 제출 자료 (텍스트){docs_section}"
    )

    # vision content block 구성
    content_blocks: list[dict] = []
    if vision_items:
        for item in vision_items[:30]:  # max 30개 (안전 마진)
            try:
                b64 = base64.standard_b64encode(item['data']).decode('ascii')
            except Exception:
                continue
            if item['type'] == 'pdf':
                content_blocks.append({
                    "type": "document",
                    "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
                    "title": item.get('name', 'document.pdf')[:100],
                })
            elif item['type'] == 'image':
                content_blocks.append({
                    "type": "image",
                    "source": {"type": "base64",
                               "media_type": item.get('media_type', 'image/png'), "data": b64},
                })
    content_blocks.append({"type": "text", "text": user_text})

    # vision 자료 있으면 처음부터 sonnet (vision 더 강함). 없으면 haiku → sonnet fallback.
    has_vision = bool(vision_items)
    primary_model = FALLBACK_MODEL if has_vision else MODEL
    primary_max = 4000 if has_vision else 2500

    def _try(model: str, max_tokens: int, blocks: list[dict]):
        msg = client.messages.create(
            model=model, max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": blocks}],
        )
        text = msg.content[0].text.strip()
        m = re.search(r'\{[\s\S]*\}', text)
        if not m:
            return None, text, msg, "JSON 블록 없음"
        try:
            return json.loads(m.group(0)), text, msg, None
        except json.JSONDecodeError as e:
            return None, text, msg, f"{e}"

    # 413 RequestTooLargeError 대응: vision 자료를 큰 것부터 하나씩 떨궈가며 재시도
    from anthropic import APIStatusError
    def _try_with_413_retry(model: str, max_tokens: int, initial_blocks: list[dict]):
        blocks = list(initial_blocks)
        dropped_count = 0
        last_exc: Exception | None = None
        for attempt in range(4):  # 최대 4번 시도 (원본 + 3회 페이로드 축소)
            try:
                return _try(model, max_tokens, blocks) + (dropped_count,)
            except APIStatusError as e:
                last_exc = e
                code = getattr(e, 'status_code', None)
                if code != 413:
                    raise
                # vision PDF/image 블록 중 가장 큰 것 1개 제거
                non_text_idx = [i for i, b in enumerate(blocks)
                                if b.get('type') in ('document', 'image')]
                if not non_text_idx:
                    raise  # 더 떨굴 게 없음
                largest_i = max(non_text_idx,
                                key=lambda i: len(blocks[i].get('source', {}).get('data', '')))
                blocks.pop(largest_i)
                dropped_count += 1
        # 모든 시도 실패
        if last_exc:
            raise last_exc
        return None, "", None, "exhausted", dropped_count

    try:
        result_tuple = _try_with_413_retry(primary_model, primary_max, content_blocks)
        data, raw_text, msg, err, vision_dropped = result_tuple
    except APIStatusError as e:
        return {"error": f"API 오류: {e}", "raw": str(e)}
    used_model = primary_model

    # haiku 실패 시 sonnet fallback (vision 없는 경우)
    if data is None and not has_vision:
        try:
            data, raw_text, msg, err = _try(FALLBACK_MODEL, 4000, content_blocks)
            used_model = FALLBACK_MODEL if data else used_model
        except Exception as e:
            err = f"sonnet 재시도도 실패: {e}"

    if data is None:
        return {"error": f"JSON 파싱 실패: {err}", "raw": raw_text}

    data["_model"] = used_model
    data["_tokens"] = {"input": msg.usage.input_tokens, "output": msg.usage.output_tokens}
    data["_vision_count"] = (len(vision_items) - vision_dropped) if vision_items else 0
    if vision_dropped:
        data["_vision_dropped_413"] = vision_dropped
    return data
