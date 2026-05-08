from flask import Flask, request, jsonify, send_from_directory, session, redirect
import sqlite3
import os
from datetime import datetime

app = Flask(__name__, static_folder='public', static_url_path='')

# إعدادات الأمان
app.secret_key = os.environ.get('SECRET_KEY', 'miar_secure_key_2026')
DB = 'bookings.db'
ADMIN_KEY = os.environ.get('ADMIN_KEY', 'adam2025admin')

# ───────── تهيئة قاعدة البيانات المطورة ─────────
def init_db():
    conn = sqlite3.connect(DB)
    # جدول الحجوزات المطور
    conn.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            car TEXT NOT NULL,
            service TEXT NOT NULL,
            booking_date TEXT NOT NULL,
            booking_time TEXT NOT NULL,
            status TEXT DEFAULT 'جديد',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')
    # جدول المصروفات والأرباح لكل سيارة
    conn.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER,
            item_name TEXT NOT NULL,
            cost_price REAL NOT NULL,
            selling_price REAL NOT NULL,
            profit REAL NOT NULL,
            FOREIGN KEY (booking_id) REFERENCES bookings (id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON") # لتفعيل الحذف المتسلسل
    return conn

def is_admin():
    return session.get('admin') is True

# ───────── منطق الحجوزات والمواعيد ─────────
@app.route('/api/booking', methods=['POST'])
def add_booking():
    data = request.get_json()
    name = (data.get('name') or '').strip()
    phone = (data.get('phone') or '').strip()
    car = (data.get('car') or '').strip()
    service = (data.get('service') or '').strip()
    b_date = data.get('date') # YYYY-MM-DD
    b_time = data.get('time') # HH:MM (24h format)

    # 1. التحقق من رقم الهاتف (مثال: 11 رقم)
    if not phone.isdigit() or len(phone) < 10:
        return jsonify({'success': False, 'message': 'رقم الهاتف غير صحيح'}), 400

    # 2. التحقق من المواعيد (9 صباحاً إلى 9 مساءً)
    hour = int(b_time.split(':')[0])
    if hour < 9 or hour >= 21:
        return jsonify({'success': False, 'message': 'المواعيد المتاحة من 9 ص حتى 9 م'}), 400

    # 3. منع التضارب في المواعيد
    conn = get_db()
    existing = conn.execute('SELECT id FROM bookings WHERE booking_date=? AND booking_time=?', (b_date, b_time)).fetchone()
    if existing:
        conn.close()
        return jsonify({'success': False, 'message': 'هذا الموعد محجوز مسبقاً'}), 400

    cur = conn.execute(
        'INSERT INTO bookings (name, phone, car, service, booking_date, booking_time) VALUES (?, ?, ?, ?, ?, ?)',
        (name, phone, car, service, b_date, b_time)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'id': cur.lastrowid})

# ───────── إدارة المصروفات والأرباح ─────────
@app.route('/api/expenses', methods=['POST'])
def add_expense():
    if not is_admin(): return jsonify({'success': False}), 401
    
    data = request.get_json()
    bid = data.get('booking_id')
    item = data.get('item')
    cost = float(data.get('cost'))
    sell = float(data.get('sell'))
    profit = sell - cost

    conn = get_db()
    conn.execute('INSERT INTO expenses (booking_id, item_name, cost_price, selling_price, profit) VALUES (?, ?, ?, ?, ?)',
                 (bid, item, cost, sell, profit))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'profit': profit})

# ───────── لوحة التحكم (الداشبورد) ─────────
@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    if not is_admin(): return jsonify({'success': False}), 401
    
    conn = get_db()
    # جلب الحجوزات مع إعادة ترتيب الأرقام للعرض فقط
    rows = conn.execute('SELECT * FROM bookings ORDER BY booking_date ASC, booking_time ASC').fetchall()
    bookings = [dict(r) for r in rows]
    
    # حساب الإجماليات
    stats = conn.execute('SELECT SUM(cost_price) as total_costs, SUM(profit) as total_profits FROM expenses').fetchone()
    
    conn.close()
    return jsonify({
        'success': True, 
        'bookings': bookings,
        'total_costs': stats['total_costs'] or 0,
        'total_profits': stats['total_profits'] or 0
    })

# ───────── تحديث الحالة وحذف الحجز ─────────
@app.route('/api/bookings/<int:bid>', methods=['PATCH'])
def update_status(bid):
    if not is_admin(): return jsonify({'success': False}), 401
    status = request.get_json().get('status')
    conn = get_db()
    conn.execute('UPDATE bookings SET status=? WHERE id=?', (status, bid))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/bookings/<int:bid>', methods=['DELETE'])
def delete_booking(bid):
    if not is_admin(): return jsonify({'success': False}), 401
    conn = get_db()
    conn.execute('DELETE FROM bookings WHERE id=?', (bid,))
    # SQLite سيتولى حذف المصروفات المرتبطة تلقائياً بسبب ON DELETE CASCADE
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ───────── المسارات التقليدية ─────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_KEY:
            session['admin'] = True
            return redirect('/admin')
        return "❌ كلمة المرور غير صحيحة", 401
    return send_from_directory('public', 'login.html')

@app.route('/')
def index(): return send_from_directory('public', 'index.html')

@app.route('/admin')
def admin():
    if not is_admin(): return redirect('/login')
    return send_from_directory('public', 'admin.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
