import requests
from bs4 import BeautifulSoup
import time

# 텔레그램 설정
BOT_TOKEN = '8059473480:AAHWayTZDViTfTk-VtCAmPxvYAmTrjhtMMs'
CHAT_ID = '2037756724'

# 제목 길이 자르기
def shorten_title(title, max_length=60):
    return title if len(title) <= max_length else title[:max_length] + "..."

# 뉴스 크롤링 (속보 실시간)
def get_news():
    url = 'https://news.naver.com/main/ranking/popularDay.naver?mid=etc&sid1=111'  # 속보
    res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(res.text, 'html.parser')

    news_list = []
    for li in soup.select('.type06_headline li'):
        a_tag = li.select_one('a')
        if a_tag:
            title = a_tag.get_text(strip=True)
            link = a_tag['href']
            news_list.append((title, link))
    return news_list

# 텔레그램 전송 (프리뷰 자동)
def send_telegram_news(title, link):
    short_title = shorten_title(title)
    message = f"""🔥 <b>속보 뉴스</b> 🔥

{short_title}
{link}
"""

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'HTML',
        'disable_web_page_preview': False  # 프리뷰 ON
    }

    response = requests.post(url, data=data)
    print(f"[텔레그램 응답] {response.text}")

# 뉴스 감시 루프
old_links = []
while True:
    news = get_news()
    for title, link in news:
        if link not in old_links:
            print(f"[뉴스 감지] {title}")
            send_telegram_news(title, link)
            old_links.append(link)
            if len(old_links) > 30:
                old_links.pop(0)
    time.sleep(30)  # 60초마다 체크
