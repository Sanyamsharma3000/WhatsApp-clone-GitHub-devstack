from flask import Flask, jsonify, request
from flask_cors import CORS
import requests, re
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)
BASE = "https://agclms.in"

@app.route("/")
def home():
    return open("index.html").read()

@app.route("/api/sync", methods=["POST"])
def sync():
    d = request.json or {}
    roll = d.get("roll", "").strip()
    pw = d.get("password", "").strip()
    if not roll or not pw:
        return jsonify({"success": False, "error": "Enter roll and password"}), 400
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 Chrome/120"})
    r = s.get(BASE + "/Elogin/StudentLogin", timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    p = {i["name"]: i.get("value", "") for i in soup.find_all("input") if i.get("name")}
    p["StudentId"] = roll
    p["Password"] = pw
    r2 = s.post(BASE + "/Elogin/StudentLogin", data=p, timeout=15, allow_redirects=True)
    if "Elogin" in r2.url:
        return jsonify({"success": False, "error": "Wrong credentials."}), 401
    rd = s.get(BASE + "/DashBoardStudent", timeout=15)
    sd = BeautifulSoup(rd.text, "html.parser")
    links = []
    for a in sd.find_all("a", href=True):
        h = a["href"]
        if "AttendanceReport" in h and "SAId" in h:
            full = h if h.startswith("http") else BASE + h
            row = a.find_parent("tr")
            cells = row.find_all("td") if row else []
            nm = cells[0].get_text(strip=True) if cells else "Subject " + str(len(links) + 1)
            links.append({"url": full, "name": nm})
    if not links:
        return jsonify({"success": False, "error": "No subjects found."}), 500
    subs = []
    for i, lnk in enumerate(links):
        try:
            ra = s.get(lnk["url"], timeout=15)
            parsed = parse(ra.text, lnk["name"], i + 1)
            subs.extend(parsed)
        except:
            continue
    if not subs:
        return jsonify({"success": False, "error": "Could not read attendance."}), 500
    return jsonify({"success": True, "subjects": subs, "student": roll})

def parse(html, name, sid):
    soup = BeautifulSoup(html, "html.parser")
    nl = name.lower()
    t = "lab" if any(k in nl for k in ["lab", "practical"]) else "theory"
    results = []
    sub_id = sid * 10
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows: continue
        ht = rows[0].get_text(strip=True).lower()
        ist = "tutorial" in ht
        p = 0; tot = 0; dates = []
        for row in rows[1:]:
            cells = [td.get_text(strip=True).upper() for td in row.find_all("td")]
            if len(cells) >= 2:
                if "ABSENT" in cells[1] or "PRESENT" in cells[1]:
                    tot += 1
                    dates.append({"date": cells[0], "status": cells[1]})
                    if "PRESENT" in cells[1]: p += 1
        if tot > 0:
            lb = name + " (Tutorial)" if ist else name
            st = "tutorial" if ist else t
            results.append({"id": sub_id, "name": lb, "type": st, "present": p, "total": tot, "dates": dates})
            sub_id += 1
    if len(results) == 2:
        cp = sum(r["present"] for r in results)
        ct = sum(r["total"] for r in results)
        cd = results[0]["dates"] + results[1]["dates"]
        results.append({"id": sub_id + 1, "name": results[0]["name"].replace(" (Tutorial)", "") + " (Combined)", "type": "combined", "present": cp, "total": ct, "dates": cd})
    return results

if __name__ == "__main__":
    print("Open Chrome -> http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
