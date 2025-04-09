from flask import Flask
import threading
import requests
from bs4 import BeautifulSoup
import time

# 🔒 디마니코 정보
BOT_TOKEN = '8059473480:AAHWayTZDViTfTk-VtCAmPxvYAmTrjhtMMs'
CHAT_ID = '2037756724'

# ✅ Flask 포트 오픈 (Render용)
app = Flask(__name__)

@app.route('/')
def home():
    return "디마니코 뉴스봇 작동 중!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

threading.Thread(target=run_flask).start()

# ✅ 제목 길이 제한
def shorten_title(title, max_length=60):
    return title if len(title) <= max_length else title[:max_length] + "..."

# ✅ 뉴스 수집 (네이버 속보 랭킹)
def get_news():
    url = 'https://news.naver.com/main/ranking/popularDay.naver?mid=etc&sid1=111'
    res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(res.text, 'html.parser')

    news_list = []
    for li in soup.select('.rankingnews_list li'):
        a_tag = li.select_one('a')
        if a_tag:
            title = a_tag.get_text(strip=True)
            link = a_tag['href']
            if title and link:
                news_list.append((title, link))
    return news_list

# ✅ 텔레그램 전송 (프리뷰 지원)
def send_telegram_news(title, link):
    short_title = shorten_title(title)
    message = f"""🔥 <b>속보 뉴스</b>

{short_title}
{link}
"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'HTML',
        'disable_web_page_preview': False  # ✅ 프리뷰 ON
    }

    response = requests.post(url, data=data)
    print(f"[텔레그램 응답] {response.text}")

# ✅ 뉴스 감시 루프
old_links = []

while True:
    print(f"[{time.strftime('%H:%M:%S')}] 루프 돌고 있음...")
    news = get_news()
    for title, link in news:
        if link not in old_links:
            print(f"[뉴스 감지] {title}")
            send_telegram_news(title, link)
            old_links.append(link)
            if len(old_links) > 50:
                old_links.pop(0)
    time.sleep(60)
