"""ConnectDI Recruit Dashboard — AI 기반 채용 이력서 분석 도구."""
from __future__ import annotations

import hashlib
import os
from datetime import datetime

import pandas as pd
import streamlit as st

import analyzer
import cache_store
import data_loader
import extractors
import jd_fetcher
import slack_notify

# ============== 색상 팔레트 (ConnectDI Keyword Dashboard와 동일) ==============
PRIMARY = "#5B43C9"
PRIMARY_DARK = "#4A35B0"
PRIMARY_LIGHT = "#F1EEFB"
ACCENT = "#10B981"
WARN = "#F59E0B"
DANGER = "#E84C3D"

st.set_page_config(
    page_title="ConnectDI Recruit",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    f"""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

    html, body, *, [class*="css"], button, input, select, textarea {{
        font-family: 'Pretendard', 'Malgun Gothic', '맑은 고딕', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }}

    .stApp {{ background: white; padding-top: 64px; padding-bottom: 0 !important; }}
    [data-testid="stAppViewContainer"] {{ background: white !important; }}
    body, html {{ background: white !important; }}

    /* Streamlit Cloud의 default toolbar/header 숨김 — 우리 보라 헤더가 보이도록 */
    [data-testid="stHeader"],
    header[data-testid="stHeader"],
    div[data-testid="stToolbar"] {{
        display: none !important;
        height: 0 !important;
        visibility: hidden !important;
    }}

    section[data-testid="stSidebar"] {{ top: 64px !important; }}

    /* 사이드바 collapse 후 다시 여는 버튼 — 헤더 아래 */
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapseButton"],
    button[kind="headerNoPadding"] {{
        position: fixed !important;
        top: 72px !important;
        left: 12px !important;
        z-index: 9999 !important;
        background: white !important;
        border: 1px solid #EDECF1 !important;
        border-radius: 8px !important;
        box-shadow: 0 2px 6px rgba(91, 67, 201, 0.12) !important;
        padding: 6px !important;
    }}
    [data-testid="stSidebarCollapsedControl"] svg,
    [data-testid="collapsedControl"] svg,
    [data-testid="stSidebarCollapseButton"] svg {{
        color: {PRIMARY} !important; fill: {PRIMARY} !important;
    }}

    /* 상단 진보라 헤더 — 전체 너비 fixed + 브라우저 호환 fallback */
    .top-header {{
        background-color: {PRIMARY}; /* fallback */
        background: -webkit-linear-gradient(left, {PRIMARY} 0%, {PRIMARY_DARK} 100%);
        background: linear-gradient(90deg, {PRIMARY} 0%, {PRIMARY_DARK} 100%);
        padding: 0 32px;
        display: -webkit-flex;
        display: flex; align-items: center; gap: 20px;
        color: white !important;
        position: fixed;
        top: 0; left: 0;
        width: 100vw;
        height: 64px;
        z-index: 999999;
        box-shadow: 0 1px 4px rgba(91, 67, 201, 0.15);
    }}
    .top-header * {{ color: white !important; }}
    .top-logo {{
        color: white; font-size: 1.2rem; font-weight: 800;
        display: flex; align-items: center; gap: 8px;
    }}
    .top-tag {{
        background: rgba(255,255,255,0.2); color: white;
        padding: 4px 10px; border-radius: 4px;
        font-size: 0.7rem; font-weight: 500;
    }}

    /* 메인 영역 */
    section[data-testid="stMain"] {{
        background: white !important;
        position: relative;
    }}
    [data-testid="stMainBlockContainer"] {{
        max-width: 100% !important; width: 100% !important;
        padding-left: 24px !important; padding-right: 24px !important;
        padding-top: 32px !important;
    }}

    /* 사이드바 (브라우저 호환 fallback) */
    section[data-testid="stSidebar"],
    section[data-testid="stSidebar"] > div {{
        background-color: #FFFFFF !important;
        background: #FFFFFF !important;
        border-right: 1px solid #EDECF1 !important;
    }}

    /* st.container(border=True) 카드 — 박스 시각 완전 제거 (텍스트만 흐름) */
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        background: transparent !important;
        border: 0 !important;
        border-radius: 0 !important;
        padding: 6px 0 !important;
        margin-bottom: 18px !important;
        box-shadow: none !important;
    }}

    /* stColumn 박스 시각 완전 제거 (자식 wrapper 포함) */
    div[data-testid="stColumn"],
    .stColumn,
    div[data-testid="stColumn"] > div,
    div[data-testid="stColumn"] > div > div:not([data-testid="stVerticalBlockBorderWrapper"]) {{
        background: none !important;
        background-color: transparent !important;
        background-image: none !important;
        border: 0 !important;
        border-color: transparent !important;
        box-shadow: none !important;
        outline: 0 !important;
    }}
    /* baseweb 위젯 wrapper 박스도 제거 */
    [data-baseweb="select"] > div,
    [data-baseweb="input"] > div,
    [data-testid="stSelectbox"] > div,
    [data-testid="stTextArea"] > div {{
        background: transparent !important;
        box-shadow: none !important;
    }}

    /* KPI */
    .kpi-box {{
        background: white; padding: 18px 22px;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(91, 67, 201, 0.06);
        height: 100%;
    }}
    .kpi-label {{ font-size: 0.78rem; color: #8B8A95; font-weight: 500; }}
    .kpi-value {{ font-size: 1.7rem; font-weight: 800; color: {PRIMARY}; margin-top: 6px; line-height: 1; }}

    /* 점수 표시 */
    .score-badge {{
        display: inline-block; padding: 6px 16px;
        border-radius: 999px; font-weight: 800; font-size: 1.1rem;
        color: white;
    }}
    .score-high {{ background: {ACCENT}; }}
    .score-mid {{ background: {WARN}; }}
    .score-low {{ background: {DANGER}; }}

    /* 상태 뱃지 */
    .status-badge {{
        display: inline-block; padding: 3px 10px;
        border-radius: 6px; font-size: 0.78rem; font-weight: 600;
    }}

    /* primary 버튼 (ConnectDI Keyword 스타일) */
    button[kind="primary"],
    button[data-testid="baseButton-primary"] {{
        background: {PRIMARY} !important; color: white !important;
        border: none !important; border-radius: 8px !important;
        font-size: 0.95rem !important; font-weight: 700 !important;
        padding: 10px 20px !important; white-space: nowrap !important;
        min-width: 80px !important;
        box-shadow: 0 2px 6px rgba(91, 67, 201, 0.25);
        transition: background 0.15s;
    }}
    button[kind="primary"]:hover {{
        background: {PRIMARY_DARK} !important;
        box-shadow: 0 4px 10px rgba(91, 67, 201, 0.35);
    }}

    /* secondary 버튼 (← 목록으로 등) — 명확한 시각 */
    button[kind="secondary"],
    button[data-testid="baseButton-secondary"] {{
        background: white !important;
        color: {PRIMARY} !important;
        border: 1px solid {PRIMARY} !important;
        border-radius: 8px !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
        padding: 6px 14px !important;
    }}
    button[kind="secondary"]:hover {{
        background: {PRIMARY_LIGHT} !important;
    }}

    /* 사이드바 라디오 메뉴 — 평평한 텍스트 (선택 시 색깔만) */
    section[data-testid="stSidebar"] div[role="radiogroup"] {{
        flex-direction: column !important; gap: 4px !important;
        background: transparent !important; padding: 0 !important;
        border-radius: 0 !important; display: flex !important;
        width: 100% !important;
    }}
    section[data-testid="stSidebar"] div[role="radiogroup"] > label {{
        background: transparent !important; border: 0 !important;
        padding: 10px 14px !important; border-radius: 0 !important;
        color: #6B6A73 !important; font-size: 0.92rem !important;
        width: 100%; box-shadow: none !important;
    }}
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {{
        background: transparent !important;
        color: {PRIMARY} !important; font-weight: 700 !important;
        box-shadow: none !important;
    }}

    /* 텍스트 입력 박스 — underline + 최소 클릭 영역 (Safari 호환) */
    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea {{
        background: white !important;
        border: 0 !important;
        border-bottom: 2px solid #D5D3DE !important;
        border-radius: 0 !important;
        box-shadow: none !important;
        min-height: 38px !important;
        padding: 8px 12px !important;
        color: #1E1B2E !important;
        cursor: text !important;
    }}
    [data-testid="stTextInput"] input:focus,
    [data-testid="stTextArea"] textarea:focus {{
        border-bottom-color: {PRIMARY} !important;
        outline: none !important;
    }}
    [data-baseweb="input"], [data-baseweb="select"], [data-baseweb="base-input"] {{
        background: transparent !important;
        border: 0 !important;
        box-shadow: none !important;
    }}

    h1, h2, h3, h4, h5, h6 {{ color: #1E1B2E; }}

    /* Streamlit이 markdown 헤더에 자동 추가하는 anchor 링크 완전 제거 (hover 포함) */
    h1 a, h2 a, h3 a, h4 a, h5 a, h6 a,
    h1 > a, h2 > a, h3 > a, h4 > a, h5 > a, h6 > a,
    [data-testid="stMarkdown"] h1 a,
    [data-testid="stMarkdown"] h2 a,
    [data-testid="stMarkdown"] h3 a,
    [data-testid="stMarkdown"] h4 a,
    [data-testid="stMarkdown"] h5 a,
    [data-testid="stMarkdown"] h6 a,
    [data-testid="stMarkdown"] a[class*="anchor"],
    [data-testid="stHeading"] a,
    [data-testid="stHeading"] a[href^="#"],
    a[class*="anchor-link"],
    a[href^="#"][class*="header"] {{
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }}
    h1:hover a, h2:hover a, h3:hover a, h4:hover a, h5:hover a, h6:hover a {{
        display: none !important;
        visibility: hidden !important;
    }}

    /* 최종 nuclear: stMain 안 모든 div 박스 시각 제거 (의도된 카드는 화이트리스트로 보호) */
    section[data-testid="stMain"] div:not([data-testid="stVerticalBlockBorderWrapper"]):not(.kpi-box):not(.score-badge):not(.status-badge):not(.top-header):not(.top-logo):not(.top-tag) {{
        background-color: transparent !important;
        background-image: none !important;
        box-shadow: none !important;
        border: 0 !important;
        outline: 0 !important;
    }}
    /* pseudo-element도 박스 시각 제거 */
    section[data-testid="stMain"] div::before,
    section[data-testid="stMain"] div::after {{
        box-shadow: none !important;
        background: transparent !important;
        border: 0 !important;
    }}
    /* 단, stMain 자체의 ::before는 흰색 배경 유지 (회색 영역 방지) */
    section[data-testid="stMain"]::before {{
        background: white !important;
    }}

    /* nuclear: 박스 시각 완전 제거 (stColumn 자식 + baseweb wrapper + stHorizontalBlock 자식) */
    section[data-testid="stMain"] [data-testid="stColumn"],
    section[data-testid="stMain"] [data-testid="stColumn"] > div,
    section[data-testid="stMain"] [data-testid="stColumn"] > div > div:not([data-testid="stVerticalBlockBorderWrapper"]),
    section[data-testid="stMain"] [data-testid="stHorizontalBlock"],
    section[data-testid="stMain"] [data-testid="stHorizontalBlock"] > div,
    [data-baseweb="select"],
    [data-baseweb="select"] > div,
    [data-baseweb="select"] > div > div,
    [data-baseweb="input"],
    [data-baseweb="input"] > div,
    [data-baseweb="base-input"],
    [data-testid="stSelectbox"],
    [data-testid="stSelectbox"] > div,
    [data-testid="stSelectbox"] > div > div,
    [data-testid="stTextInput"],
    [data-testid="stTextArea"],
    [data-testid="stTextArea"] > div,
    [data-testid="stToggle"],
    [data-testid="stToggle"] > div {{
        background: transparent !important;
        background-color: transparent !important;
        background-image: none !important;
        border: 0 !important;
        border-color: transparent !important;
        box-shadow: none !important;
        outline: 0 !important;
    }}
    /* st.container(border=True)도 박스 시각 X (텍스트만) */
    [data-testid="stVerticalBlockBorderWrapper"] {{
        background: transparent !important;
        box-shadow: none !important;
        border: 0 !important;
    }}
    /* select dropdown 옵션 패널 텍스트 input은 시각 유지 (조작 가능하게) */
    [data-baseweb="select"] input,
    [data-baseweb="select"] [role="listbox"] {{
        background: white !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ============== 공통 ==============
STATUS_OPTIONS = ["미검토", "서류통과", "1차면접통과", "2차면접통과",
                  "최종합격", "탈락", "보류"]

STATUS_COLORS = {
    "미검토": "#9CA3AF",
    "서류통과": "#3B82F6",
    "1차면접통과": "#8B5CF6",
    "2차면접통과": "#7C3AED",
    "최종합격": "#10B981",
    "탈락": "#EF4444",
    "보류": "#F59E0B",
}

# 포지션별 채용 프로세스 정의
SLACK_CHANNEL = "#원스글로벌_채용"

PROCESS_FLOW = {
    "개발자": {
        "서류검토자": "Furi",
        "1차면접관": "Furi",
        "2차면접관": "Furi · Y · Lina",
        "1차면접_연락": "Owen",
        "2차면접_연락": "Owen",
        "최종연락_연봉협상": "Lina",
    },
    "AI연구원": {
        "서류검토자": "Y · Ryan · Eden",
        "1차면접관": "Y · Ryan · Eden",
        "2차면접관": "Furi · Y · Lina",
        "1차면접_연락": "Owen",
        "2차면접_연락": "Owen",
        "최종연락_연봉협상": "Lina",
    },
    "Project Leader": {
        "서류검토자": "Lina",
        "1차면접관": "Lina",
        "2차면접관": "Furi · Y · Lina",
        "1차면접_연락": "Owen",
        "2차면접_연락": "Owen",
        "최종연락_연봉협상": "Lina",
    },
}


def _next_status_choices(status: str) -> list[tuple[str, str, str]]:
    """현재 status별로 가능한 다음 status 버튼 (label, new_status, button_type)."""
    forward = {
        "미검토": ("✅ 서류 통과", "서류통과"),
        "서류통과": ("✅ 1차면접 통과", "1차면접통과"),
        "1차면접통과": ("✅ 2차면접 통과", "2차면접통과"),
        "2차면접통과": ("✅ 최종합격", "최종합격"),
    }
    choices = []
    if status in forward:
        l, n = forward[status]
        choices.append((l, n, "secondary"))
        choices.append(("❌ 탈락", "탈락", "secondary"))
        choices.append(("⏸️ 보류", "보류", "secondary"))
    return choices


def _advance_status(applicant: dict, new_status: str,
                    status_data: dict, all_statuses: dict, analysis: dict):
    """status 변경 + 메모 자동 기록 + Slack 자동 알림."""
    prev_status = status_data.get('status', '미검토')
    now = datetime.now().isoformat(timespec='minutes')
    auto_note = f"[{now}] {prev_status} → {new_status}"
    prev_notes = status_data.get('notes', '').strip()
    new_notes = f"{prev_notes}\n{auto_note}" if prev_notes else auto_note

    all_statuses[applicant['id']] = {
        'status': new_status,
        'notes': new_notes,
        'updated_at': datetime.now().isoformat(timespec='seconds'),
    }
    cache_store.save_statuses(get_shared_drive_id(), all_statuses)
    load_cached_statuses.clear()

    # Slack 알림
    next_act = next_action_for(applicant['position'], new_status)
    score = analysis.get('매칭도', {}).get('점수') if analysis else None
    if next_act and next_act['owner'] != '—':
        owner_first = next_act['owner'].split(' · ')[0]
        action_text = next_act['action']
        result = slack_notify.notify_status_change(
            applicant_name=applicant['name'],
            position=applicant['position'],
            prev_status=prev_status,
            new_status=new_status,
            matching_score=score,
            owner_name=owner_first,
            action_text=action_text,
        )
        if result.get('ok'):
            st.toast(f"✅ '{new_status}' + Slack 알림 전송 완료", icon="📣")
        else:
            st.toast(f"⚠️ status 변경됨. Slack 실패: {result.get('error')}", icon="⚠️")
    else:
        st.toast(f"✅ '{new_status}' 변경 완료", icon="✅")


def next_action_for(position: str, status: str) -> dict | None:
    """현재 status에 따른 다음 액션 안내. None이면 종료/대기 상태."""
    flow = PROCESS_FLOW.get(position)
    if not flow:
        return None
    # "·" → ", " 변환 + 존칭 제거
    reviewers = flow['서류검토자'].replace(' · ', ', ')
    first_interviewers = flow['1차면접관'].replace(' · ', ', ')
    second_interviewers = flow['2차면접관'].replace(' · ', ', ')
    mapping = {
        "미검토": {
            "label": "1️⃣ 서류 검토",
            "owner": flow["서류검토자"],
            "action": f"이력서, 포트폴리오, 자기소개서를 검토해주세요.",
            "next_status": "서류통과 / 탈락",
        },
        "서류통과": {
            "label": "2️⃣ 1차면접 일정 안내",
            "owner": flow["1차면접_연락"],
            "action": f"지원자에게 연락하여 1차면접 일정을 조율해주세요. 1차면접은 {first_interviewers}이 진행합니다.",
            "next_status": "1차면접통과 / 탈락",
        },
        "1차면접통과": {
            "label": "3️⃣ 2차면접 일정 안내",
            "owner": flow["2차면접_연락"],
            "action": f"지원자에게 연락하여 2차면접 일정을 조율해주세요. 2차면접은 {second_interviewers}이 참여하여 최종 의사결정합니다.",
            "next_status": "2차면접통과 / 탈락",
        },
        "2차면접통과": {
            "label": "4️⃣ 최종합격 · 연봉협상",
            "owner": flow["최종연락_연봉협상"],
            "action": f"지원자에게 연락하여 연봉협상 등을 진행해주세요.",
            "next_status": "최종합격",
        },
        "최종합격": {
            "label": "✅ 채용 완료",
            "owner": "—",
            "action": "최종합격으로 채용 프로세스가 완료되었습니다.",
            "next_status": "—",
        },
        "탈락": {
            "label": "❌ 종료",
            "owner": "—",
            "action": "탈락으로 채용 프로세스가 종료되었습니다.",
            "next_status": "—",
        },
        "보류": {
            "label": "⏸️ 검토 보류",
            "owner": "—",
            "action": "현재 보류 상태입니다. 검토 재개 시 다음 단계로 진행하세요.",
            "next_status": "—",
        },
    }
    return mapping.get(status)


def get_shared_drive_id() -> str:
    try:
        return st.secrets.get("DRIVE_RECRUIT_ID", "0ADZEJI4H5G9QUk9PVA")
    except Exception:
        return os.environ.get("DRIVE_RECRUIT_ID", "0ADZEJI4H5G9QUk9PVA")


def get_position_url(position: str) -> str | None:
    try:
        return st.secrets.get("positions", {}).get(position)
    except Exception:
        return None


def score_class(score: int) -> str:
    if score >= 80: return "score-high"
    if score >= 60: return "score-mid"
    return "score-low"


# ============== 인증 ==============
def _auth_token() -> str:
    try:
        app_pw = st.secrets.get("app_password", "")
    except Exception:
        app_pw = os.environ.get("APP_PASSWORD", "")
    return hashlib.sha256(app_pw.encode()).hexdigest()[:16] if app_pw else ""


def check_password() -> bool:
    if st.session_state.get('authenticated'):
        return True

    app_pw = ""
    try:
        app_pw = st.secrets.get("app_password", "")
    except Exception:
        app_pw = os.environ.get("APP_PASSWORD", "")
    if not app_pw:
        return True

    token = _auth_token()
    if token and st.query_params.get('auth') == token:
        st.session_state['authenticated'] = True
        return True

    st.markdown(
        f'<div style="max-width:420px;margin:80px auto;padding:36px 28px;background:white;'
        f'border-radius:14px;box-shadow:0 4px 18px rgba(91,67,201,0.12);text-align:center;">'
        f'<div style="font-size:1.6rem;font-weight:800;color:{PRIMARY};margin-bottom:6px;">🔍 원스글로벌 채용 인사이트</div>'
        f'<div style="color:#8B8A95;font-size:0.9rem;margin-bottom:24px;">사내 채용 전용 — 비밀번호를 입력하세요</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    c = st.columns([1, 2, 1])
    with c[1]:
        pwd = st.text_input("비밀번호", type="password", label_visibility="collapsed",
                            placeholder="비밀번호 입력", key="login_pwd")
        if st.button("로그인", use_container_width=True, type="primary"):
            if pwd == app_pw:
                st.session_state['authenticated'] = True
                st.query_params['auth'] = token
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다.")
    return False


def render_top_header():
    st.markdown(
        f'<div class="top-header">'
        f'<div class="top-logo">🔍 원스글로벌</div>'
        f'<div class="top-tag">채용 인사이트</div>'
        f'<div style="flex:1;"></div>'
        f'<a href="https://connectdi-dashboard.streamlit.app" target="_blank" '
        f'style="color:white;text-decoration:none;background:rgba(255,255,255,0.18);'
        f'padding:7px 14px;border-radius:6px;font-size:0.85rem;font-weight:600;">'
        f'🔍 검색 인사이트 ↗</a>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ============== 데이터 로딩 ==============
@st.cache_data(ttl=600, show_spinner="Drive 폴더 탐색 중...")
def load_positions():
    return data_loader.list_position_folders(get_shared_drive_id())


@st.cache_data(ttl=3600, show_spinner="지원자 로드 중...")
def load_applicants_for_position(position_name: str, _folder_id: str):
    apps = data_loader.list_applicants(_folder_id, position_name)
    # dataclass를 dict로 직렬화 (cache_data는 dataclass 직렬화 까다로움)
    return [
        {
            'id': a.id, 'name': a.name, 'position': a.position,
            'files': [
                {'id': f.id, 'name': f.name, 'mime_type': f.mime_type, 'size': f.size}
                for f in a.files
            ],
        }
        for a in apps
    ]


@st.cache_data(ttl=3600, show_spinner="채용 공고 가져오는 중...")
def load_jd(url: str, position: str = "") -> str:
    text_override = ""
    if position:
        try:
            text_override = st.secrets.get("position_jd_text", {}).get(position, "")
        except Exception:
            pass
    return jd_fetcher.fetch_jd(position, url, text_override)


@st.cache_data(ttl=300)
def load_cached_analyses():
    return cache_store.load_analyses(get_shared_drive_id())


@st.cache_data(ttl=300)
def load_cached_statuses():
    return cache_store.load_statuses(get_shared_drive_id())


@st.cache_data(ttl=300)
def load_cached_profiles():
    return cache_store.load_profiles(get_shared_drive_id())


# ============== 분석 실행 ==============
def analyze_one(applicant_dict: dict, jd_text: str, ideal_profile: str = "",
                notify_high: bool = True, current_status: str = "") -> dict:
    """지원자 1명 분석 — 자료 다운로드 후 Claude API 호출.

    notify_high=True 시 매칭도 >=임계값이면서 미검토 상태일 때만 Slack 알림.
    이미 서류통과/탈락/보류 등으로 검토된 지원자는 알림 skip.
    """
    documents = {}
    for f in applicant_dict['files']:
        fname = f['name']
        if fname.endswith(('.pdf', '.pptx', '.html')):
            try:
                data = data_loader.download_file(f['id'])
                text = extractors.extract_any(fname, data)
                if text and not text.startswith('['):
                    documents[fname] = text
            except Exception as e:
                documents[fname] = f"[다운로드 실패: {e}]"

    result = analyzer.analyze_applicant(
        jd_text, applicant_dict['name'], documents, ideal_profile=ideal_profile,
    )
    result['_analyzed_at'] = datetime.now().isoformat(timespec='seconds')

    # 포지션별 임계값 이상 + 미검토 상태일 때만 자동 슬랙 알림
    if notify_high and 'error' not in result and slack_notify.is_pending_review(current_status):
        score = result.get('매칭도', {}).get('점수', 0) or 0
        if score >= slack_notify.threshold_for(applicant_dict['position']):
            try:
                slack_notify.notify_high_match(
                    applicant_name=applicant_dict['name'],
                    position=applicant_dict['position'],
                    score=score,
                    oneliner=result.get('매칭도', {}).get('한줄평', ''),
                )
            except Exception:
                pass
    return result


# ============== UI 페이지 ==============
def page_home(positions_map: dict, all_applicants: dict,
              all_analyses: dict, all_statuses: dict):
    """전체 채용 현황 홈 — 포지션·지원자·매칭·상태 종합 개요."""
    import slack_notify

    # ── 전체 KPI ──
    total_apps = sum(len(v) for v in all_applicants.values())
    total_analyzed = sum(
        1 for apps in all_applicants.values() for a in apps
        if a['id'] in all_analyses and 'error' not in all_analyses[a['id']]
    )
    # 매칭 후보 (미검토 + 포지션별 임계값 이상)
    match_candidates = 0
    for pos, apps in all_applicants.items():
        th = slack_notify.threshold_for(pos)
        for a in apps:
            analysis = all_analyses.get(a['id'], {})
            score = analysis.get('매칭도', {}).get('점수', 0) or 0
            status = all_statuses.get(a['id'], {}).get('status', '')
            if score >= th and slack_notify.is_pending_review(status):
                match_candidates += 1

    st.markdown(
        f'<div style="margin-bottom:8px;">'
        f'<span style="font-size:1.5rem;font-weight:800;color:{PRIMARY};">🏠 채용 현황 개요</span>'
        f'<span style="margin-left:12px;color:#8B8A95;font-size:0.9rem;">전체 포지션 한눈에</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    k = st.columns(4)
    for col, (label, value, color) in zip(k, [
        ("채용 중인 포지션", f"{len(positions_map)}개", PRIMARY),
        ("전체 지원자", f"{total_apps:,}명", PRIMARY),
        ("AI 분석 완료", f"{total_analyzed:,}명", "#10B981"),
        ("🎯 매칭 후보 (미검토)", f"{match_candidates:,}명", "#EF4444" if match_candidates else PRIMARY),
    ]):
        col.markdown(
            f'<div class="kpi-box"><div class="kpi-label">{label}</div>'
            f'<div class="kpi-value" style="color:{color};">{value}</div></div>',
            unsafe_allow_html=True,
        )

    st.write("")
    st.markdown("### 📋 포지션별 현황")

    # ── 포지션별 카드 ──
    POSITION_ICONS = {"개발자": "👩‍💻", "AI연구원": "🤖", "Project Leader": "🧐"}
    REVIEWERS = {"개발자": "Furi", "AI연구원": "Y", "Project Leader": "Lina"}
    PERSON_LINKS = {  # 채용공고 노션 URL (page_jd의 NOTION_JD_URLS와 동일)
        "개발자": "https://www.notion.so/3253a7334743807998f3c9c0f8d589be",
        "AI연구원": "https://www.notion.so/3713a7334743808a927ff335888811a5",
        "Project Leader": "https://www.notion.so/b462514264984e968434391940ca4349",
    }

    pos_cols = st.columns(len(positions_map))
    for col, (position, _) in zip(pos_cols, positions_map.items()):
        apps = all_applicants.get(position, [])
        threshold = slack_notify.threshold_for(position)
        icon = POSITION_ICONS.get(position, "📋")
        reviewer = REVIEWERS.get(position, "-")

        # 상태 분포
        status_count = {}
        for a in apps:
            s = all_statuses.get(a['id'], {}).get('status', '미검토') or '미검토'
            status_count[s] = status_count.get(s, 0) + 1
        # 매칭도 분포 (분석 완료된 것만)
        scores = [
            all_analyses[a['id']].get('매칭도', {}).get('점수', 0) or 0
            for a in apps
            if a['id'] in all_analyses and 'error' not in all_analyses[a['id']]
        ]
        avg_score = sum(scores) / len(scores) if scores else 0
        high_pending = []
        for a in apps:
            analysis = all_analyses.get(a['id'], {})
            score = analysis.get('매칭도', {}).get('점수', 0) or 0
            status = all_statuses.get(a['id'], {}).get('status', '')
            if score >= threshold and slack_notify.is_pending_review(status):
                high_pending.append({'name': a['name'], 'score': score})
        high_pending.sort(key=lambda x: -x['score'])

        with col:
            with st.container(border=True):
                # 헤더
                notion_url = PERSON_LINKS.get(position, "")
                link_html = (
                    f'<a href="{notion_url}" target="_blank" '
                    f'style="text-decoration:none;background:#f5f3ff;color:{PRIMARY};'
                    f'padding:3px 9px;border-radius:5px;font-size:0.72rem;'
                    f'font-weight:600;margin-left:8px;">📔 JD</a>'
                ) if notion_url else ""
                st.markdown(
                    f'<div style="font-size:1.1rem;font-weight:800;color:{PRIMARY};">'
                    f'{icon} {position}{link_html}</div>'
                    f'<div style="font-size:0.78rem;color:#8B8A95;margin-top:2px;">'
                    f'담당: {reviewer} · 임계값 {threshold}점</div>',
                    unsafe_allow_html=True,
                )
                st.divider()

                # 수치
                if not apps:
                    st.caption("아직 지원자가 없습니다.")
                    continue

                ck = st.columns(3)
                ck[0].markdown(
                    f'<div style="text-align:center;"><div style="font-size:0.7rem;color:#8B8A95;">지원자</div>'
                    f'<div style="font-size:1.4rem;font-weight:800;color:#111;">{len(apps)}</div></div>',
                    unsafe_allow_html=True,
                )
                ck[1].markdown(
                    f'<div style="text-align:center;"><div style="font-size:0.7rem;color:#8B8A95;">분석</div>'
                    f'<div style="font-size:1.4rem;font-weight:800;color:#10B981;">{len(scores)}</div></div>',
                    unsafe_allow_html=True,
                )
                ck[2].markdown(
                    f'<div style="text-align:center;"><div style="font-size:0.7rem;color:#8B8A95;">평균 매칭</div>'
                    f'<div style="font-size:1.4rem;font-weight:800;color:{PRIMARY};">{avg_score:.0f}점</div></div>',
                    unsafe_allow_html=True,
                )


def page_dashboard(applicants: list[dict], analyses: dict, statuses: dict, jd_text: str,
                   ideal_profile: str = ""):
    """포지션별 지원자 리스트 + 매칭도."""
    # KPI
    total = len(applicants)
    analyzed = sum(1 for a in applicants if a['id'] in analyses)
    high_score = sum(
        1 for a in applicants
        if a['id'] in analyses
        and analyses[a['id']].get('매칭도', {}).get('점수', 0) >= 80
    )

    k = st.columns(4)
    for col, (label, value) in zip(k, [
        ("전체 지원자", f"{total:,}"),
        ("AI 분석 완료", f"{analyzed:,}"),
        ("매칭도 80점+", f"{high_score:,}"),
        ("대기 (미분석)", f"{total - analyzed:,}"),
    ]):
        col.markdown(
            f'<div class="kpi-box"><div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value}</div></div>',
            unsafe_allow_html=True,
        )

    st.write("")

    # 미분석 / 전체 재분석
    pending = [a for a in applicants if a['id'] not in analyses]
    cols = st.columns([3, 1, 1])
    if pending:
        with cols[0]:
            st.info(f"📌 미분석 지원자 **{len(pending)}명** 있습니다. "
                    f"AI 분석을 실행하면 매칭도와 핵심역량을 확인할 수 있습니다.")
        with cols[1]:
            if st.button(f"🚀 미분석 {len(pending)}명 분석",
                         use_container_width=True, type="primary",
                         key="btn_analyze_pending"):
                _bulk_analyze(pending, jd_text, analyses, ideal_profile)
                st.rerun()
    else:
        with cols[0]:
            st.success(f"✅ {len(applicants)}명 모두 분석 완료. "
                       f"인재상이나 JD가 변경되었으면 전체 재분석으로 갱신할 수 있습니다.")
    with cols[2]:
        if st.button(f"🔄 전체 재분석 ({len(applicants)}명)",
                     use_container_width=True,
                     help="인재상/JD 변경 후 모든 지원자를 새로 분석합니다.",
                     key="btn_reanalyze_all"):
            _bulk_analyze(applicants, jd_text, analyses, ideal_profile)
            st.rerun()

    # 정렬·필터
    sort_col, filter_col = st.columns([2, 3])
    with sort_col:
        sort_by = st.selectbox(
            "정렬",
            ["매칭도 ↓", "매칭도 ↑", "이름", "상태"],
            key="sort_by",
        )
    with filter_col:
        statuses_filter = st.multiselect(
            "상태 필터",
            STATUS_OPTIONS,
            default=[],
            placeholder="모든 상태 (필터 없음)",
        )

    # 리스트 build
    rows = []
    for a in applicants:
        anl = analyses.get(a['id'], {})
        st_data = statuses.get(a['id'], {})
        score = anl.get('매칭도', {}).get('점수')
        rows.append({
            '_app': a,
            '_anl': anl,
            'name': a['name'],
            'score': score if score is not None else -1,
            'status': st_data.get('status', '미검토'),
            'note': st_data.get('notes', ''),
        })

    if statuses_filter:
        rows = [r for r in rows if r['status'] in statuses_filter]

    if sort_by == "매칭도 ↓":
        rows.sort(key=lambda r: r['score'], reverse=True)
    elif sort_by == "매칭도 ↑":
        rows.sort(key=lambda r: r['score'] if r['score'] >= 0 else 999)
    elif sort_by == "이름":
        rows.sort(key=lambda r: r['name'])
    else:
        rows.sort(key=lambda r: r['status'])

    st.write("")
    # 헤더
    h = st.columns([0.6, 2, 1.5, 1.5, 4, 1])
    h[0].markdown("**#**")
    h[1].markdown("**이름**")
    h[2].markdown("**매칭도**")
    h[3].markdown("**상태**")
    h[4].markdown("**한줄평**")
    h[5].markdown("**상세**")
    st.markdown("<hr style='margin:8px 0 12px 0;border:none;border-top:1px solid #EDECF1;'>",
                unsafe_allow_html=True)

    for i, r in enumerate(rows, start=1):
        c = st.columns([0.6, 2, 1.5, 1.5, 4, 1])
        c[0].markdown(f"<div style='padding-top:8px;color:#8B8A95;'>{i}</div>", unsafe_allow_html=True)
        c[1].markdown(f"<div style='padding-top:8px;font-weight:600;'>{r['name']}</div>",
                      unsafe_allow_html=True)
        if r['score'] >= 0:
            c[2].markdown(
                f'<div style="padding-top:4px;"><span class="score-badge {score_class(r["score"])}">{r["score"]}점</span></div>',
                unsafe_allow_html=True,
            )
        else:
            c[2].markdown("<div style='padding-top:8px;color:#9CA3AF;'>—</div>",
                          unsafe_allow_html=True)
        color = STATUS_COLORS.get(r['status'], '#9CA3AF')
        c[3].markdown(
            f'<div style="padding-top:4px;"><span class="status-badge" style="background:{color}22;color:{color};border:1px solid {color}44;">{r["status"]}</span></div>',
            unsafe_allow_html=True,
        )
        oneliner = r['_anl'].get('매칭도', {}).get('한줄평', '')
        if not oneliner and r['_anl']:
            oneliner = '(분석 완료)'
        elif not r['_anl']:
            oneliner = '(미분석)'
        c[4].markdown(f"<div style='padding-top:8px;color:#4B5563;font-size:0.9rem;'>{oneliner[:90]}</div>",
                      unsafe_allow_html=True)
        with c[5]:
            if st.button("→", key=f"detail_{r['_app']['id']}", use_container_width=True):
                st.session_state['selected_applicant_id'] = r['_app']['id']
                st.rerun()


def _bulk_analyze(pending: list[dict], jd_text: str, analyses: dict, ideal_profile: str = ""):
    """진행률 표시하며 일괄 분석. 미검토 상태일 때만 슬랙 알림."""
    statuses = load_cached_statuses()
    progress = st.progress(0.0)
    status_text = st.empty()
    for i, app in enumerate(pending, 1):
        status_text.text(f"분석 중 [{i}/{len(pending)}]: {app['name']}")
        try:
            current = statuses.get(app['id'], {}).get('status', '')
            result = analyze_one(app, jd_text, ideal_profile, current_status=current)
            analyses[app['id']] = result
            cache_store.save_analyses(get_shared_drive_id(), analyses)
        except Exception as e:
            analyses[app['id']] = {'error': str(e),
                                   '_analyzed_at': datetime.now().isoformat()}
        progress.progress(i / len(pending))
    status_text.text(f"✅ {len(pending)}명 분석 완료")
    load_cached_analyses.clear()


def page_applicant_detail(applicant: dict, analysis: dict, status_data: dict,
                          all_analyses: dict, all_statuses: dict, jd_text: str,
                          ideal_profile: str = ""):
    """지원자 상세 보기."""
    # 뒤로 가기
    if st.button("← 목록으로", type="secondary"):
        st.session_state.pop('selected_applicant_id', None)
        st.rerun()

    st.markdown(f"## 📋 {applicant['name']}")
    st.markdown(f"<div style='color:#8B8A95;'>{applicant['position']} 지원</div>",
                unsafe_allow_html=True)
    st.write("")

    # 다음 액션 안내 + 1-클릭 진행/탈락 버튼
    current_status = status_data.get('status', '미검토')
    action = next_action_for(applicant['position'], current_status)
    if action:
        st.markdown(
            f'<div style="background:{PRIMARY_LIGHT};border-left:4px solid {PRIMARY};'
            f'padding:12px 18px;margin-bottom:8px;border-radius:6px;">'
            f'<div style="color:{PRIMARY};font-weight:700;font-size:0.95rem;">'
            f'{action["label"]} · 담당: {action["owner"]}</div>'
            f'<div style="color:#4B5563;font-size:0.88rem;margin-top:4px;">{action["action"]}</div>'
            f'<div style="color:#8B8A95;font-size:0.78rem;margin-top:6px;">'
            f'다음 상태: {action["next_status"]} · Slack: {SLACK_CHANNEL}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # 진행/탈락/보류 1-클릭 버튼 (status에 따라 노출)
    flow_next = _next_status_choices(current_status)
    if flow_next:
        bc = st.columns(len(flow_next) + 1)
        for i, (label, new_st, btn_kind) in enumerate(flow_next):
            with bc[i]:
                if st.button(label, use_container_width=True, type=btn_kind,
                             key=f"step_{applicant['id']}_{new_st}"):
                    _advance_status(applicant, new_st, status_data, all_statuses, analysis)
                    st.rerun()

    # 진행 상태 + 메모 (상단 가로 배치)
    with st.container(border=True):
        st.markdown("**📌 진행 상태 / 메모**")
        sc = st.columns([1.5, 4, 1])
        with sc[0]:
            current = status_data.get('status')
            idx = STATUS_OPTIONS.index(current) if current in STATUS_OPTIONS else None
            new_status = st.selectbox(
                "상태", STATUS_OPTIONS,
                index=idx,
                placeholder="상태 선택...",
                label_visibility="collapsed",
                key=f"status_{applicant['id']}",
            )
        with sc[1]:
            notes = st.text_input(
                "메모", value=status_data.get('notes', ''),
                placeholder="면접 코멘트, 특이사항 등",
                label_visibility="collapsed",
                key=f"notes_{applicant['id']}",
            )
        with sc[2]:
            if st.button("💾 저장", type="primary", use_container_width=True,
                         key=f"save_{applicant['id']}"):
                if not new_status:
                    st.warning("상태를 선택해주세요.")
                else:
                    all_statuses[applicant['id']] = {
                        'status': new_status,
                        'notes': notes,
                        'updated_at': datetime.now().isoformat(timespec='seconds'),
                    }
                    cache_store.save_statuses(get_shared_drive_id(), all_statuses)
                    load_cached_statuses.clear()
                    st.success("저장 완료")
                    st.rerun()

    # 분석 결과 (전체 너비)
    current_st = all_statuses.get(applicant['id'], {}).get('status', '')
    if not analysis:
        st.warning("아직 AI 분석이 안 됐습니다.")
        if st.button("🚀 지금 분석", type="primary"):
            with st.spinner("분석 중..."):
                result = analyze_one(applicant, jd_text, ideal_profile, current_status=current_st)
                all_analyses[applicant['id']] = result
                cache_store.save_analyses(get_shared_drive_id(), all_analyses)
                load_cached_analyses.clear()
            st.rerun()
    elif 'error' in analysis:
        st.error(f"분석 오류: {analysis['error']}")
        if st.button("🔄 재분석", type="primary"):
            with st.spinner("분석 중..."):
                result = analyze_one(applicant, jd_text, ideal_profile, current_status=current_st)
                all_analyses[applicant['id']] = result
                cache_store.save_analyses(get_shared_drive_id(), all_analyses)
                load_cached_analyses.clear()
            st.rerun()
    else:
        _render_analysis(applicant, analysis, all_analyses, jd_text, ideal_profile, current_status=current_st)


def _render_analysis(applicant: dict, analysis: dict,
                     all_analyses: dict, jd_text: str,
                     ideal_profile: str = "", current_status: str = ""):
    """분석 결과 카드 표시."""
    score = analysis.get('매칭도', {}).get('점수', 0)
    with st.container(border=True):
        c = st.columns([1, 4])
        with c[0]:
            st.markdown(
                f'<div style="text-align:center;padding-top:8px;">'
                f'<div style="font-size:0.75rem;color:#8B8A95;">매칭도</div>'
                f'<div style="font-size:2.6rem;font-weight:800;color:{PRIMARY};line-height:1;">{score}</div>'
                f'<div style="font-size:0.75rem;color:#8B8A95;margin-top:2px;">/ 100</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with c[1]:
            st.markdown(f"**💬 한줄평**\n\n{analysis.get('매칭도', {}).get('한줄평', '')}")
            st.markdown(f"**🕒 분석 시각**: {analysis.get('_analyzed_at', '-')}")

    # 기본정보
    with st.container(border=True):
        st.markdown("### 👤 기본정보")
        info = analysis.get('기본정보', {})
        c = st.columns(3)
        items = [
            ("이름", info.get('이름', '-')),
            ("이메일", info.get('이메일', '-')),
            ("연락처", info.get('연락처', '-')),
            ("나이", info.get('나이', '-')),
            ("학력", info.get('최종학력', '-')),
            ("경력연수", info.get('경력연수', '-')),
        ]
        for i, (label, value) in enumerate(items):
            c[i % 3].markdown(f"**{label}**\n\n{value or '-'}")

    # 핵심역량 + 기술스택
    cc = st.columns(2)
    with cc[0]:
        with st.container(border=True):
            st.markdown("### ⭐ 핵심역량")
            for skill in analysis.get('핵심역량', []):
                st.markdown(f"- {skill}")
    with cc[1]:
        with st.container(border=True):
            st.markdown("### 🛠 주요 기술스택")
            tech_html = " ".join(
                f'<span style="background:{PRIMARY_LIGHT};color:{PRIMARY};padding:4px 10px;border-radius:6px;font-size:0.85rem;font-weight:600;margin:2px 4px 2px 0;display:inline-block;">{t}</span>'
                for t in analysis.get('주요기술스택', [])
            )
            st.markdown(tech_html, unsafe_allow_html=True)

    # 경력사항 (회사별 재직기간 색깔 표기)
    careers = analysis.get('경력사항', [])
    if careers:
        with st.container(border=True):
            st.markdown("### 💼 경력사항")
            st.caption("재직 기간: 🟢 3년+ · 🟠 1~3년 · 🔴 1년 미만 (인턴·교육 제외)")
            for c in careers:
                months = int(c.get('재직개월', 0) or 0)
                kind = c.get('구분', '') or ''
                # 인턴은 회색으로 표시
                if '인턴' in kind:
                    color = '#9CA3AF'
                    badge_text = f"인턴 · {c.get('기간', '')}"
                elif months >= 36:
                    color = ACCENT
                    badge_text = f"{months/12:.1f}년 · {c.get('기간', '')}"
                elif months >= 12:
                    color = WARN
                    badge_text = f"{months/12:.1f}년 · {c.get('기간', '')}"
                elif months > 0:
                    color = DANGER
                    badge_text = f"{months}개월 · {c.get('기간', '')}"
                else:
                    color = '#6B6A73'
                    badge_text = c.get('기간', '')
                company = c.get('회사명', '') or '-'
                role = c.get('역할', '') or ''
                st.markdown(
                    f'<div style="background:white;border-left:4px solid {color};'
                    f'padding:10px 14px;margin-bottom:8px;border-radius:6px;'
                    f'box-shadow:0 1px 3px rgba(0,0,0,0.04);">'
                    f'<div style="display:flex;justify-content:space-between;align-items:baseline;">'
                    f'<div><b style="color:{color};font-size:1rem;">{company}</b>'
                    f'<span style="color:#6B6A73;margin-left:8px;font-size:0.9rem;">{role}</span></div>'
                    f'<div style="color:{color};font-weight:700;font-size:0.85rem;">{badge_text}</div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

    # 경험요약
    with st.container(border=True):
        st.markdown("### 📝 경험요약")
        st.markdown(analysis.get('경험요약', ''))

    # 자격및기타
    with st.container(border=True):
        st.markdown("### 🎓 자격 및 기타")
        for q in analysis.get('자격및기타', []):
            st.markdown(f"- {q}")

    # 장점 / 약점
    cc = st.columns(2)
    with cc[0]:
        with st.container(border=True):
            st.markdown(f"### ✅ 장점 (JD · 인재상)")
            for pt in analysis.get('매칭도', {}).get('장점', []):
                st.markdown(f"- {pt}")
    with cc[1]:
        with st.container(border=True):
            st.markdown(f"### ⚠️ 약점 (JD · 인재상)")
            for pt in analysis.get('매칭도', {}).get('약점', []):
                st.markdown(f"- {pt}")

    # 재분석 + 원본 파일
    with st.container(border=True):
        cols = st.columns([1, 3])
        with cols[0]:
            if st.button("🔄 재분석", use_container_width=True):
                with st.spinner("분석 중..."):
                    result = analyze_one(applicant, jd_text, ideal_profile, current_status=current_status)
                    all_analyses[applicant['id']] = result
                    cache_store.save_analyses(get_shared_drive_id(), all_analyses)
                    load_cached_analyses.clear()
                st.rerun()
        with cols[1]:
            st.markdown("**📎 첨부 파일**")
            for f in applicant['files']:
                st.markdown(
                    f'- [{f["name"]}](https://drive.google.com/file/d/{f["id"]}/view)'
                )


@st.cache_data(ttl=600, show_spinner="합격자 자료 로드 중...")
def load_hired_examples(position: str, _drive_id: str) -> list[dict]:
    """합격자 폴더에서 자료 텍스트 추출."""
    raw = cache_store.list_hired_examples(_drive_id, position)
    result = []
    for h in raw:
        docs = {}
        for f in h.get('files', []):
            fname = f['name']
            if fname.endswith(('.pdf', '.pptx', '.html')):
                try:
                    data = data_loader.download_file(f['id'])
                    text = extractors.extract_any(fname, data)
                    if text and not text.startswith('['):
                        docs[fname] = text
                except Exception:
                    pass
        if docs:
            result.append({'id': h['id'], 'name': h['name'], 'documents': docs})
    return result


def page_learn_profile(position: str, jd_text: str, profiles: dict[str, str]):
    """인재상 자동 학습 — 백그라운드 처리, 결과는 인재상 관리에 자동 저장."""
    st.markdown(f"## 🧠 {position} 인재상 자동 학습")
    st.write("")

    if not jd_text:
        st.warning("이 포지션의 JD가 설정되지 않아 학습 불가합니다.")
        return

    try:
        examples = load_hired_examples(position, get_shared_drive_id())
    except Exception as e:
        st.error(f"학습 자료 로드 실패: {e}")
        return

    if not examples:
        st.info("학습할 자료가 없습니다.")
        return

    # 학습 버튼만 노출
    cols = st.columns([2, 1])
    with cols[1]:
        if st.button("🚀 인재상 학습 실행", type="primary", use_container_width=True,
                     key=f"learn_btn_{position}"):
            with st.spinner("분석 중... (약 30초)"):
                result = analyzer.learn_ideal_profile(jd_text, examples)
            if 'error' in result:
                st.error(f"학습 실패: {result['error']}")
                return
            profiles[position] = result.get('인재상_요약', '')
            cache_store.save_profiles(get_shared_drive_id(), profiles)
            load_cached_profiles.clear()
            st.session_state[f'learned_at_{position}'] = datetime.now().isoformat(timespec='seconds')
            st.success(
                f"✅ 학습 완료. `{position}` 인재상에 자동 반영되었습니다. "
                f"내용은 사이드바 **🎯 인재상 관리**에서 확인·편집하세요."
            )
            st.rerun()

    last = st.session_state.get(f'learned_at_{position}')
    if last:
        st.caption(f"마지막 학습: {last}")


def page_process(position: str):
    """포지션별 채용 프로세스 흐름 표시."""
    st.markdown(f"## 📞 {position} 채용 프로세스")
    flow = PROCESS_FLOW.get(position)
    if not flow:
        st.warning(f"'{position}' 프로세스가 정의되어 있지 않습니다.")
        return
    st.caption(f"모든 커뮤니케이션은 Slack **{SLACK_CHANNEL}** 채널에서 진행됩니다.")
    st.write("")

    reviewers = flow['서류검토자'].replace(' · ', ', ')
    first_interviewers = flow['1차면접관'].replace(' · ', ', ')
    second_interviewers = flow['2차면접관'].replace(' · ', ', ')
    steps = [
        ("1️⃣", "서류 검토", flow["서류검토자"],
         f"{reviewers}이 지원자의 이력서, 포트폴리오, 자기소개서를 검토합니다.",
         "→ 통과 시 Owen에게 알림"),
        ("2️⃣", "1차면접 일정 조율", flow["1차면접_연락"],
         f"{flow['1차면접_연락']}이 지원자에게 연락하여 1차면접 일정을 잡습니다.", ""),
        ("3️⃣", "1차면접", flow["1차면접관"],
         f"{first_interviewers}이 1차면접을 진행합니다.",
         "→ 통과 시 Owen에게 알림"),
        ("4️⃣", "2차면접 일정 조율", flow["2차면접_연락"],
         f"{flow['2차면접_연락']}이 지원자에게 연락하여 2차면접 일정을 잡습니다.", ""),
        ("5️⃣", "2차면접 + 최종 의사결정", flow["2차면접관"],
         f"{second_interviewers}이 2차면접에 참여하고 같이 의사결정해서 최종 후보자를 결정합니다.",
         "→ 결정 시 Lina에게 알림"),
        ("6️⃣", "최종합격 · 연봉협상", flow["최종연락_연봉협상"],
         f"{flow['최종연락_연봉협상']}이 지원자에게 연락하여 연봉협상 등을 진행 후 최종합격합니다.", ""),
    ]
    for emoji, title, owner, action, note in steps:
        st.markdown(
            f'<div style="background:white;border-left:4px solid {PRIMARY};'
            f'padding:14px 18px;margin-bottom:10px;border-radius:6px;'
            f'box-shadow:0 1px 3px rgba(0,0,0,0.04);">'
            f'<div style="display:flex;justify-content:space-between;align-items:baseline;">'
            f'<div><b style="color:{PRIMARY};font-size:1.05rem;">{emoji} {title}</b>'
            f'<span style="color:#6B6A73;margin-left:8px;font-size:0.85rem;">담당: <b>{owner}</b></span></div>'
            f'</div>'
            f'<div style="color:#4B5563;font-size:0.92rem;margin-top:6px;">{action}</div>'
            + (f'<div style="color:#8B8A95;font-size:0.82rem;margin-top:4px;">{note}</div>' if note else '')
            + '</div>',
            unsafe_allow_html=True,
        )


NOTION_JD_URLS = {
    "개발자": "https://www.notion.so/3253a7334743807998f3c9c0f8d589be",
    "AI연구원": "https://www.notion.so/3713a7334743808a927ff335888811a5",
    "Project Leader": "https://www.notion.so/b462514264984e968434391940ca4349",
}


def page_jd(jd_text: str, position: str):
    """채용 공고 보기 — Notion JD를 마크다운으로 표시."""
    with st.container(border=True):
        cols = st.columns([3, 1])
        with cols[0]:
            st.markdown(f"### 📌 {position} — 채용 공고")
        with cols[1]:
            notion_url = NOTION_JD_URLS.get(position, "")
            if notion_url:
                st.markdown(
                    f'<div style="text-align:right;padding-top:6px;">'
                    f'<a href="{notion_url}" target="_blank" style="text-decoration:none;'
                    f'background:#f5f3ff;color:#6d28d9;padding:6px 12px;border-radius:6px;'
                    f'font-size:0.9rem;font-weight:600;">📔 Notion에서 보기</a></div>',
                    unsafe_allow_html=True,
                )
        st.markdown(jd_text if jd_text.strip() else "_채용공고 내용이 등록되지 않았습니다._")


def page_profiles(current_position: str, all_positions: list[str], profiles: dict[str, str]):
    """회사 인재상 관리 — 공통 + 포지션별 자유 텍스트 편집."""
    st.markdown("## 🎯 인재상 관리")
    st.caption(
        "회사가 추구하는 인재상을 자유롭게 작성하세요. 매칭도 평가 시 JD와 함께 종합 반영됩니다.\n"
        "공통 인재상은 모든 포지션에 적용되며, 포지션별 인재상은 해당 포지션 분석에만 추가로 반영됩니다."
    )
    st.write("")

    # 공통 인재상
    with st.container(border=True):
        st.markdown("### 📐 공통 인재상 (모든 포지션 공통)")
        common = st.text_area(
            "공통 인재상",
            value=profiles.get('_common', ''),
            placeholder=(
                "예: 호기심이 많고 새 기술을 자기주도적으로 학습하는 분.\n"
                "협업·문서화에 가치를 두고, 단순 기술 스택보다 문제 해결 임팩트를 중시합니다.\n"
                "의약·헬스케어 도메인에 관심이 있거나 경험이 있으면 가점."
            ),
            height=180,
            label_visibility="collapsed",
            key="profile_common",
        )
        if st.button("💾 공통 인재상 저장", type="primary", key="save_common"):
            profiles['_common'] = common
            cache_store.save_profiles(get_shared_drive_id(), profiles)
            load_cached_profiles.clear()
            st.success("저장되었습니다. 다음 분석부터 반영됩니다.")
            st.rerun()

    st.write("")

    # 포지션별 인재상
    with st.container(border=True):
        st.markdown("### 🎯 포지션별 인재상")
        pos_for_edit = st.selectbox(
            "편집할 포지션",
            all_positions,
            index=all_positions.index(current_position) if current_position in all_positions else 0,
            key="profile_pos_select",
        )
        st.caption(f"'{pos_for_edit}' 포지션에만 추가 반영됩니다.")
        text = st.text_area(
            f"{pos_for_edit} 인재상",
            value=profiles.get(pos_for_edit, ''),
            placeholder=(
                f"예 ({pos_for_edit} 전용):\n"
                "- 백엔드/데이터 파이프라인 실무 경험 우대\n"
                "- 의약 데이터 또는 헬스케어 도메인 경험 가점\n"
                "- 빠른 학습 능력과 자기주도적 문제 해결 마인드"
            ),
            height=200,
            label_visibility="collapsed",
            key=f"profile_pos_{pos_for_edit}",
        )
        if st.button(f"💾 '{pos_for_edit}' 인재상 저장", type="primary", key=f"save_pos_{pos_for_edit}"):
            profiles[pos_for_edit] = text
            cache_store.save_profiles(get_shared_drive_id(), profiles)
            load_cached_profiles.clear()
            st.success(f"'{pos_for_edit}' 인재상이 저장되었습니다.")
            st.rerun()

    st.write("")

    # 현재 적용되는 인재상 미리보기
    merged = cache_store.merged_profile_for(current_position, profiles)
    if merged:
        with st.container(border=True):
            st.markdown(f"### 👀 현재 '{current_position}' 분석에 적용되는 인재상")
            st.text(merged)

    st.info(
        "ℹ️ 인재상을 변경한 후 기존 분석 결과에 반영하려면 지원자 상세 화면에서 "
        "**🔄 재분석** 또는 미분석 일괄 분석을 다시 실행하세요."
    )


# ============== Main ==============
def main():
    if not check_password():
        return

    render_top_header()

    # 사이드바
    with st.sidebar:
        try:
            positions_map = load_positions()
        except Exception as e:
            st.error(f"Drive 접근 실패: {e}")
            return

        if not positions_map:
            st.warning("채용 폴더에 포지션이 없습니다.")
            return

        # 메뉴(보기) — 홈이 첫 항목, 사이드바 맨 위
        st.markdown(
            f'<div style="font-size:0.75rem;color:#8B8A95;font-weight:600;'
            f'text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">메뉴</div>',
            unsafe_allow_html=True,
        )
        view_mode = st.radio(
            "메뉴",
            options=["🏠 홈", "📊 지원자 목록", "📞 채용 프로세스", "📋 채용 공고",
                     "🎯 인재상 관리", "🧠 인재상 학습"],
            key='view_mode',
            label_visibility="collapsed",
        )

        st.divider()

        # 포지션 — 홈 화면에서는 숨김
        if view_mode != "🏠 홈":
            st.markdown(
                f'<div style="font-size:0.75rem;color:#8B8A95;font-weight:600;'
                f'text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">포지션</div>',
                unsafe_allow_html=True,
            )
            position = st.radio(
                "포지션",
                options=list(positions_map.keys()),
                key='nav_position',
                label_visibility="collapsed",
            )
        else:
            position = st.session_state.get('nav_position') or list(positions_map.keys())[0]

        st.divider()
        if st.button("🔄 데이터 새로고침", use_container_width=True):
            load_positions.clear()
            load_applicants_for_position.clear()
            load_cached_analyses.clear()
            load_cached_statuses.clear()
            load_cached_profiles.clear()
            st.rerun()

    # 데이터 로드
    folder_id = positions_map[position]
    applicants = load_applicants_for_position(position, folder_id)
    analyses = load_cached_analyses()
    statuses = load_cached_statuses()
    profiles = load_cached_profiles()
    ideal_profile = cache_store.merged_profile_for(position, profiles)

    # JD 가져오기 (홈 화면은 JD 불필요 → 다른 view_mode일 때만)
    jd_text = ""
    if view_mode != "🏠 홈":
        jd_url = get_position_url(position)
        try:
            jd_text = load_jd(jd_url, position)
        except Exception as e:
            st.warning(f"JD 가져오기 실패: {e}")
        if not jd_text:
            st.info(
                f"⚠️ '{position}' JD를 가져올 수 없습니다. "
                f"secrets.toml `[position_jd_text]` 섹션에 JD 텍스트를 등록하거나 "
                f"사람인 URL을 `[positions]`에 추가하세요."
            )

    # 라우팅
    selected = st.session_state.get('selected_applicant_id')
    if view_mode == "🏠 홈":
        # 전체 포지션 지원자 로드 (cache hit ratio 높음)
        all_apps = {}
        for pos, fid in positions_map.items():
            try:
                all_apps[pos] = load_applicants_for_position(pos, fid)
            except Exception:
                all_apps[pos] = []
        page_home(positions_map, all_apps, analyses, statuses)
    elif view_mode == "🎯 인재상 관리":
        page_profiles(position, list(positions_map.keys()), profiles)
    elif view_mode == "🧠 인재상 학습":
        page_learn_profile(position, jd_text, profiles)
    elif view_mode == "📞 채용 프로세스":
        page_process(position)
    elif selected and view_mode == "📊 지원자 목록":
        applicant = next((a for a in applicants if a['id'] == selected), None)
        if applicant:
            page_applicant_detail(
                applicant, analyses.get(selected, {}), statuses.get(selected, {}),
                analyses, statuses, jd_text, ideal_profile,
            )
        else:
            st.session_state.pop('selected_applicant_id', None)
            st.rerun()
    elif view_mode == "📋 채용 공고":
        if jd_text:
            page_jd(jd_text, position)
        else:
            st.warning("JD가 없습니다.")
    else:
        page_dashboard(applicants, analyses, statuses, jd_text, ideal_profile)


if __name__ == "__main__":
    main()
