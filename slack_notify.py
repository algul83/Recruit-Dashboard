"""Slack Bot으로 채용 진행 알림 전송."""
from __future__ import annotations

import os

import requests


def _get_secret(key: str, default: str = "") -> str:
    try:
        import streamlit as st
        v = st.secrets.get(key, default)
        if v:
            return v
    except Exception:
        pass
    return os.environ.get(key, default)


def _get_members() -> dict[str, str]:
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
