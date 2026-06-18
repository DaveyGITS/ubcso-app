# Screenshot Capture Guide for UBCSO Documentation

## Quick Start

### Prerequisites
- Python 3.14+ with virtual environment activated
- Django dev server running
- PostgreSQL database with sample data
- Modern web browser (Chrome recommended)

---

## Step 1: Start the Development Server

Open a terminal and run:

```bash
# Activate virtual environment
venv\Scripts\activate  # Windows

# Run Django development server
python manage.py runserver

# Output should show:
# Starting development server at http://127.0.0.1:8000/
```

Keep this terminal open. The server will run on http://localhost:8000

---

## Step 2: Populate Test Data (Optional)

If you need sample data for realistic screenshots:

```bash
# Create test users
python manage.py shell

# In the Django shell:
from accounts.models import User, Organization, Membership
from django.contrib.auth import get_user_model

# Create test student
student = get_user_model().objects.create_user(
    email='student@ub.edu.ph',
    password='testpass123',
    first_name='John',
    last_name='Dela Cruz'
)

# Create test organization
org = Organization.objects.create(
    name='Computer Science Society',
    abbreviation='CSS',
    category='student',
    status='Active'
)

# Add membership
Membership.objects.create(
    user=student,
    organization=org,
    role='Member',
    status='Active'
)

print("Test data created!")
exit()
```

---

## Step 3: Access Application in Browser

1. Open web browser (Chrome or Firefox)
2. Go to: **http://localhost:8000**
3. You should see the UBCSO app login page

---

## Step 4: Capture Screenshots Using Chrome DevTools

### Method 1: Full Page Screenshot (RECOMMENDED)

```
1. Right-click anywhere on the page
2. Select "Inspect" (or press F12)
3. Press Ctrl+Shift+P (or Cmd+Shift+P on Mac)
4. Type: "capture full page screenshot"
5. Press Enter
6. Screenshot automatically saves to Downloads folder
7. Rename with descriptive name (e.g., "01-login-page.png")
```

### Method 2: Responsive Design Screenshots

For mobile screenshots:

```
1. Open DevTools (F12)
2. Click responsive design mode icon (Ctrl+Shift+M)
3. Change device to: iPhone 12 Pro (390 × 844)
4. Or device: iPad Pro (1024 × 1366)
5. Navigate to the page
6. Follow "Method 1" to capture screenshot
```

### Method 3: Element Screenshot

To capture just one section:

```
1. Right-click on the element you want
2. Choose "Inspect"
3. Right-click the element in DevTools
4. Select "Capture node screenshot"
5. Image saves automatically
```

---

## Step 5: Screenshots to Capture

### Login/Registration (2 images)

**Image 1: Login Page**
```
1. Go to: http://localhost:8000
2. You should see login form (if not logged in)
3. Capture full page
4. Save as: "01-login-page.png"
```

**Image 2: Registration Form**
```
1. Click "Don't have account? Sign up"
2. You'll see registration form
3. Capture full page
4. Save as: "02-registration-form.png"
```

---

### Student Dashboard (3 images)

**Image 1: Student Dashboard**
```
1. Login with student credentials
2. You'll be on student dashboard
3. Capture full page
4. Save as: "03-student-dashboard.png"
```

**Image 2: Organization Directory**
```
1. Click "Organizations" in navigation
2. You'll see list of organizations
3. Scroll to show multiple org cards
4. Capture full page
5. Save as: "04-org-directory.png"
```

**Image 3: Organization Details**
```
1. Click on any organization card
2. You'll see organization details page
3. Capture full page
4. Save as: "05-org-details.png"
```

---

### Voting (2 images)

**Image 1: Elections List**
```
1. Click "Elections" in navigation
2. You'll see active elections
3. Capture full page
4. Save as: "06-elections-list.png"
```

**Image 2: Voting Interface**
```
1. Click "Vote Now" on an active election
2. You'll see voting form with candidates
3. Scroll to show all positions
4. Capture full page
5. Save as: "07-voting-interface.png"
```

---

### Organization Leader (3 images)

**Image 1: Leader Dashboard**
```
1. Logout and login as organization leader/chairman
2. You'll see leader-specific dashboard
3. Capture full page
4. Save as: "08-leader-dashboard.png"
```

**Image 2: Member Management**
```
1. Click "Members" in navigation
2. You'll see member list and pending requests
3. Capture full page
4. Save as: "09-members-management.png"
```

**Image 3: Create Election**
```
1. Click "Elections" 
2. Click "Create Election"
3. You'll see election creation form
4. Fill in some details (they don't have to be complete)
5. Capture full page
6. Save as: "10-create-election.png"
```

