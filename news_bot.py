import os
import time
import threading
import requests
import feedparser
from http.server import HTTPServer, BaseHTTPRequestHandler

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
RSS_URL = os.getenv("RSS_URL", "https://example.com/feed.xml")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "600"))

last_sent = set()

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"}
    requests.post(url, json=data)

def fetch_news():
    feed = feedparser.parse(RSS_URL)
    if not feed.entries:
        return
    for entry in feed.entries[:5]:
        if entry.link in last_sent:
            continue
        title = entry.title
        link = entry.link
        summary = entry.summary[:300] + "..." if len(entry.summary) > 300 else entry.summary
        text = f"<b>{title}</b>\n\n{summary}\n\n<a href=\"{link}\">Читать</a>"
        send_message(text)
        last_sent.add(link)
    if len(last_sent) > 100:
        last_sent.clear()
        for e in feed.entries:
            last_sent.add(e.link)

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, *args):
        pass

def news_loop():
    while True:
        try:
            fetch_news()
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    print("Bot started")
    t = threading.Thread(target=news_loop, daemon=True)
    t.start()
    server = HTTPServer(("0.0.0.0", 8080), HealthHandler)
    server.serve_forever()

