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
    EvaluationScore,
    Examination,
    ExaminerAssignment,
    ExaminationRubric,
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
    error = request.args.get("error")
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


def get_active_examiner(user_id):
    user = db.session.get(User, user_id)
    if user is None or user.role != "examiner":
        return None, "Examiner access is only available to Examiner accounts."
    if user.account_status != "active":
        return None, "Your Examiner account is pending or deactivated."
    profile = user.examiner_profile
    if profile is None or not profile.is_approved or not profile.is_active:
        return None, "Your Examiner profile is not approved and active."
    return user, None


def examiner_or_login(user_id):
    user, error = get_active_examiner(user_id)
    if error:
        return None, redirect(url_for("login", error=error))
    return user, None


def examiner_assignment(user_id, examination_id):
    return ExaminerAssignment.query.filter_by(
        examiner_id=user_id, examination_id=examination_id, status="active"
    ).first()


def slot_form_values():
    try:
        slot_date = datetime.strptime(request.form.get("date", ""), "%Y-%m-%d").date()
        start_time = datetime.strptime(request.form.get("start_time", ""), "%H:%M").time()
        end_time = datetime.strptime(request.form.get("end_time", ""), "%H:%M").time()
        capacity = int(request.form.get("max_capacity", ""))
    except (TypeError, ValueError):
        return None, "Enter a valid date, start time, end time, and capacity."
    return (slot_date, start_time, end_time, capacity), None


def validate_slot(user_id, examination, values, slot_id=None):
    slot_date, start_time, end_time, capacity = values
    now = datetime.now()
    slot_start = datetime.combine(slot_date, start_time)
    if examination is None or examiner_assignment(user_id, examination.id) is None:
        return "You may create slots only for examinations assigned to you."
    if examination.status != "Slot Creation":
        return "This examination is not in the Slot Creation status."
    if not (examination.slot_creation_start <= now <= examination.slot_creation_end):
        return "Slot creation is outside the permitted period."
    if slot_date < date.today():
        return "The examination date cannot be in the past."
    if end_time <= start_time:
        return "End time must be after start time."
    if capacity <= 0:
        return "Maximum capacity must be a positive number."
    if slot_start < examination.slot_booking_end:
        return "The slot must begin after the Student booking period ends."
    conflicts = ExaminationSlot.query.filter(
        ExaminationSlot.examiner_id == user_id,
        ExaminationSlot.date == slot_date,
        ExaminationSlot.status != "Cancelled",
        ExaminationSlot.start_time < end_time,
        ExaminationSlot.end_time > start_time,
    )
    if slot_id is not None:
        conflicts = conflicts.filter(ExaminationSlot.id != slot_id)
    if conflicts.first():
        return "This slot overlaps another slot in your schedule."
    return None


@app.route("/examiner/<int:user_id>")
def examiner_dashboard(user_id):
    user, response = examiner_or_login(user_id)
    if response:
        return response
    assignments = ExaminerAssignment.query.filter_by(examiner_id=user.id, status="active").all()
    slots = ExaminationSlot.query.filter_by(examiner_id=user.id).all()
    bookings = Booking.query.join(ExaminationSlot).filter(
        ExaminationSlot.examiner_id == user.id,
        Booking.status.in_(("Booked", "Completed")),
    ).all()
    pending_count = sum(1 for booking in bookings if booking.evaluation is None)
    completed_count = sum(1 for booking in bookings if booking.evaluation and booking.evaluation.is_finalized)
    return render_template(
        "examiner/dashboard.html", user=user, assignments=assignments, slots=slots,
        booked_count=len(bookings), pending_count=pending_count, completed_count=completed_count,
        message=request.args.get("message"), error=request.args.get("error"),
    )


@app.route("/examiner/<int:user_id>/examinations")
def examiner_examinations(user_id):
    user, response = examiner_or_login(user_id)
    if response:
        return response
    assignments = ExaminerAssignment.query.filter_by(examiner_id=user.id, status="active").all()
    return render_template("examiner/examinations.html", user=user, assignments=assignments)


@app.route("/examiner/<int:user_id>/slots", methods=["GET", "POST"])
def examiner_slots(user_id):
    user, response = examiner_or_login(user_id)
    if response:
        return response
    if request.method == "POST":
        try:
            examination_id = int(request.form.get("examination_id", ""))
        except ValueError:
            examination_id = 0
        examination = db.session.get(Examination, examination_id)
        values, error = slot_form_values()
        if not error:
            error = validate_slot(user.id, examination, values)
        if error:
            return redirect(url_for("examiner_slots", user_id=user.id, error=error))
        slot_date, start_time, end_time, capacity = values
        db.session.add(ExaminationSlot(
            examination_id=examination.id, examiner_id=user.id, date=slot_date,
            start_time=start_time, end_time=end_time, max_capacity=capacity,
            available_seats=capacity, status="Available",
        ))
        db.session.commit()
        return redirect(url_for("examiner_slots", user_id=user.id, message="Slot created successfully."))
    assignments = ExaminerAssignment.query.filter_by(examiner_id=user.id, status="active").all()
    slots = ExaminationSlot.query.filter_by(examiner_id=user.id).order_by(
        ExaminationSlot.date, ExaminationSlot.start_time
    ).all()
    return render_template(
        "examiner/slots.html", user=user, assignments=assignments, slots=slots,
        message=request.args.get("message"), error=request.args.get("error"),
    )


