"""분석 결과 및 진행 상태를 Drive에 JSON으로 캐시."""
from __future__ import annotations

import json
from typing import Any

import data_loader

# 채용 root에 dashboard_data 하위 폴더를 만들고 그 안에 두 파일 저장
DATA_FOLDER_NAME = "_dashboard_data"
ANALYSES_FILENAME = "analyses.json"
STATUSES_FILENAME = "statuses.json"
PROFILES_FILENAME = "ideal_profiles.json"  # 인재상 (공통 + 포지션별)


def _ensure_data_folder(shared_drive_id: str) -> str:
    """채용 root에 _dashboard_data 폴더 보장."""
    drive = data_loader._drive_client()
    r = drive.files().list(
        q=(
            f"'{shared_drive_id}' in parents and trashed=false "
            f"and name='{DATA_FOLDER_NAME}' "
            f"and mimeType='application/vnd.google-apps.folder'"
        ),
        fields="files(id,name)",
        corpora='drive', driveId=shared_drive_id,
        includeItemsFromAllDrives=True, supportsAllDrives=True,
    ).execute()
    existing = r.get('files', [])
    if existing:
        return existing[0]['id']
    new = drive.files().create(
        body={
            'name': DATA_FOLDER_NAME, 'parents': [shared_drive_id],
            'mimeType': 'application/vnd.google-apps.folder',
        },
        fields='id', supportsAllDrives=True,
    ).execute()
    return new['id']


def _read_json(folder_id: str, filename: str) -> dict[str, Any]:
    drive = data_loader._drive_client()
    r = drive.files().list(
        q=f"'{folder_id}' in parents and name='{filename}' and trashed=false",
        fields="files(id)",
        includeItemsFromAllDrives=True, supportsAllDrives=True,
    ).execute()
    files = r.get('files', [])
    if not files:
        return {}
    data = data_loader.download_file(files[0]['id'])
    try:
        return json.loads(data.decode('utf-8'))
    except Exception:
        return {}


def _write_json(folder_id: str, filename: str, payload: dict[str, Any]) -> str:
    content = json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')
    return data_loader.upload_or_update_file(folder_id, filename, content, 'application/json')


def load_analyses(shared_drive_id: str) -> dict[str, dict]:
    """{applicant_folder_id: analysis_dict} 형태로 반환."""
    folder_id = _ensure_data_folder(shared_drive_id)
    return _read_json(folder_id, ANALYSES_FILENAME)


def save_analyses(shared_drive_id: str, analyses: dict[str, dict]):
    folder_id = _ensure_data_folder(shared_drive_id)
    _write_json(folder_id, ANALYSES_FILENAME, analyses)


def load_statuses(shared_drive_id: str) -> dict[str, dict]:
    """{applicant_folder_id: {status: ..., notes: ..., updated_at: ...}}."""
    folder_id = _ensure_data_folder(shared_drive_id)
    return _read_json(folder_id, STATUSES_FILENAME)


def save_statuses(shared_drive_id: str, statuses: dict[str, dict]):
    folder_id = _ensure_data_folder(shared_drive_id)
    _write_json(folder_id, STATUSES_FILENAME, statuses)


def load_profiles(shared_drive_id: str) -> dict[str, str]:
    """{position_name: ideal_profile_text, '_common': 공통 인재상}."""
    folder_id = _ensure_data_folder(shared_drive_id)
    return _read_json(folder_id, PROFILES_FILENAME)


def save_profiles(shared_drive_id: str, profiles: dict[str, str]):
    folder_id = _ensure_data_folder(shared_drive_id)
    _write_json(folder_id, PROFILES_FILENAME, profiles)


def merged_profile_for(position: str, profiles: dict[str, str]) -> str:
    """공통 + 포지션별 인재상을 합쳐 반환."""
    common = (profiles.get('_common') or '').strip()
    specific = (profiles.get(position) or '').strip()
    parts = []
    if common:
        parts.append(f"[공통 인재상]\n{common}")
    if specific:
        parts.append(f"[{position} 포지션 인재상]\n{specific}")
    return "\n\n".join(parts)
