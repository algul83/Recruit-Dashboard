"""PDF / PPTX / HTML에서 텍스트 추출."""
from __future__ import annotations

import io
import re


def extract_pdf(data: bytes) -> str:
    """PDF 바이너리 → 텍스트."""
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages).strip()
    except Exception as e:
        return f"[PDF 추출 실패: {e}]"


def extract_pptx(data: bytes) -> str:
    """PPTX 바이너리 → 슬라이드별 텍스트."""
    from pptx import Presentation
    try:
        prs = Presentation(io.BytesIO(data))
        slides_text = []
        for i, slide in enumerate(prs.slides, 1):
            parts = []
            for shape in slide.shapes:
                if hasattr(shape, 'text') and shape.text:
                    parts.append(shape.text)
            if parts:
                slides_text.append(f"[Slide {i}]\n" + "\n".join(parts))
        return "\n\n".join(slides_text)
    except Exception as e:
        return f"[PPTX 추출 실패: {e}]"


def extract_html(data: bytes) -> str:
    """HTML 바이너리 → 텍스트 (사람인 URL.html 등)."""
    from bs4 import BeautifulSoup
    try:
        html = data.decode('utf-8', errors='replace')
        soup = BeautifulSoup(html, 'html.parser')
        for s in soup(['script', 'style']):
            s.decompose()
        text = soup.get_text(separator='\n')
        # URL 추출 (사람인 첨부 URL이 보통 안에 있음)
        urls = list(set(re.findall(r'https?://[^\s"\'<>]+', html)))
        result = re.sub(r'\n\s*\n', '\n', text).strip()
        if urls:
            result += "\n\n[추출된 URL]\n" + "\n".join(urls)
        return result
    except Exception as e:
        return f"[HTML 추출 실패: {e}]"


def extract_any(filename: str, data: bytes) -> str:
    """파일명 확장자로 적절한 추출기 선택."""
    fname = filename.lower()
    if fname.endswith('.pdf'):
        return extract_pdf(data)
    if fname.endswith('.pptx'):
        return extract_pptx(data)
    if fname.endswith('.html') or fname.endswith('.htm'):
        return extract_html(data)
    return f"[지원 안 되는 형식: {filename}]"
