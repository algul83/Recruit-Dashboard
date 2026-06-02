"""PDF / PPTX / HTML / ZIP / 이미지 처리.

- 텍스트 추출: PDF, PPTX, HTML
- Vision 자료 수집: 이미지(.jpg/.png/.webp/.gif), 이미지 기반 PDF, zip 내부 파일
"""
from __future__ import annotations

import io
import re
import zipfile

IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
IMAGE_MIME = {
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.png': 'image/png', '.gif': 'image/gif', '.webp': 'image/webp',
}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB (Anthropic 제한)
MAX_PDF_SIZE = 32 * 1024 * 1024   # 32 MB (Anthropic 제한)


def is_image_filename(name: str) -> bool:
    return name.lower().endswith(IMAGE_EXTS)


def image_media_type(name: str) -> str:
    for ext, mime in IMAGE_MIME.items():
        if name.lower().endswith(ext):
            return mime
    return 'image/png'


def extract_zip(data: bytes) -> list[dict]:
    """zip 풀어서 안의 PDF/이미지/PPTX/HTML 반환 [{name, data, ext}]."""
    out = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                # __MACOSX 등 시스템 파일 제외
                if info.filename.startswith('__MACOSX') or info.filename.startswith('.'):
                    continue
                name_lower = info.filename.lower()
                if name_lower.endswith(('.pdf', '.pptx', '.html', '.htm') + IMAGE_EXTS):
                    if info.file_size > MAX_PDF_SIZE:
                        continue
                    content = zf.read(info.filename)
                    ext = name_lower.split('.')[-1]
                    out.append({'name': info.filename, 'data': content, 'ext': ext})
    except Exception:
        pass
    return out


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
