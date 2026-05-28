"""포지션 1개에 대해 미분석 지원자 모두 분석."""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# 환경변수 로드 (.streamlit/secrets.toml 에서)
def _load_secrets():
    import tomllib
    p = Path(__file__).parent / '.streamlit' / 'secrets.toml'
    if not p.exists():
        return {}
    with open(p, 'rb') as f:
        return tomllib.load(f)

secrets = _load_secrets()
os.environ.setdefault('ANTHROPIC_API_KEY', secrets.get('ANTHROPIC_API_KEY', ''))
os.environ.setdefault('GOOGLE_SERVICE_ACCOUNT_FILE', '/Users/will/claude/projects/Data Analytics/service-account.json')

import analyzer
import cache_store
import data_loader
import extractors
import jd_fetcher


def analyze_one(applicant, jd_text: str) -> dict:
    documents = {}
    for f in applicant.files:
        if f.name.endswith(('.pdf', '.pptx', '.html')):
            try:
                data = data_loader.download_file(f.id)
                text = extractors.extract_any(f.name, data)
                if text and not text.startswith('['):
                    documents[f.name] = text
            except Exception as e:
                print(f"  [warn] {f.name}: {e}")
    if not documents:
        return {'error': '추출 가능한 문서 없음', '_analyzed_at': datetime.now().isoformat(timespec='seconds')}
    result = analyzer.analyze_applicant(jd_text, applicant.name, documents)
    result['_analyzed_at'] = datetime.now().isoformat(timespec='seconds')
    return result


def main(position_name: str = 'AI연구원'):
    shared_drive = secrets.get('DRIVE_RECRUIT_ID', '0ADZEJI4H5G9QUk9PVA')
    pos_url = secrets.get('positions', {}).get(position_name)
    if not pos_url:
        print(f"[error] {position_name} JD URL이 secrets에 없음")
        return

    print(f"[1/4] JD 가져오기...")
    jd = jd_fetcher.fetch_saramin_jd(pos_url)
    print(f"  JD: {len(jd)}자")

    print(f"[2/4] 지원자 로드...")
    positions = data_loader.list_position_folders(shared_drive)
    if position_name not in positions:
        print(f"[error] '{position_name}' 폴더 없음")
        return
    applicants = data_loader.list_applicants(positions[position_name], position_name)
    print(f"  지원자 {len(applicants)}명")

    print(f"[3/4] 기존 분석 결과 로드...")
    analyses = cache_store.load_analyses(shared_drive)
    print(f"  기존 분석 {len(analyses)}명")

    pending = [a for a in applicants if a.id not in analyses]
    print(f"  미분석 {len(pending)}명")
    if not pending:
        print("모두 분석 완료. 종료.")
        return

    print(f"[4/4] {len(pending)}명 분석 시작...")
    t0 = time.time()
    success = 0
    fail = 0
    total_in_tok = 0
    total_out_tok = 0

    for i, app in enumerate(pending, 1):
        try:
            result = analyze_one(app, jd)
            analyses[app.id] = result
            if 'error' not in result:
                success += 1
                tk = result.get('_tokens', {})
                total_in_tok += tk.get('input', 0)
                total_out_tok += tk.get('output', 0)
                score = result.get('매칭도', {}).get('점수', '-')
                print(f"  [{i:>2}/{len(pending)}] ✓ {app.name} (매칭도 {score}점)")
            else:
                fail += 1
                print(f"  [{i:>2}/{len(pending)}] ✗ {app.name}: {result['error']}")
        except Exception as e:
            fail += 1
            analyses[app.id] = {'error': str(e), '_analyzed_at': datetime.now().isoformat()}
            print(f"  [{i:>2}/{len(pending)}] ✗ {app.name}: {e}")

        # 매번 저장 (중간 중단 대비)
        cache_store.save_analyses(shared_drive, analyses)

    elapsed = time.time() - t0
    # 비용 계산 (claude-haiku-4-5: $0.80/1M input, $4/1M output)
    cost = (total_in_tok * 0.80 + total_out_tok * 4.0) / 1_000_000

    print()
    print(f"=== 완료 ===")
    print(f"  성공: {success}, 실패: {fail}, 소요: {elapsed/60:.1f}분")
    print(f"  토큰: input {total_in_tok:,} / output {total_out_tok:,}")
    print(f"  비용: 약 ${cost:.3f}")


if __name__ == "__main__":
    pos = sys.argv[1] if len(sys.argv) > 1 else 'AI연구원'
    main(pos)
