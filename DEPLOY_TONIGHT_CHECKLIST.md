# Deploy UBCSO App Tonight - Complete Checklist

**Goal:** Get your app LIVE on Railway (100% FREE) in 2-3 hours

**Status:** ✅ READY TO GO

---

## 📋 PRE-DEPLOYMENT CHECKLIST

### Before You Start:

- [ ] **Virtual environment activated** (venv\Scripts\activate)
- [ ] **Database running** (PostgreSQL)
- [ ] **App tested locally** (python manage.py runserver works)
- [ ] **GitHub account created** (free at github.com)
- [ ] **Railway account ready to create** (free at railway.app)
- [ ] **Internet connection good** (deployment needs upload)
- [ ] **Have 2-3 hours available** (don't rush)

---

## ⏱️ TIME BREAKDOWN

```
Phase 1: Prepare Code           10 minutes
Phase 2: Create Railway Account  5 minutes
Phase 3: Deploy to Railway      15 minutes
Phase 4: Testing                10 minutes
────────────────────────────────────────
TOTAL:                         40 minutes
With breaks/delays:         2-3 hours
```

---

## 🚀 PHASE 1: PREPARE CODE (10 MINS)

### Step 1.1: Create `Procfile`

```bash
# In: c:\Users\User\Desktop\UBCSO APP\
# Create new file: Procfile (no extension)
# Content:
web: gunicorn ubcso.wsgi:application
release: python manage.py migrate
```

- [ ] File created: Procfile
- [ ] Content correct
- [ ] No file extension (.txt, .py, etc)

### Step 1.2: Create `runtime.txt`

```bash
# In: c:\Users\User\Desktop\UBCSO APP\
# Create new file: runtime.txt
# Content:
python-3.14.0
```

- [ ] File created: runtime.txt
- [ ] Content: python-3.14.0

### Step 1.3: Check `requirements.txt`

These packages MUST be in requirements.txt:

```
Django==6.0.6
psycopg2-binary==2.9.9
gunicorn==21.2.0
python-dotenv==1.0.0
```

- [ ] Open requirements.txt
- [ ] Check all 4 packages are there
- [ ] If missing, add them and save

### Step 1.4: Push to GitHub

```bash
# Open Command Prompt
# Navigate to app folder
cd c:\Users\User\Desktop\UBCSO APP

# Run these commands:
git init
git add .
git commit -m "UBCSO App ready for Railway"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/ubcso-app.git
git push -u origin main
```

**Replace:** YOUR_USERNAME with your GitHub username

- [ ] `git init` executed
- [ ] `git add .` executed
- [ ] `git commit` executed
- [ ] `git remote add origin` executed (with YOUR_USERNAME)
- [ ] `git push -u origin main` executed
- [ ] Verify on GitHub: https://github.com/YOUR_USERNAME/ubcso-app

---

## 🌐 PHASE 2: RAILWAY ACCOUNT (5 MINS)

### Step 2.1: Create Railway Account

1. Go to: https://railway.app
2. Click: **"Start Project"**
3. Click: **"Deploy from GitHub"**
4. Click: **"Authorize"** (allow Railway to access GitHub)
5. Done! ✅

- [ ] Railway account created
- [ ] GitHub authorized
- [ ] Ready to deploy

---

## 🚀 PHASE 3: DEPLOY (15 MINS)

### Step 3.1: Create Project

In Railway dashboard:

1. Click: **"New Project"**
2. Click: **"Deploy from GitHub repo"**
3. Search: **"ubcso-app"**
4. Click: **Select your repo**
5. Click: **"Deploy now"**

- [ ] Repo selected
- [ ] Deploy clicked
- [ ] See "Building..." status

### Step 3.2: Add PostgreSQL

In Railway dashboard:

1. Click: **"New"** (or + icon)
2. Select: **"Database"**
3. Choose: **"PostgreSQL"**
4. Click: **"Create"**

- [ ] PostgreSQL added
- [ ] Wait 1-2 minutes
- [ ] See "Connected" status

### Step 3.3: Set Environment Variables

In Railway dashboard:

1. Click your **"ubcso-app"** service
2. Go to: **"Variables"** tab
3. Add these exactly:

```
DEBUG=False
SECRET_KEY=<PASTE_HERE>
ALLOWED_HOSTS=*.up.railway.app,localhost
DATABASE_URL=<AUTO_FILLED>
```

**For SECRET_KEY:**
- Visit: https://www.miniwebtool.com/django-secret-key-generator/
- Copy the key
- Paste as SECRET_KEY value

- [ ] DEBUG set to False
- [ ] SECRET_KEY pasted
- [ ] ALLOWED_HOSTS set
- [ ] DATABASE_URL auto-filled
- [ ] All variables saved

### Step 3.4: Wait for Build

Check **"Deployments"** tab:

- [ ] See green checkmark ✅
- [ ] See "Successfully deployed"
- [ ] Wait 2-3 minutes

### Step 3.5: Create Admin User

1. Click **"Logs"** tab
2. Click **"Run console"**
3. Type:

```bash
python manage.py createsuperuser
```

4. Enter:
   - Email: `admin@ub.edu.ph`
   - Password: (type password, won't show)
   - Confirm password: (repeat password)

- [ ] Console opened
- [ ] Command executed
- [ ] Admin user created
- [ ] See "Successfully created"

### Step 3.6: Get Live URL

In Railway dashboard:

1. Click your **"ubcso-app"** service
2. Find **"Domains"** section
3. Copy the URL (example: `https://ubcso-app-xxxx.up.railway.app`)

- [ ] URL found
- [ ] URL copied
- [ ] Save this URL!

---

## ✅ PHASE 4: TESTING (10 MINS)

### Test 1: Frontend

- [ ] Open: `https://YOUR_LIVE_URL` (from Phase 3.6)
- [ ] See: Login page
- [ ] No errors

### Test 2: Admin Panel

- [ ] Open: `https://YOUR_LIVE_URL/admin`
- [ ] Login: `admin@ub.edu.ph` / (your password)
- [ ] See: Django admin interface

### Test 3: API

- [ ] Open: `https://YOUR_LIVE_URL/api/organizations/`
- [ ] See: JSON response (even if empty)
- [ ] No 404 errors

### Test 4: Try Features

- [ ] Try clicking links
- [ ] Try navigation menu
- [ ] Check if responsive (resize browser)

All tests passing?

- [ ] ✅ Frontend works
- [ ] ✅ Admin works
- [ ] ✅ API works
- [ ] ✅ Navigation works

**CONGRATULATIONS! 🎉 You're LIVE!**

---

## 🎁 BONUS: Share Your App

### Tell People It's Live

- [ ] Copy live URL
- [ ] Email to team
- [ ] Post on chat
- [ ] Add to documentation
- [ ] Test with other users

**Example:**
```
Hey everyone! 🎊

UBCSO App is now LIVE!

Check it out: https://ubcso-app-xxxx.up.railway.app

Login with:
- Email: admin@ub.edu.ph
- Password: (your-password)

Try creating an organization, browsing, voting!
```

---

## 🔧 TROUBLESHOOTING

### Issue: Build Failed

**Check:**
- [ ] Procfile exists in root folder
- [ ] runtime.txt exists
- [ ] requirements.txt has all packages

**Fix:**
- [ ] Fix the issue
- [ ] Run: `git add . && git commit -m "fix" && git push origin main`
- [ ] Railway auto-redeploys

### Issue: PostgreSQL Not Connected

**Check:**
- [ ] DATABASE_URL is set
- [ ] Wait 3+ minutes after adding PostgreSQL

**Fix:**
- [ ] Try deploying again
- [ ] Check Railway logs

### Issue: Can't Login

**Check:**
- [ ] Email: `admin@ub.edu.ph`
- [ ] Password: (what you set)

**Fix:**
- [ ] Run createuser again from console

### Issue: Static Files (CSS/Images) Not Loading

**Expected:** This may happen first time

**Fix:**
- [ ] Run in console: `python manage.py collectstatic --noinput`
- [ ] Redeploy

---

## 📞 HELP

### If Stuck:

1. **Check Railway logs** (Logs tab)
2. **Read error message carefully**
3. **Google the error**
4. **Check Railway docs**: https://docs.railway.app
5. **Ask in Railway Discord**: https://discord.gg/railway

### For UBCSO App Issues:

1. **Check app locally first** (does it work locally?)
2. **Check DATABASE_URL** (is it set?)
3. **Run migrations** (console: `python manage.py migrate`)
4. **Check logs** (Railway logs tab)

---

## ✨ YOU DID IT!

After this checklist:

✅ App is live on Railway (FREE!)  
✅ Database connected (PostgreSQL)  
✅ Admin can login  
✅ Team can access  
✅ Cost: $0  

**Celebrate! 🎉**

---

## 📝 NEXT STEPS (After Deploy)

- [ ] **Day 1:** Test thoroughly
- [ ] **Day 2:** Gather team feedback
- [ ] **Day 3:** Fix any bugs
- [ ] **Week 1:** Plan improvements for v2.0
- [ ] **Future:** Add custom domain (if needed)

---

## 🎓 WHAT YOU LEARNED

✅ Created production files (Procfile, runtime.txt)  
✅ Deployed to cloud (Railway)  
✅ Connected PostgreSQL database  
✅ Set environment variables  
✅ Ran database migrations  
✅ Created admin user  
✅ Tested live app  

**You're officially a DevOps engineer!** 🚀

---

## 💾 KEEP THIS CHECKLIST

Save this file! You may need it to:
- Deploy updates
- Create another project
- Train someone else
- Remember what you did

---

**Start Time:** ______ (write when you start)  
**Phase 1 Done:** ______ 
**Phase 2 Done:** ______ 
**Phase 3 Done:** ______ 
**Phase 4 Done:** ______ 
**Live URL:** ____________________________________

---

**Last Updated:** June 18, 2026  
**Status:** ✅ READY TO DEPLOY  
**Cost:** 💰 $0 FREE  

**Good luck! 🚀 You've got this!**