@app.route("/examiner/<int:user_id>/slots/<int:slot_id>/edit", methods=["GET", "POST"])
def edit_examiner_slot(user_id, slot_id):
    user, response = examiner_or_login(user_id)
    if response:
        return response
    slot = db.session.get(ExaminationSlot, slot_id)
    if slot is None or slot.examiner_id != user.id:
        return "Slot not found.", 404
    active_bookings = sum(1 for booking in slot.bookings if booking.status in ("Booked", "Completed"))
    if datetime.now() >= slot.examination.slot_booking_start or active_bookings:
        return redirect(url_for("examiner_slots", user_id=user.id, error="Slots cannot be changed after booking begins or while active bookings exist."))
    if request.method == "POST":
        values, error = slot_form_values()
        if not error:
            error = validate_slot(user.id, slot.examination, values, slot.id)
        if error:
            return render_template("examiner/slot_edit.html", user=user, slot=slot, error=error)
        slot_date, start_time, end_time, capacity = values
        slot.date, slot.start_time, slot.end_time = slot_date, start_time, end_time
        slot.max_capacity = capacity
        slot.available_seats = capacity
        slot.status = "Available"
        db.session.commit()
        return redirect(url_for("examiner_slots", user_id=user.id, message="Slot updated successfully."))
    return render_template("examiner/slot_edit.html", user=user, slot=slot, error=None)


@app.post("/examiner/<int:user_id>/slots/<int:slot_id>/remove")
def remove_examiner_slot(user_id, slot_id):
    user, response = examiner_or_login(user_id)
    if response:
        return response
    slot = db.session.get(ExaminationSlot, slot_id)
    if slot is None or slot.examiner_id != user.id:
        return "Slot not found.", 404
    active_bookings = any(booking.status in ("Booked", "Completed") for booking in slot.bookings)
    if datetime.now() >= slot.examination.slot_booking_start or active_bookings:
        return redirect(url_for("examiner_slots", user_id=user.id, error="Slots cannot be removed after booking begins or while active bookings exist."))
    if slot.bookings:
        slot.status = "Cancelled"
        message = "Slot cancelled because booking history exists."
    else:
        db.session.delete(slot)
        message = "Slot removed successfully."
    db.session.commit()
    return redirect(url_for("examiner_slots", user_id=user.id, message=message))


@app.route("/examiner/<int:user_id>/students")
def examiner_students(user_id):
    user, response = examiner_or_login(user_id)
    if response:
        return response
    bookings = Booking.query.join(ExaminationSlot).filter(
        ExaminationSlot.examiner_id == user.id
    ).order_by(ExaminationSlot.date, ExaminationSlot.start_time).all()
    return render_template("examiner/students.html", user=user, bookings=bookings)


@app.route("/examiner/<int:user_id>/evaluations")
def examiner_evaluations(user_id):
    user, response = examiner_or_login(user_id)
    if response:
        return response
    bookings = Booking.query.join(ExaminationSlot).join(ExaminerAssignment,
        (ExaminerAssignment.examination_id == ExaminationSlot.examination_id) &
        (ExaminerAssignment.examiner_id == user.id) & (ExaminerAssignment.status == "active")
    ).filter(ExaminationSlot.examiner_id == user.id, Booking.status.in_(("Booked", "Completed"))).all()
    return render_template("examiner/evaluations.html", user=user, bookings=bookings,
                           message=request.args.get("message"), error=request.args.get("error"))


