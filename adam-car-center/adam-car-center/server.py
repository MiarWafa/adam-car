from flask import Flask, request, jsonify, send_from_directory, session, redirect
import sqlite3, os
from datetime import datetime

app = Flask(__name__, static_folder='public', static_url_path='')

app.secret_key = os.environ.get('SECRET_KEY', 'miar_secure_key_2026')

DB = 'bookings.db'
ADMIN_KEY = os.environ.get('ADMIN_KEY', 'adam2025admin')


# ───────── DB INIT ─────────
def init_db():
    conn = sqlite3.connect(DB)

    # bookings
    conn.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            car TEXT NOT NULL,
            service TEXT NOT NULL,
            notes TEXT DEFAULT '',
            status TEXT DEFAULT 'جديد',
            appointment_id INTEGER,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')

    # appointments (المواعيد)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            time TEXT,
            is_booked INTEGER DEFAULT 0
        )
    ''')

    # expenses (مصروفات السيارة)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER,
            item TEXT,
            cost REAL,
            notes TEXT
        )
    ''')

    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def is_admin():
    return session.get('admin') is True


# ───────── LOGIN ─────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')

        if password == ADMIN_KEY:
            session['admin'] = True
            return redirect('/admin')

        return "❌ كلمة المرور غلط", 401

    return send_from_directory('public', 'login.html')


# ───────── BOOKING ─────────
@app.route('/api/booking', methods=['POST'])
def add_booking():
    data = request.get_json()

    name = (data.get('name') or '').strip()
    phone = (data.get('phone') or '').strip()
    car = (data.get('car') or '').strip()
    service = (data.get('service') or '').strip()
    notes = (data.get('notes') or '').strip()
    appointment_id = data.get('appointment_id')

    if not all([name, phone, car, service]):
        return jsonify({'success': False, 'message': 'يرجى ملء جميع الحقول'}), 400

    conn = get_db()

    # التأكد من الميعاد
    if appointment_id:
        slot = conn.execute(
            'SELECT * FROM appointments WHERE id=? AND is_booked=0',
            (appointment_id,)
        ).fetchone()

        if not slot:
            return jsonify({'success': False, 'message': 'الموعد غير متاح'}), 400

        conn.execute(
            'UPDATE appointments SET is_booked=1 WHERE id=?',
            (appointment_id,)
        )

    cur = conn.execute(
        '''INSERT INTO bookings 
        (name, phone, car, service, notes, appointment_id) 
        VALUES (?, ?, ?, ?, ?, ?)''',
        (name, phone, car, service, notes, appointment_id)
    )

    conn.commit()
    conn.close()

    return jsonify({'success': True, 'id': cur.lastrowid})


# ───────── BOOKINGS ─────────
@app.route('/api/bookings', methods=['GET'])
def get_bookings():
    if not is_admin():
        return jsonify({'success': False, 'message': 'غير مصرح'}), 401

    conn = get_db()
    rows = conn.execute('SELECT * FROM bookings ORDER BY id DESC').fetchall()
    conn.close()

    return jsonify({'success': True, 'bookings': [dict(r) for r in rows]})


# ───────── UPDATE STATUS ─────────
@app.route('/api/bookings/<int:bid>', methods=['PATCH'])
def update_booking(bid):
    if not is_admin():
        return jsonify({'success': False}), 401

    data = request.get_json()
    status = data.get('status')

    allowed = ['جديد', 'تم التواصل', 'مكتمل', 'ملغي']
    if status not in allowed:
        return jsonify({'success': False, 'message': 'حالة غير صالحة'}), 400

    conn = get_db()
    conn.execute('UPDATE bookings SET status=? WHERE id=?', (status, bid))
    conn.commit()
    conn.close()

    return jsonify({'success': True})


# ───────── DELETE BOOKING ─────────
@app.route('/api/bookings/<int:bid>', methods=['DELETE'])
def delete_booking(bid):
    if not is_admin():
        return jsonify({'success': False}), 401

    conn = get_db()
    conn.execute('DELETE FROM bookings WHERE id=?', (bid,))
    conn.commit()
    conn.close()

    return jsonify({'success': True})


# ───────── EXPENSES ─────────
@app.route('/api/expenses/<int:bid>', methods=['POST'])
def add_expense(bid):
    if not is_admin():
        return jsonify({'success': False}), 401

    data = request.get_json()

    item = data.get('item')
    cost = data.get('cost')
    notes = data.get('notes', '')

    conn = get_db()
    conn.execute(
        'INSERT INTO expenses (booking_id, item, cost, notes) VALUES (?,?,?,?)',
        (bid, item, cost, notes)
    )
    conn.commit()
    conn.close()

    return jsonify({'success': True})


@app.route('/api/expenses/<int:bid>')
def get_expenses(bid):
    if not is_admin():
        return jsonify({'success': False}), 401

    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM expenses WHERE booking_id=?',
        (bid,)
    ).fetchall()
    conn.close()

    return jsonify([dict(r) for r in rows])


# ───────── PAGES ─────────
@app.route('/')
def index():
    return send_from_directory('public', 'index.html')


@app.route('/admin')
def admin():
    if not is_admin():
        return redirect('/login')

    return send_from_directory('public', 'admin.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# ───────── START ─────────
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