---

### Admin Panel (2 images)

**Image 1: Admin Dashboard**
```
1. Logout and login as CSO admin/superuser
2. You'll see admin-specific dashboard
3. Capture full page
4. Save as: "11-admin-dashboard.png"
```

**Image 2: Organization Management**
```
1. Click "Organizations" in admin menu
2. You'll see organization list and actions
3. Capture full page
4. Save as: "12-admin-organizations.png"
```

---

### Mobile Views (2 images)

**Image 1: Mobile Login**
```
1. Open DevTools (F12)
2. Click responsive design mode (Ctrl+Shift+M)
3. Change to iPhone 12 Pro
4. Go to http://localhost:8000
5. Capture full page
6. Save as: "13-mobile-login.png"
```

**Image 2: Mobile Dashboard**
```
1. Login on mobile view
2. You'll see responsive dashboard
3. Scroll to show navigation and content
4. Capture full page
5. Save as: "14-mobile-dashboard.png"
```

---

## Step 6: Organize Screenshots

Create folder structure:

```
c:\Users\User\Desktop\UBCSO APP\
├── documentation/
│   └── screenshots/
│       ├── 01-login-page.png
│       ├── 02-registration-form.png
│       ├── 03-student-dashboard.png
│       ├── 04-org-directory.png
│       ├── 05-org-details.png
│       ├── 06-elections-list.png
│       ├── 07-voting-interface.png
│       ├── 08-leader-dashboard.png
│       ├── 09-members-management.png
│       ├── 10-create-election.png
│       ├── 11-admin-dashboard.png
│       ├── 12-admin-organizations.png
│       ├── 13-mobile-login.png
│       └── 14-mobile-dashboard.png
```

---

## Step 7: Use Screenshots in Documentation

Add screenshots to DOCUMENTATION.md with links:

```markdown
### Example Usage:

![Login Page](documentation/screenshots/01-login-page.png)
**Figure 1: Student Login Interface**

The login page shows the authentication form where students enter...
```

Or reference them in HTML if using web-based docs:

```html
<figure>
    <img src="documentation/screenshots/01-login-page.png" 
         alt="Student Login Page" 
         width="800">
    <figcaption>Figure 1: Student Login Interface</figcaption>
</figure>
```

---

## Troubleshooting

### "Screenshots folder not visible"
- Create the folder manually: `mkdir documentation\screenshots`
- On Windows Explorer: Right-click → New Folder

### "Chrome DevTools shortcut not working"
- Try: Right-click on page → Inspect → DevTools opens
- Then press Ctrl+Shift+P for screenshot menu

### "Screenshots too large"
- Screenshots are typically 1-2 MB, which is fine
- For documentation: Keep as is (high quality is better)
- For web: Consider compressing with TinyPNG or ImageOptim

### "Page looks different than expected"
- Make sure dev server is running
- Clear browser cache (Ctrl+Shift+Delete)
- Refresh page (Ctrl+F5)

---

## Additional Tips

### 1. Adjust Page Zoom for Better Screenshots

If text is too small:
```
1. Open DevTools (F12)
2. Click the three dots menu
3. Find "Zoom" setting
4. Increase to 110-125%
5. Take screenshot
```

### 2. Hide Sensitive Information

Before taking screenshots:
- Don't show real email addresses or phone numbers
- Use test data (student@ub.edu.ph, etc.)
- Don't capture API keys or passwords

### 3. Take Multiple Angles

Capture:
- Full page (scroll to show complete content)
- Zoomed sections (for detail)
- Different screen sizes (desktop, tablet, mobile)
- Different user roles (student, leader, admin)

### 4. Edit Screenshots (Optional)

After capturing, you can add annotations:
- Use Paint (Windows) to add arrows/boxes
- Use Markup (Mac) to highlight areas
- Use Preview (Mac) to add text
- Use online tools: https://pixlr.com (free)

---

## Next Steps

1. ✅ Capture all 14+ screenshots
2. ✅ Save to `/documentation/screenshots/` folder
3. ✅ Update DOCUMENTATION.md with screenshot links
4. ✅ Add captions and descriptions
5. ✅ Create README in screenshots folder
6. ✅ Commit to Git with: `git add documentation/`

---

## Questions?

If you encounter any issues:
1. Check that dev server is running: http://localhost:8000
2. Verify you have test data (admin user, student user, organization)
3. Try refreshing the page (Ctrl+F5)
4. Try a different browser (Chrome, Firefox, Safari)

Good luck capturing screenshots! 📸