@app.route("/examiner/<int:user_id>/evaluations/<int:booking_id>", methods=["GET", "POST"])
def evaluate_booking(user_id, booking_id):
    user, response = examiner_or_login(user_id)
    if response:
        return response
    booking = db.session.get(Booking, booking_id)
    if (booking is None or booking.status not in ("Booked", "Completed") or
            booking.slot.examiner_id != user.id or
            examiner_assignment(user.id, booking.slot.examination_id) is None):
        return "Eligible booking not found.", 404
    evaluation = booking.evaluation
    if evaluation and evaluation.examiner_id != user.id:
        return "Eligible booking not found.", 404
    if evaluation and (evaluation.is_published or evaluation.is_finalized):
        return redirect(url_for("examiner_evaluations", user_id=user.id, error="Finalized or published evaluations cannot be edited."))
    rubrics = ExaminationRubric.query.filter_by(examination_id=booking.slot.examination_id).order_by(ExaminationRubric.id).all()
    if request.method == "POST":
        if not rubrics:
            return render_template("examiner/evaluation_form.html", user=user, booking=booking, rubrics=rubrics, evaluation=evaluation, error="This examination has no rubric criteria.")
        scores = []
        error = None
        for rubric in rubrics:
            try:
                marks = float(request.form.get(f"marks_{rubric.id}", ""))
            except ValueError:
                error = "Enter a valid mark for every rubric criterion."
                break
            if marks < 0 or marks > rubric.maximum_marks:
                error = f"Marks for {rubric.criterion_name} must be between 0 and {rubric.maximum_marks}."
                break
            scores.append((rubric, marks, request.form.get(f"remarks_{rubric.id}", "").strip()))
        total = sum(item[1] for item in scores)
        if not error and total > booking.slot.examination.max_marks:
            error = "The calculated total exceeds the examination maximum marks."
        if error:
            return render_template("examiner/evaluation_form.html", user=user, booking=booking, rubrics=rubrics, evaluation=evaluation, error=error)
        if evaluation is None:
            evaluation = Evaluation(booking_id=booking.id, examiner_id=user.id, total_marks=total)
            db.session.add(evaluation)
            db.session.flush()
        evaluation.total_marks = total
        evaluation.remarks = request.form.get("remarks", "").strip() or None
        evaluation.is_finalized = request.form.get("action") == "submit"
        EvaluationScore.query.filter_by(evaluation_id=evaluation.id).delete()
        for rubric, marks, remarks in scores:
            db.session.add(EvaluationScore(evaluation_id=evaluation.id, rubric_id=rubric.id, awarded_marks=marks, remarks=remarks or None))
        db.session.commit()
        message = "Evaluation submitted for Admin publication." if evaluation.is_finalized else "Evaluation draft saved."
        return redirect(url_for("examiner_evaluations", user_id=user.id, message=message))
    return render_template("examiner/evaluation_form.html", user=user, booking=booking, rubrics=rubrics, evaluation=evaluation, error=None)


@app.route("/examiner/<int:user_id>/profile", methods=["GET", "POST"])
def examiner_profile(user_id):
    user, response = examiner_or_login(user_id)
    if response:
        return response
    error = None
    message = None
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        examiner_id = request.form.get("examiner_id", "").strip() or None
        duplicate = ExaminerProfile.query.filter(ExaminerProfile.examiner_id == examiner_id, ExaminerProfile.user_id != user.id).first() if examiner_id else None
        if not full_name:
            error = "Full name is required."
        elif duplicate:
            error = "That Examiner ID is already in use."
        else:
            user.examiner_profile.full_name = full_name
            user.examiner_profile.examiner_id = examiner_id
            user.examiner_profile.contact_details = request.form.get("contact_details", "").strip() or None
            user.examiner_profile.department = request.form.get("department", "").strip() or None
            db.session.commit()
            message = "Profile updated successfully."
    return render_template("examiner/profile.html", user=user, error=error, message=message)


EXAM_TYPES = ("Viva", "Practical", "Project Demo", "Assessment")
EXAM_STATUSES = ("Draft", "Slot Creation", "Booking Open", "Closed", "Completed")
NEXT_EXAM_STATUSES = {
    "Draft": ("Slot Creation",),
    "Slot Creation": ("Draft", "Booking Open"),
    "Booking Open": ("Slot Creation", "Closed"),
    "Closed": ("Booking Open", "Completed"),
    "Completed": (),
}


def get_admin(user_id):
    user = db.session.get(User, user_id)
    if user is None or user.role != "admin":
        return None
    if user.account_status != "active":
        return None
    return user


def admin_or_login(user_id):
    user = get_admin(user_id)
    if user is None:
        return None, redirect(url_for("login", error="Active Admin access is required."))
    return user, None


def parse_datetime(value):
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except (TypeError, ValueError):
        return None


def examination_form_values():
    return {
        "course_id": request.form.get("course_id", "").strip(),
        "exam_name": request.form.get("exam_name", "").strip(),
        "exam_type": request.form.get("exam_type", "").strip(),
        "duration": request.form.get("duration", "").strip(),
        "max_marks": request.form.get("max_marks", "").strip(),
        "slot_creation_start": request.form.get("slot_creation_start", "").strip(),
        "slot_creation_end": request.form.get("slot_creation_end", "").strip(),
        "slot_booking_start": request.form.get("slot_booking_start", "").strip(),
        "slot_booking_end": request.form.get("slot_booking_end", "").strip(),
        "status": request.form.get("status", "Draft").strip(),
    }


