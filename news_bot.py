import os
import time
import json
import threading
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from flask import Flask
import openai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import traceback
import builtins

# ✅ print 재귀 오류 방지 (원본 백업)
real_print = builtins.print
builtins.print = lambda *args, **kwargs: real_print(*args, **{**kwargs, "flush": True})

# 🧠 설정import os
import time
import json
import threading
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime
from flask import Flask
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import traceback
import builtins

# ✅ 실시간 로그 출력
real_print = builtins.print
builtins.print = lambda *args, **kwargs: real_print(*args, **{**kwargs, "flush": True})

# 🧠 설정
BOT_TOKEN = '8059473480:AAHWayTZDViTfTk-VtCAmPxvYAmTrjhtMMs'
CHAT_ID = '2037756724'
SHEET_NAME = '디마니코 뉴스 트래커'
MAX_SEND_PER_LOOP = 3
LINK_CACHE_FILE = 'old_links.json'

# ✅ Flask 서버
app = Flask(__name__)
@app.route('/')
def home():
    return "🟢 디마니코 뉴스봇 (GPT 비활성 + 한글 필터)"

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

def get_daily_worksheet(sheet):
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        worksheet = sheet.worksheet(today)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=today, rows="1000", cols="6")
        worksheet.append_row(["기록시간", "뉴스제목", "요약", "감성", "링크", "언론사"])
    return worksheet

def log_to_sheet(sheet, title, summary, sentiment, link, press):
    worksheet = get_daily_worksheet(sheet)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        worksheet.append_row([now, title, summary, sentiment, link, press])
        print(f"[시트 기록됨] {title}")
    except Exception as e:
        print(f"❌ 시트 기록 실패:")
        traceback.print_exc()

def load_old_links():
    try:
        with open(LINK_CACHE_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_old_links(links):
    with open(LINK_CACHE_FILE, 'w') as f:
        json.dump(links[-100:], f)

def get_live_news():
    url = "https://news.naver.com/main/list.naver?mode=LSD&mid=sec&sid1=001"
    res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(res.text, 'html.parser')

    news_list = []
    for li in soup.select("ul.type06_headline li"):
        a_tag = li.select_one("a")
        press = li.select_one(".writing")
        if a_tag and press:
            title = a_tag.get_text(strip=True)
            link = a_tag['href']
            press_name = press.get_text(strip=True)
            news_list.append((title, link, press_name))
    return news_list

def fetch_article_content(url):
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(res.text, 'html.parser')
        paragraphs = soup.select("#dic_area p")
        content = "\n".join([p.get_text(strip=True) for p in paragraphs])
        print(f"📄 본문 길이: {len(content)}")
        return content[:1000]
    except Exception as e:
        print(f"❌ 본문 추출 실패:")
        traceback.print_exc()
        return ""

# ✅ GPT 비활성 모드용 고정값
def summarize_news(title, content):
    return "요약 생략"

def analyze_sentiment(title, content):
    return "분석 생략"

# ✅ 한글 필터링 함수
def contains_korean(text):
    return bool(re.search(r'[가-힣]', text))

def send_telegram(title, summary, sentiment, link, press):
    message = f"""📰 <b>{title}</b>\n\n<b>요약:</b> {summary}\n<b>감성:</b> {sentiment}\n<b>언론사:</b> {press}\n\n{link}"""
    url_api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'HTML',
        'disable_web_page_preview': False
    }
    try:
        requests.post(url_api, data=data)
        print(f"📤 텔레그램 전송 완료: {title}")
    except Exception as e:
        print(f"❌ 텔레그램 전송 실패:")
        traceback.print_exc()

# ✅ 뉴스 루프
def news_loop():
    old_links = load_old_links()
    while True:
        now = datetime.now().strftime('%H:%M:%S')
        print(f"\n🔁 [{now}] 뉴스 루프 시작")
        news_items = get_live_news()
        count = 0
        for title, link, press in news_items:
            if link not in old_links and contains_korean(title):
                content = fetch_article_content(link)
                if not contains_korean(content):
                    print(f"⛔ 본문에 한글 없음 → 제외: {title}")
                    continue
                summary = summarize_news(title, content)
                sentiment = analyze_sentiment(title, content)
                send_telegram(title, summary, sentiment, link, press)
                log_to_sheet(sheet, title, summary, sentiment, link, press)
                old_links.append(link)
                count += 1
                time.sleep(1)
                if count >= MAX_SEND_PER_LOOP:
                    break
        save_old_links(old_links)
        time.sleep(60)

