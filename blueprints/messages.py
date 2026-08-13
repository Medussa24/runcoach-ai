"""Read-only private Community Messages workspace."""

from __future__ import annotations

from time import time

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app import current_user, current_user_id, get_user_by_id, login_required
from stores import community_message_store


messages_bp = Blueprint("messages", __name__, url_prefix="/community/messages")

START_RATE_LIMIT = 5
START_RATE_WINDOW_SECONDS = 10 * 60
NEUTRAL_START_NOTICE = (
    "If that account can receive messages, the conversation will appear here "
    "when messaging is enabled."
)
def _start_attempt_allowed(user_id, now=None):
    """Apply a database-backed per-account limit without inspecting email."""
    current_time = time() if now is None else float(now)
    return community_message_store.allow_start_attempt(
        user_id,
        current_time,
        limit=START_RATE_LIMIT,
        window_seconds=START_RATE_WINDOW_SECONDS,
    )


def _conversation_summary(user_id, conversation):
    other_user_id = (
        conversation["user_high_id"]
        if conversation["user_low_id"] == user_id
        else conversation["user_low_id"]
    )
    other_user = get_user_by_id(other_user_id)
    messages = community_message_store.list_messages(
        user_id, conversation["id"], limit=1
    )
    latest = messages[-1] if messages else None
    email = other_user["email"] if other_user else "RunCoach member"
    label = email.split("@", 1)[0] if "@" in email else email
    initial = (label[:1] or "R").upper()
    return {
        **conversation,
        "other_user_id": other_user_id,
        "other_user_email": email,
        "other_user_label": label,
        "other_user_initial": initial,
        "latest_message": latest,
    }


@messages_bp.route("", methods=["GET"])
@login_required
def inbox():
    user = current_user()
    user_id = user["id"]
    conversations = [
        _conversation_summary(user_id, conversation)
        for conversation in community_message_store.list_conversations(user_id)
    ]
    return render_template(
        "community_messages.html",
        current_user=user,
        conversations=conversations,
        active_conversation=None,
        thread_messages=[],
    )


@messages_bp.route("/<int:conversation_id>", methods=["GET"])
@login_required
def conversation(conversation_id):
    user = current_user()
    user_id = user["id"]
    authorized_conversation = community_message_store.get_conversation(
        user_id, conversation_id
    )
    if not authorized_conversation:
        abort(404)

    conversations = [
        _conversation_summary(user_id, item)
        for item in community_message_store.list_conversations(user_id)
    ]
    active_conversation = next(
        item for item in conversations if item["id"] == conversation_id
    )
    return render_template(
        "community_messages.html",
        current_user=user,
        conversations=conversations,
        active_conversation=active_conversation,
        thread_messages=community_message_store.list_messages(
            user_id, conversation_id
        ),
    )


@messages_bp.route("/start", methods=["POST"])
@login_required
def request_conversation():
    """Accept a discovery request without looking up or revealing an account."""
    user_id = current_user_id()
    if not _start_attempt_allowed(user_id):
        return "Please wait before trying again.", 429

    # Reading the field keeps the request shape stable for Phase 3. Deliberately
    # do not query users or create a conversation in this read-only phase.
    request.form.get("email", "").strip().lower()
    flash(NEUTRAL_START_NOTICE, "success")
    return redirect(url_for("messages.inbox"), code=303)