def validate_examination(values, existing=None):
    required = all(values.values())
    if not required:
        return "All examination fields are required.", None
    course = db.session.get(Course, int(values["course_id"])) if values["course_id"].isdigit() else None
    if course is None:
        return "Select a valid course.", None
    if values["exam_type"] not in EXAM_TYPES or values["status"] not in EXAM_STATUSES:
        return "Select a valid examination type and status.", None
    try:
        duration, max_marks = int(values["duration"]), int(values["max_marks"])
    except ValueError:
        return "Duration and maximum marks must be whole numbers.", None
    if duration <= 0 or max_marks <= 0:
        return "Duration and maximum marks must be positive.", None
    times = [parse_datetime(values[key]) for key in ("slot_creation_start", "slot_creation_end", "slot_booking_start", "slot_booking_end")]
    if any(item is None for item in times):
        return "Enter valid start and end date/times.", None
    creation_start, creation_end, booking_start, booking_end = times
    if creation_start >= creation_end or booking_start >= booking_end:
        return "Each start date/time must be before its end date/time.", None
    if creation_end > booking_start:
        return "Slot creation must finish before or when booking opens.", None
    if existing and values["status"] != existing.status:
        return "Use the lifecycle controls to change examination status.", None
    if existing is None and values["status"] != "Draft":
        return "A new examination must start in Draft status.", None
    return None, (course, duration, max_marks, times)


@app.route("/admin/<int:user_id>")
def admin_dashboard(user_id):
    user, response = admin_or_login(user_id)
    if response:
        return response
    counts = {
        "courses": Course.query.count(), "examinations": Examination.query.count(),
        "examiners": User.query.filter_by(role="examiner").count(),
        "students": User.query.filter_by(role="student").count(),
        "slots": ExaminationSlot.query.count(), "bookings": Booking.query.count(),
        "pending": User.query.filter_by(role="examiner", account_status="pending").count(),
    }
    return render_template("admin/dashboard.html", user=user, counts=counts)


@app.route("/admin/<int:user_id>/courses", methods=["GET", "POST"])
def admin_courses(user_id):
    user, response = admin_or_login(user_id)
    if response: return response
    error = None
    if request.method == "POST":
        code = request.form.get("course_code", "").strip().upper()
        name = request.form.get("course_name", "").strip()
        if not code or not name:
            error = "Course code and name are required."
        elif Course.query.filter(db.func.lower(Course.course_code) == code.lower()).first():
            error = "Course code already exists."
        else:
            db.session.add(Course(course_code=code, course_name=name, description=request.form.get("description", "").strip() or None, status="active"))
            db.session.commit()
            return redirect(url_for("admin_courses", user_id=user.id, message="Course created."))
    search = request.args.get("search", "").strip()
    query = Course.query
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(Course.course_code.ilike(pattern), Course.course_name.ilike(pattern)))
    return render_template("admin/courses.html", user=user, courses=query.order_by(Course.course_code).all(), search=search, error=error, message=request.args.get("message"))


@app.route("/admin/<int:user_id>/courses/<int:course_id>/edit", methods=["GET", "POST"])
def admin_edit_course(user_id, course_id):
    user, response = admin_or_login(user_id)
    if response: return response
    course = db.session.get(Course, course_id)
    if course is None: return "Course not found.", 404
    error = None
    if request.method == "POST":
        code, name = request.form.get("course_code", "").strip().upper(), request.form.get("course_name", "").strip()
        duplicate = Course.query.filter(db.func.lower(Course.course_code) == code.lower(), Course.id != course.id).first() if code else None
        if not code or not name: error = "Course code and name are required."
        elif duplicate: error = "Course code already exists."
        else:
            course.course_code, course.course_name = code, name
            course.description = request.form.get("description", "").strip() or None
            db.session.commit()
            return redirect(url_for("admin_courses", user_id=user.id, message="Course updated."))
    return render_template("admin/course_form.html", user=user, course=course, error=error)


@app.post("/admin/<int:user_id>/courses/<int:course_id>/status")
def admin_course_status(user_id, course_id):
    user, response = admin_or_login(user_id)
    if response: return response
    course = db.session.get(Course, course_id)
    if course is None: return "Course not found.", 404
    course.status = "inactive" if course.status == "active" else "active"
    db.session.commit()
    return redirect(url_for("admin_courses", user_id=user.id, message="Course status updated."))


@app.route("/admin/<int:user_id>/courses/<int:course_id>/remove", methods=["GET", "POST"])
def admin_remove_course(user_id, course_id):
    user, response = admin_or_login(user_id)
    if response: return response
    course = db.session.get(Course, course_id)
    if course is None: return "Course not found.", 404
    blocked = Examination.query.filter_by(course_id=course.id).first() is not None
    if request.method == "POST" and not blocked:
        db.session.delete(course); db.session.commit()
        return redirect(url_for("admin_courses", user_id=user.id, message="Course removed."))
    return render_template("admin/confirm.html", user=user, title="Remove course", item=f"{course.course_code} - {course.course_name}", blocked=blocked, blocked_message="This course has examination history and cannot be removed.", cancel_url=url_for("admin_courses", user_id=user.id))


@app.route("/admin/<int:user_id>/examinations")
def admin_examinations(user_id):
    user, response = admin_or_login(user_id)
    if response: return response
    search, status = request.args.get("search", "").strip(), request.args.get("status", "").strip()
    query = Examination.query.join(Course)
    if search:
        pattern = f"%{search}%"; query = query.filter(or_(Examination.exam_name.ilike(pattern), Examination.exam_type.ilike(pattern), Course.course_code.ilike(pattern), Course.course_name.ilike(pattern)))
    if status in EXAM_STATUSES: query = query.filter(Examination.status == status)
    return render_template("admin/examinations.html", user=user, examinations=query.order_by(Examination.id.desc()).all(), statuses=EXAM_STATUSES, search=search, selected_status=status, message=request.args.get("message"))


