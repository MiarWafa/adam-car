from flask import Flask, request, jsonify, send_from_directory, session, redirect
import sqlite3, os

app = Flask(__name__, static_folder='public', static_url_path='')

# مهم جدًا للجلسات
app.secret_key = os.environ.get('SECRET_KEY', 'miar_secure_key_2026')

DB = 'bookings.db'
ADMIN_KEY = os.environ.get('ADMIN_KEY', 'adam2025admin')


# ───────── DB INIT ─────────
def init_db():
    conn = sqlite3.connect(DB)
    
    # تحديث جدول الحجوزات ليشمل المواعيد (التاريخ والوقت)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            car TEXT NOT NULL,
            service TEXT NOT NULL,
            appointment_date TEXT NOT NULL, 
            appointment_time TEXT NOT NULL,
            notes TEXT DEFAULT '',
            status TEXT DEFAULT 'جديد',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')

    # إضافة جدول جديد للمصروفات وقطع الغيار
    conn.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            cost REAL NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (booking_id) REFERENCES bookings (id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    # تفعيل القيود الخاصة بالمفاتيح الأجنبية (Foreign keys)
    conn.execute('PRAGMA foreign_keys = ON')
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


# ───────── ADD BOOKING ─────────
@app.route('/api/booking', methods=['POST'])
def add_booking():
    data = request.get_json()

    name = (data.get('name') or '').strip()
    phone = (data.get('phone') or '').strip()
    car = (data.get('car') or '').strip()
    service = (data.get('service') or '').strip()
    appointment_date = (data.get('appointment_date') or '').strip()
    appointment_time = (data.get('appointment_time') or '').strip()
    notes = (data.get('notes') or '').strip()

    # التحقق من أن العميل اختار موعد
    if not all([name, phone, car, service, appointment_date, appointment_time]):
        return jsonify({'success': False, 'message': 'يرجى ملء جميع الحقول بما فيها تاريخ ووقت الحجز'}), 400

    conn = get_db()
    cur = conn.execute(
        'INSERT INTO bookings (name, phone, car, service, appointment_date, appointment_time, notes) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (name, phone, car, service, appointment_date, appointment_time, notes)
    )
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'id': cur.lastrowid})


# ───────── GET BOOKINGS ─────────
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


# ───────── EXPENSES (المصروفات) ─────────
@app.route('/api/bookings/<int:bid>/expenses', methods=['GET', 'POST'])
def manage_expenses(bid):
    if not is_admin():
        return jsonify({'success': False, 'message': 'غير مصرح'}), 401

    conn = get_db()

    if request.method == 'POST':
        # التأكد أن حالة الحجز "تم التواصل" قبل السماح بإضافة مصروفات
        booking = conn.execute('SELECT status FROM bookings WHERE id=?', (bid,)).fetchone()
        
        if not booking:
            conn.close()
            return jsonify({'success': False, 'message': 'الحجز غير موجود'}), 404
            
        if booking['status'] != 'تم التواصل':
            conn.close()
            return jsonify({'success': False, 'message': 'لا يمكن إضافة مصروفات إلا للسيارات التي حالتها "تم التواصل"'}), 400

        data = request.get_json()
        description = data.get('description', '').strip()
        cost = data.get('cost')

        if not description or cost is None:
            conn.close()
            return jsonify({'success': False, 'message': 'يرجى إدخال وصف وقيمة المصروف'}), 400

        conn.execute('INSERT INTO expenses (booking_id, description, cost) VALUES (?, ?, ?)', 
                     (bid, description, float(cost)))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'تم إضافة المصروفات بنجاح'})

    # في حالة الـ GET، استرجاع كل المصروفات الخاصة بهذه السيارة
    rows = conn.execute('SELECT * FROM expenses WHERE booking_id=? ORDER BY id DESC', (bid,)).fetchall()
    conn.close()

    return jsonify({'success': True, 'expenses': [dict(r) for r in rows]})


# ───────── DELETE ─────────
@app.route('/api/bookings/<int:bid>', methods=['DELETE'])
def delete_booking(bid):
    if not is_admin():
        return jsonify({'success': False, 'message': 'غير مصرح'}), 401

    conn = get_db()
    conn.execute('DELETE FROM bookings WHERE id=?', (bid,))
    # بفضل الـ CASCADE في الداتابيز، سيتم مسح مصروفات هذه السيارة تلقائياً
    conn.commit()
    conn.close()

    return jsonify({'success': True})


# ───────── FRONTEND ─────────
@app.route('/')
def index():
    return send_from_directory('public', 'index.html')


@app.route('/admin')
def admin():
    # هذا الكود هو الذي يحمي صفحة الأدمن. لا تضع أي فورم تسجيل دخول في الـ HTML الخاص بالأدمن
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
