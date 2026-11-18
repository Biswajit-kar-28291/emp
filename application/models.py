from datetime import datetime

from sqlalchemy import CheckConstraint, UniqueConstraint

from .database import db

ROLE_ADMIN = "admin"
ROLE_EXAMINER = "examiner"
ROLE_STUDENT = "student"
STATUS_ACTIVE = "active"
STATUS_PENDING = "pending"
STATUS_DEACTIVATED = "deactivated"


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    # Owner-required deviation: fictional demo passwords are plaintext and insecure.
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    account_status = db.Column(db.String(20), nullable=False, default=STATUS_ACTIVE)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'examiner', 'student')", name="ck_users_role"),
        CheckConstraint(
            "account_status IN ('active', 'pending', 'deactivated')",
            name="ck_users_account_status",
        ),
    )
    student_profile = db.relationship("StudentProfile", back_populates="user", uselist=False)
    examiner_profile = db.relationship("ExaminerProfile", back_populates="user", uselist=False)


class StudentProfile(db.Model):
    __tablename__ = "student_profiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    student_id = db.Column(db.String(64), unique=True)
    user = db.relationship("User", back_populates="student_profile")


class ExaminerProfile(db.Model):
    __tablename__ = "examiner_profiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    examiner_id = db.Column(db.String(64), unique=True)
    contact_details = db.Column(db.String(255))
    department = db.Column(db.String(255))
    is_approved = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    user = db.relationship("User", back_populates="examiner_profile")


class Course(db.Model):
    __tablename__ = "courses"
    id = db.Column(db.Integer, primary_key=True)
    course_code = db.Column(db.String(100), unique=True, nullable=False)
    course_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default="active")


class Examination(db.Model):
    __tablename__ = "examinations"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    exam_name = db.Column(db.String(255), nullable=False)
    exam_type = db.Column(db.String(50), nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    max_marks = db.Column(db.Integer, nullable=False)
    slot_creation_start = db.Column(db.DateTime, nullable=False)
    slot_creation_end = db.Column(db.DateTime, nullable=False)
    slot_booking_start = db.Column(db.DateTime, nullable=False)
    slot_booking_end = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    course = db.relationship("Course", backref="examinations")
    slots = db.relationship("ExaminationSlot", back_populates="examination")
    assignments = db.relationship("ExaminerAssignment", back_populates="examination")


class ExaminerAssignment(db.Model):
    __tablename__ = "examiner_assignments"
    id = db.Column(db.Integer, primary_key=True)
    examination_id = db.Column(db.Integer, db.ForeignKey("examinations.id"), nullable=False)
    examiner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active")
    __table_args__ = (
        UniqueConstraint("examination_id", "examiner_id", name="uq_examiner_assignment"),
        CheckConstraint("status IN ('active', 'inactive')", name="ck_assignment_status"),
    )
    examination = db.relationship("Examination", back_populates="assignments")
    examiner = db.relationship("User", foreign_keys=[examiner_id])


class ExaminationSlot(db.Model):
    __tablename__ = "examination_slots"
    id = db.Column(db.Integer, primary_key=True)
    examination_id = db.Column(db.Integer, db.ForeignKey("examinations.id"), nullable=False)
    examiner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    max_capacity = db.Column(db.Integer, nullable=False)
    available_seats = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Available")
    __table_args__ = (
        CheckConstraint("max_capacity > 0", name="ck_slots_positive_capacity"),
        CheckConstraint("available_seats >= 0", name="ck_slots_available_seats"),
        CheckConstraint("available_seats <= max_capacity", name="ck_slots_seats_capacity"),
        CheckConstraint("end_time > start_time", name="ck_slots_time_order"),
    )
    examination = db.relationship("Examination", back_populates="slots")
    examiner = db.relationship("User", foreign_keys=[examiner_id])
    bookings = db.relationship("Booking", back_populates="slot")


class Booking(db.Model):
    __tablename__ = "bookings"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey("examination_slots.id"), nullable=False)
    booking_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default="Booked")
    __table_args__ = (
        CheckConstraint(
            "status IN ('Booked', 'Cancelled', 'Completed')",
            name="ck_bookings_status",
        ),
    )
    student = db.relationship("User", foreign_keys=[student_id])
    slot = db.relationship("ExaminationSlot", back_populates="bookings")
    history = db.relationship("BookingHistory", back_populates="booking")
    evaluation = db.relationship("Evaluation", back_populates="booking", uselist=False)


class BookingHistory(db.Model):
    __tablename__ = "booking_history"
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False)
    old_slot_id = db.Column(db.Integer, db.ForeignKey("examination_slots.id"))
    new_slot_id = db.Column(db.Integer, db.ForeignKey("examination_slots.id"))
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(30), nullable=False)
    details = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    booking = db.relationship("Booking", back_populates="history")
    old_slot = db.relationship("ExaminationSlot", foreign_keys=[old_slot_id])
    new_slot = db.relationship("ExaminationSlot", foreign_keys=[new_slot_id])
    actor = db.relationship("User", foreign_keys=[actor_id])


class ExaminationRubric(db.Model):
    __tablename__ = "examination_rubrics"
    id = db.Column(db.Integer, primary_key=True)
    examination_id = db.Column(db.Integer, db.ForeignKey("examinations.id"), nullable=False)
    criterion_name = db.Column(db.String(255), nullable=False)
    maximum_marks = db.Column(db.Integer, nullable=False)
    weightage = db.Column(db.Integer, nullable=False, default=100)
    description = db.Column(db.Text)
    examination = db.relationship("Examination", backref="rubrics")


class Evaluation(db.Model):
    __tablename__ = "evaluations"
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), unique=True, nullable=False)
    examiner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    total_marks = db.Column(db.Float, nullable=False)
    remarks = db.Column(db.Text)
    is_finalized = db.Column(db.Boolean, nullable=False, default=False)
    is_published = db.Column(db.Boolean, nullable=False, default=False)
    published_at = db.Column(db.DateTime)
    __table_args__ = (
        CheckConstraint("total_marks >= 0", name="ck_evaluations_nonnegative_marks"),
        UniqueConstraint("booking_id", name="uq_evaluations_booking"),
    )
    booking = db.relationship("Booking", back_populates="evaluation")
    examiner = db.relationship("User", foreign_keys=[examiner_id])
    scores = db.relationship(
        "EvaluationScore", back_populates="evaluation", cascade="all, delete-orphan"
    )


class EvaluationScore(db.Model):
    __tablename__ = "evaluation_scores"
    id = db.Column(db.Integer, primary_key=True)
    evaluation_id = db.Column(db.Integer, db.ForeignKey("evaluations.id"), nullable=False)
    rubric_id = db.Column(db.Integer, db.ForeignKey("examination_rubrics.id"), nullable=False)
    awarded_marks = db.Column(db.Float, nullable=False)
    remarks = db.Column(db.Text)
    __table_args__ = (
        UniqueConstraint("evaluation_id", "rubric_id", name="uq_evaluation_rubric"),
        CheckConstraint("awarded_marks >= 0", name="ck_score_nonnegative_marks"),
    )
    evaluation = db.relationship("Evaluation", back_populates="scores")
    rubric = db.relationship("ExaminationRubric")
