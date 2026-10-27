# StudyFind Telegram Bot 📚

**Telegram Bot Username**: `@HighlessbestBot`

StudyFind is a modern, high-performance Telegram-first academic resource platform. It enables college students to seamlessly access lecture notes, previous year question papers (PYQs), and assignments categorized by **Branch**, **Semester**, and **Subject**. It provides instant file delivery within Telegram, real-time contribution and Chief approval workflows, end-of-day digest notifications, dynamic curriculum management, and bulk uploading tools without modifying code.

---

## 🚀 Key Features

- **Hierarchical Navigation**:
  1. Main Menu (`📤 Upload`, `📚 Access`)
  2. Branch Selection (`CSE`, `CSE(AI)`, etc.)
  3. Semester Selection (`2-2`, `3-1`, `3-2`, etc.)
  4. Subject Selection (`OS`, `DBMS`, `CN`, etc.)
  5. Resource Type (`Notes`, `PYQ`, `Assignment`)
- **Zero-Code Dynamic Management**:
  - Add engineering branches (`/addbranch`).
  - Add semesters to branches (`/addsem`).
  - Add subjects dynamically (`/addsubject`).
  - Interactive Chief Control Center dashboard (`/admin` or `/manage`).
- **Telegram Command Scoping**:
  - **Regular Students**: Only see `/start` and `/upload` in their Telegram command menu button `[/]`.
  - **Chief (Admin)**: Full administrative command suite (`/admin`, `/addbranch`, `/addsem`, `/addsubject`, `/branches`, `/subjects`, `/delete`, `/stats`, `/daily_digest`).
- **Continuous Fast Upload Mode**:
  - Once a resource is submitted via Telegram, users get a `"➕ Upload another for <Subject>"` button that skips menu re-navigation and prompts directly for the next file.
- **Bulk / Batch Local File Sync (`upload_local.py`)**:
  - Upload entire semester directory trees in one CLI command.
  - Automatically infers subject names from folders.
  - Auto-creates branches, semesters, and subjects in the database if missing.
- **Automated Daily Notifications (Digest)**:
  - Scheduled automatically at **22:00 IST** every evening using `apscheduler`.
  - Sends a consolidated list of resources uploaded and approved on that day.
  - **Zero-Spam Guarantee**: If 0 resources were uploaded today, **no notification** is sent.
  - Manual preview or broadcast trigger via `/daily_digest`.
- **Content Moderation & Management**:
  - Student uploads go to Chief with 1-click `[✅ Approve]` / `[❌ Reject]` inline buttons.
  - Resource rename and file deletion controls (`/delete`).
- **Robust Database Engine**:
  - Powered by Neon Serverless PostgreSQL with automatic retry connection handling, pool recycling, and fallback safety.

---

## 🛠️ Requirements & Setup

