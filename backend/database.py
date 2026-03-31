import os
import logging
from pathlib import Path
import psycopg2
import psycopg2.extras
from passlib.context import CryptContext

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ats")

DATABASE_URL = os.environ.get("DATABASE_URL", "")
UPLOAD_PATH = Path(os.environ.get("ATS_UPLOAD_DIR", Path(__file__).parent.parent / "uploads"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

logger.info(f"DATABASE_URL={'set' if DATABASE_URL else 'NOT SET'}, UPLOAD_PATH={UPLOAD_PATH}")


def get_db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    return conn


def init_db():
    os.makedirs(UPLOAD_PATH, exist_ok=True)
    logger.info(f"Upload dir exists: {UPLOAD_PATH.exists()}, writable: {os.access(UPLOAD_PATH, os.W_OK)}")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL,
            email TEXT DEFAULT ''
        )
    """)
    # Migration: add email column if missing
    cur.execute("""
        DO $$ BEGIN
            ALTER TABLE users ADD COLUMN email TEXT DEFAULT '';
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            id SERIAL PRIMARY KEY,
            full_name TEXT NOT NULL,
            position TEXT NOT NULL DEFAULT '',
            email TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            telegram TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Новый',
            portfolio_url TEXT DEFAULT '',
            source TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id SERIAL PRIMARY KEY,
            candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
            author_id INTEGER NOT NULL REFERENCES users(id),
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS test_assignments (
            id SERIAL PRIMARY KEY,
            candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Выдано',
            rating INTEGER,
            comment TEXT DEFAULT '',
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            received_at TIMESTAMP,
            reviewed_at TIMESTAMP,
            created_by INTEGER NOT NULL REFERENCES users(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS meetings (
            id SERIAL PRIMARY KEY,
            candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
            meeting_date TEXT NOT NULL,
            meeting_time TEXT DEFAULT '',
            format TEXT NOT NULL DEFAULT 'zoom',
            recording_url TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            created_by INTEGER NOT NULL REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ics_sequence INTEGER DEFAULT 0
        )
    """)
    # Migration: add new columns if missing
    cur.execute("""
        DO $$ BEGIN
            ALTER TABLE meetings ADD COLUMN meeting_time TEXT DEFAULT '';
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$
    """)
    cur.execute("""
        DO $$ BEGIN
            ALTER TABLE meetings ADD COLUMN ics_sequence INTEGER DEFAULT 0;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id SERIAL PRIMARY KEY,
            candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_type TEXT DEFAULT 'other',
            uploaded_by INTEGER NOT NULL REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            id SERIAL PRIMARY KEY,
            candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id),
            score INTEGER NOT NULL CHECK(score >= 1 AND score <= 5),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(candidate_id, user_id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id SERIAL PRIMARY KEY,
            candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id),
            action TEXT NOT NULL,
            details TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    # Seed users
    users = [
        ("venera", pwd_context.hash("venera123"), "Venera (CEO)", "ceo", "veneramiray@gmail.com"),
        ("dmitry", pwd_context.hash("dmitry123"), "Dmitry (Founder)", "cto", "khrapov@gmail.com"),
    ]
    for username, pw_hash, display, role, email in users:
        cur.execute(
            """INSERT INTO users (username, password_hash, display_name, role, email)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (username) DO UPDATE SET email = EXCLUDED.email
               WHERE users.email = '' OR users.email IS NULL""",
            (username, pw_hash, display, role, email),
        )
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")
