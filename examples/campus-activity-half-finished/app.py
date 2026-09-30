"""Run with python app.py; this teaching server listens on loopback only."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from auth import login
from enrollment import Activity

activity = Activity()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        result = {"name": "Campus workshop", "capacity": activity.capacity,
                  "registered": len(activity.members)}
        if self.path.startswith("/enroll"):
            result = {"success": activity.enroll(query.get("user", ["student"])[0])}
        elif self.path.startswith("/cancel"):
            activity.cancel(query.get("user", ["student"])[0])
            result = {"success": True}
        elif self.path.startswith("/login"):
            result = {"success": login(query.get("user", [""])[0], query.get("password", [""])[0])}
        body = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    print("Campus activity system: http://127.0.0.1:8890")
    ThreadingHTTPServer(("127.0.0.1", 8890), Handler).serve_forever()
