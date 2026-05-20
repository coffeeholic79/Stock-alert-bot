import os
import html
import time
import requests
from bs4 import BeautifulSoup
import schedule
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 대상 종목 코드
STOCKS = {
    "삼성전자": "005930",
    "SK하이닉스": "000660",
    "현대자동차": "005380",
    "한화에어로스페이스": "012450",
    "LIG넥스원": "079550"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_market_index():
    url = "https://finance.naver.com/sise/"
    try:
        res = requests.get(url, headers=HEADERS)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        
        def parse_index(id_now, id_change):
            now = soup.select_one(f"#{id_now}").text.strip()
            change_node = soup.select_one(f"#{id_change}")
            if not change_node:
                return now
            
            if change_node.select_one(".nup"):
                icon = "🔺"
            elif change_node.select_one(".ndown"):
                icon = "🔻"
            else:
                icon = "-"
                
            clean_text = change_node.text.replace('상승', '').replace('하락', '').replace('보합', '').strip()
            parts = clean_text.split()
            if len(parts) >= 2:
                change_str = f"({icon}{parts[0]}, {parts[1]})"
            else:
                change_str = f"({icon}{clean_text})"
            return f"{now} {change_str}"

        kospi = parse_index("KOSPI_now", "KOSPI_change")
        kosdaq = parse_index("KOSDAQ_now", "KOSDAQ_change")
        return kospi, kosdaq
    except Exception as e:
        print(f"지수 가져오기 실패: {e}")
        return "N/A", "N/A"

def get_stock_price(code):
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    try:
        res = requests.get(url, headers=HEADERS)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 현재가
        price = soup.select_one(".no_today .blind").text.strip()
        
        # 전일대비
        exday_node = soup.select_one(".no_exday")
        if exday_node:
            ems = exday_node.select("em")
            if len(ems) >= 2:
                change_amt = ems[0].select_one(".blind").text.strip()
                change_pct = ems[1].select_one(".blind").text.strip()
                
                if "no_up" in ems[0].get("class", []):
                    icon = "🔺"
                    pct_prefix = "+"
                elif "no_down" in ems[0].get("class", []):
                    icon = "🔻"
                    pct_prefix = "-"
                else:
                    icon = "-"
                    pct_prefix = ""
                    
                return f"{price}원 ({icon}{change_amt}원, {pct_prefix}{change_pct}%)"
            
        return f"{price}원"
    except Exception as e:
        print(f"{code} 가격 가져오기 실패: {e}")
        return "N/A"

def get_top_trading():
    url = "https://finance.naver.com/sise/sise_quant.naver"
    top_stocks = []
    try:
        res = requests.get(url, headers=HEADERS)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # type_2 클래스를 가진 테이블의 tr 태그들을 가져옴
        rows = soup.select("table.type_2 tr")
        
        for row in rows:
            cols = row.select("td")
            # 데이터가 있는 행인지 확인 (순위, 종목명, 현재가 등)
            if len(cols) >= 3 and cols[0].text.strip().isdigit():
                name = cols[1].select_one("a").text.strip()
                price = cols[2].text.strip()
                top_stocks.append(f"{name} ({price}원)")
                
                if len(top_stocks) >= 5:
                    break
        return top_stocks
    except Exception as e:
        print(f"거래상위 종목 가져오기 실패: {e}")
        return []

def get_major_news():
    url = "https://finance.naver.com/news/mainnews.naver"
    news_list = []
    try:
        res = requests.get(url, headers=HEADERS)
        res.raise_for_status()
        
        # 인코딩 처리
        res.encoding = 'euc-kr' 
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 주요 뉴스 리스트
        articles = soup.select(".mainNewsList .articleSubject a")
        
        for a_tag in articles:
            title = a_tag.text.strip()
            link = a_tag.get('href')
            if title and link:
                if link.startswith('/'):
                    link = "https://finance.naver.com" + link
                news_list.append((title, link))
            
            if len(news_list) >= 5:
                break
        return news_list
    except Exception as e:
        print(f"뉴스 가져오기 실패: {e}")
        return []

def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("텔레그램 토큰 또는 Chat ID가 설정되지 않았습니다.")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        res = requests.post(url, json=payload)
        res.raise_for_status()
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 알림 전송 완료")
    except requests.exceptions.HTTPError as e:
        print(f"텔레그램 메시지 전송 실패 (HTTP 에러): {e}")
        if e.response is not None:
            print(f"상세 에러 내용: {e.response.text}")
    except Exception as e:
        print(f"텔레그램 메시지 전송 실패: {e}")

def job():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 데이터 수집 시작...")
    
    # 1. 지수
    kospi, kosdaq = get_market_index()
    
    # 2. 특정 종목
    stock_texts = []
    for name, code in STOCKS.items():
        price = get_stock_price(code)
        stock_texts.append(f"- {name}: {price}")
    
    # 3. 거래량 상위 5종목
    top_trading = get_top_trading()
    top_trading_text = "\n".join([f"{i+1}. {s}" for i, s in enumerate(top_trading)]) if top_trading else "데이터 없음"
    
    # 4. 주요 뉴스
    major_news = get_major_news()
    news_text = "\n".join([f"• <a href='{link}'>{html.escape(title)}</a>" for title, link in major_news]) if major_news else "데이터 없음"
    
    # 메시지 포맷팅
    message = f"""
<b>📈 실시간 증시 알림</b>

<b>[시장 지수]</b>
• KOSPI: {kospi}
• KOSDAQ: {kosdaq}

<b>[관심 종목]</b>
{chr(10).join(stock_texts)}

<b>[거래량 상위 5종목]</b>
{top_trading_text}

<b>[실시간 주요 뉴스]</b>
{news_text}
"""
    send_telegram_message(message.strip())

def main():
    print("주식 알림 봇을 시작합니다. (5분 주기)")
    # 시작 시 바로 1회 실행
    job()
    
    # 5분마다 실행 스케줄 등록
    schedule.every(5).minutes.do(job)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        job()
    else:
        main()
