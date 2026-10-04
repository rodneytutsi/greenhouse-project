"""Tiny Smart Greenhouse demo: simulated sensors + live dashboard (stdlib only)."""
import json, math, random, time
from http.server import BaseHTTPRequestHandler, HTTPServer

START = time.time()

def reading():
    t = time.time() - START
    temp = 24 + 4 * math.sin(t / 30) + random.uniform(-0.3, 0.3)
    hum = 65 + 10 * math.cos(t / 40) + random.uniform(-1, 1)
    soil = 40 + 15 * math.sin(t / 55) + random.uniform(-1, 1)
    alerts = []
    if temp > 27: alerts.append("Temperature high - open vents")
    if hum < 58: alerts.append("Humidity low - run misting")
    if soil < 30: alerts.append("Soil dry - start irrigation")
    return {"time": time.strftime("%H:%M:%S"), "temperature_c": round(temp, 1),
            "humidity_pct": round(hum, 1), "soil_moisture_pct": round(soil, 1), "alerts": alerts}

PAGE = """<!doctype html><meta charset=utf-8><title>Greenhouse Demo</title>
<style>body{font-family:sans-serif;background:#eef6ee;max-width:560px;margin:2rem auto}
.c{display:inline-block;background:#fff;border-radius:10px;padding:1rem 1.4rem;margin:.4rem;box-shadow:0 1px 4px #0002}
b{font-size:1.8rem}.a{color:#b00}</style>
<h1>Greenhouse Live</h1><div id=d>loading...</div>
<script>async function u(){const r=await (await fetch('/api/reading')).json();
d.innerHTML=`<div class=c>Temp<br><b>${r.temperature_c}&deg;C</b></div>
<div class=c>Humidity<br><b>${r.humidity_pct}%</b></div>
<div class=c>Soil<br><b>${r.soil_moisture_pct}%</b></div>
<p>${r.alerts.map(a=>'<div class=a>&#9888; '+a+'</div>').join('')||'All good'}</p><small>${r.time}</small>`}
u();setInterval(u,2000)</script>"""

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/reading":
            body, ctype = json.dumps(reading()).encode(), "application/json"
        else:
            body, ctype = PAGE.encode(), "text/html"
        self.send_response(200); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass

if __name__ == "__main__":
    print("Serving on http://localhost:8000")
    HTTPServer(("0.0.0.0", 8000), H).serve_forever()
