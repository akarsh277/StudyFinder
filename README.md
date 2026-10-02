# StudyFind Telegram Bot 📚

**Telegram Bot Username**: `@HighlessbestBot`

StudyFind is a Telegram-first study resource access and contribution platform for students. It enables students to access notes, previous year question papers (PYQs), and assignments for their academic semesters, and contribute missing study resources with Chief approval workflow.

---

## 🛠️ Requirements & Setup

### 1. Python Version
Requires **Python 3.10+** (Tested on Python 3.14).

### 2. Create Virtual Environment
```bash
# On Windows
python -m venv venv
.\venv\Scripts\Activate.ps1

# On Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Create PostgreSQL Database
Ensure PostgreSQL is running, then create the database:
```sql
CREATE DATABASE studyfind;
```
*(Note: If PostgreSQL connection fails or password is not provided, the application safely falls back to local SQLite `studyfind.db` for testing.)*

### 5. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your configuration:
```bash
cp .env.example .env
```

Edit `.env`:
```env
BOT_TOKEN=8571722863:AAHSfklN9pJya_IGnM7sw56-AMnDNwyKeoc
CHIEF_TELEGRAM_ID=YOUR_TELEGRAM_NUMERIC_ID
DATABASE_URL=postgresql://postgres:password@localhost:5432/studyfind
```

### 6. Initialize Database & Seed Data
Run the DB initialization script to create tables and seed default subjects (`CSE 2-2` and `CSE 3-1`):
```bash
python init_db.py
```

### 7. Start the Telegram Bot
```bash
python -m bot.main
```
*(Or run `python bot/main.py`)*

---

## 👨‍✈️ Configuring the Chief (Admin)

1. Find your numeric Telegram ID (e.g. via `@userinfobot` on Telegram).
2. Set `CHIEF_TELEGRAM_ID=your_id` in `.env`.
3. Restart the bot.

---

## 🧪 End-to-End Testing Workflows

### 1. Test Start Message & Main Menu
1. Send `/start` to `@HighlessbestBot`.
2. Verify exact text:
   ```text
   Hello Maawa!!
   Notes ledha,
   Digulu endhuku? Dhandaga nenunna neeku andagaa 🫶🏻
   ```
3. Verify main menu buttons appear:
   - `[📤 Upload Resource]`
   - `[📚 Access Resources]`

### 2. Test Student Access Flow
1. Click `📚 Access Resources`.
2. Select semester (`🎓 CSE 3-1`).
3. Select subject (`DBMS`).
4. Select type (`📒 Notes`).
5. If approved resources exist, click the download button (`[⬇️ DBMS Complete Notes]`). The PDF file will be delivered directly inside Telegram.
6. If no approved resources exist, verify `"⚠️ Source unavailable"` appears along with `[📤 Upload Resource]`.

### 3. Test Student Upload Flow
1. Click `📤 Upload Resource`.
2. Select semester (`🎓 CSE 3-1`) -> subject (`DBMS`) -> type (`📒 Notes`).
3. Enter title: `DBMS Unit 3 Notes`.
4. Upload a `.pdf` file.
5. Verify response:
   ```text
   ✅ Resource submitted successfully.

   Your resource has been sent to the Chief for approval.
   ```

### 4. Test Chief Approval & Rejection
1. Chief receives submission notification with document attached and buttons: `[✅ Approve]` `[❌ Reject]`.
2. **Approval Test**:
   - Chief clicks `[✅ Approve]`.
   - Chief UI updates to `✅ [APPROVED BY CHIEF]`.
   - Uploader receives notification:
     ```text
     ✅ Your resource has been approved!

     It is now available to other students.
     ```
   - Resource becomes immediately visible in `📚 Access Resources`.
3. **Rejection Test**:
   - Upload another resource.
   - Chief clicks `[❌ Reject]`.
   - Chief UI updates to `❌ [REJECTED BY CHIEF]`.
   - Uploader receives exact notification:
     ```text
     ❌ Your resource was rejected by the Chief.
     ```
   - Resource does NOT appear in student access listings.

---

## 📂 Project Structure

```
StudyFinder/
│
├── bot/
│   ├── main.py                # Main bot runner & polling
│   ├── handlers/
│   │   ├── start.py           # /start command handler
│   │   ├── access.py          # Access & download resource handlers
│   │   ├── upload.py          # Multi-step upload ConversationHandler
│   │   └── admin.py           # Chief Approve/Reject handlers
│   ├── keyboards/
│   │   └── menus.py           # Inline keyboard builders
│   └── states/
│       └── conversation.py    # Conversation state definitions
│
├── database/
│   ├── connection.py          # SQLAlchemy engine & session factory
│   ├── models.py              # User, Subject, Resource tables
│   └── crud.py                # CRUD queries & subject seeding
│
├── config.py                  # Environment variable configuration
├── init_db.py                 # DB initialization script
├── .env                       # Environment secrets (gitignored)
├── .env.example               # Template environment configuration
├── .gitignore                 # Git ignore rules
├── requirements.txt           # Dependency manifest
└── README.md                  # Project documentation
```
