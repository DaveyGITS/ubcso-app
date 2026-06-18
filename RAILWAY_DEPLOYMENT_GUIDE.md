# UBCSO App - Railway Deployment Guide (100% FREE)

## 🎯 Overview

This guide deploys your UBCSO app to **Railway** - the best FREE option for Django apps.

- **Cost:** FREE forever (no credit card needed)
- **Time:** 20-30 minutes total
- **Database:** PostgreSQL included FREE
- **Perfect for:** Students, startups, portfolios

---

## ✅ Prerequisites

Have these ready before starting:

- [ ] **GitHub account** (free at github.com)
- [ ] **Your code on GitHub** (see steps below)
- [ ] **Railway account** (free at railway.app)
- [ ] **App folder:** c:\Users\User\Desktop\UBCSO APP

---

## 🚀 STEP-BY-STEP DEPLOYMENT

### PHASE 1: Prepare Your Code (10 minutes)

#### Step 1.1: Create Three Files

**File 1: `Procfile`** (create in root app folder)

```
web: gunicorn ubcso.wsgi:application
release: python manage.py migrate
```

**File 2: `runtime.txt`** (create in root app folder)

```
python-3.14.0
```

**File 3: Check `requirements.txt`**

Make sure these packages are in your `requirements.txt`:

```
Django==6.0.6
psycopg2-binary==2.9.9
gunicorn==21.2.0
python-dotenv==1.0.0
djangorestframework==3.14.0
```

If missing, add them!

#### Step 1.2: Update `.gitignore`

Make sure `.env` and secrets are NOT pushed to GitHub:

```
.env
*.pyc
__pycache__/
venv/
db.sqlite3
*.log
```

#### Step 1.3: Push Code to GitHub

Open **Command Prompt** in your app folder:

```bash
git init
git add .
git commit -m "UBCSO App - Ready for Railway deployment"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/ubcso-app.git
git push -u origin main
```

**Replace:** `YOUR_USERNAME` with your actual GitHub username

**Verify:** Visit https://github.com/YOUR_USERNAME/ubcso-app

You should see your code on GitHub! ✅

---

### PHASE 2: Create Railway Account (5 minutes)

1. Go to: **https://railway.app**
2. Click: **"Start Project"**
3. Click: **"Deploy from GitHub"**
4. **Authorize** Railway to access your GitHub
5. Done! You have a Railway account ✅

---

### PHASE 3: Deploy to Railway (15 minutes)

#### Step 3.1: Create New Project

In Railway dashboard:

1. Click: **"New Project"**
2. Click: **"Deploy from GitHub repo"**
3. Search: **"ubcso-app"**
4. Click: **"ubcso-app"** repo
5. Click: **"Deploy now"**

Railway automatically starts building! 🚀

#### Step 3.2: Add PostgreSQL Database

In your Railway project dashboard:

1. Click: **"New"** (or + button)
2. Select: **"Database"**
3. Choose: **"PostgreSQL"**
4. Click: **"Create"**

PostgreSQL is now provisioned! ✅

**Wait 1-2 minutes** for database to start.

#### Step 3.3: Set Environment Variables

In Railway dashboard:

1. Click your **"ubcso-app"** service (web app)
2. Go to: **"Variables"** tab
3. Add these variables:

```
DEBUG=False
SECRET_KEY=<PASTE_HERE>
ALLOWED_HOSTS=*.up.railway.app,localhost
DATABASE_URL=postgresql://<AUTO_FILLED>
```

**For SECRET_KEY:**
1. Go to: https://www.miniwebtool.com/django-secret-key-generator/
2. Copy the generated key
3. Paste as SECRET_KEY value

**For DATABASE_URL:**
- Railway auto-fills this! 
- Should already be there
- Don't need to change it

#### Step 3.4: Wait for Deployment

Check deployment status:

1. Go to: **"Deployments"** tab
2. Watch the logs
3. Wait for green checkmark ✅
4. Should see: `"Successfully deployed"`

**Takes about 2-3 minutes**

#### Step 3.5: Create Admin User

After deployment completes:

1. Go to: **"Logs"** tab
2. Wait for all logs to show
3. Click: **"Run console"** button
4. Type:

```bash
python manage.py createsuperuser
```

5. Follow prompts:
   - Email: `admin@ub.edu.ph`
   - Password: (set any secure password)