@app.route("/admin/<int:user_id>/examinations/new", methods=["GET", "POST"])
@app.route("/admin/<int:user_id>/examinations/<int:examination_id>/edit", methods=["GET", "POST"])
def admin_examination_form(user_id, examination_id=None):
    user, response = admin_or_login(user_id)
    if response: return response
    examination = db.session.get(Examination, examination_id) if examination_id else None
    if examination_id and examination is None: return "Examination not found.", 404
    values, error = examination_form_values() if request.method == "POST" else {}, None
    if request.method == "POST":
        error, parsed = validate_examination(values, examination)
        if not error:
            course, duration, max_marks, times = parsed
            examination = examination or Examination()
            examination.course_id, examination.exam_name, examination.exam_type = course.id, values["exam_name"], values["exam_type"]
            examination.duration, examination.max_marks = duration, max_marks
            examination.slot_creation_start, examination.slot_creation_end, examination.slot_booking_start, examination.slot_booking_end = times
            examination.status = values["status"]
            db.session.add(examination); db.session.commit()
            return redirect(url_for("admin_examinations", user_id=user.id, message="Examination saved."))
    return render_template("admin/examination_form.html", user=user, examination=examination, courses=Course.query.order_by(Course.course_code).all(), exam_types=EXAM_TYPES, statuses=EXAM_STATUSES, values=values, error=error)


@app.route("/admin/<int:user_id>/examinations/<int:examination_id>/remove", methods=["GET", "POST"])
def admin_remove_examination(user_id, examination_id):
    user, response = admin_or_login(user_id)
    if response: return response
    examination = db.session.get(Examination, examination_id)
    if examination is None: return "Examination not found.", 404
    blocked = bool(examination.slots or examination.assignments or examination.rubrics)
    if request.method == "POST" and not blocked:
        db.session.delete(examination); db.session.commit()
        return redirect(url_for("admin_examinations", user_id=user.id, message="Examination removed."))
    return render_template("admin/confirm.html", user=user, title="Remove examination", item=examination.exam_name, blocked=blocked, blocked_message="Assignments, rubrics, or slot history depend on this examination.", cancel_url=url_for("admin_examinations", user_id=user.id))


@app.post("/admin/<int:user_id>/examinations/<int:examination_id>/status")
def admin_examination_status(user_id, examination_id):
    user, response = admin_or_login(user_id)
    if response: return response
    examination = db.session.get(Examination, examination_id)
    target = request.form.get("status", "")
    if examination is None: return "Examination not found.", 404
    if target not in NEXT_EXAM_STATUSES.get(examination.status, ()):
        return redirect(url_for("admin_examinations", user_id=user.id, message="Invalid lifecycle transition."))
    now = datetime.now()
    if target == "Slot Creation" and not (examination.slot_creation_start <= now <= examination.slot_creation_end):
        return redirect(url_for("admin_examinations", user_id=user.id, message="Slot creation is outside its configured timeline."))
    if target == "Booking Open" and not (examination.slot_booking_start <= now <= examination.slot_booking_end):
        return redirect(url_for("admin_examinations", user_id=user.id, message="Booking is outside its configured timeline."))
    examination.status = target; db.session.commit()
    return redirect(url_for("admin_examinations", user_id=user.id, message="Examination status updated."))


@app.route("/admin/<int:user_id>/examinations/<int:examination_id>/rubrics", methods=["GET", "POST"])
def admin_rubrics(user_id, examination_id):
    user, response = admin_or_login(user_id)
    if response: return response
    examination = db.session.get(Examination, examination_id)
    if examination is None: return "Examination not found.", 404
    error = None
    if request.method == "POST":
        name = request.form.get("criterion_name", "").strip()
        try: marks, weightage = int(request.form.get("maximum_marks", "")), int(request.form.get("weightage", ""))
        except ValueError: marks = weightage = 0
        current_total = sum(item.maximum_marks for item in examination.rubrics)
        current_weightage = sum(item.weightage for item in examination.rubrics)
        if not name or marks <= 0 or not 1 <= weightage <= 100: error = "Enter a name, positive marks, and weightage from 1 to 100."
        elif current_total + marks > examination.max_marks: error = "Rubric marks cannot exceed the examination maximum marks."
        elif current_weightage + weightage > 100: error = "Total rubric weightage cannot exceed 100%."
        else:
            db.session.add(ExaminationRubric(examination_id=examination.id, criterion_name=name, maximum_marks=marks, weightage=weightage, description=request.form.get("description", "").strip() or None)); db.session.commit()
            return redirect(url_for("admin_rubrics", user_id=user.id, examination_id=examination.id, message="Rubric criterion added."))
    return render_template("admin/rubrics.html", user=user, examination=examination, error=error, message=request.args.get("message"))


