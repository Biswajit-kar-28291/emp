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
- Examiner Dashboard with empty states for assignments, slots, and evaluations
- Admin Dashboard with user counts and honest examination-data empty states
- SQLite tables created automatically when `run.py` starts

The current project does not use Flask-Login, JavaScript, an API, or authentication
tokens. Course and examination administration, examiner slot management, and
evaluation entry are not implemented yet.

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
| `/admin/<user_id>` | Admin Dashboard |
| `/logout` | Returns to the login page using POST |

## Important password notice

At the project owner's explicit direction, this academic demonstration stores
fictional passwords without hashing. This is not secure. Never enter real
credentials or deploy the current implementation as a production application.
