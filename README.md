# 🌿 Swachtha — Full Stack Backend

A complete Flask backend for the Swachtha civic cleanliness portal with AI-powered waste classification.

---

## 🏗️ Project Structure

```
Swachtha/
├── app.py                  ← Main Flask server
├── requirements.txt
├── Swachtha.db             ← Auto-created SQLite database
├── static/
│   └── styles.css
└── templates/
    ├── index.html          ← Login page
    ├── reg.html            ← Registration page
    ├── user.html           ← Citizen home dashboard
    ├── admin.html          ← Admin dashboard
    ├── report.html         ← Report an issue
    ├── washroom.html       ← Washroom complaint
    ├── ai.html             ← AI Waste Classifier (Claude-powered)
    ├── eco.html            ← Eco store
    ├── reward.html         ← Citizen rewards page
    └── waste.html          ← Waste picker tracking
```

---

## 🚀 Quick Setup

### 1. Install Dependencies
```bash
pip install flask flask-cors anthropic
```

### 2. Set Anthropic API Key
```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

### 3. Run the Server
```bash
cd cleanify
python app.py
```

Server starts at: **http://localhost:5000**

---

## 🔑 Default Accounts

| Role  | Email                  | Password  |
|-------|------------------------|-----------|
| Admin | admin@cleanify.com     | admin123  |

Citizens can register at `/reg.html`.

---

## 🌐 Page Routes

| URL             | Description              |
|-----------------|--------------------------|
| `/`             | Login page               |
| `/reg.html`     | Registration page        |
| `/user.html`    | Citizen dashboard        |
| `/admin.html`   | Admin dashboard          |
| `/report.html`  | Report an issue          |
| `/washroom.html`| Report unclean washroom  |
| `/ai.html`      | AI Waste Classifier      |
| `/eco.html`     | Eco-friendly store       |
| `/reward.html`  | Rewards & badges         |
| `/waste.html`   | Waste picker tracking    |

---

## 📡 API Endpoints

### Auth
| Method | Endpoint             | Description           |
|--------|----------------------|-----------------------|
| POST   | `/api/auth/register` | Register new user     |
| POST   | `/api/auth/login`    | Login                 |
| POST   | `/api/auth/logout`   | Logout                |
| GET    | `/api/auth/me`       | Get current user      |

### Complaints
| Method | Endpoint                            | Auth     | Description               |
|--------|-------------------------------------|----------|---------------------------|
| POST   | `/api/complaints`                   | User     | Submit complaint (+15 pts)|
| GET    | `/api/complaints`                   | User     | Get complaints            |
| PATCH  | `/api/complaints/<id>/status`       | Admin    | Update status             |
| DELETE | `/api/complaints/<id>`              | Admin    | Delete complaint          |
| DELETE | `/api/complaints/clear`             | Admin    | Clear all complaints      |

### AI Classifier
| Method | Endpoint        | Auth | Description                         |
|--------|-----------------|------|-------------------------------------|
| POST   | `/api/classify` | User | Classify waste image (+5 pts)       |

**Request body:** `{ "image": "data:image/jpeg;base64,..." }`

**Response:**
```json
{
  "category": "Dry Waste",
  "confidence": 92,
  "items_detected": "plastic bottles and cardboard",
  "disposal_tip": "Rinse bottles and flatten boxes before placing in blue bin",
  "bin_color": "Blue",
  "icon": "📦",
  "points_awarded": 5
}
```

### Rewards (Admin)
| Method | Endpoint          | Auth  | Description      |
|--------|-------------------|-------|------------------|
| GET    | `/api/rewards`    | User  | Get all rewards  |
| POST   | `/api/rewards`    | Admin | Add reward       |
| DELETE | `/api/rewards/id` | Admin | Delete reward    |

### Stats (Admin)
| Method | Endpoint    | Auth  | Description    |
|--------|-------------|-------|----------------|
| GET    | `/api/stats`| Admin | Get statistics |

### Profile
| Method | Endpoint      | Auth | Description                    |
|--------|---------------|------|--------------------------------|
| GET    | `/api/profile`| User | Get user profile + badges      |

---

## 🤖 AI Waste Classifier

The AI classifier uses **Claude claude-sonnet-4-20250514** with vision to classify waste into:

- **🥬 Wet Waste** → Green Bin (food scraps, peels, garden waste)
- **📦 Dry Waste** → Blue Bin (paper, plastic, glass, metal, electronics)

Users earn **+5 green points** each time they use the classifier.

---

## 🏆 Points System

| Action                    | Points |
|---------------------------|--------|
| Submit complaint          | +15    |
| Complaint resolved        | +10    |
| Use AI Classifier         | +5     |

**Levels:** Every 100 points = 1 level up

---

## 🗄️ Database Schema

The SQLite database is auto-created at first run with these tables:
- `users` — Registered citizens and admins
- `complaints` — All submitted complaints
- `rewards` — Admin-issued community rewards
- `sessions` — Auth tokens (7-day expiry)
