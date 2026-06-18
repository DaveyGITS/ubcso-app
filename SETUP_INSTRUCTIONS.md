# UBCSO App - Setup Instructions

## Prerequisites
Before starting, ensure you have installed:
- **Python 3.8+** (https://www.python.org/downloads/)
- **PostgreSQL** (https://www.postgresql.org/download/)
- **Git** (optional, for version control)

---

## Step 1: Extract the Archive
Extract the `ubcso-complete.zip` to your desired location on your computer.

```
Example: C:\Projects\ubcso-app
```

---

## Step 2: Set Up Python Virtual Environment

Navigate to the project directory and create a virtual environment:

```bash
# On Windows (Command Prompt or PowerShell)
cd C:\Projects\ubcso-app
python -m venv venv

# Activate the virtual environment
# For Command Prompt:
venv\Scripts\activate

# For PowerShell:
venv\Scripts\Activate.ps1
```

After activation, your terminal should show `(venv)` prefix.

---

## Step 3: Install Python Dependencies

With the virtual environment activated, install all required packages:

```bash
pip install -r requirements.txt
```

This installs:
- Django 6.0.3
- PostgreSQL driver (psycopg2)
- Celery & Redis support
- Tailwind CSS
- And all other dependencies

---

## Step 4: Set Up PostgreSQL Database

### 4A: Create the Database

Open **PostgreSQL Command Line** or **pgAdmin**:

**Using pgAdmin (GUI - Easiest):**
1. Open pgAdmin
2. Right-click on **Databases** → **Create** → **Database**
3. Name: `ubcso_db`
4. Click **Save**

**Using Command Line (psql):**
```sql
-- Open psql as postgres user
psql -U postgres

-- Create the database
CREATE DATABASE ubcso_db;

-- Exit psql
\q
```

### 4B: Restore the Database Backup

The app includes a `database_backup.sql` file with all existing data.

**Using Command Line (Recommended):**
```bash
# Make sure you're NOT in the virtual environment for this step
# Or use the full path to psql

psql -U postgres -d ubcso_db < database_backup.sql
```

**On Windows (if psql is not in PATH):**
```bash
# Find PostgreSQL installation (usually in Program Files)
# Then use the full path:
"C:\Program Files\PostgreSQL\15\bin\psql" -U postgres -d ubcso_db < database_backup.sql
```

**Using pgAdmin (GUI):**
1. Right-click on `ubcso_db` → **Restore**
2. Select `database_backup.sql`
3. Click **Restore**

### 4C: Verify Database Connection

Once restored, verify the connection in your `.env` file:

```
DB_NAME=ubcso_db
DB_USER=postgres
DB_PASSWORD=My_firstproj2026
DB_HOST=localhost
DB_PORT=5432
```

**Test the connection:**
```bash
# Activate virtual environment if not already active
venv\Scripts\activate

# Test Django database connection
python manage.py dbshell

# If successful, you'll see: PostgreSQL prompt
# Type \q to exit
```

---

## Step 5: Verify Installation

Run migrations to ensure everything is set up correctly:

```bash
# With virtual environment activated
python manage.py migrate

# Create a superuser account (optional, for admin access)
python manage.py createsuperuser
```

---

## Step 6: Run the Development Server

Start the Django development server:

```bash
# With virtual environment activated
python manage.py runserver
```

You should see:
```
Starting development server at http://127.0.0.1:8000/
Quit the server with CONTROL-C.
```

---

## Step 7: Access the Application

Open your web browser and go to:
```
http://localhost:8000
```

You should see the UBCSO App home page.

**Admin Panel:** http://localhost:8000/admin-panel/

---

## Troubleshooting

### Virtual Environment Issues
```bash
# If venv doesn't activate, try:
python -m venv venv --clear
venv\Scripts\activate
```

### Database Connection Errors
```bash
# Verify PostgreSQL is running
# On Windows, check Services (services.msc) for PostgreSQL service

# Test connection directly
psql -U postgres -h localhost -d ubcso_db
```

### Port Already in Use (8000)
```bash
# Run on different port
python manage.py runserver 8001
```

### Missing Dependencies
```bash
# Reinstall all dependencies
pip install -r requirements.txt --force-reinstall
```

### Database Restore Issues
```bash
# Drop and recreate database
psql -U postgres -c "DROP DATABASE ubcso_db;"
psql -U postgres -c "CREATE DATABASE ubcso_db;"
psql -U postgres -d ubcso_db < database_backup.sql
```

---

## Environment Variables (.env)

The `.env` file contains sensitive configuration. Key variables:

```
DB_NAME=ubcso_db              # PostgreSQL database name
DB_USER=postgres              # PostgreSQL username
DB_PASSWORD=...               # PostgreSQL password
DB_HOST=localhost             # Database server address
DB_PORT=5432                  # PostgreSQL port (default)
SECRET_KEY=...                # Django secret key (change in production)
CELERY_BROKER_URL=...         # Redis connection (for background tasks)
```

⚠️ **SECURITY WARNING:** Change `SECRET_KEY` before deploying to production!

---

## Next Steps

### Development
- Access admin panel: http://localhost:8000/admin-panel/
- Create test users and organizations
- Explore features

### Production Deployment
1. Change `DEBUG = False` in `ubcso/settings.py`
2. Update `ALLOWED_HOSTS` with your domain
3. Use a production server (Gunicorn, uWSGI)
4. Use a production database server
5. Set up SSL/HTTPS
6. Configure email backend for notifications

---

## Support & Documentation

- **Django Documentation:** https://docs.djangoproject.com/
- **PostgreSQL Documentation:** https://www.postgresql.org/docs/
- **Project Features:** See feature overview in app dashboard

---

## Quick Reference Commands

```bash
# Activate virtual environment
venv\Scripts\activate

# Deactivate virtual environment
deactivate

# Run development server
python manage.py runserver

# Access Django shell
python manage.py shell

# Make migrations (after model changes)
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Collect static files (production)
python manage.py collectstatic
```

---

**Last Updated:** June 16, 2026
**Version:** 1.0
