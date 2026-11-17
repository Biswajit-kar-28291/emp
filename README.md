# Examination Management Portal

A simple server-rendered examination portal built with Python, Flask,
Flask-SQLAlchemy, SQLite, HTML, and Bootstrap CSS.

## Current features

- Student and Examiner registration
- Email and password login
- Examiner accounts remain pending after registration
- Active Student login redirects to the Student Dashboard
- Student Dashboard with empty states for available slots and upcoming examinations
- SQLite tables created automatically when `run.py` starts

The current project does not use Flask-Login, JavaScript, an API, or authentication
tokens. Examination, slot, booking, and result data are not implemented yet.

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

## Routes

| Route | Purpose |
| --- | --- |
| `/` | Redirects to the login page |
| `/login` | Login form |
| `/register` | Student or Examiner registration form |
| `/student/<user_id>` | Student Dashboard |
| `/logout` | Returns to the login page using POST |

## Important password notice

At the project owner's explicit direction, this academic demonstration stores
fictional passwords without hashing. This is not secure. Never enter real
credentials or deploy the current implementation as a production application.
