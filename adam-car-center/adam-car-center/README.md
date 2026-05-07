# مركز آدم - موقع + Backend

## الملفات
- `server.py` — السيرفر (Python/Flask)
- `public/index.html` — الموقع الرئيسي
- `public/admin.html` — لوحة الإدارة
- `requirements.txt` — المكتبات المطلوبة

## تشغيل محلي (على تليفونك أو لابتوب)
```bash
pip install flask
python3 server.py
```
ثم افتح: http://localhost:5000

## الرفع على الإنترنت (Render.com - مجاني)
1. رفع المجلد على GitHub
2. اتصل بـ Render.com وعمل "New Web Service"
3. اختر الـ repo
4. Start Command: `python server.py`
5. Add env variable: ADMIN_KEY = كلمة_سرك

## كلمة مرور الإدارة الافتراضية
`adam2025admin`
غيّرها في server.py السطر 8
