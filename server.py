"""Kalamela 2026 attendance tracker - local laptop server.

Run:  python server.py            (default port 8000)
Then open http://localhost:8000 on this laptop, or http://<laptop-ip>:8000 on
phones/tablets on the same Wi-Fi. Data is kept in kalamela.db next to this file.
The same app also deploys to Vercel (see README.md).
"""
import argparse
import os
import socket
import sys
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "api", "_lib"))

import kalamela  # noqa: E402


class LocalHandler(kalamela.Handler):
    serve_static = True


def lan_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except Exception:
        pass
    return sorted(i for i in ips if not i.startswith("127."))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    ap.add_argument("--host", default="0.0.0.0")
    a = ap.parse_args()
    with kalamela.STORE.tx() as t:
        codes = kalamela.codes_of(t.config())
    ThreadingHTTPServer.daemon_threads = True
    ThreadingHTTPServer.request_queue_size = 64
    srv = ThreadingHTTPServer((a.host, a.port), LocalHandler)
    print("\n  Kalamela 2026 attendance tracker is running.\n")
    print(f"  On this laptop:      http://localhost:{a.port}")
    for ip in lan_ips():
        print(f"  Phones / tablets:    http://{ip}:{a.port}   (same Wi-Fi)")
    print("\n  Sign-in codes:  admin " + (codes["admin"] or kalamela.env_admin_code() or "(not set)") + " | "
          + " | ".join(f"{k} {codes.get(k, '')}" for k in ("V1", "V2", "V3", "V4")))
    print("  Database: " + ("Postgres (DATABASE_URL)" if kalamela.PG_URL else kalamela.SQLITE_PATH))
    print("  Keep this window open. Press Ctrl+C to stop.\n", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
