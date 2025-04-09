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

# 🔐 디마니코 설정
BOT_TOKEN = '8059473480:AAHWayTZDViTfTk-VtCAmPxvYAmTrjhtMMs'
CHAT_ID = '2037756724'
SHEET_NAME = '디마니코 뉴스 트래커'

# 🌐 Flask 서버 (Render용 유지)
app = Flask(__name__)
@app.route('/')
def home():
    return "디마니코 뉴스봇 작동 중!"
def run_flask():
    app.run(host='0.0.0.0', port=10000)

# 📦 종목 리스트 불러오기
def get_krx_stock_list():
    url = "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download"
    df = pd.read_html(url, encoding='cp949')[0]
    df['종목코드'] = df['종목코드'].apply(lambda x: f"{x:06d}")
    return dict(zip(df['회사명'], df['종목코드']))

stock_dict = get_krx_stock_list()

# 🔍 뉴스 본문에서 종목명 추출
def extract_stock_from_article(title, url, stock_dict):
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

# ✅ 프리뷰 지원 매체 필터
def preview_supported(url):
    return any(domain in url for domain in [
        "n.news.naver.com", "biz.chosun.com", "news.mt.co.kr",
        "news.mk.co.kr", "hankyung.com", "fnnews.com",
        "biz.heraldcorp.com", "edaily.co.kr", "sedaily.com"
    ])

# 📥 각 매체별 뉴스 크롤링 함수
def get_naver_finance():
    url = "https://finance.naver.com/news/mainnews.naver"
    res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(res.text, "html.parser")
    return [("https://finance.naver.com" + a['href'], a.get_text(strip=True)) for a in soup.select(".mainNewsList li a")]

def get_naver_ranking():
    url = "https://news.naver.com/main/ranking/popularDay.naver"
    res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(res.text, "html.parser")
    return [("https://news.naver.com" + a['href'], a.get_text(strip=True)) for a in soup.select("ul.ranking_list li a")]

def get_chosunbiz():
    url = "https://biz.chosun.com/"
    res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(res.text, "html.parser")
    return [(a['href'], a.get_text(strip=True)) for a in soup.select("a") if a.get('href', '').startswith("https://biz.chosun.com")]

def get_mt():
    url = "https://news.mt.co.kr/newsList.html?sec=sisa&sec2=&pageNum=1"
    res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(res.text, "html.parser")
    return [("https://news.mt.co.kr" + a['href'], a.get_text(strip=True)) for a in soup.select("ul.list_news a") if a['href'].startswith("/mtview")]

# 📊 구글시트 연결
def connect_sheet():
    key_json = os.environ.get('GOOGLE_KEY_JSON')
    if not key_json:
        print("❌ GOOGLE_KEY_JSON 환경변수 없음!")
        exit()
    key_dict = json.loads(key_json)
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    return gspread.authorize(creds).open(SHEET_NAME).sheet1

sheet = connect_sheet()

# 📝 시트 기록
def log_to_sheet(sheet, title, link):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([now, title, link])
    print(f"[시트 기록됨] {title}")

# 🚀 텔레그램 전송
def send_telegram_news(title, link):
    message = f"""[디마니코 뉴스]

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
    print(f"[텔레그램 응답] {response.text}")

# 🔄 메인 루프
def start_news_loop():
    old_links = []
    while True:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 루프 돌고 있음...")

        all_news = []
        for fn in [get_naver_finance, get_naver_ranking, get_chosunbiz, get_mt]:
            try:
                all_news += fn()
            except Exception as e:
                print(f"[에러] {fn.__name__}: {e}")

        for link, title in all_news:
            if link not in old_links and preview_supported(link):
                stock_name, stock_code = extract_stock_from_article(title, link, stock_dict)
                if stock_name:
                    title = f"[{stock_name}] {title}"
                    send_telegram_news(title, link)
                    log_to_sheet(sheet, title, link)
                    old_links.append(link)
                    if len(old_links) > 50:
                        old_links.pop(0)

        time.sleep(60)

# 🔁 실행 시작
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    threading.Thread(target=start_news_loop).start()
