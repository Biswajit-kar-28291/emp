from datetime import date, datetime

from flask import render_template
from flask import current_app as app
from flask import request, redirect, url_for
from sqlalchemy import or_
from application.database import db
from application.models import (
    Booking,
    BookingHistory,
    Course,
    Evaluation,
    Examination,
    ExaminationSlot,
    ExaminerProfile,
    StudentProfile,
    User,
)


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
            if user.role == "examiner":
                return redirect(url_for("examiner_dashboard", user_id=user.id))
            if user.role == "admin":
                return redirect(url_for("admin_dashboard", user_id=user.id))
            error = "This account has an unsupported role."
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

    now = datetime.now()
    search = request.args.get("search", "").strip()
    exam_type = request.args.get("exam_type", "").strip()
    examinations_query = Examination.query.join(Course).filter(
        Examination.status == "Booking Open",
        Examination.slot_booking_start <= now,
        Examination.slot_booking_end >= now,
        Course.status == "active",
    )
    if search:
        pattern = f"%{search}%"
        examinations_query = examinations_query.filter(
            or_(
                Examination.exam_name.ilike(pattern),
                Examination.exam_type.ilike(pattern),
                Course.course_code.ilike(pattern),
                Course.course_name.ilike(pattern),
            )
        )
    if exam_type:
        examinations_query = examinations_query.filter(Examination.exam_type == exam_type)

    examinations = examinations_query.order_by(Examination.exam_name).all()
    examination_ids = [examination.id for examination in examinations]
    available_slots = []
    if examination_ids:
        available_slots = ExaminationSlot.query.filter(
            ExaminationSlot.examination_id.in_(examination_ids),
            ExaminationSlot.date >= date.today(),
            ExaminationSlot.status == "Available",
            ExaminationSlot.available_seats > 0,
        ).order_by(ExaminationSlot.date, ExaminationSlot.start_time).all()

    bookings = Booking.query.join(ExaminationSlot).filter(
        Booking.student_id == user.id,
        Booking.status == "Booked",
    ).order_by(ExaminationSlot.date, ExaminationSlot.start_time).all()
    upcoming_bookings = [booking for booking in bookings if booking.slot.date >= date.today()]
    published_results = Evaluation.query.join(Booking).filter(
        Booking.student_id == user.id,
        Evaluation.is_published.is_(True),
    ).order_by(Evaluation.published_at.desc()).all()
    exam_types = [row[0] for row in db.session.query(Examination.exam_type).distinct().order_by(Examination.exam_type)]

    return render_template(
        "student/dashboard.html",
        user=user,
        examinations=examinations,
        available_slots=available_slots,
        bookings=bookings,
        upcoming_bookings=upcoming_bookings,
        published_results=published_results,
        exam_types=exam_types,
        search=search,
        selected_exam_type=exam_type,
        message=request.args.get("message"),
        error=request.args.get("error"),
    )


@app.post("/student/<int:user_id>/book/<int:slot_id>")
def book_examination_slot(user_id, slot_id):
    user = db.session.get(User, user_id)
    if user is None or user.role != "student":
        return "Student not found.", 404
    if user.account_status != "active":
        return redirect(url_for("login"))

    slot = db.session.get(ExaminationSlot, slot_id)
    now = datetime.now()
    error = None
    if slot is None:
        error = "The selected examination slot was not found."
    elif slot.examination.status != "Booking Open":
        error = "Booking is not open for this examination."
    elif not (slot.examination.slot_booking_start <= now <= slot.examination.slot_booking_end):
        error = "This examination is outside its booking period."
    elif slot.status != "Available" or slot.available_seats <= 0:
        error = "This examination slot is no longer available."
    elif slot.date < date.today():
        error = "Past examination slots cannot be booked."
    else:
        duplicate = Booking.query.join(ExaminationSlot).filter(
            Booking.student_id == user.id,
            Booking.status == "Booked",
            ExaminationSlot.examination_id == slot.examination_id,
        ).first()
        if duplicate:
            error = "You already have an active booking for this examination."

    if error:
        return redirect(url_for("student_dashboard", user_id=user.id, error=error))

    booking = Booking(student_id=user.id, slot_id=slot.id, status="Booked")
    db.session.add(booking)
    db.session.flush()
    slot.available_seats -= 1
    if slot.available_seats == 0:
        slot.status = "Full"
    db.session.add(
        BookingHistory(
            booking_id=booking.id,
            action="Booked",
            details=f"Booked slot {slot.id} for {slot.examination.exam_name}.",
        )
    )
    db.session.commit()
    return redirect(
        url_for("student_dashboard", user_id=user.id, message="Examination slot booked successfully.")
    )


