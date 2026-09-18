import os
import requests
import feedparser

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"}
    requests.post(url, json=data)

def fetch_news():
    feed = feedparser.parse("https://example.com/feed.xml")
    if not feed.entries:
        send_message("Новостей пока нет.")
        return
    entry = feed.entries[0]
    title = entry.title
    link = entry.link
    summary = entry.summary[:300] + "..." if len(entry.summary) > 300 else entry.summary
    text = f"<b>{title}</b>\n\n{summary}\n\n<a href=\"{link}\">Читать</a>"
    send_message(text)

if __name__ == "__main__":
    print("Bot started")
    fetch_news()
    print("Done")