### 1. Prerequisites
- **Python 3.10+** (Tested on Python 3.11, 3.12, 3.14)
- **PostgreSQL** (e.g. [Neon Serverless Postgres](https://neon.tech) or local PostgreSQL)
- **Telegram Bot Token** (from [@BotFather](https://t.me/BotFather))

### 2. Virtual Environment Setup
```powershell
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the root directory:
```env
BOT_TOKEN=your_telegram_bot_token_from_botfather
CHIEF_TELEGRAM_ID=your_numeric_telegram_id
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
PORT=10000
```
> [!NOTE]
> Find your numeric Telegram ID by messaging [@userinfobot](https://t.me/userinfobot) on Telegram.

### 5. Initialize Database & Seed Initial Data
Run the database initialization script to create tables and seed default branches (`CSE`, `CSE(AI)`) and subjects:
```bash
python init_db.py
```

### 6. Start the Bot
```bash
python -m bot.main
```
*(Or run `python bot/main.py`)*

---

## 📱 Bot Usage & Navigation

### Student Flow: Accessing Notes
1. Send `/start` to `@HighlessbestBot`.
2. Tap **`📚 Access`**.
3. Select your **Branch** (e.g. `🏛️ CSE` or `🏛️ CSE(AI)`).
4. Select your **Semester** (e.g. `🎓 2-2` or `🎓 3-1`).
5. Select your **Subject** (e.g. `OS`, `DBMS`).
6. Select resource type: `📒 Notes`, `📑 PYQ`, or `📝 Assignment`.
7. Tap the resource to download it directly inside Telegram!

### Student Flow: Uploading Notes
1. Tap **`📤 Upload`** or send `/upload`.
2. Follow the prompt to choose Branch → Semester → Subject → Resource Type.
3. Enter the resource title (e.g., `Unit 2 Operating System Notes`).
4. Send the document (`.pdf`, `.doc`, `.docx`).
5. After upload, tap **`➕ Upload another for <Subject>`** to quickly upload subsequent files for the same subject without repeating the selection menus!

---

## 👨‍✈️ Chief Admin Suite (Dynamic Curriculum)

All administrative actions can be done directly from Telegram without modifying code:

| Command | Description | Example |
| :--- | :--- | :--- |
| `/admin` or `/manage` | Opens the interactive Chief Control Center dashboard with buttons | `/admin` |
| `/addbranch <Name> [sems]` | Add an engineering branch (or open interactive selector) | `/addbranch ECE 2-2, 3-1` |
| `/addsem <Branch> <Sem>` | Add a semester to an existing branch | `/addsem CSE 3-2` |
| `/addsubject <Branch> <Sem> <Name>` | Add a subject to a branch semester | `/addsubject CSE 3-1 Computer Networks` |
| `/branches` | Lists all configured branches and their active semesters | `/branches` |
| `/subjects` | Lists all subjects organized by branch and semester | `/subjects` |
| `/delete` | Interactive menu to delete or rename uploaded study resources | `/delete` |
| `/stats` or `/analytics` | View 30-day download and upload analytics | `/stats` |
| `/daily_digest [send]` | Preview today's uploaded notes digest (or force broadcast) | `/daily_digest` |

---

## ⚡ Bulk Uploading via CLI (`upload_local.py`)

For uploading dozens or hundreds of files at once from your PC, use `upload_local.py`. It uploads the files directly to Telegram servers, saves the Telegram `file_id` in Postgres, and marks the resources `APPROVED` instantly.

### 1. Multi-Subject Folder Sync (`--batch`)
Organize your semester folder with subfolders for each subject:
```text
Semester_3_1/
  ├── Computer Networks/
  │     ├── CN_Unit1.pdf
  │     └── CN_Unit2.pdf
  ├── Operating Systems/
  │     ├── OS_Unit1.pdf
  │     └── OS_Unit2.pdf
  └── Cloud Computing/
        └── CC_Overview.pdf
```
Run this single command:
```powershell
python upload_local.py --batch "C:\path\to\Semester_3_1" --semester "CSE 3-1" --type NOTES
```
- Subfolder names are used as the subject names.
- If the subject or semester does not exist in the database, the script **auto-creates** it dynamically!

### 2. Single Subject Folder (`--folder`)
```powershell
python upload_local.py --folder "C:\path\to\DBMS_notes" --semester "CSE 3-1" --subject "DBMS" --type NOTES
```

### 3. Single Document File (`--file`)
```powershell
python upload_local.py --file "C:\path\to\Unit1.pdf" --semester "CSE 2-2" --subject "OS" --type NOTES --title "OS Unit 1 Handout"
```

---

## 📅 Daily Notification Digest (22:00 IST)

- Every day at **22:00 IST** (Indian Standard Time), the bot runs an automated background job (`send_daily_digest_job`).
- It compiles all resources uploaded and approved on that calendar day and formats a clean notification:
  ```text
  📢 Daily Resource Digest — 27 Oct 2026

  Here are the new study materials uploaded today:

  🎓 CSE 3-1:
    📚 Computer Networks:
      • Unit 1 Complete Notes (Notes)
      • 2024 End-Sem Question Paper (PYQ)

  Open @HighlessbestBot to access or download!
  ```
- **Anti-Spam Logic**: If no resources were uploaded that day, the notification is automatically skipped.
- The Chief can test the preview at any time with `/daily_digest` or broadcast immediately with `/daily_digest send`.

---

## 📂 Project Architecture

```
StudyFinder/
│
├── bot/
│   ├── main.py                  # Application entry point, JobQueue, scoping, health server
│   ├── handlers/
│   │   ├── start.py             # /start command & main menu router
│   │   ├── access.py            # Branch -> Semester -> Subject -> Resource file delivery
│   │   ├── upload.py            # Telegram upload flow & continuous upload handler
│   │   ├── admin.py             # Chief dashboard, branch/sem/subject CRUD, approvals, delete
│   │   ├── notifications.py     # End-of-day 22:00 IST digest & broadcast handlers
│   │   └── analytics.py         # 30-day analytics report handler
│   ├── keyboards/
│   │   └── menus.py             # Inline keyboard generators (Branches, Semesters, Subjects)
│   └── states/
│       └── conversation.py      # Conversation state enums
│
├── database/
│   ├── connection.py            # Neon PostgreSQL connection pool & resilient retry engine
│   ├── models.py                # Branch, Subject, Resource, User, DownloadLog models
│   └── crud.py                  # Database queries, relations, and seeding routines
│
├── config.py                    # Environment variable parser
├── init_db.py                   # Schema migration & initial seed script
├── upload_local.py              # High-throughput batch/folder CLI uploader
├── requirements.txt             # Project Python dependencies
├── Procfile                     # Deployment configuration for PaaS (Heroku/Render/Koyeb)
└── README.md                    # Project documentation
```

---

## ☁️ Deployment

### Running on Cloud Web Services (Render / Koyeb / Railway)
The project includes a built-in lightweight HTTP health check server listening on `PORT` (default `10000`). This satisfies cloud platforms requiring a responding HTTP port on Free Tier Web Services.

To deploy:
1. Connect your GitHub repository to Render/Koyeb.
2. Select **Web Service** (or Background Worker).
3. Set Build Command: `pip install -r requirements.txt`
4. Set Start Command: `python -m bot.main`
5. Configure Environment Variables (`BOT_TOKEN`, `CHIEF_TELEGRAM_ID`, `DATABASE_URL`).