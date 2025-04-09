import os
import time
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 디마니코 전용 설정값
BOT_TOKEN = '8059473480:AAHWayTZDViTfTk-VtCAmPxvYAmTrjhtMMs'
CHAT_ID = '2037756724'
SHEET_NAME = '디마니코 뉴스 트래커'
MAX_SEND_PER_LOOP = 5  # 루프당 전송 개수 제한

# ✅ 구글 시트 연결
def connect_google_sheet(sheet_name):
    key_json = os.environ.get('GOOGLE_KEY_JSON')
    if not key_json:
        print("❌ GOOGLE_KEY_JSON 환경변수 없음!")
        exit()
    key_dict = json.loads(key_json)
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    client = gspread.authorize(creds)
    return client.open(sheet_name)

sheet = connect_google_sheet(SHEET_NAME)

# ✅ 날짜별 워크시트 가져오기
def get_daily_worksheet(sheet):
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        worksheet = sheet.worksheet(today)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=today, rows="1000", cols="4")
        worksheet.append_row(["기록시간", "섹션", "뉴스제목", "링크"])
    return worksheet

# ✅ 시트에 기록
def log_to_sheet(sheet, section, title, link):
    worksheet = get_daily_worksheet(sheet)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    worksheet.append_row([now, section, title, link])
    print(f"[시트 기록됨] {title}")

# ✅ 네이버 랭킹 뉴스 수집 (모든 카테고리 + 언론사별 TOP 1)
def get_ranking_news():
    url = "https://news.naver.com/main/ranking/popularDay.naver"
    res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(res.text, 'html.parser')

    news_list = []
    categories = soup.select(".rankingnews_box")

    for category in categories:
        category_name = category.select_one("h4.rankingnews_box_title").get_text(strip=True)
        media_groups = category.select(".rankingnews_box_inner")

        for media in media_groups:
            press_name_tag = media.select_one(".rankingnews_name")
            press_name = press_name_tag.get_text(strip=True) if press_name_tag else "언론사 없음"

            articles = media.select("li")
            if articles:
                li = articles[0]  # ✅ 1위 기사만
                a_tag = li.select_one("a")
                img_tag = li.select_one("img")
                if a_tag:
                    title = a_tag.get_text(strip=True)
                    link = a_tag['href']
                    img_url = img_tag['src'] if img_tag else None
                    full_section = f"{category_name} - {press_name}"
                    news_list.append((full_section, 1, title, link, img_url))

    return news_list

# ✅ 텔레그램 전송
def send_telegram(section, rank, title, link, img_url=None):
    message = f"""📢 <b>[{section} TOP {rank}]</b>\n\n{title}\n{link}"""
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
first_run = True
old_links = []

while True:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 루프 작동 중...")
    news_items = get_ranking_news()
    count = 0

    for section, rank, title, link, img_url in news_items:
        if link not in old_links:
            if not first_run:
                send_telegram(section, rank, title, link, img_url)
                log_to_sheet(sheet, section, title, link)
                count += 1
                time.sleep(1)
            old_links.append(link)

            if count >= MAX_SEND_PER_LOOP:
                print("⚠️ 전송 제한 도달. 다음 루프까지 대기.")
                break

    if first_run:
        print("🔕 첫 루프에서는 뉴스 전송 없이 링크만 저장합니다.")
        first_run = False

    if len(old_links) > 100:
        old_links = old_links[-50:]

    time.sleep(60)
