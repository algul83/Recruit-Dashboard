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
HIRED_FOLDER_NAME = "_hired_examples"  # 합격자 자료 (학습용)


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


def _ensure_hired_position_folder(shared_drive_id: str, position: str) -> str:
    """_hired_examples/{position}/ 폴더 보장 (없으면 생성). 폴더 ID 반환."""
    drive = data_loader._drive_client()
    # _hired_examples
    r = drive.files().list(
        q=f"'{shared_drive_id}' in parents and name='{HIRED_FOLDER_NAME}' "
          f"and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id)",
        corpora='drive', driveId=shared_drive_id,
        includeItemsFromAllDrives=True, supportsAllDrives=True,
    ).execute()
    if r.get('files'):
        hired_root = r['files'][0]['id']
    else:
        hired_root = drive.files().create(
            body={
                'name': HIRED_FOLDER_NAME, 'parents': [shared_drive_id],
                'mimeType': 'application/vnd.google-apps.folder',
            },
            fields='id', supportsAllDrives=True,
        ).execute()['id']
    # {position}
    r = drive.files().list(
        q=f"'{hired_root}' in parents and name='{position}' "
          f"and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id)",
        includeItemsFromAllDrives=True, supportsAllDrives=True,
    ).execute()
    if r.get('files'):
        return r['files'][0]['id']
    return drive.files().create(
        body={
            'name': position, 'parents': [hired_root],
            'mimeType': 'application/vnd.google-apps.folder',
        },
        fields='id', supportsAllDrives=True,
    ).execute()['id']


def close_position(
    shared_drive_id: str, position_name: str, position_folder_id: str,
) -> dict:
    """포지션 채용 종료 처리.

    1. 최종합격자 폴더/파일을 _hired_examples/{position}/ 로 복사 (학습용 보존)
    2. 포지션 폴더명에 `_` prefix 추가 → list_position_folders가 자동 제외 → UI에서 사라짐
    3. secrets.toml의 [positions] URL 제거는 GitHub Secret 수동 갱신 필요 (반환값에 안내)

    Returns: {hired: [{name, copied_files}], renamed: '_{position}', warning: '...'}
    """
    drive = data_loader._drive_client()
    statuses = load_statuses(shared_drive_id)
    applicants = data_loader.list_applicants(position_folder_id, position_name)

    # 1) 최종합격자 식별
    hired_apps = [
        a for a in applicants
        if statuses.get(a.id, {}).get('status') == '최종합격'
    ]

    # 2) _hired_examples/{position}/ 준비
    hired_pos_folder = _ensure_hired_position_folder(shared_drive_id, position_name)

    # 3) 합격자별 폴더 만들고 파일 복사
    copied_summary = []
    for app in hired_apps:
        # 동명이인 폴더 있으면 skip (중복 복사 방지)
        existing = drive.files().list(
            q=f"'{hired_pos_folder}' in parents and name='{app.name}' "
              f"and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id)",
            includeItemsFromAllDrives=True, supportsAllDrives=True,
        ).execute()
        if existing.get('files'):
            copied_summary.append({'name': app.name, 'copied_files': [], 'note': '이미 존재 (건너뜀)'})
            continue
        new_folder = drive.files().create(
            body={
                'name': app.name, 'parents': [hired_pos_folder],
                'mimeType': 'application/vnd.google-apps.folder',
            },
            fields='id', supportsAllDrives=True,
        ).execute()
        copied_files = []
        for f in app.files:
            drive.files().copy(
                fileId=f.id,
                body={'name': f.name, 'parents': [new_folder['id']]},
                supportsAllDrives=True,
            ).execute()
            copied_files.append(f.name)
        copied_summary.append({'name': app.name, 'copied_files': copied_files})

    # 4) 포지션 폴더명에 `_` prefix 추가 (이미 있으면 skip)
    new_name = position_name if position_name.startswith('_') else f"_{position_name}"
    if new_name != position_name:
        drive.files().update(
            fileId=position_folder_id,
            body={'name': new_name},
            supportsAllDrives=True,
        ).execute()

    return {
        'hired': copied_summary,
        'renamed': new_name,
        'warning': (
            f"secrets.toml의 [positions]에서 '{position_name}' 줄을 제거하고 "
            f"GitHub Secret도 동일하게 갱신해주세요. "
            f"(JD 텍스트는 [position_jd_text]에 보존하셔도 됩니다.)"
        ),
    }


def list_hired_examples(shared_drive_id: str, position: str) -> list[dict]:
    """_hired_examples/{position}/ 안의 합격자 폴더 목록 + 각 폴더의 파일 list 반환.

    Returns: [{id, name, files: [{id, name, mime_type}]}]
    """
    drive = data_loader._drive_client()
    # _hired_examples 폴더 찾기
    r = drive.files().list(
        q=f"'{shared_drive_id}' in parents and name='{HIRED_FOLDER_NAME}' "
          f"and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id,name)",
        corpora='drive', driveId=shared_drive_id,
        includeItemsFromAllDrives=True, supportsAllDrives=True,
    ).execute()
    if not r.get('files'):
        return []
    hired_root = r['files'][0]['id']
    # 포지션 폴더 찾기
    r = drive.files().list(
        q=f"'{hired_root}' in parents and name='{position}' "
          f"and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id,name)",
        includeItemsFromAllDrives=True, supportsAllDrives=True,
    ).execute()
    if not r.get('files'):
        return []
    pos_folder = r['files'][0]['id']
    # 합격자 폴더 목록
    r = drive.files().list(
        q=f"'{pos_folder}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id,name)",
        includeItemsFromAllDrives=True, supportsAllDrives=True,
        pageSize=50,
    ).execute()
    hired = []
    for f in r.get('files', []):
        files_r = drive.files().list(
            q=f"'{f['id']}' in parents and trashed=false",
            fields="files(id,name,mimeType,size)",
            includeItemsFromAllDrives=True, supportsAllDrives=True,
        ).execute()
        hired.append({
            'id': f['id'], 'name': f['name'],
            'files': files_r.get('files', []),
        })
    return hired