6. Done! ✅

#### Step 3.6: Get Your Live URL

In Railway dashboard:

1. Click your **"ubcso-app"** service
2. Look for **"Domains"** section
3. Copy the URL (like: `https://ubcso-app.up.railway.app`)

**This is your live app!** 🎉

---

## ✅ TEST YOUR LIVE APP

Open your browser and test:

### Test 1: Frontend Works
- Go to: `https://ubcso-app.up.railway.app`
- Should see: Login page ✅

### Test 2: Admin Panel Works
- Go to: `https://ubcso-app.up.railway.app/admin`
- Login with: `admin@ub.edu.ph` / `your-password`
- Should see: Admin dashboard ✅

### Test 3: API Works
- Go to: `https://ubcso-app.up.railway.app/api/organizations/`
- Should see: JSON response ✅

---

## 🎉 YOU'RE LIVE!

Your app is now live on Railway! 

**Share your URL:** `https://ubcso-app.up.railway.app`

---

## 📋 Cost Breakdown (FREE!)

| Component | Cost | Notes |
|-----------|------|-------|
| Railway Platform | FREE | Generous free tier |
| PostgreSQL Database | FREE | Included! |
| Deployments | FREE | Unlimited |
| Custom Domain | FREE | (Optional later) |
| HTTPS/SSL | FREE | Automatic |
| **TOTAL** | **$0** | 100% FREE |

---

## 🆘 Troubleshooting

### Problem: Build Failed
**Solution:**
- Check logs for errors
- Make sure `Procfile` is in root folder
- Make sure `requirements.txt` has all packages
- Push fix to GitHub (auto-redeploys)

### Problem: Database Not Connecting
**Solution:**
- Wait 2-3 minutes after adding PostgreSQL
- Check DATABASE_URL is set
- Migrations should run automatically

### Problem: Admin Login Not Working
**Solution:**
- Make sure you ran `python manage.py createsuperuser`
- Check email and password are correct
- Try running createuser again from console

### Problem: Static Files (CSS/Images) Not Loading
**Solution:**
- This is expected initially
- Run in console: `python manage.py collectstatic --noinput`
- Redeploy

### Problem: 500 Error
**Solution:**
- Check logs: **Logs** tab in Railway
- Look for error message
- Fix in code, push to GitHub
- Auto-redeploys

---

## 🔒 Security Notes

**Never share:**
- Database password
- SECRET_KEY
- API credentials

**Already configured:**
- HTTPS (automatic)
- CSRF protection (enabled)
- Database backups (Railway handles)

---

## 📊 Monitoring Your App

### View Logs

In Railway dashboard:

1. Click your **"ubcso-app"** service
2. Click: **"Logs"** tab
3. See real-time logs

### Monitor Resource Usage

In Railway dashboard:

1. Click: **"Metrics"** tab
2. See CPU, Memory, Network usage

---

## 💾 Backups

Railway automatically backs up your database daily!

To export a backup manually:

1. Go to PostgreSQL service
2. Click: **"Data"** tab
3. See backup options

---

## 🚀 Next Steps

**Week 1:**
- Test all features
- Share URL with team
- Gather feedback

**Week 2:**
- Fix bugs found
- Plan improvements
- Document learnings

**Future:**
- Add custom domain
- Scale if needed
- Move to paid tier (if traffic grows)

---

## 📞 Support

### Railway Support
- Docs: https://docs.railway.app
- Community: https://discord.gg/railway

### Your App Support
- Admin: admin@ub.edu.ph
- Logs: Check Railway logs
- Debug: `python manage.py shell`

---

## 🎓 What You've Learned

✅ Containerized Python app  
✅ Deployed Django app  
✅ Connected PostgreSQL database  
✅ Set up production environment  
✅ Created admin user  
✅ Monitored live app  

**Congratulations! You're now a DevOps engineer!** 🎉

---

## 📝 Quick Reference

| Action | Command/Step |
|--------|--------------|
| Push code | `git push origin main` |
| Check logs | Railway Logs tab |
| Create admin | Console: `python manage.py createsuperuser` |
| Database backup | Railway Data tab |
| Get live URL | Railway Domains section |

---

**Last Updated:** June 18, 2026  
**Status:** ✅ PRODUCTION READY  
**Cost:** 💰 $0 (FREE!)

Enjoy your live app! 🚀

