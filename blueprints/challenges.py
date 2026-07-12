from flask import Blueprint, render_template, redirect, url_for, flash, request
from app import (
    login_required, current_user, current_user_id,
    get_all_challenges, is_user_joined_challenge, calculate_challenge_progress,
    get_challenge_by_id, get_challenge_participants, join_challenge, leave_challenge
)

challenges_bp = Blueprint("challenges", __name__)

@challenges_bp.route("/challenges")
@login_required
def challenges_page():
    user = current_user()
    user_id = user["id"]

    challenges = get_all_challenges()
    for c in challenges:
        c["joined"] = is_user_joined_challenge(user_id, c["id"])
        c["progress"] = calculate_challenge_progress(user_id, c)

    return render_template("challenges.html", challenges=challenges, current_user=user)


@challenges_bp.route("/challenge/<int:challenge_id>")
def challenge_detail(challenge_id):
    challenge = get_challenge_by_id(challenge_id)
    if not challenge:
        return "Challenge not found", 404

    user_id = current_user_id()
    joined = False
    user_progress = None
    if user_id:
        joined = is_user_joined_challenge(user_id, challenge_id)
        user_progress = calculate_challenge_progress(user_id, challenge)

    participants = get_challenge_participants(challenge_id)

    for p in participants:
        p["progress"] = calculate_challenge_progress(p["id"], challenge)

    act = challenge["activity_type"].lower()
    if act == "run":
        coach_message = "Rico says: Keep pushin' those miles, one step at a time! Consistency is your superpower!"
    elif act == "walk":
        coach_message = "Iggy says: A steady walk clears the mind and builds the heart. You've got this!"
    else:
        coach_message = "Luna says: Recovery and pacing are just as important as speed. Listen to your body!"

    user = current_user()
    return render_template(
        "challenge_detail.html",
        challenge=challenge,
        joined=joined,
        user_progress=user_progress,
        participants=participants,
        coach_message=coach_message,
        current_user=user
    )


@challenges_bp.route("/challenge/<int:challenge_id>/join", methods=["POST"])
@login_required
def join_challenge_route(challenge_id):
    user_id = current_user_id()
    challenge = get_challenge_by_id(challenge_id)
    if not challenge:
        flash("Challenge not found.", "error")
        return redirect(url_for("challenges.challenges_page"))

    join_challenge(user_id, challenge_id)
    flash("Successfully joined the challenge! Keep moving!", "success")
    return redirect(url_for("challenges.challenge_detail", challenge_id=challenge_id))


@challenges_bp.route("/challenge/<int:challenge_id>/leave", methods=["POST"])
@login_required
def leave_challenge_route(challenge_id):
    user_id = current_user_id()
    challenge = get_challenge_by_id(challenge_id)
    if not challenge:
        flash("Challenge not found.", "error")
        return redirect(url_for("challenges.challenges_page"))

    leave_challenge(user_id, challenge_id)
    flash("You have left the challenge.", "success")
    return redirect(url_for("challenges.challenge_detail", challenge_id=challenge_id))
