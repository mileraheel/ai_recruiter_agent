# Role Pace — Phase 1 (Core Brain)

Config-driven, automation-free foundation: load candidate config, run the
eligibility filter against job text, get an auditable decision back.

## Setup (Windows)

1. Install Python 3.11+ from python.org (check "Add python.exe to PATH" during install).
2. Open **PowerShell**, `cd` into this folder.
3. Create and activate a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\Activate.ps1
   ```
   If PowerShell blocks the activation script with an execution-policy error, run
   this once (as your normal user, not admin):
   ```
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```
4. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
5. The `.env` file in this folder already has your candidate email/phone/sender
   email filled in — `cli.py` loads it automatically via `python-dotenv`, no manual
   environment variable setup needed.
6. Run a check:
   ```
   python cli.py check-job --config config\candidate.yaml --file sample_jobs\test_clean.txt --location "Reston, VA" --work-mode hybrid
   ```
7. Run the tests:
   ```
   python -m pytest tests\ -v
   ```

## Setup (macOS/Linux)
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python cli.py check-job --config config/candidate.yaml --file sample_jobs/test_clean.txt --location "Reston, VA" --work-mode hybrid
python -m pytest tests/ -v
```

## Try it on a real job posting
Paste any job description into a new `.txt` file under `sample_jobs/`, then run:
```
python cli.py check-job --config config\candidate.yaml --file sample_jobs\your_file.txt --location "<job's location>" --work-mode <remote|hybrid|onsite>
```


## Environment variables

Two `.env` files, one per stack -- both git-ignored, neither is committed:

- **Backend** (`.env` in the repo root, loaded by `cli.py` / `api/main.py` via
  `python-dotenv`): candidate email/phone/sender, `DATABASE_URL`, and:
  - `APP_NAME` -- the platform's display name used anywhere the backend names
    itself out loud (FastAPI docs title, CLI banner, generated `schema.sql`
    header, the outreach-email disclosure line). Defaults to `Role Pace` if
    unset -- see `config/app_info.py`.
- **Frontend** (`frontend/.env`, loaded by Vite -- copy from
  `frontend/.env.example` to start):
  - `VITE_APP_NAME` -- the same display name, used for the browser tab title,
    the PWA manifest (`public/manifest.json`, regenerated automatically at
    `npm run dev` / `npm run build` time), and the in-app header/login
    screen. Defaults to `Role Pace` if unset -- see `frontend/src/config/appInfo.js`.

To rename the app later, change both of those two values and restart/rebuild
-- no code changes needed.


- `config/schema.py` — Pydantic models for candidate.yaml (fails fast on bad config)
- `config/loader.py` — YAML loader with `${ENV_VAR}` resolution
- `config/candidate.example.yaml` — safe-to-commit example config
- `core/eligibility.py` — the eligibility filter engine (pure function, heavily tested)
- `db/models.py` — SQLAlchemy models for the full schema (jobs, emails, applications,
  follow_ups, pending_actions, etc.)
- `db/session.py` — engine/session setup, `python -m db.session` to create tables
  (requires `DATABASE_URL` env var, e.g. `postgresql+psycopg://user:pass@localhost/db`)
- `cli.py` — manual job-check command for Phase 1 testing
- `tests/test_eligibility.py` — 13 tests covering each skip/keep rule

## Not yet built (next steps)
- Role classifier
- Resume tailoring engine + grounding check
- DOCX generation
- Email draft generation
- Match/confidence report
- `pending_actions` wiring for approval workflow
- Browser-automation adapter base class (Dice/Monster/TechFetch)
