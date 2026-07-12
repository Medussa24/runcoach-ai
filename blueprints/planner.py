from datetime import timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, Response
from app import (
    login_required, current_user, current_user_id,
    get_user_timezone, parse_week_start, planner_calendar_days,
    SUPPORTED_TIMEZONES, build_private_agent_summary, get_all_runs,
    WeeklyPlannerAgent, save_generated_plan, add_personal_planner_event,
    update_user_timezone, get_planner_events, build_calendar_ics,
    PlanEmailService, planner_store
)

planner_bp = Blueprint("planner", __name__)

@planner_bp.route("/planner")
@login_required
def planner():
    user = current_user()
    timezone_name = get_user_timezone(user["id"])
    week_start = parse_week_start(request.args.get("week_start"), timezone_name)
    week_end = week_start + timedelta(days=6)
    return render_template(
        "planner.html",
        current_user=user,
        week_start=week_start.isoformat(),
        week_label=(
            f"{week_start.strftime('%b %d')} - "
            f"{week_end.strftime('%b %d, %Y')}"
        ),
        previous_week=(week_start - timedelta(days=7)).isoformat(),
        next_week=(week_start + timedelta(days=7)).isoformat(),
        calendar_days=planner_calendar_days(
            user["id"],
            week_start,
            timezone_name,
        ),
        timezone_name=timezone_name,
        supported_timezones=SUPPORTED_TIMEZONES,
    )


@planner_bp.route("/planner/generate", methods=["POST"])
@login_required
def generate_weekly_plan():
    user_id = current_user_id()
    week_start = parse_week_start(
        request.form.get("week_start"),
        get_user_timezone(user_id),
    )
    preferred_time = request.form.get("preferred_time", "07:00")
    goal = request.form.get("goal", "")
    summary = build_private_agent_summary(user_id, get_all_runs(user_id))
    events, source = WeeklyPlannerAgent().generate(
        week_start,
        preferred_time,
        goal,
        summary,
    )
    save_generated_plan(user_id, events, week_start, source)
    flash(
        f"{len(events)} workouts added using {source}.",
        "success",
    )
    return redirect(url_for("planner.planner", week_start=week_start.isoformat()))


@planner_bp.route("/planner/event", methods=["POST"])
@login_required
def add_planner_event():
    event_day = parse_week_start(
        request.form.get("event_date"),
        get_user_timezone(current_user_id()),
    )
    week_start = event_day - timedelta(days=event_day.weekday())
    try:
        add_personal_planner_event(current_user_id(), request.form)
    except ValueError as error:
        flash(str(error), "error")
    else:
        flash("Personal event added.", "success")
    return redirect(url_for("planner.planner", week_start=week_start.isoformat()))


@planner_bp.route("/planner/event/<int:event_id>/toggle", methods=["POST"])
@login_required
def toggle_planner_event(event_id):
    planner_store.toggle_event(event_id, current_user_id())
    return redirect(request.referrer or url_for("planner.planner"))


@planner_bp.route("/planner/timezone", methods=["POST"])
@login_required
def update_planner_timezone():
    timezone_name = update_user_timezone(
        current_user_id(),
        request.form.get("timezone"),
    )
    flash(f"Planner timezone updated to {timezone_name}.", "success")
    return redirect(
        url_for(
            "planner.planner",
            week_start=request.form.get("week_start") or None,
        )
    )


@planner_bp.route("/planner/calendar.ics")
@login_required
def planner_calendar():
    user_id = current_user_id()
    timezone_name = get_user_timezone(user_id)
    start = parse_week_start(request.args.get("week_start"), timezone_name)
    events = get_planner_events(
        user_id,
        start,
        start + timedelta(days=6),
    )
    return Response(
        build_calendar_ics(events, timezone_name),
        mimetype="text/calendar",
        headers={
            "Content-Disposition": "attachment; filename=runcoach-week.ics"
        },
    )


@planner_bp.route("/planner/email", methods=["POST"])
@login_required
def email_weekly_plan():
    user = current_user()
    timezone_name = get_user_timezone(user["id"])
    start = parse_week_start(request.form.get("week_start"), timezone_name)
    events = get_planner_events(
        user["id"],
        start,
        start + timedelta(days=6),
    )
    if not events:
        flash("Add or generate events before emailing your week.", "error")
        return redirect(url_for("planner.planner", week_start=start.isoformat()))
    sent, message = PlanEmailService().send_week(
        user["email"],
        events,
        build_calendar_ics(events, timezone_name),
        timezone_name,
    )
    flash(message, "success" if sent else "warning")
    return redirect(url_for("planner.planner", week_start=start.isoformat()))
