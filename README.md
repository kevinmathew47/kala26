# Kalamela 2026 – Attendance & Venue Tracker

## Start it
Double-click **START-KALAMELA.bat**. The site opens at http://localhost:8000.
Keep the black window open the whole day. Closing it stops the website.

## Phones and tablets
1. Connect them to the **same Wi-Fi** (or the laptop's hotspot) as the laptop.
2. The black window shows a line like `Phones / tablets: http://192.168.1.5:8000`.
   Open that address in Chrome on each device.
3. If it doesn't open, allow Python through the Windows Firewall when Windows asks
   (choose "Private networks").

## Sign-in codes (change them in Settings)
| Code | Opens |
|---|---|
| ADMIN2026 | Admin: dashboard, all venues, Excel export, settings |
| CHURCH1 | V1 – Inside the Church |
| BALCONY2 | V2 – Balcony |
| SSHALL3 | V3 – Sunday School Hall / Vestry |
| FHALL4 | V4 – Fellowship Hall |

## Excel
Admin → **Export Excel** (top right) or **Reports & export**. Volunteers cannot download.

## Before the real day
Settings → **Reset attendance** clears all practice marks.
All data is stored in `kalamela.db` in this folder. Copy it to keep a backup.

## Online hosting (optional)
The app also runs on a Python host (Render, Railway, a VPS).
- Install: `pip install -r requirements.txt`
- Start: `python server.py` (it reads the `PORT` environment variable)
- Set `KALAMELA_DB` to a path on a persistent disk, or attendance is lost when the host restarts.
- Set `KALAMELA_ADMIN_CODE` to your own admin code, and change the venue codes in Settings
  straight after the first sign-in. The default codes above are public in this repository.

## Updating the participant list
`tools/build_data.py` rebuilds `data.json` from the schedule PDF and master sheet:
`python tools/build_data.py "<folder with the PDF and xlsx>"`, then copy `build/data.json` here.
