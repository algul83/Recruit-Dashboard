"""Slack Bot으로 채용 진행 알림 전송."""
from __future__ import annotations

import os

import requests

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


HIGH_MATCH_THRESHOLD = 70

# 포지션별로 멘션 받을 사람 (서류 검토 단계 담당자)
HIGH_MATCH_REVIEWERS = {
    "개발자": ["Furi"],
    "AI연구원": ["Y"],
    "Project Leader": ["Lina"],
}


def notify_high_match(applicant_name: str, position: str, score: int,
                       oneliner: str = "") -> dict:
    """매칭도 70점 이상 지원자 발생 시 담당자 멘션 알림."""
    reviewers = HIGH_MATCH_REVIEWERS.get(position, [])
    if not reviewers:
        return {"ok": False, "error": f"포지션 '{position}' 담당자 미설정"}
    mentions = " ".join(mention(n) for n in reviewers)
    one_line = f"\n💬 _{oneliner}_" if oneliner else ""
    text = (
        f"🎯 *매칭도 {score}점 신규 지원자* — {position}\n"
        f"👤 *{applicant_name}*  ·  {mentions} 서류 검토 부탁드려요."
        f"{one_line}"
    )
    return post_message(text)


def notify_status_change(
    applicant_name: str, position: str, prev_status: str, new_status: str,
    matching_score: int | None, owner_name: str, action_text: str,
    decided_by: str = "",
) -> dict:
    """상태 전환 시 알림. 담당자 멘션 + 지원자 정보 + 다음 액션."""
    score_str = f"매칭도 *{matching_score}점* · " if matching_score is not None else ""
    decided = f" (결정: {mention(decided_by)})" if decided_by else ""
    text = (
        f"📋 *{position} · {applicant_name}* — `{prev_status}` → `{new_status}`{decided}\n"
        f"{score_str}다음: {mention(owner_name)} {action_text}"
    )
    return post_message(text)
