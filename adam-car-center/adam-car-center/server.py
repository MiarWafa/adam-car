from flask import Flask, request, jsonify, send_from_directory, session, redirect
import sqlite3
import os

app = Flask(__name__, static_folder='public', static_url_path='')

# إعدادات الأمان والجلسات
app.secret_key = os.environ.get('SECRET_KEY', 'miar_secure_key_2026')
DB = 'bookings.db'
ADMIN_KEY = os.environ.get('ADMIN_KEY', 'adam2025admin')

# ───────── تهيئة قاعدة البيانات ─────────
def init_db():
    conn = sqlite3.connect(DB)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            car TEXT NOT NULL,
            service TEXT NOT NULL,
            notes TEXT DEFAULT '',
            status TEXT DEFAULT 'جديد',
            created_at TEXT DEFAULT (datetime('now','localtime'))
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

# ───────── تسجيل الدخول ─────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_KEY:
            session['admin'] = True
            return redirect('/admin')
        return "❌ كلمة المرور غير صحيحة", 401
    return send_from_directory('public', 'login.html')

# ───────── إضافة حجز جديد ─────────
@app.route('/api/booking', methods=['POST'])
def add_booking():
    data = request.get_json()
    name = (data.get('name') or '').strip()
    phone = (data.get('phone') or '').strip()
    car = (data.get('car') or '').strip()
    service = (data.get('service') or '').strip()
    notes = (data.get('notes') or '').strip()

    if not all([name, phone, car, service]):
        return jsonify({'success': False, 'message': 'يرجى ملء جميع الحقول'}), 400

    conn = get_db()
    cur = conn.execute(
        'INSERT INTO bookings (name, phone, car, service, notes) VALUES (?, ?, ?, ?, ?)',
        (name, phone, car, service, notes)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'id': cur.lastrowid})

# ───────── جلب الحجوزات (للمسؤول فقط) ─────────
@app.route('/api/bookings', methods=['GET'])
def get_bookings():
    if not is_admin():
        return jsonify({'success': False, 'message': 'غير مصرح'}), 401
    
    conn = get_db()
    rows = conn.execute('SELECT * FROM bookings ORDER BY id DESC').fetchall()
    conn.close()
    return jsonify({'success': True, 'bookings': [dict(r) for r in rows]})

# ───────── تحديث حالة الحجز ─────────
@app.route('/api/bookings/<int:bid>', methods=['PATCH'])
def update_booking(bid):
    if not is_admin():
        return jsonify({'success': False, 'message': 'غير مصرح'}), 401
    
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

# ───────── حذف حجز ─────────
@app.route('/api/bookings/<int:bid>', methods=['DELETE'])
def delete_booking(bid):
    if not is_admin():
        return jsonify({'success': False, 'message': 'غير مصرح'}), 401
    
    conn = get_db()
    conn.execute('DELETE FROM bookings WHERE id=?', (bid,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ───────── المسارات الأمامية ─────────
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

# ───────── التشغيل ─────────
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
