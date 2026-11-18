# Examination Management Portal

A simple server-rendered examination portal built with Python, Flask,
Flask-SQLAlchemy, SQLite, HTML, and Bootstrap CSS.

## Current features

- Student and Examiner registration
- Email and password login
- Examiner accounts remain pending after registration
- Active Student login redirects to the Student Dashboard
- Active, approved Examiner login redirects to the Examiner Dashboard
- Active Admin login redirects to the Admin Dashboard
- Student Dashboard with searchable examinations, available slots, bookings, schedule, and results
- Student slot booking with booking-period, capacity, and duplicate-booking checks
- Booking cancellation before the deadline with complete booking history
- Published results and examiner feedback for Students
- Student profile editing
- Examiner access restricted to active, approved Examiner profiles
- Examiner Dashboard with assignment, slot, booking, and evaluation counts
- Assigned examination and rubric viewing
- Examiner slot creation and management with timeline, capacity, and overlap checks
- Examiner-owned booked Student lists
- Rubric-based evaluation drafts and final submission for Admin publication
- Examiner profile editing for permitted identity, contact, and department fields
- Admin Dashboard with live totals for courses, examinations, users, slots, bookings, and pending approvals
- Admin course, examination, rubric, Examiner approval, assignment, slot, and booking management
- Admin lifecycle controls, safe deletion checks, booking rescheduling, and exceptional Examiner reassignment
- Server-rendered Admin search and filters for Students, Examiners, courses, examinations, slots, and bookings
- SQLite tables created automatically when `run.py` starts

The current project does not use Flask-Login, JavaScript, an API, or authentication
tokens. Result publication remains an Admin responsibility.

## Requirements

- Python 3.10 or newer
- The packages listed in `requirements.txt`
- Internet access for the Bootstrap CSS CDN used by the HTML templates

## Setup and run

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the exact dependencies:

```powershell
python -m pip install -r requirements.txt
```

Start the application:

```powershell
python run.py
```

Open `http://127.0.0.1:5000/login` in a browser.

The generated database is stored at `instance/emp.sqlite3`. The `instance/`
directory is ignored by Git.

On the first start, the application creates this fictional Admin account if no
Admin exists:

- Email: `admin@emp.local`
- Password: `admin123`

Set the `ADMIN_EMAIL` and `ADMIN_PASSWORD` environment variables before the
first start to use different demonstration credentials. Starting the application
again does not replace an existing Admin account or its password.

## Routes

| Route | Purpose |
| --- | --- |
| `/` | Redirects to the login page |
| `/login` | Login form |
| `/register` | Student or Examiner registration form |
| `/student/<user_id>` | Student Dashboard |
| `/student/<user_id>/book/<slot_id>` | Book an available slot using POST |
| `/student/<user_id>/cancel/<booking_id>` | Cancel an eligible booking using POST |
| `/student/<user_id>/history` | Student booking history |
| `/student/<user_id>/results` | Published Student results and feedback |
| `/student/<user_id>/profile` | View or edit the Student profile |
| `/examiner/<user_id>` | Approved Examiner Dashboard |
| `/examiner/<user_id>/examinations` | View assigned examinations and rubrics |
| `/examiner/<user_id>/slots` | Create and manage owned examination slots |
| `/examiner/<user_id>/students` | View Students booked into owned slots |
| `/examiner/<user_id>/evaluations` | View eligible evaluation work |
| `/examiner/<user_id>/evaluations/<booking_id>` | Save or submit rubric scores |
| `/examiner/<user_id>/profile` | View or edit permitted Examiner profile fields |
| `/admin/<user_id>` | Admin Dashboard |
| `/admin/<user_id>/courses` | Search and manage courses |
| `/admin/<user_id>/examinations` | Search, manage, and control examination lifecycles |
| `/admin/<user_id>/examinations/<examination_id>/rubrics` | Manage examination rubrics |
| `/admin/<user_id>/examiners` | Search, approve, deactivate, and update Examiners |
| `/admin/<user_id>/assignments` | Manage Examiner assignments |
| `/admin/<user_id>/students` | Search registered Students |
| `/admin/<user_id>/slots` | Filter slots and perform exceptional Examiner reassignment |
| `/admin/<user_id>/bookings` | Search bookings, view history, and reschedule active bookings |
| `/logout` | Returns to the login page using POST |

## Important password notice

At the project owner's explicit direction, this academic demonstration stores
fictional passwords without hashing. This is not secure. Never enter real
credentials or deploy the current implementation as a production application.
