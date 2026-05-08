from flask import Flask, request, jsonify, session, redirect, send_from_directory
from flask_socketio import SocketIO, emit
import sqlite3
import os
from datetime import datetime
import json

app = Flask(__name__, static_folder='public', static_url_path='')
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret")

socketio = SocketIO(app, cors_allowed_origins="*")

DB = "bookings.db"

ADMIN_KEY = os.environ.get("ADMIN_KEY", "adam2025admin")

# ================= DB =================

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    # BOOKINGS (atomic protection added)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        car TEXT NOT NULL,
        service TEXT NOT NULL,
        booking_date TEXT NOT NULL,
        booking_time TEXT NOT NULL,
        notes TEXT DEFAULT '',
        status TEXT DEFAULT 'جديد',
        total_cost REAL DEFAULT 0,
        total_profit REAL DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(booking_date, booking_time)
    )
    """)

    # EXPENSES
    conn.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER,
        item_name TEXT,
        cost_price REAL,
        sell_price REAL,
        profit REAL
    )
    """)

    # AUDIT LOG
    conn.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT,
        entity TEXT,
        entity_id INTEGER,
        data TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


# ================= HELPERS =================

def log_action(action, entity, entity_id, data):
    conn = get_db()
    conn.execute("""
        INSERT INTO audit_log (action, entity, entity_id, data)
        VALUES (?, ?, ?, ?)
    """, (action, entity, entity_id, json.dumps(data)))
    conn.commit()
    conn.close()


def valid_phone(phone):
    return phone.isdigit() and phone.startswith("01") and len(phone) == 11


def is_admin():
    return session.get("role") == "admin"


def is_staff():
    return session.get("role") in ["admin", "staff"]


# ================= AUTH =================

@app.route("/login", methods=["POST"])
def login():
    password = request.json.get("password")

    if password == ADMIN_KEY:
        session["role"] = "admin"
        return jsonify({"success": True, "role": "admin"})

    return jsonify({"success": False}), 401


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ================= ATOMIC BOOKING =================

@app.route("/api/booking", methods=["POST"])
def booking():

    data = request.json

    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    car = (data.get("car") or "").strip()
    service = (data.get("service") or "").strip()
    date = (data.get("booking_date") or "").strip()
    time = (data.get("booking_time") or "").strip()
    notes = (data.get("notes") or "").strip()

    if not all([name, phone, car, service, date, time]):
        return jsonify({"success": False, "message": "Missing fields"}), 400

    if not valid_phone(phone):
        return jsonify({"success": False, "message": "Invalid phone"}), 400

    try:
        conn = get_db()
        conn.execute("BEGIN IMMEDIATE")

        cur = conn.execute("""
            INSERT INTO bookings
            (name, phone, car, service, booking_date, booking_time, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, phone, car, service, date, time, notes))

        booking_id = cur.lastrowid

        conn.commit()

        log_action("CREATE", "booking", booking_id, data)

        socketio.emit("new_booking", {"id": booking_id, "name": name})

        return jsonify({
            "success": True,
            "id": booking_id
        })

    except sqlite3.IntegrityError:
        return jsonify({
            "success": False,
            "message": "هذا الموعد محجوز بالفعل"
        }), 409

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


# ================= AVAILABLE TIMES =================

@app.route("/api/available-times")
def available_times():

    date = request.args.get("date")

    all_times = [
        "09:00","10:00","11:00","12:00",
        "13:00","14:00","15:00","16:00",
        "17:00","18:00","19:00","20:00","21:00"
    ]

    conn = get_db()

    booked = conn.execute(
        "SELECT booking_time FROM bookings WHERE booking_date=?",
        (date,)
    ).fetchall()

    booked = {b["booking_time"] for b in booked}

    available = [t for t in all_times if t not in booked]

    return jsonify({"success": True, "times": available})


# ================= BOOKINGS =================

@app.route("/api/bookings")
def bookings():

    if not is_admin():
        return jsonify({"success": False}), 401

    conn = get_db()

    rows = conn.execute("""
        SELECT * FROM bookings ORDER BY id DESC
    """).fetchall()

    return jsonify({
        "success": True,
        "bookings": [dict(r) for r in rows]
    })


# ================= STATUS UPDATE =================

@app.route("/api/bookings/<int:bid>", methods=["PATCH"])
def update_status(bid):

    if not is_admin():
        return jsonify({"success": False}), 401

    status = request.json.get("status")

    allowed = ["جديد", "تم التواصل", "مكتمل", "ملغي"]

    if status not in allowed:
        return jsonify({"success": False}), 400

    conn = get_db()

    conn.execute(
        "UPDATE bookings SET status=? WHERE id=?",
        (status, bid)
    )

    conn.commit()

    log_action("UPDATE_STATUS", "booking", bid, {"status": status})

    return jsonify({"success": True})


# ================= EXPENSE + PROFIT =================

@app.route("/api/bookings/<int:bid>/expense", methods=["POST"])
def expense(bid):

    if not is_admin():
        return jsonify({"success": False}), 401

    data = request.json

    try:
        cost = float(data.get("cost_price", 0))
        sell = float(data.get("sell_price", 0))
    except:
        return jsonify({"success": False}), 400

    profit = sell - cost

    conn = get_db()

    conn.execute("""
        INSERT INTO expenses
        (booking_id, item_name, cost_price, sell_price, profit)
        VALUES (?, ?, ?, ?, ?)
    """, (bid, data["item_name"], cost, sell, profit))

    totals = conn.execute("""
        SELECT
        SUM(cost_price) as cost,
        SUM(profit) as profit
        FROM expenses
        WHERE booking_id=?
    """, (bid,)).fetchone()

    conn.execute("""
        UPDATE bookings
        SET total_cost=?, total_profit=?
        WHERE id=?
    """, (totals["cost"] or 0, totals["profit"] or 0, bid))

    conn.commit()

    log_action("ADD_EXPENSE", "booking", bid, data)

    return jsonify({"success": True})


# ================= DASHBOARD (PROFIT DAILY) =================

@app.route("/api/dashboard")
def dashboard():

    if not is_admin():
        return jsonify({"success": False}), 401

    conn = get_db()

    stats = conn.execute("""
        SELECT
        COUNT(*) as bookings,
        IFNULL(SUM(total_profit),0) as profit
        FROM bookings
        WHERE date(created_at)=date('now')
    """).fetchone()

    return jsonify({"success": True, "stats": dict(stats)})


# ================= INVOICE =================

@app.route("/api/invoice/<int:bid>")
def invoice(bid):

    conn = get_db()

    booking = conn.execute(
        "SELECT * FROM bookings WHERE id=?",
        (bid,)
    ).fetchone()

    expenses = conn.execute(
        "SELECT * FROM expenses WHERE booking_id=?",
        (bid,)
    ).fetchall()

    return jsonify({
        "booking": dict(booking),
        "expenses": [dict(e) for e in expenses]
    })


# ================= RUN =================

if __name__ == "__main__":
    init_db()
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