@app.route("/admin/<int:user_id>/rubrics/<int:rubric_id>/edit", methods=["GET", "POST"])
def admin_edit_rubric(user_id, rubric_id):
    user, response = admin_or_login(user_id)
    if response: return response
    rubric = db.session.get(ExaminationRubric, rubric_id)
    if rubric is None: return "Rubric not found.", 404
    error = None
    if request.method == "POST":
        name = request.form.get("criterion_name", "").strip()
        try: marks, weightage = int(request.form.get("maximum_marks", "")), int(request.form.get("weightage", ""))
        except ValueError: marks = weightage = 0
        other_total = sum(item.maximum_marks for item in rubric.examination.rubrics if item.id != rubric.id)
        other_weightage = sum(item.weightage for item in rubric.examination.rubrics if item.id != rubric.id)
        if not name or marks <= 0 or not 1 <= weightage <= 100: error = "Enter valid rubric values."
        elif other_total + marks > rubric.examination.max_marks: error = "Rubric marks cannot exceed the examination maximum marks."
        elif other_weightage + weightage > 100: error = "Total rubric weightage cannot exceed 100%."
        else:
            rubric.criterion_name, rubric.maximum_marks, rubric.weightage = name, marks, weightage
            rubric.description = request.form.get("description", "").strip() or None; db.session.commit()
            return redirect(url_for("admin_rubrics", user_id=user.id, examination_id=rubric.examination_id, message="Rubric updated."))
    return render_template("admin/rubric_form.html", user=user, rubric=rubric, error=error)


@app.route("/admin/<int:user_id>/rubrics/<int:rubric_id>/remove", methods=["GET", "POST"])
def admin_remove_rubric(user_id, rubric_id):
    user, response = admin_or_login(user_id)
    if response: return response
    rubric = db.session.get(ExaminationRubric, rubric_id)
    if rubric is None: return "Rubric not found.", 404
    blocked = EvaluationScore.query.filter_by(rubric_id=rubric.id).first() is not None
    exam_id = rubric.examination_id
    if request.method == "POST" and not blocked:
        db.session.delete(rubric); db.session.commit(); return redirect(url_for("admin_rubrics", user_id=user.id, examination_id=exam_id, message="Rubric removed."))
    return render_template("admin/confirm.html", user=user, title="Remove rubric", item=rubric.criterion_name, blocked=blocked, blocked_message="Evaluation scores depend on this criterion.", cancel_url=url_for("admin_rubrics", user_id=user.id, examination_id=exam_id))


@app.route("/admin/<int:user_id>/examiners")
def admin_examiners(user_id):
    user, response = admin_or_login(user_id)
    if response: return response
    search, status = request.args.get("search", "").strip(), request.args.get("status", "").strip()
    query = User.query.join(ExaminerProfile).filter(User.role == "examiner")
    if search:
        pattern=f"%{search}%"; query=query.filter(or_(User.email.ilike(pattern), ExaminerProfile.full_name.ilike(pattern), ExaminerProfile.examiner_id.ilike(pattern), ExaminerProfile.department.ilike(pattern)))
    if status in ("active", "pending", "deactivated"): query=query.filter(User.account_status == status)
    return render_template("admin/examiners.html", user=user, examiners=query.order_by(ExaminerProfile.full_name).all(), search=search, selected_status=status, message=request.args.get("message"))


@app.route("/admin/<int:user_id>/examiners/<int:examiner_id>/edit", methods=["GET", "POST"])
def admin_edit_examiner(user_id, examiner_id):
    user, response = admin_or_login(user_id)
    if response: return response
    examiner = db.session.get(User, examiner_id)
    if examiner is None or examiner.role != "examiner" or examiner.examiner_profile is None: return "Examiner not found.", 404
    error = None
    if request.method == "POST":
        profile, requested_id = examiner.examiner_profile, request.form.get("examiner_id", "").strip() or None
        duplicate = ExaminerProfile.query.filter(ExaminerProfile.examiner_id == requested_id, ExaminerProfile.id != profile.id).first() if requested_id else None
        if not request.form.get("full_name", "").strip(): error = "Full name is required."
        elif duplicate: error = "Examiner ID is already in use."
        else:
            profile.full_name, profile.examiner_id = request.form.get("full_name").strip(), requested_id
            profile.department, profile.contact_details = request.form.get("department", "").strip() or None, request.form.get("contact_details", "").strip() or None
            db.session.commit(); return redirect(url_for("admin_examiners", user_id=user.id, message="Examiner updated."))
    return render_template("admin/examiner_form.html", user=user, examiner=examiner, error=error)


