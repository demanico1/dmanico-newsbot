import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os

# ▶️ 디마니코 정보
BOT_TOKEN = '8059473480:AAHWayTZDViTfTk-VtCAmPxvYAmTrjhtMMs'
CHAT_ID = '2037756724'
SHEET_NAME = '디마니코 뉴스 트래커'
MAX_SEND_PER_LOOP = 5  # 루프마다 최대 전송 뉴스 수

# ✅ 구글 시트 연결
def connect_google_sheet(sheet_name):
    key_json = os.environ.get('GOOGLE_KEY_JSON')
    key_dict = json.loads(key_json)
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    client = gspread.authorize(creds)
    return client.open(sheet_name)

sheet = connect_google_sheet(SHEET_NAME)

# ✅ 날짜별 시트 생성 또는 불러오기
def get_daily_worksheet(sheet):
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        worksheet = sheet.worksheet(today)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=today, rows="1000", cols="3")
        worksheet.append_row(["기록시간", "뉴스제목", "링크"])
    return worksheet

# ✅ 시트 기록
def log_to_sheet(sheet, title, link):
    worksheet = get_daily_worksheet(sheet)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    worksheet.append_row([now, title, link])
    print(f"[시트 기록됨] {title}")

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

# ✅ 텔레그램 전송 (텍스트 + 이미지 썸네일)
def send_telegram(title, link, img_url=None):
    message = f"""📢 <b>디마니코 뉴스</b>\n\n{title}\n{link}"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto" if img_url else f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': CHAT_ID,
        'caption': message if img_url else None,
        'photo': img_url if img_url else None,
        'text': None if img_url else message,
        'parse_mode': 'HTML',
        'disable_web_page_preview': False
    }
    try:
        response = requests.post(url, data={k: v for k, v in data.items() if v is not None})
        if response.status_code == 429:
            retry_after = response.json().get("parameters", {}).get("retry_after", 60)
            print(f"🔁 너무 많은 요청! {retry_after}초 대기")
            time.sleep(retry_after + 1)
        else:
            print(f"[텔레그램 응답] {response.text}")
    except Exception as e:
        print(f"[텔레그램 에러] {e}")

# ✅ 실행 루프
old_links = []
while True:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 루프 작동 중...")
    news_items = get_stockinfo7_news()
    count = 0
    for title, link, timestamp, img_url in news_items:
        if link not in old_links:
            send_telegram(title, link, img_url)
            log_to_sheet(sheet, title, link)
            old_links.append(link)
            count += 1
            if count >= MAX_SEND_PER_LOOP:
                print("⚠️ 전송 제한 도달. 다음 루프까지 대기.")
                break
            time.sleep(1)  # 뉴스 간 최소 1초 간격
    if len(old_links) > 100:
        old_links = old_links[-50:]
    time.sleep(60)
