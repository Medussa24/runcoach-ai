import sqlite3
from flask import Blueprint, render_template, redirect, url_for, request, session
from app import (
    seed_demo_user, create_user, establish_user_session,
    DEMO_EMAIL, DEMO_PASSWORD, seed_demo_data, get_user_by_email,
    check_password_hash, reset_demo_account
)

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    seed_demo_user()

    error = None

    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")

        if not email or not password:
            error = "Enter an email and password."
        elif len(password) < 6:
            error = "Use at least 6 characters for the password."
        else:
            try:
                user_id = create_user(email, password)
            except sqlite3.IntegrityError:
                error = "An account with that email already exists."
            else:
                establish_user_session(user_id)
                return redirect(url_for("index", welcome=1))

    return render_template(
        "auth.html",
        mode="signup",
        error=error,
        demo_email=DEMO_EMAIL,
        demo_password=DEMO_PASSWORD,
    )


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    seed_demo_data()

    error = None

    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")
        user = get_user_by_email(email)

        if user and check_password_hash(user["password_hash"], password):
            establish_user_session(user["id"], is_demo=user["email"] == DEMO_EMAIL)
            return redirect(url_for("index", welcome=1))

        error = "Email or password was not correct."

    return render_template(
        "auth.html",
        mode="login",
        error=error,
        demo_email=DEMO_EMAIL,
        demo_password=DEMO_PASSWORD,
    )


@auth_bp.route("/demo-login", methods=["POST"])
def demo_login():
    """Log evaluators into the privacy-safe demo account in one click."""
    demo_user_id = reset_demo_account()
    establish_user_session(demo_user_id, is_demo=True)
    return redirect(url_for("index", welcome=1))


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
