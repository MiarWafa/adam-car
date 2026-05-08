from flask import Flask, request, jsonify, send_from_directory, session, redirect
import sqlite3
import os
from datetime import datetime

app = Flask(__name__, static_folder='public', static_url_path='')
app.secret_key = 'miar_secure_key_2026'

DB = 'bookings.db'
ADMIN_KEY = 'adam2025admin'


# ================= DATABASE =================

def init_db():
    conn = sqlite3.connect(DB)

    conn.execute('''
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER,
            item_name TEXT,
            cost_price REAL,
            sell_price REAL,
            profit REAL,
            FOREIGN KEY (booking_id) REFERENCES bookings(id)
        )
    ''')

    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


# ================= VALIDATION =================

def valid_phone(phone):
    return phone.startswith('01') and len(phone) == 11 and phone.isdigit()


def booking_exists(date, time):
    conn = get_db()

    row = conn.execute(
        '''
        SELECT id FROM bookings
        WHERE booking_date=? AND booking_time=?
        ''',
        (date, time)
    ).fetchone()

    conn.close()

    return row is not None


# ================= LOGIN =================

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        password = request.form.get('password')

        if password == ADMIN_KEY:
            session['admin'] = True
            return redirect('/admin')

        return '❌ كلمة المرور غلط', 401

    return send_from_directory('public', 'login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


def is_admin():
    return session.get('admin')


# ================= BOOKING =================

@app.route('/api/booking', methods=['POST'])
def add_booking():

    data = request.form

    name = (data.get('name') or '').strip()
    phone = (data.get('phone') or '').strip()
    car = (data.get('car') or '').strip()
    service = (data.get('service') or '').strip()
    booking_date = (data.get('booking_date') or '').strip()
    booking_time = (data.get('booking_time') or '').strip()
    notes = (data.get('notes') or '').strip()

    if not all([name, phone, car, service, booking_date, booking_time]):
        return jsonify({
            'success': False,
            'message': 'يرجى ملء كل البيانات'
        }), 400

    if not valid_phone(phone):
        return jsonify({
            'success': False,
            'message': 'رقم الهاتف غير صحيح'
        }), 400

    # الوقت من 9 لـ 9
    try:
        hour = int(booking_time.split(':')[0])

        if hour < 9 or hour > 21:
            return jsonify({
                'success': False,
                'message': 'الحجز متاح من 9 صباحاً لـ 9 مساءً فقط'
            }), 400

    except:
        return jsonify({
            'success': False,
            'message': 'وقت غير صالح'
        }), 400

    if booking_exists(booking_date, booking_time):
        return jsonify({
            'success': False,
            'message': 'هذا الموعد محجوز بالفعل'
        }), 400

    conn = get_db()

    cur = conn.execute(
        '''
        INSERT INTO bookings
        (
            name,
            phone,
            car,
            service,
            booking_date,
            booking_time,
            notes
        )
        VALUES (?,?,?,?,?,?,?)
        ''',
        (
            name,
            phone,
            car,
            service,
            booking_date,
            booking_time,
            notes
        )
    )

    conn.commit()

    booking_id = cur.lastrowid

    conn.close()

    return jsonify({
        'success': True,
        'message': 'تم الحجز بنجاح',
        'id': booking_id
    })


# ================= GET BOOKINGS =================

@app.route('/api/bookings', methods=['GET'])
def get_bookings():

    if not is_admin():
        return jsonify({
            'success': False,
            'message': 'غير مصرح'
        }), 401

    conn = get_db()

    bookings = conn.execute(
        '''
        SELECT * FROM bookings
        ORDER BY id DESC
        '''
    ).fetchall()

    result = []

    for booking in bookings:

        expenses = conn.execute(
            '''
            SELECT * FROM expenses
            WHERE booking_id=?
            ''',
            (booking['id'],)
        ).fetchall()

        result.append({
            **dict(booking),
            'expenses': [dict(e) for e in expenses]
        })

    conn.close()

    return jsonify({
        'success': True,
        'bookings': result
    })


# ================= UPDATE STATUS =================

@app.route('/api/bookings/<int:bid>', methods=['PATCH'])
def update_booking(bid):

    if not is_admin():
        return jsonify({
            'success': False
        }), 401

    data = request.get_json()

    status = data.get('status')

    allowed = [
        'جديد',
        'تم التواصل',
        'مكتمل',
        'ملغي'
    ]

    if status not in allowed:
        return jsonify({
            'success': False,
            'message': 'حالة غير صالحة'
        }), 400

    conn = get_db()

    conn.execute(
        '''
        UPDATE bookings
        SET status=?
        WHERE id=?
        ''',
        (status, bid)
    )

    conn.commit()
    conn.close()

    return jsonify({
        'success': True
    })


# ================= ADD EXPENSE =================

@app.route('/api/bookings/<int:bid>/expense', methods=['POST'])
def add_expense(bid):

    if not is_admin():
        return jsonify({
            'success': False
        }), 401

    data = request.get_json()

    item_name = data.get('item_name')
    cost_price = float(data.get('cost_price'))
    sell_price = float(data.get('sell_price'))

    profit = sell_price - cost_price

    conn = get_db()

    conn.execute(
        '''
        INSERT INTO expenses
        (
            booking_id,
            item_name,
            cost_price,
            sell_price,
            profit
        )
        VALUES (?,?,?,?,?)
        ''',
        (
            bid,
            item_name,
            cost_price,
            sell_price,
            profit
        )
    )

    # totals
    totals = conn.execute(
        '''
        SELECT
        SUM(cost_price) as total_cost,
        SUM(profit) as total_profit
        FROM expenses
        WHERE booking_id=?
        ''',
        (bid,)
    ).fetchone()

    conn.execute(
        '''
        UPDATE bookings
        SET total_cost=?,
            total_profit=?
        WHERE id=?
        ''',
        (
            totals['total_cost'] or 0,
            totals['total_profit'] or 0,
            bid
        )
    )

    conn.commit()
    conn.close()

    return jsonify({
        'success': True
    })


# ================= DASHBOARD STATS =================

@app.route('/api/dashboard')
def dashboard_stats():

    if not is_admin():
        return jsonify({
            'success': False
        }), 401

    conn = get_db()

    stats = conn.execute(
        '''
        SELECT
        COUNT(*) as total_bookings,
        SUM(total_cost) as total_costs,
        SUM(total_profit) as total_profits
        FROM bookings
        '''
    ).fetchone()

    conn.close()

    return jsonify({
        'success': True,
        'stats': dict(stats)
    })


# ================= DELETE =================

@app.route('/api/bookings/<int:bid>', methods=['DELETE'])
def delete_booking(bid):

    if not is_admin():
        return jsonify({
            'success': False
        }), 401

    conn = get_db()

    conn.execute(
        'DELETE FROM expenses WHERE booking_id=?',
        (bid,)
    )

    conn.execute(
        'DELETE FROM bookings WHERE id=?',
        (bid,)
    )

    conn.commit()

    # ترتيب الـ IDs
    rows = conn.execute(
        '''
        SELECT * FROM bookings
        ORDER BY id
        '''
    ).fetchall()

    conn.execute('DELETE FROM bookings')

    new_id = 1

    for row in rows:

        conn.execute(
            '''
            INSERT INTO bookings
            (
                id,
                name,
                phone,
                car,
                service,
                booking_date,
                booking_time,
                notes,
                status,
                total_cost,
                total_profit,
                created_at
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ''',
            (
                new_id,
                row['name'],
                row['phone'],
                row['car'],
                row['service'],
                row['booking_date'],
                row['booking_time'],
                row['notes'],
                row['status'],
                row['total_cost'],
                row['total_profit'],
                row['created_at']
            )
        )

        new_id += 1

    conn.commit()
    conn.close()

    return jsonify({
        'success': True
    })


# ================= PAGES =================

@app.route('/')
def home():
    return send_from_directory('public', 'index.html')


@app.route('/admin')
def admin():

    if not is_admin():
        return redirect('/login')

    return send_from_directory('public', 'admin.html')


# ================= START =================

if __name__ == '__main__':

    init_db()

    print('✅ Server Running')

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False
    )
