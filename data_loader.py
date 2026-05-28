"""Google Drive에서 채용 폴더 구조 탐색 및 파일 다운로드."""
from __future__ import annotations

import io
import os
from dataclasses import dataclass, field
from functools import lru_cache

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ['https://www.googleapis.com/auth/drive']


def _drive_client():
    """Streamlit secrets 또는 환경변수에서 SA 자격증명 로드."""
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and 'gcp_service_account' in st.secrets:
            creds = service_account.Credentials.from_service_account_info(
                dict(st.secrets['gcp_service_account']), scopes=SCOPES
            )
            return build('drive', 'v3', credentials=creds)
    except Exception:
        pass
    sa_file = os.environ.get('GOOGLE_SERVICE_ACCOUNT_FILE')
    if not sa_file or not os.path.exists(sa_file):
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_FILE 환경변수 없음")
    creds = service_account.Credentials.from_service_account_file(sa_file, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)


@dataclass
class ApplicantFile:
    id: str
    name: str
    mime_type: str
    size: int = 0


@dataclass
class Applicant:
    id: str          # Drive folder id
    name: str        # 지원자 이름 (폴더명)
    position: str    # 포지션 (상위 폴더명)
    files: list[ApplicantFile] = field(default_factory=list)

    @property
    def resume_file(self) -> ApplicantFile | None:
        """가장 적합한 이력서 파일 추정 — '이력서' 또는 '입사지원서' 포함 PDF."""
        candidates = [f for f in self.files
                      if f.name.endswith('.pdf')
                      and any(kw in f.name for kw in ['이력서', '입사지원서', 'CV', 'cv', 'Resume', 'resume'])]
        if candidates:
            # 가장 작은 파일이 보통 압축된 깔끔한 이력서
            return min(candidates, key=lambda f: f.size or 999999999)
        # fallback: 가장 작은 PDF
        pdfs = [f for f in self.files if f.name.endswith('.pdf')]
        return min(pdfs, key=lambda f: f.size or 999999999) if pdfs else None

    @property
    def portfolio_files(self) -> list[ApplicantFile]:
        """포트폴리오 파일들 — PDF/PPTX 중 이력서 아닌 것."""
        resume = self.resume_file
        return [f for f in self.files
                if f != resume
                and (f.name.endswith('.pdf') or f.name.endswith('.pptx'))]

    @property
    def url_attachments(self) -> list[ApplicantFile]:
        """URL.html 첨부 (지원자가 사람인에 등록한 외부 링크)."""
        return [f for f in self.files if f.name.endswith('.html')]


@lru_cache(maxsize=1)
def list_position_folders(shared_drive_id: str) -> dict[str, str]:
    """공유드라이브 root에서 포지션 폴더 목록 (`_` 로 시작하는 시스템 폴더 제외)."""
    drive = _drive_client()
    r = drive.files().list(
        q=f"'{shared_drive_id}' in parents and trashed=false "
          f"and mimeType='application/vnd.google-apps.folder'",
        fields="files(id,name)",
        corpora='drive', driveId=shared_drive_id,
        includeItemsFromAllDrives=True, supportsAllDrives=True,
        pageSize=100,
    ).execute()
    return {
        f['name']: f['id']
        for f in r.get('files', [])
        if not f['name'].startswith('_')
    }


def list_applicants(position_folder_id: str, position_name: str) -> list[Applicant]:
    """포지션 폴더 안 지원자 목록 + 각 지원자의 파일 목록.

    최적화: 지원자별 파일을 N번 API 호출 대신, parents OR query로 청크당 1회 호출.
    50명이면 N+1번 → 2~3번 호출로 단축 (약 25초 → 1~2초).
    """
    drive = _drive_client()

    # 1. 지원자 폴더 목록
    applicants: list[Applicant] = []
    page_token = None
    while True:
        r = drive.files().list(
            q=f"'{position_folder_id}' in parents and trashed=false "
              f"and mimeType='application/vnd.google-apps.folder'",
            fields="nextPageToken, files(id,name)",
            includeItemsFromAllDrives=True, supportsAllDrives=True,
            pageSize=200, pageToken=page_token,
        ).execute()
        for f in r.get('files', []):
            applicants.append(Applicant(id=f['id'], name=f['name'], position=position_name))
        page_token = r.get('nextPageToken')
        if not page_token:
            break

    if not applicants:
        return applicants

    # 2. 각 지원자 파일을 ThreadPoolExecutor로 병렬 호출
    # httplib2 transport는 thread-safe 아님 → 각 worker가 자기 client 사용
    from concurrent.futures import ThreadPoolExecutor

    def _fetch_one(app: Applicant):
        local_drive = _drive_client()
        app.files = _list_files(local_drive, app.id)
        return app

    with ThreadPoolExecutor(max_workers=10) as ex:
        applicants = list(ex.map(_fetch_one, applicants))
    return applicants


def _list_files(drive, folder_id: str) -> list[ApplicantFile]:
    """단일 폴더 파일 list (개별 조회용, list_applicants에서는 사용 안 함)."""
    r = drive.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields="files(id,name,mimeType,size)",
        includeItemsFromAllDrives=True, supportsAllDrives=True,
        pageSize=100,
    ).execute()
    return [ApplicantFile(
        id=f['id'], name=f['name'],
        mime_type=f['mimeType'], size=int(f.get('size', 0)),
    ) for f in r.get('files', [])]


def download_file(file_id: str) -> bytes:
    """파일 바이너리 다운로드."""
    drive = _drive_client()
    request = drive.files().get_media(fileId=file_id, supportsAllDrives=True)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()


def upload_or_update_file(
    folder_id: str, filename: str, content: bytes, mime_type: str = 'application/json',
) -> str:
    """폴더에 같은 이름 파일 있으면 update, 없으면 create."""
    from googleapiclient.http import MediaIoBaseUpload
    drive = _drive_client()
    r = drive.files().list(
        q=f"'{folder_id}' in parents and name='{filename}' and trashed=false",
        fields="files(id)",
        includeItemsFromAllDrives=True, supportsAllDrives=True,
    ).execute()
    media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type, resumable=False)
    existing = r.get('files', [])
    if existing:
        fid = existing[0]['id']
        drive.files().update(
            fileId=fid, media_body=media, supportsAllDrives=True,
        ).execute()
        return fid
    new = drive.files().create(
        body={'name': filename, 'parents': [folder_id], 'mimeType': mime_type},
        media_body=media, fields='id', supportsAllDrives=True,
    ).execute()
    return new['id']
