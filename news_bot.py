-- coding: utf-8 --

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

디마니코 정보

BOT_TOKEN = '텔레그램봇토큰'
CHAT_ID = '채팅ID'
SHEET_NAME = '디마니코 뉴스 트래커'

Flask 백그라운드 서버 유지 (Render용)

app = Flask(name)
@app.route('/')
def home():
return "디마니코 뉴스봇 작동 중!"

def run_flask():
app.run(host='0.0.0.0', port=10000)
threading.Thread(target=run_flask).start()

종목 리스트 (cp949 인코딩)

def get_krx_stock_list():
url = "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download"
df = pd.read_html(url, encoding='cp949')[0]
df['종목코드'] = df['종목코드'].apply(lambda x: f"{x:06d}")
return dict(zip(df['회사명'], df['종목코드']))

stock_dict = get_krx_stock_list()

종목명 추출

def extract_stock_from_article(title, url, stock_dict):
text = title
try:
res = requests.get(url, timeout=3)
soup = BeautifulSoup(res.text, 'html.parser')
body = soup.get_text()
text += body
except:
pass

for name in stock_dict.keys():
    if name in text:
        return name, stock_dict[name]
return None, None

뉴스 수집 (네이버 메인 뉴스 기준)

def get_all_news():
news_list = []
url = "https://finance.naver.com/news/mainnews.naver"
res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
soup = BeautifulSoup(res.text, "html.parser")
for a in soup.select(".mainNewsList li a"):
title = a.get_text(strip=True)
link = "https://finance.naver.com" + a['href']
if title:
news_list.append((link, title))
return news_list

구글시트 연결

def connect_sheet():
key_json = os.environ.get('GOOGLE_KEY_JSON')
if not key_json:
print("GOOGLE_KEY_JSON 환경변수 없음!")
exit()

key_dict = json.loads(key_json)
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1
return sheet

sheet = connect_sheet()

시트 기록

def log_to_sheet(sheet, title, link):
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
sheet.append_row([now, title, link])
print(f"[시트 기록됨] {title}")

텔레그램 전송

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

뉴스 수집 루프

def start_news_loop():
old_links = []
while True:
print(f"[{datetime.now().strftime('%H:%M:%S')}] 루프 돌고 있음...")
news = get_all_news()
print(f"[{datetime.now().strftime('%H:%M:%S')}] 수집된 뉴스 개수: {len(news)}")
for link, title in news:
if link not in old_links:
stock_name, stock_code = extract_stock_from_article(title, link, stock_dict)
if stock_name:
title = f"[{stock_name}] {title}"
send_telegram_news(title, link)
log_to_sheet(sheet, title, link)
old_links.append(link)
if len(old_links) > 30:
old_links.pop(0)
time.sleep(60)

threading.Thread(target=start_news_loop).start()