# ✅ 백그라운드 실행
threading.Thread(target=news_loop, daemon=True).start()

# ✅ Flask 실행
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

BOT_TOKEN = '8059473480:AAHWayTZDViTfTk-VtCAmPxvYAmTrjhtMMs'
CHAT_ID = '2037756724'
SHEET_NAME = '디마니코 뉴스 트래커'
MAX_SEND_PER_LOOP = 3
LINK_CACHE_FILE = 'old_links.json'
openai.api_key = os.environ.get("OPENAI_API_KEY")

# ✅ Flask 서버
app = Flask(__name__)
@app.route('/')
def home():
    return "🟢 디마니코 뉴스봇 작동 중!"

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

def get_daily_worksheet(sheet):
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        worksheet = sheet.worksheet(today)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=today, rows="1000", cols="6")
        worksheet.append_row(["기록시간", "뉴스제목", "요약", "감성", "링크", "언론사"])
    return worksheet

def log_to_sheet(sheet, title, summary, sentiment, link, press):
    worksheet = get_daily_worksheet(sheet)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        worksheet.append_row([now, title, summary, sentiment, link, press])
        print(f"[시트 기록됨] {title}")
    except Exception as e:
        print(f"❌ 시트 기록 실패:")
        traceback.print_exc()

def load_old_links():
    try:
        with open(LINK_CACHE_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_old_links(links):
    with open(LINK_CACHE_FILE, 'w') as f:
        json.dump(links[-100:], f)

def get_live_news():
    url = "https://news.naver.com/main/list.naver?mode=LSD&mid=sec&sid1=001"
    res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(res.text, 'html.parser')

    news_list = []
    for li in soup.select("ul.type06_headline li"):
        a_tag = li.select_one("a")
        press = li.select_one(".writing")
        if a_tag and press:
            title = a_tag.get_text(strip=True)
            link = a_tag['href']
            press_name = press.get_text(strip=True)
            news_list.append((title, link, press_name))
    return news_list

def fetch_article_content(url):
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(res.text, 'html.parser')
        paragraphs = soup.select("#dic_area p")
        content = "\n".join([p.get_text(strip=True) for p in paragraphs])
        print(f"📄 본문 길이: {len(content)}")
        return content[:1000]
    except Exception as e:
        print(f"❌ 본문 추출 실패:")
        traceback.print_exc()
        return ""

def summarize_news(title, content):
    try:
        print(f"🧠 GPT 요약 요청: {title}")
        prompt = f"다음 뉴스 내용을 한 문장으로 요약해줘:\n\n제목: {title}\n\n내용: {content}"
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        print("✅ GPT 응답 도착")
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ 요약 실패:")
        traceback.print_exc()
        return "요약 실패"

def analyze_sentiment(title, content):
    try:
        print(f"📊 감성 분석 요청: {title}")
        prompt = f"다음 뉴스가 투자자 관점에서 긍정적인지, 부정적인지, 중립적인지 판단해줘:\n\n제목: {title}\n\n내용: {content}"
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        print("✅ 감성 분석 결과 수신")
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ 감성 분석 실패:")
        traceback.print_exc()
        return "분석 실패"

def send_telegram(title, summary, sentiment, link, press):
    message = f"""📰 <b>{title}</b>\n\n<b>요약:</b> {summary}\n<b>감성:</b> {sentiment}\n<b>언론사:</b> {press}\n\n{link}"""
    url_api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'HTML',
        'disable_web_page_preview': False
    }
    try:
        requests.post(url_api, data=data)
        print(f"📤 텔레그램 전송 완료: {title}")
    except Exception as e:
        print(f"❌ 텔레그램 전송 실패:")
        traceback.print_exc()

def news_loop():
    old_links = load_old_links()
    while True:
        now = datetime.now().strftime('%H:%M:%S')
        print(f"\n🔁 [{now}] 뉴스 루프 시작")
        news_items = get_live_news()
        count = 0
        for title, link, press in news_items:
            if link not in old_links:
                content = fetch_article_content(link)
                summary = summarize_news(title, content)
                sentiment = analyze_sentiment(title, content)
                send_telegram(title, summary, sentiment, link, press)
                log_to_sheet(sheet, title, summary, sentiment, link, press)
                old_links.append(link)
                count += 1
                time.sleep(1)
                if count >= MAX_SEND_PER_LOOP:
                    break
        save_old_links(old_links)
        time.sleep(60)

# ✅ 루프 백그라운드 실행
threading.Thread(target=news_loop, daemon=True).start()

# ✅ Flask 서버 실행
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
