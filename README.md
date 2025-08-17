# Multi-user Expense Tracker (Option 1)

This is a multi-user expense tracker built with **Streamlit**, **SQLite**, **Pandas**, and **Matplotlib**.
Each user has a private account (username + password) and sees only their own expenses, budgets, and reports.

## Features
- Sign up and login (local accounts)
- Add, edit, delete expenses (per-user)
- Monthly budget per user with alerts (>=90% warning, >=100% error)
- Visualizations (category pie, daily trend, monthly totals)
- Export filtered data to CSV (per-user)
- Top spending category notification

## Security note
Password hashing uses salted SHA-256 for demonstration. For real-world apps, use a secure password hashing algorithm (e.g., bcrypt/argon2) and a proper auth system.

## Quick setup

1. Open a terminal and navigate to the project folder:
```bash
cd expense_tracker_multi
```

2. (Optional but recommended) Create & activate a virtual environment:
```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the app:
```bash
streamlit run app.py
```

5. Open the app in your browser (usually at http://localhost:8501). Use the sidebar to create an account, log in, and start tracking expenses.

## Project structure
```
expense_tracker_multi/
├─ app.py
├─ database.py
├─ requirements.txt
├─ data/         # SQLite DB will be created here
└─ reports/      # optional directory for exports
```

## How it works
- Accounts are stored in `users` table.
- Expenses and budgets are linked to a `user_id` so each user sees only their own data.
- Use the sidebar to set filters and monthly budgets.

---
Enjoy! 🧾💸