@app.post("/admin/<int:user_id>/examiners/<int:examiner_id>/status")
def admin_examiner_status(user_id, examiner_id):
    user, response = admin_or_login(user_id)
    if response: return response
    examiner, action = db.session.get(User, examiner_id), request.form.get("action")
    if examiner is None or examiner.role != "examiner" or examiner.examiner_profile is None: return "Examiner not found.", 404
    profile = examiner.examiner_profile
    if action in ("approve", "reactivate"):
        examiner.account_status, profile.is_approved, profile.is_active = "active", True, True
    elif action in ("reject", "deactivate"):
        examiner.account_status, profile.is_approved, profile.is_active = "deactivated", False, False
    else: return "Invalid status action.", 400
    db.session.commit(); return redirect(url_for("admin_examiners", user_id=user.id, message="Examiner status updated."))


@app.route("/admin/<int:user_id>/assignments", methods=["GET", "POST"])
def admin_assignments(user_id):
    user, response = admin_or_login(user_id)
    if response: return response
    error = None
    if request.method == "POST":
        examination = db.session.get(Examination, request.form.get("examination_id", type=int))
        examiner = db.session.get(User, request.form.get("examiner_id", type=int))
        if examination is None or examiner is None or examiner.role != "examiner" or examiner.account_status != "active" or not examiner.examiner_profile or not examiner.examiner_profile.is_approved or not examiner.examiner_profile.is_active:
            error = "Select an active, approved Examiner and a valid examination."
        elif ExaminerAssignment.query.filter_by(examination_id=examination.id, examiner_id=examiner.id).first(): error = "This Examiner is already assigned to that examination."
        else:
            db.session.add(ExaminerAssignment(examination_id=examination.id, examiner_id=examiner.id)); db.session.commit(); return redirect(url_for("admin_assignments", user_id=user.id, message="Examiner assigned."))
    examiners = User.query.join(ExaminerProfile).filter(User.role == "examiner", User.account_status == "active", ExaminerProfile.is_approved.is_(True), ExaminerProfile.is_active.is_(True)).order_by(ExaminerProfile.full_name).all()
    return render_template("admin/assignments.html", user=user, assignments=ExaminerAssignment.query.order_by(ExaminerAssignment.id.desc()).all(), examinations=Examination.query.order_by(Examination.exam_name).all(), examiners=examiners, error=error, message=request.args.get("message"))


@app.route("/admin/<int:user_id>/assignments/<int:assignment_id>/remove", methods=["GET", "POST"])
def admin_remove_assignment(user_id, assignment_id):
    user, response = admin_or_login(user_id)
    if response: return response
    assignment = db.session.get(ExaminerAssignment, assignment_id)
    if assignment is None: return "Assignment not found.", 404
    blocked = ExaminationSlot.query.filter_by(examination_id=assignment.examination_id, examiner_id=assignment.examiner_id).first() is not None
    if request.method == "POST" and not blocked:
        db.session.delete(assignment); db.session.commit(); return redirect(url_for("admin_assignments", user_id=user.id, message="Assignment removed."))
    return render_template("admin/confirm.html", user=user, title="Remove assignment", item=f"{assignment.examiner.email} - {assignment.examination.exam_name}", blocked=blocked, blocked_message="Slot or booking history depends on this assignment.", cancel_url=url_for("admin_assignments", user_id=user.id))


@app.route("/admin/<int:user_id>/students")
def admin_students(user_id):
    user, response = admin_or_login(user_id)
    if response: return response
    search=request.args.get("search", "").strip(); query=User.query.join(StudentProfile).filter(User.role == "student")
    if search:
        pattern=f"%{search}%"; query=query.filter(or_(User.email.ilike(pattern), StudentProfile.full_name.ilike(pattern), StudentProfile.student_id.ilike(pattern)))
    return render_template("admin/students.html", user=user, students=query.order_by(StudentProfile.full_name).all(), search=search)


@app.route("/admin/<int:user_id>/slots")
def admin_slots(user_id):
    user, response = admin_or_login(user_id)
    if response: return response
    query=ExaminationSlot.query.join(Examination).join(User, ExaminationSlot.examiner_id == User.id).outerjoin(ExaminerProfile)
    examination_id=request.args.get("examination_id", type=int); examiner_id=request.args.get("examiner_id", type=int); status=request.args.get("status", "").strip(); slot_date=request.args.get("date", "").strip()
    if examination_id: query=query.filter(ExaminationSlot.examination_id == examination_id)
    if examiner_id: query=query.filter(ExaminationSlot.examiner_id == examiner_id)
    if status: query=query.filter(ExaminationSlot.status == status)
    if slot_date:
        try: query=query.filter(ExaminationSlot.date == datetime.strptime(slot_date, "%Y-%m-%d").date())
        except ValueError: pass
    return render_template("admin/slots.html", user=user, slots=query.order_by(ExaminationSlot.date.desc(), ExaminationSlot.start_time).all(), examinations=Examination.query.order_by(Examination.exam_name).all(), examiners=User.query.filter_by(role="examiner").all(), selected_examination=examination_id, selected_examiner=examiner_id, selected_status=status, selected_date=slot_date, message=request.args.get("message"))


