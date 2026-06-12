"""Slack Bot으로 채용 진행 알림 전송."""
from __future__ import annotations

import os
import re
from urllib.parse import quote

import requests

# Dashboard URL (지원자 상세 페이지 deep link용)
DASHBOARD_URL = "https://onesglobal-recruit.streamlit.app"


def applicant_link(position: str, applicant_id: str) -> str:
    """Dashboard에서 해당 지원자 상세로 바로 가는 URL."""
    return f"{DASHBOARD_URL}/?position={quote(position)}&applicant={applicant_id}"

# bulk_analyze.py 같은 standalone 실행 시 주입용
_overrides: dict = {}


def configure(token: str = "", channel: str = "", members: dict | None = None):
    """standalone 스크립트에서 호출 (streamlit secrets 없이 사용 시)."""
    if token:
        _overrides['token'] = token
    if channel:
        _overrides['channel'] = channel
    if members:
        _overrides['members'] = dict(members)


def _get_secret(key: str, default: str = "") -> str:
    # 1순위: 명시적 주입값
    if key == "SLACK_BOT_TOKEN" and _overrides.get('token'):
        return _overrides['token']
    if key == "SLACK_RECRUIT_CHANNEL" and _overrides.get('channel'):
        return _overrides['channel']
    # 2순위: streamlit secrets
    try:
        import streamlit as st
        v = st.secrets.get(key, default)
        if v:
            return v
    except Exception:
        pass
    return os.environ.get(key, default)


def _get_members() -> dict[str, str]:
    if _overrides.get('members'):
        return _overrides['members']
    try:
        import streamlit as st
        return dict(st.secrets.get("slack_members", {}))
    except Exception:
        return {}


def mention(name: str) -> str:
    """이름 → Slack 멘션 (`<@U...>`). ID 없으면 이름 그대로."""
    uid = _get_members().get(name)
    return f"<@{uid}>" if uid else f"*{name}*"


def mentionize_names(text: str) -> str:
    """문장 내 알려진 멤버 이름을 Slack 멘션 형태로 자동 치환.

    UI에는 plain text("Furi, Y, Lina")로 표시하고 Slack 전송 직전에만 멘션화
    하기 위한 유틸. 단어 경계는 한글/영문/숫자 인접 시 매칭 제외로 흉내.
    이름 길이가 긴 것부터 처리해 substring 충돌(예: "Y"가 "Y · Lina"에서 두 번
    매칭되는 문제) 방지.
    """
    members = _get_members()
    if not members:
        return text
    for name in sorted(members.keys(), key=len, reverse=True):
        uid = members[name]
        if not uid:
            continue
        # 영문명은 인접 한글 조사("Lina가") 허용해야 하므로 boundary는 알파뉴메릭만 차단
        pattern = re.compile(rf'(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])')
        text = pattern.sub(f'<@{uid}>', text)
    return text


def post_message(text: str, blocks: list | None = None) -> dict:
    """#채용 채널에 메시지 전송."""
    token = _get_secret("SLACK_BOT_TOKEN")
    channel = _get_secret("SLACK_RECRUIT_CHANNEL")
    if not token or not channel:
        return {"ok": False, "error": "Slack 설정 없음 (SLACK_BOT_TOKEN/SLACK_RECRUIT_CHANNEL)"}
    payload = {"channel": channel, "text": text}
    if blocks:
        payload["blocks"] = blocks
    r = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
        json=payload, timeout=10,
    )
    return r.json()


HIGH_MATCH_THRESHOLD = 70  # 기본 임계값

# 포지션별 임계값 override (기본 70점)
HIGH_MATCH_THRESHOLDS = {
    "AI연구원": 75,  # 인재상 적용 후 점수가 전반적으로 높아 상향
}

# 포지션별로 멘션 받을 사람 (서류 검토 단계 담당자)
HIGH_MATCH_REVIEWERS = {
    "개발자": ["Furi"],
    "AI연구원": ["Y"],
    "Project Leader": ["Lina"],
    "웹디자이너": ["Lina"],
}


def threshold_for(position: str) -> int:
    """포지션별 알림 임계값. 미설정 시 기본값."""
    return HIGH_MATCH_THRESHOLDS.get(position, HIGH_MATCH_THRESHOLD)


def is_pending_review(status: str) -> bool:
    """미검토(아직 서류 검토 안 한) 상태인지 — 알림 발송 대상 여부."""
    return not status or status == "미검토"


def notify_high_match(applicant_name: str, position: str, score: int,
                       oneliner: str = "", applicant_id: str = "") -> dict:
    """매칭도 70점 이상 지원자 발생 시 담당자 멘션 알림.

    applicant_id 주면 dashboard 상세 페이지 deep link 포함.
    """
    reviewers = HIGH_MATCH_REVIEWERS.get(position, [])
    if not reviewers:
        return {"ok": False, "error": f"포지션 '{position}' 담당자 미설정"}
    mentions = " ".join(mention(n) for n in reviewers)
    one_line = f"\n💬 _{oneliner}_" if oneliner else ""
    link_line = ""
    if applicant_id:
        url = applicant_link(position, applicant_id)
        link_line = f"\n🔗 <{url}|상세 보기>"
    text = (
        f"🎯 *매칭도 {score}점 신규 지원자* — {position}\n"
        f"👤 *{applicant_name}*  ·  {mentions} 서류 검토 부탁드려요."
        f"{one_line}{link_line}"
    )
    return post_message(text)


def notify_status_change(
    applicant_name: str, position: str, prev_status: str, new_status: str,
    matching_score: int | None, owner_name: str, action_text: str,
    decided_by: str = "", applicant_id: str = "",
) -> dict:
    """상태 전환 시 알림. 담당자 멘션 + 지원자 정보 + 다음 액션 + deep link."""
    score_str = f"매칭도 *{matching_score}점* · " if matching_score is not None else ""
    decided = f" (결정: {mention(decided_by)})" if decided_by else ""
    link_line = ""
    if applicant_id:
        url = applicant_link(position, applicant_id)
        link_line = f"\n🔗 <{url}|상세 보기>"
    # action_text 안의 이름들(2차면접관 등)을 멘션으로 자동 치환
    action_mentioned = mentionize_names(action_text)
    text = (
        f"📋 *{position} · {applicant_name}* — `{prev_status}` → `{new_status}`{decided}\n"
        f"{score_str}다음: {mention(owner_name)} {action_mentioned}"
        f"{link_line}"
    )
    return post_message(text)
