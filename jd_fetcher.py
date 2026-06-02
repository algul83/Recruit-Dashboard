"""채용 공고 URL → JD 본문 추출.

- 사람인: HTML fetch + 텍스트 정제
- 잡코리아: JS 렌더링이라 직접 fetch 불가 → secrets[position_jd_text]에 텍스트 저장해서 우회
- Notion에서 작성한 JD를 secrets에 직접 등록하면 어떤 URL이든 적용됨
"""
from __future__ import annotations

import os
import re

import requests

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36'
    ),
}


def fetch_saramin_jd(url: str) -> str:
    """사람인 공고 URL → 정리된 텍스트 JD.

    사람인은 `view` URL이 JS 렌더링이라 `view-detail` URL로 변환해서 fetch.
    """
    # URL 정규화: view?rec_idx=... → view-detail?rec_idx=...
    m = re.search(r'rec_idx=(\d+)', url)
    if not m:
        raise ValueError(f"rec_idx를 찾을 수 없습니다: {url}")
    rec_idx = m.group(1)
    detail_url = f"https://www.saramin.co.kr/zf_user/jobs/relay/view-detail?rec_idx={rec_idx}"
    r = requests.get(detail_url, headers=HEADERS, timeout=15)
    r.raise_for_status()

    # script/style 제거 후 텍스트 추출
    html = r.text
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '\n', html)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'\s+\n', '\n', text)
    text = re.sub(r'\n+', '\n', text)
    return text.strip()


def fetch_jd(position: str, url: str, jd_text_override: str = "") -> str:
    """포지션별 JD 가져오기.

    우선순위:
      1. jd_text_override (secrets[position_jd_text][position])가 있으면 그대로 사용
      2. 사람인 URL이면 fetch_saramin_jd
      3. 잡코리아 등 fetch 불가 → 빈 문자열 (인재상만으로 매칭됨)
    """
    if jd_text_override and jd_text_override.strip():
        return jd_text_override.strip()
    if not url:
        return ""
    if "saramin.co.kr" in url:
        return fetch_saramin_jd(url)
    # 잡코리아 등 JS 렌더링 → fetch 불가, 빈 문자열 반환
    return ""


def get_position_jd(position: str) -> str:
    """secrets에서 포지션의 JD를 가져옴 (URL + text override 모두 처리)."""
    url = ""
    text_override = ""
    try:
        import streamlit as st
        url = st.secrets.get("positions", {}).get(position, "")
        text_override = st.secrets.get("position_jd_text", {}).get(position, "")
    except Exception:
        # streamlit 외부 (bulk_analyze 등) — 호출 측에서 직접 전달
        pass
    return fetch_jd(position, url, text_override)


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else \
        "https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=53912363"
    print(fetch_saramin_jd(url))
