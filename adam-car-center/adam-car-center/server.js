const express = require('express');
const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;

// ─── Middleware ───
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// ─── Database Setup ───
const db = new Database('bookings.db');

db.exec(`
  CREATE TABLE IF NOT EXISTS bookings (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL,
    phone     TEXT NOT NULL,
    car       TEXT NOT NULL,
    service   TEXT NOT NULL,
    notes     TEXT,
    status    TEXT DEFAULT 'جديد',
    created_at TEXT DEFAULT (datetime('now','localtime'))
  )
`);

// ─── API: Submit Booking ───
app.post('/api/booking', (req, res) => {
  const { name, phone, car, service, notes } = req.body;

  if (!name || !phone || !car || !service) {
    return res.status(400).json({ success: false, message: 'يرجى ملء جميع الحقول المطلوبة' });
  }

  const stmt = db.prepare(`
    INSERT INTO bookings (name, phone, car, service, notes)
    VALUES (?, ?, ?, ?, ?)
  `);
  const result = stmt.run(name, phone, car, service, notes || '');

  res.json({
    success: true,
    message: 'تم استلام حجزك بنجاح! سنتواصل معك قريباً',
    id: result.lastInsertRowid
  });
});

// ─── API: Get All Bookings (Admin) ───
app.get('/api/bookings', (req, res) => {
  const adminKey = req.headers['x-admin-key'];
  if (adminKey !== process.env.ADMIN_KEY && adminKey !== 'adam2025admin') {
    return res.status(401).json({ success: false, message: 'غير مصرح' });
  }
  const bookings = db.prepare('SELECT * FROM bookings ORDER BY id DESC').all();
  res.json({ success: true, bookings });
});

// ─── API: Update Booking Status ───
app.patch('/api/bookings/:id', (req, res) => {
  const adminKey = req.headers['x-admin-key'];
  if (adminKey !== process.env.ADMIN_KEY && adminKey !== 'adam2025admin') {
    return res.status(401).json({ success: false, message: 'غير مصرح' });
  }
  const { status } = req.body;
  const allowed = ['جديد', 'تم التواصل', 'مكتمل', 'ملغي'];
  if (!allowed.includes(status)) {
    return res.status(400).json({ success: false, message: 'حالة غير صالحة' });
  }
  db.prepare('UPDATE bookings SET status = ? WHERE id = ?').run(status, req.params.id);
  res.json({ success: true });
});

// ─── API: Delete Booking ───
app.delete('/api/bookings/:id', (req, res) => {
  const adminKey = req.headers['x-admin-key'];
  if (adminKey !== process.env.ADMIN_KEY && adminKey !== 'adam2025admin') {
    return res.status(401).json({ success: false, message: 'غير مصرح' });
  }
  db.prepare('DELETE FROM bookings WHERE id = ?').run(req.params.id);
  res.json({ success: true });
});

// ─── Serve Frontend ───
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.get('/admin', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'admin.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`✅ مركز آدم - السيرفر شغّال على http://localhost:${PORT}`);
  console.log(`📋 لوحة الإدارة: http://localhost:${PORT}/admin`);
});
