import requests
import feedparser
import os
import time
import threading
from datetime import datetime
from flask import Flask

# Мини-сервер, чтобы Render не усыплял бот
app = Flask(__name__)

@app.route("/")
def health():
    return "OK"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# Запускаем веб-сервер в отдельном потоке
threading.Thread(target=run_web, daemon=True).start()

# --- Переменные окружения ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")
GIGACHAT_KEY = os.environ.get("GIGACHAT_KEY", "")

SEEN_FILE = "seen_posts.txt"
TITLE_FILE = "seen_titles.txt"
CHECK_INTERVAL = 600

def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return {line.strip() for line in f}

def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for link in seen:
            f.write(link + "\n")

def load_titles():
    if not os.path.exists(TITLE_FILE):
        return set()
    with open(TITLE_FILE, "r", encoding="utf-8") as f:
        return {line.strip().lower() for line in f}

def save_titles(titles):
    with open(TITLE_FILE, "w", encoding="utf-8") as f:
        for title in titles:
            f.write(title + "\n")

def normalize_title(title):
    return " ".join(title.lower().split())

def get_gigachat_token():
    url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {GIGACHAT_KEY}"
    }
    payload = "scope=GIGACHAT_API_PERS"
    try:
        r = requests.post(url, headers=headers, data=payload, timeout=10)
        if r.status_code != 200:
            print(f"[ERROR] Токен GigaChat: {r.status_code} {r.text}")
            return None
        return r.json()["access_token"]
    except Exception as e:
        print(f"[ERROR] Ошибка токена: {e}")
        return None

def rewrite_with_gigachat(headline, summary):
    prompt = (
        "Перефразируй новость простым языком, как для Дзена: "
        "без кликбейта, без восклицаний, без «сенсаций». "
        "Сделай 2–3 абзаца. Не добавляй своё мнение. "
        f"Заголовок: {headline}\n"
        f"Краткое содержание: {summary}"
    )
    token = get_gigachat_token()
    if not token:
        return None
    url = "https://gigachat.devices.sberbank.ru/api/v2/chat/completions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "GigaChat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 800
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        if r.status_code != 200:
            print(f"[ERROR] GigaChat: {r.status_code} {r.text}")
            return None
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[ERROR] Parse: {e}")
        return None

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    r = requests.post(url, json=data)
    return r.ok

def fetch_news():
    seen_links = load_seen()
    seen_titles = load_titles()
    new_posts = []
    RSS_URLS = [
        "https://ria.ru/export/rss2/politics/index.xml",
        "https://rbc.ru/rss/politics"
    ]
    for url in RSS_URLS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:
            link = entry.get("link", "")
            title = entry.get("title", "")
            if not title or not link:
                continue
            if link in seen_links:
                continue
            norm_title = normalize_title(title)
            if norm_title in seen_titles:
                continue
            summary = entry.get("summary", "") or entry.get("description", "")
            rewritten = rewrite_with_gigachat(title, summary)
            if rewritten:
                post_text = f"<b>{title}</b>\n\n{rewritten}\n\n🔗 {link}"
                new_posts.append((post_text, link, norm_title))
                seen_links.add(link)
                seen_titles.add(norm_title)
                break
    save_seen(seen_links)
    save_titles(seen_titles)
    return new_posts

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Бот запущен")
    print(f"Канал: {CHANNEL_ID}")
    while True:
        try:
            posts = fetch_news()
            for text, link, _ in posts:
                ok = send_to_telegram(text)
                status = "OK" if ok else "ERROR"
                print(f"[{status}] {link[:60]}...")
        except Exception as e:
            print(f"[ERROR] {e}")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
