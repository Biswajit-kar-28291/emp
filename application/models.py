from datetime import datetime

from sqlalchemy import CheckConstraint

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
    is_approved = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    user = db.relationship("User", back_populates="examiner_profile")
