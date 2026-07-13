from flask import Blueprint, render_template, redirect, url_for, flash, request
from app import (
    login_required, current_user, current_user_id,
    create_community_event, get_upcoming_events, is_user_rsvped,
    get_event_rsvps_count, get_event_by_id, get_event_rsvp_users, toggle_event_rsvp
)

events_bp = Blueprint("events", __name__)

@events_bp.route("/events", methods=["GET", "POST"])
@login_required
def events_list():
    user = current_user()
    user_id = user["id"]

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        event_type = request.form.get("event_type", "").strip()
        event_date = request.form.get("event_date", "").strip()
        event_time = request.form.get("event_time", "").strip()
        location = request.form.get("location", "").strip()
        pace_group = request.form.get("pace_group", "").strip()
        language = request.form.get("language", "").strip()

        errors = []
        if not title or len(title) > 120:
            errors.append("Title is required and must be under 120 characters.")
        if not description or len(description) > 1000:
            errors.append("Description is required and must be under 1000 characters.")
        if event_type not in ("run", "walk", "walkathon", "marathon", "practice"):
            errors.append("Invalid event type.")
        if not event_date or not event_time:
            errors.append("Date and time are required.")
        if not location or len(location) > 200:
            errors.append("Location is required and must be under 200 characters.")
        if not pace_group or len(pace_group) > 100:
            errors.append("Pace group is required and must be under 100 characters.")
        if not language or len(language) > 50:
            errors.append("Language is required.")

        if errors:
            for err in errors:
                flash(err, "error")
        else:
            create_community_event(user_id, title, description, event_type, event_date, event_time, location, pace_group, language)
            flash("Event created successfully!", "success")
            return redirect(url_for("events.events_list"))

    events = get_upcoming_events()
    for e in events:
        e["rsvped"] = is_user_rsvped(user_id, e["id"])
        e["rsvp_count"] = get_event_rsvps_count(e["id"])

    return render_template("events.html", events=events, current_user=user)


@events_bp.route("/event/<int:event_id>")
def event_detail(event_id):
    event = get_event_by_id(event_id)
    if not event:
        return "Event not found", 404

    user_id = current_user_id()
    rsvped = False
    if user_id:
        rsvped = is_user_rsvped(user_id, event_id)

    rsvp_count = get_event_rsvps_count(event_id)
    rsvp_users = get_event_rsvp_users(event_id)

    user = current_user()
    return render_template("event_detail.html", event=event, rsvped=rsvped, rsvp_count=rsvp_count, rsvp_users=rsvp_users, current_user=user)


@events_bp.route("/event/<int:event_id>/rsvp", methods=["POST"])
@login_required
def event_rsvp(event_id):
    user_id = current_user_id()
    event = get_event_by_id(event_id)
    if not event:
        flash("Event not found.", "error")
        return redirect(url_for("events.events_list"))

    action = toggle_event_rsvp(user_id, event_id)
    if action == "added":
        flash("Successfully RSVPed to the event!", "success")
    else:
        flash("Cancelled your RSVP.", "success")
    return redirect(request.referrer or url_for("events.event_detail", event_id=event_id))
