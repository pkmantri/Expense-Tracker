import os
import sqlite3
import pandas as pd
import secrets
import hashlib
from typing import Optional, List

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DATA_DIR, "expenses.db")

def _connect():
    os.makedirs(DATA_DIR, exist_ok=True)
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db() -> None:
    conn = _connect()
    cur = conn.cursor()
    # Users table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    # Expenses table (linked to users)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount >= 0),
            note TEXT DEFAULT '',
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_expenses_user_date ON expenses(user_id, date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_expenses_user_category ON expenses(user_id, category)")

    # Budgets per user per month
    cur.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            user_id INTEGER NOT NULL,
            month TEXT NOT NULL,   -- YYYY-MM
            amount REAL NOT NULL CHECK(amount >= 0),
            PRIMARY KEY(user_id, month),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()

# ---- User helpers ----
def _hash_password(password: str, salt: str) -> str:
    # Simple SHA-256 with salt. Good for demo, not recommended for production.
    h = hashlib.sha256()
    h.update((salt + password).encode("utf-8"))
    return h.hexdigest()

def create_user(username: str, password: str) -> Optional[int]:
    username = username.strip()
    if not username or not password:
        return None
    conn = _connect()
    cur = conn.cursor()
    # Check exists
    cur.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cur.fetchone():
        conn.close()
        return None
    salt = secrets.token_hex(16)
    password_hash = _hash_password(password, salt)
    created_at = pd.Timestamp.utcnow().isoformat()
    cur.execute("INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
                (username, password_hash, salt, created_at))
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return int(user_id)

def authenticate_user(username: str, password: str) -> Optional[int]:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT id, password_hash, salt FROM users WHERE username = ?", (username.strip(),))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    user_id, password_hash, salt = row
    if _hash_password(password, salt) == password_hash:
        return int(user_id)
    return None

def get_user_by_id(user_id: int):
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT id, username, created_at FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row

# ---- Expenses ----
def add_expense(user_id: int, date: str, category: str, amount: float, note: str = "") -> int:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("INSERT INTO expenses (user_id, date, category, amount, note) VALUES (?, ?, ?, ?, ?)",
                (user_id, date, category, amount, note or ""))
    conn.commit()
    rowid = cur.lastrowid
    conn.close()
    return int(rowid)

def get_expenses_df(user_id: int,
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None,
                    categories: Optional[List[str]] = None) -> pd.DataFrame:
    conn = _connect()
    query = "SELECT id AS ID, date AS Date, category AS Category, amount AS Amount, note AS Note FROM expenses WHERE user_id = ?"
    params: list = [user_id]
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    if categories:
        placeholders = ",".join(["?"] * len(categories))
        query += f" AND category IN ({placeholders})"
        params.extend(categories)
    query += " ORDER BY date ASC, id ASC"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def delete_expense(user_id: int, expense_id: int) -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM expenses WHERE user_id = ? AND id = ?", (user_id, expense_id))
    conn.commit()
    conn.close()

def update_expense(user_id: int, expense_id: int, date: str, category: str, amount: float, note: str) -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("UPDATE expenses SET date=?, category=?, amount=?, note=? WHERE user_id = ? AND id = ?",
                (date, category, amount, note, user_id, expense_id))
    conn.commit()
    conn.close()

# ---- Budgets ----
def set_budget(user_id: int, month: str, amount: float) -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("INSERT INTO budgets (user_id, month, amount) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id, month) DO UPDATE SET amount=excluded.amount",
                (user_id, month, amount))
    conn.commit()
    conn.close()

def get_budget(user_id: int, month: str) -> Optional[float]:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT amount FROM budgets WHERE user_id = ? AND month = ?", (user_id, month))
    row = cur.fetchone()
    conn.close()
    return float(row[0]) if row else None

def get_month_total(user_id: int, month: str) -> float:
    start = f"{month}-01"
    end = f"{month}-31"
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ? AND date >= ? AND date <= ?",
                (user_id, start, end))
    total = cur.fetchone()[0] or 0.0
    conn.close()
    return float(total)

def get_top_category(user_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None):
    conn = _connect()
    query = "SELECT category, COALESCE(SUM(amount),0) as total FROM expenses WHERE user_id = ?"
    params = [user_id]
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    query += " GROUP BY category ORDER BY total DESC LIMIT 1"
    cur = conn.cursor()
    cur.execute(query, params)
    row = cur.fetchone()
    conn.close()
    return row  # (category, total) or None
