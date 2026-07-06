# Database Setup, Backup & Recovery

## Setting up from zero (fresh clone, fresh database)

Full sequence to go from "empty Postgres database" to "app is usable":

```bash
# 1. Create every table from db/models.py
python -m db.session

# 2. Seed reference data (job_sources) from config/candidate.yaml
python -m db.seed

# 3. Create the platform-level superuser account (you)
python -m api.bootstrap_superuser --username your_username

# 4. (Optional) Create a staff account -- staff onboard organizations
#    and their first admin via the app itself (POST /api/staff/invite-organization),
#    so this is only needed if you want a staff account beyond the superuser.
python -m api.bootstrap_staff --username staff_username

# 5. Admin accounts are NOT created via CLI -- create your first
#    organization + admin through the app itself:
#      POST /api/auth/signup (self-service, creates a new org), or
#      have a staff member invite one via POST /api/staff/invite-organization
```

There is no CLI path for candidates -- they're created via self-signup
(`POST /api/candidate-auth/signup`, joining an existing org by exact
name) or an admin inviting them (`POST /api/candidates/invite`).

`db/scripts/schema.sql` is a generated, human-readable snapshot of the
full schema (all tables, as raw PostgreSQL DDL) -- useful for review or
handing to a DBA, but it is NOT what the app actually runs to create
tables (that's `db/session.py::init_db()` via SQLAlchemy's
`create_all()`, above). Regenerate it after any model change:
```bash
python -m db.scripts.generate_schema_sql
```

## Recovering the schema after data loss

This is what `db/models.py` + `db/session.py` solve — the schema is defined in code,
so it's never actually "lost" as long as this repo exists.

```
python -m db.session   # creates all tables from db/models.py
python -m db.seed      # populates job_sources rows from your current candidate.yaml
```

This gets you an empty-but-correctly-structured database with the right source
rows. It does **not** restore any jobs, recruiters, or decisions you'd already
saved -- for that, you need an actual backup (below).

**Important:** `db/session.py`'s `create_all()` only creates tables that don't
already exist -- it never alters an existing table to match a schema change. If
you change `db/models.py` and the database already has the old table, you must
drop and recreate the database (or the specific changed table) before
`python -m db.session` will apply the new structure. This tripped us up once
already -- see the note in this repo's history.

## 2. Lost actual data (jobs/recruiters/decisions you'd accumulated)

Schema scripts can't help here -- you need a real backup taken *before* the loss.
Two things need to be true for this to actually protect you:

### a) Your Postgres container needs a persistent volume

If you started Postgres with a plain `docker run` and no `-v` flag, your data
lives *inside* the container's writable layer -- deleting or recreating that
container deletes the data permanently, no backup can help after the fact.

Check whether you're already using a volume:
```
docker inspect ai_recruiter_db --format '{{ json .Mounts }}'
```
If that's empty or doesn't show a volume, recreate the container with one:
```
docker stop ai_recruiter_db
docker rm ai_recruiter_db
docker volume create ai_recruiter_pgdata
docker run --name ai_recruiter_db -e POSTGRES_PASSWORD=devpassword -e POSTGRES_DB=ai_recruiter -p 5432:5432 -v ai_recruiter_pgdata:/var/lib/postgresql/data -d postgres:16
```
Then re-run `python -m db.session` and `python -m db.seed` against the fresh
container -- the *volume* now persists independently of the container, so you
can stop/remove/recreate the container itself without losing data, as long as
you don't also delete the volume.

### b) Take actual backups on top of that

A volume protects you from container churn, not from "accidentally dropped the
wrong table" or "the disk itself died." Take real backups:

```
# Backup (run this periodically, e.g. before any risky schema change)
docker exec ai_recruiter_db pg_dump -U postgres ai_recruiter > backups/ai_recruiter_YYYY-MM-DD.sql

# Restore from a backup into a fresh database
docker exec -i ai_recruiter_db psql -U postgres -d ai_recruiter < backups/ai_recruiter_YYYY-MM-DD.sql
```

`db/scripts/backup.py` and `db/scripts/restore.py` wrap these two commands so
you don't have to remember the exact syntax.

## Recommended routine while this is still early-stage / low-volume

1. Make sure the Docker volume is set up (one-time, see above).
2. Before any schema change (new columns, restructured tables like the
   job_contacts fix), run `python db/scripts/backup.py` first.
3. Once this moves beyond manual testing into daily real use, this should
   become a scheduled task rather than a manual step -- worth revisiting then.