@app.route("/admin/<int:user_id>/slots/<int:slot_id>/reassign", methods=["GET", "POST"])
def admin_reassign_slot(user_id, slot_id):
    user, response = admin_or_login(user_id)
    if response: return response
    slot = db.session.get(ExaminationSlot, slot_id)
    if slot is None: return "Slot not found.", 404
    error = None
    eligible = User.query.join(ExaminerProfile).join(ExaminerAssignment, ExaminerAssignment.examiner_id == User.id).filter(ExaminerAssignment.examination_id == slot.examination_id, ExaminerAssignment.status == "active", User.account_status == "active", ExaminerProfile.is_approved.is_(True), ExaminerProfile.is_active.is_(True)).all()
    if request.method == "POST":
        new_examiner = db.session.get(User, request.form.get("examiner_id", type=int))
        eligible_ids = {item.id for item in eligible}
        conflict = None
        if new_examiner and new_examiner.id in eligible_ids:
            conflict = ExaminationSlot.query.filter(ExaminationSlot.examiner_id == new_examiner.id, ExaminationSlot.date == slot.date, ExaminationSlot.id != slot.id, ExaminationSlot.start_time < slot.end_time, ExaminationSlot.end_time > slot.start_time).first()
        if new_examiner is None or new_examiner.id not in eligible_ids: error = "Select an approved, active Examiner assigned to this examination."
        elif conflict: error = "The Examiner has a conflicting slot."
        else:
            old_name = slot.examiner.email; slot.examiner_id = new_examiner.id
            for booking in slot.bookings:
                db.session.add(BookingHistory(booking_id=booking.id, old_slot_id=slot.id, new_slot_id=slot.id, actor_id=user.id, action="examiner_reassigned", details=f"Examiner changed from {old_name} to {new_examiner.email}."))
            db.session.commit(); return redirect(url_for("admin_slots", user_id=user.id, message="Slot Examiner reassigned and booking history preserved."))
    return render_template("admin/reassign_slot.html", user=user, slot=slot, examiners=eligible, error=error)


@app.route("/admin/<int:user_id>/bookings")
def admin_bookings(user_id):
    user, response = admin_or_login(user_id)
    if response: return response
    search, status = request.args.get("search", "").strip(), request.args.get("status", "").strip()
    query=Booking.query.join(User, Booking.student_id == User.id).join(StudentProfile, StudentProfile.user_id == User.id).join(ExaminationSlot, Booking.slot_id == ExaminationSlot.id).join(Examination, ExaminationSlot.examination_id == Examination.id).join(Course, Examination.course_id == Course.id).join(ExaminerProfile, ExaminationSlot.examiner_id == ExaminerProfile.user_id)
    if search:
        pattern=f"%{search}%"; query=query.filter(or_(User.email.ilike(pattern), StudentProfile.full_name.ilike(pattern), StudentProfile.student_id.ilike(pattern), Examination.exam_name.ilike(pattern), Course.course_code.ilike(pattern), ExaminerProfile.full_name.ilike(pattern), ExaminerProfile.examiner_id.ilike(pattern)))
    if status: query=query.filter(Booking.status == status)
    return render_template("admin/bookings.html", user=user, bookings=query.order_by(Booking.booking_date.desc()).all(), search=search, selected_status=status, message=request.args.get("message"))


@app.route("/admin/<int:user_id>/bookings/<int:booking_id>/reschedule", methods=["GET", "POST"])
def admin_reschedule_booking(user_id, booking_id):
    user, response = admin_or_login(user_id)
    if response: return response
    booking = db.session.get(Booking, booking_id)
    if booking is None: return "Booking not found.", 404
    error = None; old_slot = booking.slot
    targets = ExaminationSlot.query.filter(ExaminationSlot.examination_id == old_slot.examination_id, ExaminationSlot.id != old_slot.id, ExaminationSlot.available_seats > 0, ExaminationSlot.status == "Available").order_by(ExaminationSlot.date, ExaminationSlot.start_time).all()
    if request.method == "POST":
        target = db.session.get(ExaminationSlot, request.form.get("slot_id", type=int))
        if booking.status != "Booked": error = "Only an active booking can be rescheduled."
        elif target is None or target.examination_id != old_slot.examination_id: error = "The target slot must belong to the same examination."
        elif target.available_seats <= 0 or target.status != "Available": error = "The target slot has no available capacity."
        else:
            old_slot.available_seats = min(old_slot.max_capacity, old_slot.available_seats + 1); old_slot.status = "Available"
            target.available_seats -= 1; target.status = "Full" if target.available_seats == 0 else "Available"
            booking.slot_id = target.id
            db.session.add(BookingHistory(booking_id=booking.id, old_slot_id=old_slot.id, new_slot_id=target.id, actor_id=user.id, action="rescheduled", details=f"Moved from slot {old_slot.id} to slot {target.id}."))
            db.session.commit(); return redirect(url_for("admin_bookings", user_id=user.id, message="Booking rescheduled and capacity updated."))
    return render_template("admin/reschedule_booking.html", user=user, booking=booking, targets=targets, error=error)


@app.post("/logout")
def logout():
    return redirect(url_for("login"))