@app.post("/student/<int:user_id>/cancel/<int:booking_id>")
def cancel_booking(user_id, booking_id):
    user = db.session.get(User, user_id)
    if user is None or user.role != "student":
        return "Student not found.", 404
    if user.account_status != "active":
        return redirect(url_for("login"))

    booking = db.session.get(Booking, booking_id)
    if booking is None or booking.student_id != user.id:
        return "Booking not found.", 404
    if booking.status != "Booked":
        return redirect(
            url_for("student_dashboard", user_id=user.id, error="Only active bookings can be cancelled.")
        )
    if datetime.now() > booking.slot.examination.slot_booking_end:
        return redirect(
            url_for("student_dashboard", user_id=user.id, error="The cancellation deadline has passed.")
        )

    booking.status = "Cancelled"
    booking.slot.available_seats = min(
        booking.slot.available_seats + 1, booking.slot.max_capacity
    )
    if booking.slot.status == "Full":
        booking.slot.status = "Available"
    db.session.add(
        BookingHistory(
            booking_id=booking.id,
            action="Cancelled",
            details=f"Cancelled slot {booking.slot.id} for {booking.slot.examination.exam_name}.",
        )
    )
    db.session.commit()
    return redirect(
        url_for("student_dashboard", user_id=user.id, message="Booking cancelled successfully.")
    )


@app.route("/student/<int:user_id>/history")
def student_booking_history(user_id):
    user = db.session.get(User, user_id)
    if user is None or user.role != "student":
        return "Student not found.", 404
    if user.account_status != "active":
        return redirect(url_for("login"))
    history = BookingHistory.query.join(Booking).filter(
        Booking.student_id == user.id
    ).order_by(BookingHistory.created_at.desc()).all()
    return render_template("student/history.html", user=user, history=history)


@app.route("/student/<int:user_id>/results")
def student_results(user_id):
    user = db.session.get(User, user_id)
    if user is None or user.role != "student":
        return "Student not found.", 404
    if user.account_status != "active":
        return redirect(url_for("login"))
    results = Evaluation.query.join(Booking).filter(
        Booking.student_id == user.id,
        Evaluation.is_published.is_(True),
    ).order_by(Evaluation.published_at.desc()).all()
    return render_template("student/results.html", user=user, results=results)


@app.route("/student/<int:user_id>/profile", methods=["GET", "POST"])
def student_profile(user_id):
    user = db.session.get(User, user_id)
    if user is None or user.role != "student":
        return "Student not found.", 404
    if user.account_status != "active":
        return redirect(url_for("login"))

    error = None
    message = None
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        student_id = request.form.get("student_id", "").strip() or None
        duplicate = None
        if student_id:
            duplicate = StudentProfile.query.filter(
                StudentProfile.student_id == student_id,
                StudentProfile.user_id != user.id,
            ).first()
        if not full_name:
            error = "Full name is required."
        elif duplicate:
            error = "That Student ID is already in use."
        else:
            user.student_profile.full_name = full_name
            user.student_profile.student_id = student_id
            db.session.commit()
            message = "Profile updated successfully."

    return render_template(
        "student/profile.html", user=user, error=error, message=message
    )


@app.route("/examiner/<int:user_id>")
def examiner_dashboard(user_id):
    user = db.session.get(User, user_id)
    if user is None or user.role != "examiner":
        return "Examiner not found.", 404
    if user.account_status != "active":
        return redirect(url_for("login"))

    profile = user.examiner_profile
    if profile is None or not profile.is_approved or not profile.is_active:
        return redirect(url_for("login"))

    return render_template("examiner/dashboard.html", user=user)


@app.route("/admin/<int:user_id>")
def admin_dashboard(user_id):
    user = db.session.get(User, user_id)
    if user is None or user.role != "admin":
        return "Admin not found.", 404
    if user.account_status != "active":
        return redirect(url_for("login"))

    student_count = User.query.filter_by(role="student").count()
    examiner_count = User.query.filter_by(role="examiner").count()
    pending_examiner_count = User.query.filter_by(
        role="examiner", account_status="pending"
    ).count()
    return render_template(
        "admin/dashboard.html",
        user=user,
        student_count=student_count,
        examiner_count=examiner_count,
        pending_examiner_count=pending_examiner_count,
    )


@app.post("/logout")
def logout():
    return redirect(url_for("login"))
