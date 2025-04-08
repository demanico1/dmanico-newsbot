import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 🔐 디마니코 정보
BOT_TOKEN = '8059473480:AAHWayTZDViTfTk-VtCAmPxvYAmTrjhtMMs'
CHAT_ID = '2037756724'
SHEET_NAME = '디마니코 뉴스 트래커'
KEY_FILE = 'dmanico-news-key.json'

# ✅ 구글시트 연결
def connect_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    return sheet

sheet = connect_sheet()

# ✅ 뉴스 크롤링 (한글 + 실제 제목 추출)
def get_news():
    url = 'https://news.naver.com/main/list.naver?mode=LSD&mid=sec&sid1=001'
    res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(res.text, 'html.parser')

    news_list = []
    for li in soup.select('.type06_headline li'):
        a_tag = li.select_one('a')
        if a_tag:
            link = a_tag['href']

            # 실제 제목 찾기 우선순위: img alt > strong > a text
            img_tag = li.select_one('img')
            strong_tag = li.select_one('strong')

            if img_tag and img_tag.has_attr('alt'):
                title = img_tag['alt']
            elif strong_tag:
                title = strong_tag.get_text(strip=True)
            else:
                title = a_tag.get_text(strip=True)

            # 필터링: 제목 없거나 짧거나 한글 없으면 건너뛰기
            if not title or len(title) < 5 or not re.search(r'[가-힣]', title):
                continue

            news_list.append((title, link))

    return news_list

# ✅ 시트 기록
def log_to_sheet(sheet, title, link):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([now, title, link])
    print(f"[시트 기록됨] {title}")

# ✅ 텔레그램 전송
def send_telegram_news(title, link):
    message = f"""🔥 <b>디마니코 뉴스</b> 🔥

[속보] {title}
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
    print(f"[텔레그램 응답] {response.text}")

# ✅ 루프: 1분마다 감지
old_links = []
while True:
    news = get_news()
    for title, link in news:
        if link not in old_links:
            print(f"[뉴스 감지] {title}")
            send_telegram_news(title, link)
            log_to_sheet(sheet, title, link)
            old_links.append(link)
            if len(old_links) > 30:
                old_links.pop(0)
    time.sleep(60)
