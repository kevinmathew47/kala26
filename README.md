# Kalamela 2026 – Attendance & Venue Tracker

Venue desks for volunteers, a live admin dashboard, participant tracking across 4 venues,
and admin-only Excel export for the Ernakulam Yuvajana Sakhyam Kalamela 2026.

The same code runs in two ways:

| | Online on Vercel | On a laptop |
|---|---|---|
| Who can open it | Anyone with the link, on any network | Devices on the same Wi-Fi |
| Data stored in | Neon Postgres (free) | `kalamela.db` file |
| Start | Deploy from GitHub | Double-click `START-KALAMELA.bat` |

---

## Deploy on Vercel

### 1. Import the repository
1. Sign in at https://vercel.com with GitHub.
2. **Add New → Project**, pick **kala26**, then **Import**.
3. Framework Preset: **Other**. Leave Build and Output settings empty.
4. Don't deploy yet. Open **Environment Variables** first (step 3), or deploy now and redeploy after step 3.

### 2. Add a database (free)
1. In the Vercel project: **Storage → Create Database → Neon (Serverless Postgres)**.
2. Choose the free plan and the region **Singapore** or **Mumbai** (closest to Kerala).
3. Connect it to the project for **Production** and **Preview**.
   This adds `DATABASE_URL` automatically. Tables are created on the first request.

### 3. Set your admin code
**Settings → Environment Variables → Add**
- Name: `KALAMELA_ADMIN_CODE`
- Value: your own secret code, at least 4 characters, e.g. `KM-7Q4X9P`

The admin code is never stored in this repository. This variable always works as an admin
login, even after you change codes in Settings, so you can't get locked out.

### 4. Deploy
**Deployments → Redeploy** (or push any commit). Open the `.vercel.app` link and sign in
with your admin code.

### 5. Before the event
- **Settings → Sign-in codes:** change all four venue codes. The defaults below are public in this repository.
  Saving new codes signs out every other device.
- **Settings → Reset attendance** clears practice data.
- Test with two phones: mark someone present on one, and watch the dashboard update on the other.

### Updating
Every `git push` to `main` redeploys automatically. Attendance in the database is kept.

---

## Run on a laptop instead
1. Install Python 3.10 or newer, then once: `pip install -r requirements.txt`
2. Double-click **START-KALAMELA.bat** and keep the black window open.
3. The window shows the admin code (random on first start) and an address like
   `http://192.168.1.5:8000` for phones on the same Wi-Fi.
4. Allow Python through the Windows Firewall if asked (Private networks).

---

## Sign-in codes
**Admin:** set `KALAMELA_ADMIN_CODE`, or on a laptop read it from the black window.

| Default venue code | Opens |
|---|---|
| CHURCH1 | V1 – Inside the Church |
| BALCONY2 | V2 – Balcony |
| SSHALL3 | V3 – Sunday School Hall / Vestry |
| FHALL4 | V4 – Fellowship Hall |

Volunteers only see and mark their own venue. Only the admin can export Excel,
edit the schedule, change codes or reset.

## Excel export
Admin → **Export Excel** (top right) or **Reports & export**. The sheets are:
Summary, Attendance, Participants, Events and Activity log.

## Project layout
```
api/index.py          Vercel serverless entry point
api/_lib/kalamela.py  backend (shared by Vercel and the laptop server)
api/_lib/data.json    127 participants, 42 events (checked against the master sheet)
public/               website (HTML, CSS, JS, logo)
server.py             laptop server
tools/build_data.py   rebuilds data.json from the schedule PDF and master sheet
```
