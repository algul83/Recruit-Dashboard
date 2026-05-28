"""사람인 채용 공고 URL → JD 본문 추출."""
from __future__ import annotations

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


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else \
        "https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=53912363"
    print(fetch_saramin_jd(url))
