import threading
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
from flask import Flask
import re

# === 디마니코 정보 ===
BOT_TOKEN = '8059473480:AAHWayTZDViTfTk-VtCAmPxvYAmTrjhtMMs'
CHAT_ID = '2037756724'
SHEET_NAME = '디마니코 뉴스 트래커'

# === 키워드 필터 ===
KEYWORDS = ['특징', '속보', '단독', '저출산', '건설', '세종시', 'AI', '전기차', '이재명', '방산']

# === Flask 백그라운드 서버 (Render 전용) ===
app = Flask(__name__)
@app.route('/')
def home():
    return "디마니코 뉴스봇 작동 중!"
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=10000)).start()

# === 구글시트 연결 ===
def connect_sheet():
    key_json = os.environ.get('GOOGLE_KEY_JSON')
    if not key_json:
        print("❌ GOOGLE_KEY_JSON 환경변수 없음!")
        exit()
    key_dict = json.loads(key_json)
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

sheet = connect_sheet()

# === 네이버 정치 뉴스 수집 ===
def get_filtered_news():
    url = 'https://news.naver.com/main/list.naver?mode=LSD&mid=sec&sid1=100'
    res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(res.text, 'html.parser')
    news = []

    for li in soup.select('.type06_headline li'):
        a_tag = li.select_one('a')
        if not a_tag:
            continue
        title = a_tag.get_text(strip=True)
        link = a_tag['href']
        if not title or len(title) < 5 or not re.search(r'[가-힣]', title):
            continue
        if any(keyword in title for keyword in KEYWORDS):
            news.append((title, link))
    return news

# === 텔레그램 알림 ===
def send_telegram(title, link):
    message = f"""🔥 <b>디마니코 뉴스</b> 🔥

{title}
{link}
"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'HTML',
        'disable_web_page_preview': False
    }
    response = requests.post(url, data=data)
    print(f"[텔레그램 전송됨] {title}")

# === 구글시트 기록 ===
def log_to_sheet(title, link):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([now, title, link])
    print(f"[시트 기록됨] {title}")

# === 뉴스봇 루프 ===
old_links = []
def start_loop():
    while True:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 루프 작동 중...")
        news = get_filtered_news()
        for title, link in news:
            if link not in old_links:
                send_telegram(title, link)
                log_to_sheet(title, link)
                old_links.append(link)
                if len(old_links) > 50:
                    old_links.pop(0)
        time.sleep(60)

threading.Thread(target=start_loop).start()
