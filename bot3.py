from telegram.ext import Application, ContextTypes
import ccxt
import pandas as pd
import os
from dotenv import load_dotenv
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID1=os.getenv("CHAT_ID1")
CHAT_ID2=os.getenv("CHAT_ID2")
exchange = ccxt.coinex({
    'enableRateLimit': True,
})

# 2. قائمة العملات المتابعة
symbols = ['TAI/USDT', 'ETHW/USDT', 'DARK/USDT','ACS/USDT','COOK/USDT',
           'JELLYJELLY/USDT','WING/USDT','LOOM/USDT','JST/USDT','HOUSE/USDT','SZN/USDT','FLM/USDT']

# 3. حساب الـ EMA (للحجم أو السعر)
def calculate_ema(data, window=10):
    series = pd.Series(data)
    return series.ewm(span=window, adjust=False).mean().iloc[-1]

# 4. التحقق من الشروط المطلوبة
def check_conditions(symbol):
    # جلب آخر 11 شمعة (لحساب الـ EMA 10 نحتاج إلى 10 بيانات سابقة + الشمعة الحالية)
    try:
        candles = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=21)
    except Exception as e:
        print(f"network error with {symbol}:{e}")
        return False
    
    if len(candles) < 21:
        return False  # لا توجد بيانات كافية
    
    # تفكيك البيانات
    opens = [candle[1] for candle in candles]
    closes = [candle[4] for candle in candles]
    volumes = [candle[5] for candle in candles]
    
    # الشمعة الأخيرة (التي نتحقق منها)
    last_open = opens[-1]
    last_close = closes[-1]
    last_volume = volumes[-1]
    
    # الشرط 1: لون الشمعة (أخضر أم أحمر)
    ticker = exchange.fetch_ticker(symbol)
    current_price = ticker['last']  
    is_green = current_price > last_open
    if not is_green:
        return False  # تستبعد إذا كانت حمراء
    
    # الشرط 2: حجم الشمعة الخضراء > EMA(10) للحجم
    ema_10_volume = calculate_ema(volumes[10:-1])  # نحسب الـ EMA على الـ 10 شموع السابقة (بدون الأخيرة)
    if last_volume<ema_10_volume:
        return False
    ema_20_close=calculate_ema(closes[:-1],window=20)
    return current_price>ema_20_close

async def send_auto_message(context: ContextTypes.DEFAULT_TYPE):
    try:
        eligible_coins = []
        for symbol in symbols:
            if check_conditions(symbol):
                eligible_coins.append(symbol)
                
        message=' '.join(eligible_coins) if eligible_coins else "no chances now..."
        message=message+"..from bot v3"
        await context.bot.send_message(
            chat_id=CHAT_ID1,
            text=message
        )
        await context.bot.send_message(
            chat_id=CHAT_ID2,
            text=message
        )
        print(message)
    except Exception as e:
        print(f"fail to send: {e}")
        

def main():
    # 1. تهيئة التطبيق مع JobQueue
    app = Application.builder() \
        .token(TOKEN) \
        .build()  # JobQueue يتم تهيئته تلقائياً مع [job-queue]
    
    # 2. جدولة المهمة (تأكد من وجود app.job_queue)
    if hasattr(app, 'job_queue') and app.job_queue:
        app.job_queue.run_repeating(
            callback=send_auto_message,
            interval=300,  # 5 دقائق
            first=10  # بدء بعد 10 ثواني
        )
    else:
        raise RuntimeError("JobQueue غير متوفر! تأكد من تثبيت [job-queue]")
    
    print("bot now running......")
    app.run_polling()

if __name__ == "__main__":
    main()