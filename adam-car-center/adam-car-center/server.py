from flask import Flask, request, jsonify, send_from_directory
import sqlite3, os, json
from datetime import datetime
 
app = Flask(__name__, static_folder='public', static_url_path='')
 
DB = 'bookings.db'
ADMIN_KEY = os.environ.get('ADMIN_KEY', 'adam2025admin')
 
ALL_HOURS = ['9:00','10:00','11:00','12:00','13:00','14:00','15:00','16:00','17:00','18:00','19:00','20:00','21:00']
 
# ─── DB INIT ────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS bookings (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            phone      TEXT NOT NULL,
            car        TEXT NOT NULL,
            service    TEXT NOT NULL,
            date       TEXT DEFAULT '',
            slot       TEXT DEFAULT '',
            notes      TEXT DEFAULT '',
            status     TEXT DEFAULT 'جديد',
            expenses   TEXT DEFAULT '[]',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
 
        CREATE TABLE IF NOT EXISTS slot_config (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            date    TEXT NOT NULL UNIQUE,
            enabled TEXT NOT NULL DEFAULT '[]'
        );
    ''')
    conn.commit()
    conn.close()
 
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn
 
def check_admin(req):
    return req.headers.get('x-admin-key') == ADMIN_KEY
 
def row_to_dict(row):
    d = dict(row)
    try:
        d['expenses'] = json.loads(d.get('expenses') or '[]')
    except:
        d['expenses'] = []
    return d
 
# ─── REORDER IDs after delete ────────────────────────────────
def reorder_ids(conn):
    rows = conn.execute('SELECT id FROM bookings ORDER BY id ASC').fetchall()
    for new_id, row in enumerate(rows, start=1):
        if row['id'] != new_id:
            conn.execute('UPDATE bookings SET id=? WHERE id=?', (new_id, row['id']))
    conn.execute("DELETE FROM sqlite_sequence WHERE name='bookings'")
    if rows:
        conn.execute("INSERT INTO sqlite_sequence(name,seq) VALUES('bookings',?)", (len(rows),))
 
# ─── SLOTS HELPERS ───────────────────────────────────────────
def get_enabled_slots(conn, date):
    row = conn.execute('SELECT enabled FROM slot_config WHERE date=?', (date,)).fetchone()
    if row:
        try:
            return json.loads(row['enabled'])
        except:
            pass
    return ALL_HOURS  # default: all enabled
 
def get_booked_slots(conn, date):
    rows = conn.execute("SELECT slot FROM bookings WHERE date=? AND status != 'ملغي'", (date,)).fetchall()
    return [r['slot'] for r in rows if r['slot']]
 
# ─── API: GET available slots ────────────────────────────────
@app.route('/api/slots')
def get_slots():
    date = request.args.get('date', '')
    if not date:
        return jsonify({'success': False, 'message': 'يرجى تحديد التاريخ'}), 400
    conn = get_db()
    enabled = get_enabled_slots(conn, date)
    booked  = get_booked_slots(conn, date)
    conn.close()
    slots = []
    slots.append({
    'value': h,
    'label': h,
    'booked': h in booked,
    'available': h in enabled
})
            
    return jsonify({'success': True, 'slots': slots})
 
# ─── API: GET slot config (admin) ───────────────────────────
@app.route('/api/slot-config')
def get_slot_config():
    if not check_admin(request):
        return jsonify({'success': False, 'message': 'غير مصرح'}), 401
    date = request.args.get('date', '')
    conn = get_db()
    enabled = get_enabled_slots(conn, date)
    conn.close()
    return jsonify({'success': True, 'enabled': enabled})
 
# ─── API: SAVE slot config (admin) ──────────────────────────
@app.route('/api/slot-config', methods=['POST'])
def save_slot_config():
    if not check_admin(request):
        return jsonify({'success': False, 'message': 'غير مصرح'}), 401
    data = request.get_json()
    date    = (data.get('date') or '').strip()
    enabled = data.get('enabled', [])
    if not date:
        return jsonify({'success': False, 'message': 'التاريخ مطلوب'}), 400
    conn = get_db()
    conn.execute('INSERT INTO slot_config(date,enabled) VALUES(?,?) ON CONFLICT(date) DO UPDATE SET enabled=?',
                 (date, json.dumps(enabled), json.dumps(enabled)))
    conn.commit()
    conn.close()
    return jsonify({'success': True})
 
# ─── API: CREATE booking ─────────────────────────────────────
@app.route('/api/booking', methods=['POST'])
def add_booking():
    data    = request.get_json()
    name    = (data.get('name') or '').strip()
    phone   = (data.get('phone') or '').strip()
    car     = (data.get('car') or '').strip()
    service = (data.get('service') or '').strip()
    date    = (data.get('date') or '').strip()
    slot    = (data.get('slot') or '').strip()
    notes   = (data.get('notes') or '').strip()
 
    if not all([name, phone, car, service, date, slot]):
        return jsonify({'success': False, 'message': 'يرجى ملء جميع الحقول المطلوبة'}), 400
 
    conn = get_db()
 
    # Check slot not already booked
    booked = get_booked_slots(conn, date)
    if slot in booked:
        conn.close()
        return jsonify({'success': False, 'message': 'عذراً، هذا الموعد محجوز بالفعل — اختار وقتاً آخر'}), 409
 
    # Check slot is enabled
    enabled = get_enabled_slots(conn, date)
    if slot not in enabled:
        conn.close()
        return jsonify({'success': False, 'message': 'هذا الموعد غير متاح'}), 400
 
    cur = conn.execute(
        'INSERT INTO bookings (name, phone, car, service, date, slot, notes) VALUES (?,?,?,?,?,?,?)',
        (name, phone, car, service, date, slot, notes)
    )
    conn.commit()
    bid = cur.lastrowid
    conn.close()
    return jsonify({'success': True, 'message': 'تم استلام حجزك بنجاح! سنتواصل معك قريباً 🚗', 'id': bid})
 
# ─── API: LIST bookings (admin) ──────────────────────────────
@app.route('/api/bookings')
def get_bookings():
    if not check_admin(request):
        return jsonify({'success': False, 'message': 'غير مصرح'}), 401
    conn = get_db()
    rows = conn.execute('SELECT * FROM bookings ORDER BY id ASC').fetchall()
    conn.close()
    return jsonify({'success': True, 'bookings': [row_to_dict(r) for r in rows]})
 
# ─── API: UPDATE status ──────────────────────────────────────
@app.route('/api/bookings/<int:bid>', methods=['PATCH'])
def update_booking(bid):
    if not check_admin(request):
        return jsonify({'success': False, 'message': 'غير مصرح'}), 401
    data   = request.get_json()
    status = data.get('status', '')
    if status not in ['جديد', 'تم التواصل', 'مكتمل', 'ملغي']:
        return jsonify({'success': False, 'message': 'حالة غير صالحة'}), 400
    conn = get_db()
    conn.execute('UPDATE bookings SET status=? WHERE id=?', (status, bid))
    conn.commit()
    conn.close()
    return jsonify({'success': True})
 
# ─── API: DELETE booking + reorder ──────────────────────────
@app.route('/api/bookings/<int:bid>', methods=['DELETE'])
def delete_booking(bid):
    if not check_admin(request):
        return jsonify({'success': False, 'message': 'غير مصرح'}), 401
    conn = get_db()
    conn.execute('DELETE FROM bookings WHERE id=?', (bid,))
    reorder_ids(conn)
    conn.commit()
    conn.close()
    return jsonify({'success': True})
 
# ─── API: ADD expense ───────────────────────────────────────
@app.route('/api/bookings/<int:bid>/expenses', methods=['POST'])
def add_expense(bid):
    if not check_admin(request):
        return jsonify({'success': False, 'message': 'غير مصرح'}), 401
    data  = request.get_json()
    desc  = (data.get('desc') or '').strip()
    price = float(data.get('price', 0))
    if not desc or price < 0:
        return jsonify({'success': False, 'message': 'بيانات غير صالحة'}), 400
    conn = get_db()
    row  = conn.execute('SELECT expenses FROM bookings WHERE id=?', (bid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'success': False, 'message': 'حجز غير موجود'}), 404
    try:
        expenses = json.loads(row['expenses'] or '[]')
    except:
        expenses = []
    expenses.append({'desc': desc, 'price': price, 'added_at': datetime.now().strftime('%Y-%m-%d %H:%M')})
    conn.execute('UPDATE bookings SET expenses=? WHERE id=?', (json.dumps(expenses, ensure_ascii=False), bid))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'expenses': expenses})
 
# ─── API: DELETE expense ────────────────────────────────────
@app.route('/api/bookings/<int:bid>/expenses/<int:idx>', methods=['DELETE'])
def delete_expense(bid, idx):
    if not check_admin(request):
        return jsonify({'success': False, 'message': 'غير مصرح'}), 401
    conn = get_db()
    row  = conn.execute('SELECT expenses FROM bookings WHERE id=?', (bid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'success': False, 'message': 'حجز غير موجود'}), 404
    try:
        expenses = json.loads(row['expenses'] or '[]')
    except:
        expenses = []
    if idx < 0 or idx >= len(expenses):
        conn.close()
        return jsonify({'success': False, 'message': 'البند غير موجود'}), 404
    expenses.pop(idx)
    conn.execute('UPDATE bookings SET expenses=? WHERE id=?', (json.dumps(expenses, ensure_ascii=False), bid))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'expenses': expenses})
 
# ─── SERVE PAGES ────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory('public', 'index.html')
 
@app.route('/admin')
def admin():
    return send_from_directory('public', 'admin.html')
 
# ─── RUN ────────────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    print(f'\n✅ مركز آدم — السيرفر شغّال على http://localhost:{port}')
    print(f'📋 لوحة الإدارة: http://localhost:{port}/admin\n')
    app.run(host='0.0.0.0', port=port, debug=False)
