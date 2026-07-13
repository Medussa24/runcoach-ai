from flask import Blueprint, render_template, redirect, url_for, flash, request
from app import (
    login_required, current_user, current_user_id,
    get_health_connections, get_imported_activities, create_health_connection,
    get_database_connection, toggle_health_sync, save_imported_activity,
    convert_imported_activity_to_run
)

integrations_bp = Blueprint("integrations", __name__)

@integrations_bp.route("/integrations")
@login_required
def integrations_page():
    user = current_user()
    user_id = user["id"]

    connections = get_health_connections(user_id)
    connections_map = {conn["provider"]: conn for conn in connections}

    imported_activities = get_imported_activities(user_id)

    for conn in connections_map.values():
        conn["access_token"] = "*" * 12 if conn["access_token"] else None
        conn["refresh_token"] = "*" * 12 if conn["refresh_token"] else None

    return render_template(
        "integrations.html",
        current_user=user,
        connections=connections_map,
        imported_activities=imported_activities
    )


@integrations_bp.route("/integrations/connect/<provider>", methods=["POST"])
@login_required
def connect_mock_provider(provider):
    if provider not in ("strava", "fitbit", "garmin"):
        flash("Invalid provider.", "error")
        return redirect(url_for("integrations.integrations_page"))

    user_id = current_user_id()
    create_health_connection(
        user_id=user_id,
        provider=provider,
        provider_user_id=f"mock-user-{user_id}",
        access_token="mock-access-token",
        refresh_token="mock-refresh-token",
        token_expires_at="2027-01-01 00:00:00",
        sync_enabled=1
    )
    flash(f"Successfully connected to mock {provider.capitalize()}!", "success")
    return redirect(url_for("integrations.integrations_page"))


@integrations_bp.route("/integrations/disconnect/<provider>", methods=["POST"])
@login_required
def disconnect_provider(provider):
    if provider not in ("strava", "fitbit", "garmin"):
        flash("Invalid provider.", "error")
        return redirect(url_for("integrations.integrations_page"))

    user_id = current_user_id()
    connection = get_database_connection()
    try:
        connection.execute(
            "DELETE FROM health_connections WHERE user_id = ? AND provider = ?",
            (user_id, provider)
        )
        connection.commit()
    finally:
        connection.close()

    flash(f"Disconnected from {provider.capitalize()}.", "success")
    return redirect(url_for("integrations.integrations_page"))


@integrations_bp.route("/integrations/toggle/<provider>", methods=["POST"])
@login_required
def toggle_provider_sync(provider):
    user_id = current_user_id()
    res = toggle_health_sync(user_id, provider)
    if res is not None:
        status = "enabled" if res else "disabled"
        flash(f"Syncing {status} for {provider.capitalize()}.", "success")
    else:
        flash("Connection not found.", "error")
    return redirect(url_for("integrations.integrations_page"))


@integrations_bp.route("/integrations/sync", methods=["POST"])
@login_required
def sync_activities():
    user_id = current_user_id()
    connections = get_health_connections(user_id)
    active_providers = [c["provider"] for c in connections if c["sync_enabled"]]

    if not active_providers:
        flash("No active connected services with sync enabled.", "error")
        return redirect(url_for("integrations.integrations_page"))

    import random
    from datetime import datetime, timedelta

    imported_count = 0
    errors_count = 0

    for provider in active_providers:
        external_id = f"act-{random.randint(100000, 999999)}"
        dist = round(random.uniform(2.0, 6.0), 2)
        dur = round(dist * random.uniform(8.0, 11.0), 2)
        pace_val = dur / dist
        start = (datetime.now() - timedelta(days=random.randint(0, 5))).strftime("%Y-%m-%d %H:%M:%S")

        try:
            save_imported_activity(
                user_id=user_id,
                provider=provider,
                external_activity_id=external_id,
                activity_type="run",
                start_time=start,
                end_time=None,
                distance=dist,
                duration=dur,
                pace=pace_val,
                avg_heart_rate=random.randint(130, 165),
                max_heart_rate=random.randint(170, 185),
                calories=random.randint(200, 600),
                steps=random.randint(4000, 12000),
                source_name=f"{provider.capitalize()} Wearable",
                raw_summary=f"Afternoon run synced via mock {provider.capitalize()} webhook."
            )
            imported_count += 1
        except Exception:
            errors_count += 1

    if imported_count > 0:
        flash(f"Sync complete! Imported {imported_count} new activity/activities.", "success")
    elif errors_count > 0:
        flash("Sync complete. No new workouts found (duplicates skipped).", "success")
    else:
        flash("No workouts found on remote servers.", "success")

    return redirect(url_for("integrations.integrations_page"))


@integrations_bp.route("/integrations/activity/<int:activity_id>/approve", methods=["POST"])
@login_required
def approve_imported_activity(activity_id):
    user_id = current_user_id()
    res = convert_imported_activity_to_run(user_id, activity_id)
    if res:
        flash("Activity approved and saved to your run history!", "success")
    else:
        flash("Unable to approve activity (already approved or not found).", "error")
    return redirect(url_for("integrations.integrations_page"))
