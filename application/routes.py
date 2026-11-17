from flask import render_template
from flask import current_app as app
from flask import request, redirect, url_for
from application.database import db
from application.models import User, StudentProfile, ExaminerProfile


@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    email = ""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if not email or not password:
            error = "Email and password are required."
        elif user is None or user.password != password:
            error = "Invalid email or password."
        elif user.account_status == "pending":
            error = "Your examiner account is waiting for Admin approval."
        elif user.account_status != "active":
            error = "This account is not active."
        else:
            if user.role == "student":
                return redirect(url_for("student_dashboard", user_id=user.id))
            return render_template("auth/login.html", signed_in=True, user=user)
    return render_template("auth/login.html", error=error, email=email)


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        role = request.form.get("role", "")

        if not full_name or not email or not password or not confirm_password or not role:
            error = "All fields are required."
        elif password != confirm_password:
            error = "Passwords do not match."
        elif role not in ("student", "examiner"):
            error = "Invalid role selected."
        elif User.query.filter_by(email=email).first():
            error = "Email already registered."
        else:
            user = User(
                email=email,
                password=password,
                role=role,
                account_status="pending" if role == "examiner" else "active",
            )
            db.session.add(user)
            db.session.flush()

            if role == "student":
                profile = StudentProfile(user_id=user.id, full_name=full_name)
                db.session.add(profile)
            else:
                profile = ExaminerProfile(
                    user_id=user.id,
                    full_name=full_name,
                    is_approved=False,
                    is_active=True,
                )
                db.session.add(profile)

            db.session.commit()
            return redirect(url_for("login"))

    return render_template("auth/register.html", error=error)


@app.route("/student/<int:user_id>")
def student_dashboard(user_id):
    user = db.session.get(User, user_id)
    if user is None or user.role != "student":
        return "Student not found.", 404
    if user.account_status != "active":
        return redirect(url_for("login"))
    return render_template("student/dashboard.html", user=user)


@app.post("/logout")
def logout():
    return redirect(url_for("login"))
