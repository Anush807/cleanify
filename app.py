"""
CLEANIFY - Full Backend (PostgreSQL version)
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import base64
import json
import hashlib
import secrets
import re
import tempfile
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor

# ── WasteClassifier ──
try:
    from waste_classifier import WasteClassifier
    waste_classifier = WasteClassifier()
    print("✅ WasteClassifier loaded successfully")
except Exception as e:
    waste_classifier = None
    print(f"⚠️  WasteClassifier not available: {e}")

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = secrets.token_hex(32)

# ── CORS ──
CORS(app, supports_credentials=True,
     origins=["https://swachtha.vercel.app",
               "http://localhost:5500", "http://127.0.0.1:5500"])

@app.after_request
def after_request(response):
    origin = request.headers.get('Origin', '')
    response.headers['Access-Control-Allow-Origin'] = origin or '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,PATCH,DELETE,OPTIONS'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response

@app.route('/api/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    response = jsonify({})
    response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,PATCH,DELETE,OPTIONS'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response, 200

# ─────────────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────────────

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        fullname TEXT NOT NULL,
        phone TEXT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        green_points INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS complaints (
        id TEXT PRIMARY KEY,
        user_id INTEGER,
        reporter_name TEXT,
        type TEXT,
        issue_type TEXT,
        severity TEXT,
        location TEXT,
        description TEXT,
        image_data TEXT,
        status TEXT DEFAULT 'Pending',
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS rewards (
        id SERIAL PRIMARY KEY,
        recipient TEXT NOT NULL,
        reward_type TEXT NOT NULL,
        points INTEGER DEFAULT 0,
        reason TEXT,
        awarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")

    ADMIN_EMAILS = [
        ('Admin User',    'admin@cleanify.com',           'admin123', 'admin'),
        ('Vamshi Poojary','vamshitharpoojary@gmail.com',  'admin123', 'admin'),
        ('Suprabha B',    'bsuprabha@gmail.com',          'admin123', 'admin'),
        ('Roshu',         'roshu042004@gmail.com',         'admin123', 'admin'),
    ]
    for name, email, pwd, role in ADMIN_EMAILS:
        try:
            c.execute("""
                INSERT INTO users (fullname, email, password_hash, role)
                VALUES (%s, %s, %s, %s) ON CONFLICT (email) DO NOTHING
            """, (name, email, hash_password(pwd), role))
        except Exception:
            pass

    conn.commit()
    c.close()
    conn.close()
    print("✅ Database initialized")

def hash_password(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def create_session(user_id):
    token = secrets.token_hex(32)
    expires = datetime.now() + timedelta(days=7)
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (%s, %s, %s)",
              (token, user_id, expires.isoformat()))
    conn.commit()
    c.close(); conn.close()
    return token

def get_user_from_token(token):
    if not token:
        return None
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT u.* FROM users u
        JOIN sessions s ON s.user_id = u.id
        WHERE s.token = %s AND s.expires_at > %s
    """, (token, datetime.now().isoformat()))
    row = c.fetchone()
    c.close(); conn.close()
    return dict(row) if row else None

