# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
from flask import Flask
import threading

# ▶️ 디마니코 정보
BOT_TOKEN = '8059473480:AAHWayTZDViTfTk-VtCAmPxvYAmTrjhtMMs'
CHAT_ID = '2037756724'
SHEET_NAME = '디마니코 뉴스 트래커'

# ✅ 구글 시트 연결
def connect_sheet():
    key_json = os.environ.get('GOOGLE_KEY_JSON')
    if not key_json:
        print("❌ GOOGLE_KEY_JSON 환경변수 없음!")
        exit()
    key_dict = json.loads(key_json)
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    return sheet

sheet = connect_sheet()

# ✅ 뉴스 수집 (stockinfo7.com 전용)
def get_stockinfo7_news():
    url = "https://stockinfo7.com/news/latest"
    res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(res.text, "html.parser")

    news_list = []
    for card in soup.select("div.card-body"):
        title_tag = card.select_one("h5.card-title a")
        time_tag = card.select_one("p.card-text small")
        img_tag = card.find_previous_sibling("img")  # 카드 위 이미지
        if title_tag:
            title = title_tag.get_text(strip=True)
            link = "https://stockinfo7.com" + title_tag['href']
            timestamp = time_tag.get_text(strip=True) if time_tag else ""
            img_url = img_tag['src'] if img_tag and img_tag.has_attr('src') else None
            news_list.append((title, link, timestamp, img_url))
    return news_list

# ✅ 시트 기록
def log_to_sheet(title, link, timestamp):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([now, title, timestamp, link])
    print(f"[시트 기록됨] {title}")

# ✅ 텔레그램 전송 (텍스트 + 썸네일)
def send_telegram(title, link, img_url=None):
    message = f"""📢 <b>디마니코 뉴스</b>\n\n{title}\n{link}"""
    if img_url:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        data = {
            'chat_id': CHAT_ID,
            'photo': img_url,
            'caption': message,
            'parse_mode': 'HTML'
        }
    else:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': CHAT_ID,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': False
        }
    response = requests.post(url, data=data)
    print(f"[텔레그램 응답] {response.text}")

# ✅ Flask 웹서버 실행 (Render keep-alive)
app = Flask(__name__)
@app.route('/')
def home():
    return "디마니코 뉴스봇 작동 중!"
def run_flask():
    app.run(host='0.0.0.0', port=10000)
threading.Thread(target=run_flask).start()

# ✅ 실시간 뉴스 감지 루프
old_links = []
while True:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 루프 작동 중...")
    news_items = get_stockinfo7_news()
    for title, link, timestamp, img_url in news_items:
        if link not in old_links:
            send_telegram(title, link, img_url)
            log_to_sheet(title, link, timestamp)
            old_links.append(link)
            if len(old_links) > 30:
                old_links.pop(0)
    time.sleep(60)
