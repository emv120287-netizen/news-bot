import os
import time
import uuid
import threading
import requests
import feedparser
import urllib3
from http.server import HTTPServer, BaseHTTPRequestHandler

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
RSS_URL = os.getenv("RSS_URL", "https://www.rbc.ru/rss/politics")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "600"))
GIGACHAT_KEY = os.getenv("GIGACHAT_KEY")

last_sent = set()
access_token = None
token_expiry = 0

GIGA_AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
GIGA_API_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"


def get_giga_token():
    global access_token, token_expiry
    if access_token and time.time() < token_expiry - 60:
        return access_token
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": str(uuid.uuid4()),
        "Authorization": f"Basic {GIGACHAT_KEY}",
    }
    payload = "scope=GIGACHAT_API_PERS"
    try:
        r = requests.post(GIGA_AUTH_URL, headers=headers, data=payload, verify=False)
        if r.status_code == 200:
            data = r.json()
            access_token = data["access_token"]
            token_expiry = time.time() + data.get("expires_in", 1800)
            print("GigaChat token obtained")
            return access_token
        else:
            print(f"Token error: {r.status_code} {r.text}")
    except Exception as e:
        print(f"Token error: {e}")
    return None


def rewrite_text(text):
    if not GIGACHAT_KEY:
        return text
    token = get_giga_token()
    if not token:
        return text
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    prompt = (
        "Перефразируй новость для Telegram-канала о политике. "
        "Сделай текст короче и живее, добавь 1-2 подходящих эмодзи. "
        "Не выдумывай факты, сохрани суть. "
        f"Текст: {text}"
    )
    payload = {
        "model": "GigaChat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 512,
    }
    try:
        r = requests.post(GIGA_API_URL, headers=headers, json=payload, verify=False)
        if r.status_code == 200:
            result = r.json()["choices"][0]["message"]["content"]
            print(f"Rewritten: {result[:80]}...")
            return result
        else:
            print(f"Rewrite error: {r.status_code} {r.text}")
    except Exception as e:
        print(f"Rewrite error: {e}")
    return text


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
        raw_text = f"{title}. {summary}"
        rewritten = rewrite_text(raw_text)
        text = f"{rewritten}\n\n🔗 <a href=\"{link}\">Читать</a>"
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
   
