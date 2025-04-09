import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os

# 사용자 설정
BOT_TOKEN = '8059473480:AAHWayTZDViTfTk-VtCAmPxvYAmTrjhtMMs'
CHAT_ID = '2037756724'
SHEET_NAME = '디마니코 뉴스 트래커'

# 구글 시트 연결
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

# 네이버 속보 뉴스 수집
def get_naver_news():
    url = 'https://news.naver.com/main/list.naver?mode=LSD&mid=sec&sid1=001'
    res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(res.text, 'html.parser')

    news_items = []
    for li in soup.select('.type06_headline li'):
        a_tag = li.select_one('a')
        if not a_tag:
            continue
        link = a_tag['href']

        strong = li.select_one('strong')
        title = strong.get_text(strip=True) if strong else a_tag.get_text(strip=True)

        # 한글 포함, 길이 필터
        if not title or len(title) < 5 or not re.search(r'[가-힣]', title):
            continue

        news_items.append((title, link))
    return news_items

# 텔레그램 메시지 전송
def send_telegram(title, link):
    msg = f"""🔥 <b>디마니코 뉴스</b> 🔥

{title}
{link}
"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': CHAT_ID,
        'text': msg,
        'parse_mode': 'HTML',
        'disable_web_page_preview': False
    }
    response = requests.post(url, data=data)
    print(f"[텔레그램 응답] {response.text}")

# 구글시트에 기록
def log_to_sheet(sheet, title, link):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([now, title, link])
    print(f"[{now}] 시트 기록됨: {title}")

# 루프 실행
def start_loop():
    sheet = connect_sheet()
    old_links = []
    while True:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 루프 동작 중...")
        news_list = get_naver_news()
        for title, link in news_list:
            if link not in old_links:
                print(f"[감지] {title}")
                send_telegram(title, link)
                log_to_sheet(sheet, title, link)
                old_links.append(link)
                if len(old_links) > 50:
                    old_links.pop(0)
        time.sleep(60)

# 시작
if __name__ == '__main__':
    start_loop()
