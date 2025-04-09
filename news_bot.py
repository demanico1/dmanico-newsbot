# -*- coding: utf-8 -*-
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
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

# 텔레그램 정보
BOT_TOKEN = '8059473480:AAHWayTZDViTfTk-VtCAmPxvYAmTrjhtMMs'
CHAT_ID = '2037756724'
SHEET_NAME = '디마니코 뉴스 트래커'

# Flask 백그라운드 서버 유지 (Render용)
app = Flask(__name__)
@app.route('/')
def home():
    return "디마니코 뉴스봇 작동 중!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)
threading.Thread(target=run_flask).start()

# 종목 리스트 불러오기
def get_krx_stock_list():
    url = "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download"
    df = pd.read_html(url, encoding='cp949')[0]
    df['종목코드'] = df['종목코드'].apply(lambda x: f"{x:06d}")
    return dict(zip(df['회사명'], df['종목코드']))

stock_dict = get_krx_stock_list()

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
    sheet = client.open(SHEET_NAME).sheet1
    return sheet

sheet = connect_sheet()

# 시트 기록
def log_to_sheet(title, link):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([now, title, link])
    print(f"[시트 기록] {title}")

# 텔레그램 전송
def send_telegram_news(title, link):
    message = f"""[디마니코 뉴스]\n\n{title}\n{link}"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'HTML',
        'disable_web_page_preview': False
    }
    response = requests.post(url, data=data)
    print(f"[텔레그램 응답] {response.text}")

# 종목 추출
def extract_stock_from_article(title, url):
    text = title
    try:
        res = requests.get(url, timeout=3)
        soup = BeautifulSoup(res.text, 'html.parser')
        text += soup.get_text()
    except:
        pass

    for name in stock_dict.keys():
        if name in text:
            return name, stock_dict[name]
    return None, None

# 병렬 수집 대상 뉴스 함수들
def get_naver_finance_news():
    news_list = []
    url = "https://finance.naver.com/news/mainnews.naver"
    res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(res.text, "html.parser")
    for a in soup.select(".mainNewsList li a"):
        title = a.get_text(strip=True)
        link = "https://finance.naver.com" + a['href']
        if title:
            news_list.append((title, link))
    return news_list

def get_naver_rank_news():
    news_list = []
    url = "https://news.naver.com/main/ranking/popularDay.naver"
    res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(res.text, "html.parser")
    for a in soup.select("ul.ranking_list a"):
        title = a.get_text(strip=True)
        link = "https://news.naver.com" + a['href']
        if title:
            news_list.append((title, link))
    return news_list

# 병렬 뉴스 수집
def collect_all_news():
    with ThreadPoolExecutor() as executor:
        results = executor.map(lambda fn: fn(), [get_naver_finance_news, get_naver_rank_news])
    all_news = []
    for result in results:
        all_news.extend(result)
    return all_news

# 루프 시작
def start_news_loop():
    old_links = []
    while True:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 루프 작동 중...")
        all_news = collect_all_news()
        for title, link in all_news:
            if link not in old_links:
                stock_name, stock_code = extract_stock_from_article(title, link)
                if stock_name:
                    tagged_title = f"[{stock_name}] {title}"
                    send_telegram_news(tagged_title, link)
                    log_to_sheet(tagged_title, link)
                    old_links.append(link)
                    if len(old_links) > 100:
                        old_links.pop(0)
        time.sleep(60)

# 실행
threading.Thread(target=start_news_loop).start()
