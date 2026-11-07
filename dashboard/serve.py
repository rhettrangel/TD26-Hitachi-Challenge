#!/usr/bin/env python3
"""Simple local server to launch the Control Tower Dashboard."""

import http.server
import os
import socketserver
import webbrowser

PORT = 8501
DIRECTORY = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)


def main():
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        url = f"http://localhost:{PORT}/index.html"
        print(f"\n=======================================================")
        print(f"🚀 CONTROL TOWER DASHBOARD LIVE AT: {url}")
        print(f"Press Ctrl+C to stop.")
        print(f"=======================================================\n")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down Control Tower server.")


if __name__ == "__main__":
    main()
