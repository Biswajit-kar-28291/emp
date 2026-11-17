# Examination Management Portal Development Rules

## Project approach

- Keep the project simple and readable like `reference/placement-portal/`.
- Use the reference project only for basic Flask coding style, route structure,
  SQLAlchemy usage, Jinja templates, and Bootstrap layout.
- Do not copy placement-specific features, models, routes, uploads, credentials,
  or unsafe code from the reference project.
- Use `docs/EMP_Software_Development_SOP.pdf` for examination-domain
  requirements.
- Use `docs/Examination Management Portal MAD-1.png` only as a workflow and
  navigation reference.
- Implement only what the user requests. Do not add future features.
- Do not create unnecessary files, folders, layers, services, utilities,
  Blueprints, or abstractions.

## Required simple structure

```text
examination-management-portal/
|-- AGENTS.md
|-- run.py
|-- requirements.txt
|-- README.md
|-- .gitignore
|-- application/
|   |-- database.py
|   |-- models.py
|   +-- routes.py
|-- templates/
|   |-- auth/
|   +-- student/
|-- docs/
|-- instance/          # generated locally and ignored by Git
+-- reference/         # local reference only and ignored by Git
```

- Keep database setup in `application/database.py`.
- Keep SQLAlchemy models in `application/models.py`.
- Keep straightforward Flask routes in `application/routes.py`.
- Keep application creation and startup in `run.py`.
- Add a template only when a requested page needs one.
- Do not reorganize the project into an `app/` package.

## Technology rules

- Backend: Python and Flask.
- Database: SQLite with Flask-SQLAlchemy.
- Frontend: server-rendered Jinja2, HTML, and Bootstrap CSS.
- Do not use JavaScript.
- Do not create a JSON API unless explicitly requested.
- Do not use Flask Blueprints.
- Do not use Flask-Login.
- Do not use Flask-WTF or WTForms.
- Do not add authentication or CSRF tokens unless the user explicitly requests
  them later.
- Use simple form POST handling directly in Flask routes.
- Passwords remain plaintext only because the project owner explicitly requires
  it for this academic demonstration. Clearly document that this is insecure,
  and never use or commit real credentials.

## Current authentication behavior

- Login identity is normalized email.
- Public registration supports only Student and Examiner.
- Admin must never be publicly registrable.
- Student registration creates an active account.
- Examiner registration creates a pending account.
- Pending or deactivated users cannot log in.
- Student login redirects to `/student/<user_id>`.
- Do not add sessions or Flask-Login unless the project owner changes this
  decision.

## Database rules

- Use one `users` table for identity and role.
- Keep Student and Examiner details in their profile tables.
- Supported roles are `admin`, `examiner`, and `student`.
- Supported account statuses are `active`, `pending`, and `deactivated`.
- Normalize email before database lookup or insertion.
- Keep email unique.
- Create tables programmatically with `db.create_all()`.
- Never delete or rebuild the local database without explicit user permission.
- Preserve existing records when repairing a schema.
- Do not commit the generated database.

## Route and template style

- Keep route functions short, direct, and beginner-friendly.
- Use clear validation messages.
- Use Post/Redirect/Get after successful form submissions.
- Use Bootstrap classes for a clean, responsive interface.
- Do not add fake data or placeholder links that imply unfinished features work.
- If a model for a dashboard section does not exist, show an honest empty state.
- Keep navigation limited to implemented pages.

## Change safety

- Inspect existing files and `git status` before editing.
- Edit existing files when possible.
- Create a new file only when the requested feature genuinely needs it.
- Preserve unrelated user work.
- Do not delete databases, reset Git, or discard work without explicit approval.
- Do not commit or push unless explicitly requested.
- Never commit `.env`, `instance/`, SQLite databases, virtual environments,
  caches, the reference repository, secrets, or real credentials.

## Verification

- Test the smallest affected route or database flow after each change.
- Use an in-memory or temporary SQLite database for verification.
- Do not modify the developer database during tests.
- Check that templates contain no JavaScript.
- Report only checks that were actually run.
- Keep `requirements.txt`, `.gitignore`, and `README.md` synchronized with
  the code that currently exists.