def require_auth(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = get_user_from_token(token)
        if not user:
            return jsonify({"error": "Unauthorized"}), 401
        request.current_user = user
        return f(*args, **kwargs)
    return wrapper

def require_admin(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = get_user_from_token(token)
        if not user:
            return jsonify({"error": "Unauthorized"}), 401
        if user['role'] != 'admin':
            return jsonify({"error": "Admin access required"}), 403
        request.current_user = user
        return f(*args, **kwargs)
    return wrapper

# ─────────────────────────────────────────────
# SERVE STATIC FILES
# ─────────────────────────────────────────────

@app.route('/')
def serve_index():
    return send_from_directory('templates', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    if filename.startswith('api/'):
        return jsonify({"error": "Not found"}), 404
    if os.path.exists(os.path.join('templates', filename)):
        return send_from_directory('templates', filename)
    if os.path.exists(os.path.join('static', filename)):
        return send_from_directory('static', filename)
    if filename.startswith('static/'):
        asset = filename[len('static/'):]
        if os.path.exists(os.path.join('static', asset)):
            return send_from_directory('static', asset)
    return "Not Found", 404

# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    fullname = data.get('fullname', '').strip()
    phone    = data.get('phone', '').strip()
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role     = data.get('role', 'user')

    if not all([fullname, email, password]):
        return jsonify({"error": "Missing required fields"}), 400
    if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
        return jsonify({"error": "Invalid email address"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    ALLOWED_ADMIN_EMAILS = [
        'vamshitharpoojary@gmail.com', 'bsuprabha@gmail.com',
        'roshu042004@gmail.com', 'admin@cleanify.com'
    ]
    if role == 'admin' and email not in ALLOWED_ADMIN_EMAILS:
        return jsonify({"error": "Admin registration is restricted."}), 403

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE email = %s", (email,))
    if c.fetchone():
        c.close(); conn.close()
        return jsonify({"error": "Account already exists. Please sign in."}), 409

    try:
        c.execute("INSERT INTO users (fullname, phone, email, password_hash, role) VALUES (%s,%s,%s,%s,%s)",
                  (fullname, phone, email, hash_password(password), role))
        conn.commit()
        c.execute("SELECT id FROM users WHERE email = %s", (email,))
        user_id = c.fetchone()['id']
        token = create_session(user_id)
        c.close(); conn.close()
        return jsonify({"message": "Account created!", "token": token, "role": role}), 201
    except Exception as e:
        c.close(); conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    data     = request.json
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')
    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email = %s AND password_hash = %s",
              (email, hash_password(password)))
    user = c.fetchone()
    c.close(); conn.close()
    if not user:
        return jsonify({"error": "Invalid email or password"}), 401
    user  = dict(user)
    token = create_session(user['id'])
    return jsonify({"token": token, "role": user['role'], "fullname": user['fullname'],
                    "email": user['email'], "green_points": user['green_points'], "level": user['level']})

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token:
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM sessions WHERE token = %s", (token,))
        conn.commit()
        c.close(); conn.close()
    return jsonify({"message": "Logged out"})

@app.route('/api/auth/me', methods=['GET'])
@require_auth
def me():
    u = request.current_user
    return jsonify({"id": u['id'], "fullname": u['fullname'], "email": u['email'],
                    "phone": u.get('phone'), "role": u['role'],
                    "green_points": u['green_points'], "level": u['level']})

# ─────────────────────────────────────────────
# COMPLAINTS
# ─────────────────────────────────────────────

def award_points(user_id, points):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET green_points = green_points + %s WHERE id = %s", (points, user_id))
    c.execute("SELECT green_points FROM users WHERE id = %s", (user_id,))
    user = c.fetchone()
    if user:
        new_level = max(1, user['green_points'] // 100 + 1)
        c.execute("UPDATE users SET level = %s WHERE id = %s", (new_level, user_id))
    conn.commit()
    c.close(); conn.close()

@app.route('/api/complaints', methods=['POST'])
@require_auth
def submit_complaint():
    data = request.json
    user = request.current_user
    complaint_id   = 'SWC' + str(int(datetime.now().timestamp() * 1000))[-8:]
    issue_type     = data.get('issueType', 'dumping')
    severity       = data.get('severity', '')
    location       = data.get('location', '')
    description    = data.get('description', '')
    image_data     = data.get('image', '')
    complaint_type = data.get('type', 'report')
    if not location or not description:
        return jsonify({"error": "Location and description are required"}), 400
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO complaints
        (id, user_id, reporter_name, type, issue_type, severity, location, description, image_data, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'Pending')""",
        (complaint_id, user['id'], user['fullname'], complaint_type,
         issue_type, severity, location, description, image_data))
    conn.commit()
    c.close(); conn.close()
    award_points(user['id'], 15)
    return jsonify({"message": "Complaint submitted!", "id": complaint_id, "points_awarded": 15}), 201

@app.route('/api/complaints', methods=['GET'])
@require_auth
def get_complaints():
    user = request.current_user
    conn = get_db()
    c = conn.cursor()
    if user['role'] == 'admin':
        c.execute("SELECT * FROM complaints ORDER BY timestamp DESC")
    else:
        c.execute("SELECT * FROM complaints WHERE user_id = %s ORDER BY timestamp DESC", (user['id'],))
    rows = c.fetchall()
    c.close(); conn.close()
    return jsonify([{
        "id": r['id'], "type": r['type'], "issueType": r['issue_type'],
        "severity": r['severity'], "location": r['location'], "description": r['description'],
        "image": r['image_data'] or '', "status": r['status'],
        "timestamp": str(r['timestamp']), "reporter": r['reporter_name'] or 'Anonymous'
    } for r in rows])

@app.route('/api/complaints/<complaint_id>/status', methods=['PATCH'])
@require_admin
def update_status(complaint_id):
    data = request.json
    new_status = data.get('status')
    if new_status not in ['Pending', 'In Progress', 'Resolved', 'Rejected']:
        return jsonify({"error": "Invalid status"}), 400
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM complaints WHERE id = %s", (complaint_id,))
    complaint = c.fetchone()
    if not complaint:
        c.close(); conn.close()
        return jsonify({"error": "Complaint not found"}), 404
    c.execute("UPDATE complaints SET status = %s WHERE id = %s", (new_status, complaint_id))
    conn.commit()
    if new_status == 'Resolved' and complaint['user_id']:
        award_points(complaint['user_id'], 10)
    c.close(); conn.close()
    return jsonify({"message": f"Status updated to {new_status}"})

@app.route('/api/complaints/<complaint_id>', methods=['DELETE'])
@require_admin
def delete_complaint(complaint_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM complaints WHERE id = %s", (complaint_id,))
    conn.commit()
    c.close(); conn.close()
    return jsonify({"message": "Complaint deleted"})

@app.route('/api/complaints/clear', methods=['DELETE'])
@require_admin
def clear_all_complaints():
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM complaints")
    conn.commit()
    c.close(); conn.close()
    return jsonify({"message": "All complaints cleared"})

# ─────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────

@app.route('/api/stats', methods=['GET'])
@require_admin
def get_stats():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) AS n FROM complaints"); total = c.fetchone()['n']
    c.execute("SELECT COUNT(*) AS n FROM complaints WHERE status='Pending'"); pending = c.fetchone()['n']
    c.execute("SELECT COUNT(*) AS n FROM complaints WHERE status='Resolved'"); resolved = c.fetchone()['n']
    c.execute("SELECT COUNT(*) AS n FROM complaints WHERE type='washroom'"); washroom = c.fetchone()['n']
    c.execute("SELECT COUNT(*) AS n FROM rewards"); total_rewards = c.fetchone()['n']
    c.close(); conn.close()
    return jsonify({"total": total, "pending": pending, "resolved": resolved,
                    "washroom": washroom, "rewards": total_rewards})

# ─────────────────────────────────────────────
# REWARDS
# ─────────────────────────────────────────────

@app.route('/api/rewards', methods=['GET'])
@require_auth
def get_rewards():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM rewards ORDER BY awarded_at DESC")
    rows = c.fetchall()
    c.close(); conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/rewards', methods=['POST'])
@require_admin
def add_reward():
    data = request.json
    recipient   = data.get('recipient', '').strip()
    reward_type = data.get('rewardType', '')
    points      = int(data.get('points', 0))
    reason      = data.get('reason', '').strip()
    if not recipient or not reward_type:
        return jsonify({"error": "Recipient and reward type are required"}), 400
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO rewards (recipient, reward_type, points, reason) VALUES (%s,%s,%s,%s)",
              (recipient, reward_type, points, reason))
    conn.commit()
    c.close(); conn.close()
    return jsonify({"message": "Reward added!"}), 201

@app.route('/api/rewards/<int:reward_id>', methods=['DELETE'])
@require_admin
def delete_reward(reward_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM rewards WHERE id = %s", (reward_id,))
    conn.commit()
    c.close(); conn.close()
    return jsonify({"message": "Reward deleted"})

# ─────────────────────────────────────────────
# AI CLASSIFIER
# ─────────────────────────────────────────────

@app.route('/api/classify', methods=['POST'])
@require_auth
def classify_waste():
    if waste_classifier is None:
        return jsonify({"error": "Classifier not available."}), 503
    data      = request.json
    image_b64 = data.get('image', '')
    if not image_b64:
        return jsonify({"error": "No image provided"}), 400
    try:
        if ',' in image_b64:
            image_b64 = image_b64.split(',', 1)[1]
        img_bytes = base64.b64decode(image_b64)
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp.write(img_bytes)
            tmp_path = tmp.name
        try:
            result = waste_classifier.predict(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        waste_type = result['waste_type']
        confidence = result['confidence']
        if waste_type == 'ewaste':
            category, bin_color, icon = "E-Waste", "Red", "💻"
        elif waste_type == 'wet':
            category, bin_color, icon = "Wet Waste", "Green", "🥬"
        else:
            category, bin_color, icon = "Dry Waste", "Blue", "📦"
        award_points(request.current_user['id'], 5)
        return jsonify({"category": category, "confidence": round(confidence, 1),
                        "items_detected": f"{category} material detected",
                        "disposal_tip": result['disposal_method'],
                        "waste_examples": result['waste_examples'],
                        "bin_color": bin_color, "icon": icon, "points_awarded": 5})
    except Exception as e:
        return jsonify({"error": f"Classification failed: {str(e)}"}), 500

# ─────────────────────────────────────────────
# PROFILE
# ─────────────────────────────────────────────

@app.route('/api/profile', methods=['GET'])
@require_auth
def get_profile():
    user = request.current_user
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) AS n FROM complaints WHERE user_id = %s", (user['id'],))
    total = c.fetchone()['n']
    c.execute("SELECT COUNT(*) AS n FROM complaints WHERE user_id = %s AND status='Resolved'", (user['id'],))
    resolved = c.fetchone()['n']
    c.close(); conn.close()
    points = user['green_points']
    level  = max(1, points // 100 + 1)
    badges = []
    if total >= 1:  badges.append({"name": "🏅 First Reporter", "earned": True})
    badges.append({"name": "🗑️ 10 Complaints Filed", "earned": total >= 10,
                   **({"progress": total, "max": 10} if total < 10 else {})})
    badges.append({"name": "🌱 Eco Warrior", "earned": points >= 50,
                   **({"progress": points, "max": 50} if points < 50 else {})})
    badges.append({"name": "🚮 Segregation Expert", "earned": resolved >= 5,
                   **({"progress": resolved, "max": 5} if resolved < 5 else {})})
    return jsonify({"fullname": user['fullname'], "email": user['email'], "role": user['role'],
                    "green_points": points, "level": level,
                    "points_to_next": max(0, level * 100 - points),
                    "total_complaints": total, "resolved_complaints": resolved, "badges": badges})

# ─────────────────────────────────────────────
# ECO STORE
# ─────────────────────────────────────────────

@app.route('/api/eco/purchase', methods=['POST'])
@require_auth
def eco_purchase():
    data  = request.json
    items = data.get('items', [])
    if not items:
        return jsonify({"error": "No items provided"}), 400
    total         = sum(i.get('price', 0) for i in items)
    points_earned = max(1, total // 10)
    award_points(request.current_user['id'], points_earned)
    return jsonify({"message": "Purchase recorded!", "total": total, "points_awarded": points_earned})

# ─────────────────────────────────────────────
# SCHEDULE
# ─────────────────────────────────────────────

@app.route('/api/schedule', methods=['GET'])
@require_auth
def get_schedule():
    user = request.current_user
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT location FROM complaints WHERE user_id = %s ORDER BY timestamp DESC LIMIT 1", (user['id'],))
    row = c.fetchone()
    c.execute("""SELECT location, severity, status, timestamp FROM complaints
                 WHERE type='washroom' OR issue_type='washroom'
                 ORDER BY timestamp DESC LIMIT 20""")
    fac_rows = c.fetchall()
    c.close(); conn.close()
    area = row['location'] if row else "Your Area"
    if area and area.startswith("Lat:"):
        area = "Your GPS Location"
    uid = user['id']
    schedules = [["Monday","Wednesday","Friday"],["Tuesday","Thursday","Saturday"],
                 ["Monday","Thursday","Saturday"],["Wednesday","Friday","Sunday"]]
    days = schedules[uid % len(schedules)]
    from datetime import date
    today   = date.today().weekday()
    day_map = {"Monday":0,"Tuesday":1,"Wednesday":2,"Thursday":3,"Friday":4,"Saturday":5,"Sunday":6}
    nums    = sorted([day_map[d] for d in days])
    next_day   = next((d for d in nums if d >= today), nums[0])
    days_until = (next_day - today) % 7
    next_pickup = "Today" if days_until == 0 else f"In {days_until} day{'s' if days_until>1 else ''}"
    facilities = []
    seen = set()
    for r in fac_rows:
        r = dict(r)
        loc = r['location']
        if not loc or loc in seen: continue
        seen.add(loc)
        if r['status'] == 'Resolved':       fstatus, icon = "Clean", "🟢"
        elif r['severity'] == 'high':       fstatus, icon = "Needs Attention", "🔴"
        else:                               fstatus, icon = "Needs Attention", "🟡"
        try:
            ts = datetime.fromisoformat(str(r['timestamp']))
            mins_ago = int((datetime.now() - ts).total_seconds() / 60)
            last = f"{mins_ago} min ago" if mins_ago < 60 else f"{mins_ago//60} hr ago"
        except: last = "Recently"
        facilities.append({"name": loc, "status": fstatus, "last": last, "icon": icon})
    return jsonify({"area": area, "truck_number": 10+(uid%15), "eta_minutes": 10+(uid%40),
                    "schedule_days": days, "next_pickup": next_pickup, "facilities": facilities})

# ─────────────────────────────────────────────
# ANALYTICS
# ─────────────────────────────────────────────

@app.route('/api/analytics', methods=['GET'])
@require_admin
def get_analytics():
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT COALESCE(issue_type,type,'general') AS issue_type, COUNT(*) AS count
                 FROM complaints GROUP BY COALESCE(issue_type,type,'general') ORDER BY count DESC""")
    type_rows = c.fetchall()
    c.execute("SELECT status, COUNT(*) AS count FROM complaints GROUP BY status")
    status_rows = c.fetchall()
    c.execute("""SELECT DATE(timestamp) AS day, COUNT(*) AS count FROM complaints
                 WHERE timestamp >= NOW() - INTERVAL '14 days'
                 GROUP BY DATE(timestamp) ORDER BY day ASC""")
    timeline_rows = c.fetchall()
    c.execute("""SELECT location, COUNT(*) AS count FROM complaints
                 WHERE location IS NOT NULL AND location != '' AND location NOT LIKE 'Lat:%%'
                 GROUP BY location ORDER BY count DESC LIMIT 5""")
    location_rows = c.fetchall()
    c.close(); conn.close()
    return jsonify({
        "type_distribution": [{"label": r['issue_type'] or 'general', "count": r['count']} for r in type_rows],
        "status_breakdown":  [{"label": r['status'], "count": r['count']} for r in status_rows],
        "timeline":          [{"day": str(r['day']), "count": r['count']} for r in timeline_rows],
        "top_locations":     [{"location": r['location'], "count": r['count']} for r in location_rows]
    })

# ─────────────────────────────────────────────
# STARTUP — runs on Gunicorn too
# ─────────────────────────────────────────────
try:
    init_db()
except Exception as e:
    print(f"⚠️ DB init failed: {e}")

if __name__ == '__main__':
    print("🌿 CLEANIFY Backend starting on http://localhost:5000")
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))