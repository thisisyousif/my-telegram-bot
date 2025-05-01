import re
from datetime import datetime
from telegram.ext import (
    Application,
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters
)
from telegram import Update, ReplyKeyboardMarkup
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
symbols = ['HOUSE/USDT', 'ALPACA/USDT', 'LOOKS/USDT','PASTERNAK/USDT','LLM/USDT',
           'OPCAT/USDT','BMT/USDT','WING/USDT','VINE/USDT','REZ/USDT','SAFE/USDT',
           'VVV/USDT','ATR/USDT','GFM/USDT','DRIFT/USDT']
now = datetime.now()
last_update = now.strftime("%Y-%m-%d %H:%M:%S")

ADD_MESSAGE, DELETE_MESSAGE = range(2)
main_keyboard = ReplyKeyboardMarkup(
    [["عرض الأزواج 📋", "إضافة زوج ➕"], ["حذف زوج ❌"]],
    resize_keyboard=True,
    input_field_placeholder="اختر خياراً..."
)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة أمر /start وعرض لوحة المفاتيح"""
    welcome_msg = """
    🏆 أهلاً بك في بوت إدارة العملات!
    
    يمكنك:
    - عرض قائمة العملات الحالية
    - إضافة عملة جديدة
    - حذف عملة موجودة
    """
    await update.message.reply_text(welcome_msg, reply_markup=main_keyboard)
async def display_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض جميع عناصر القائمة"""
    if not symbols:
        await update.message.reply_text("القائمة فارغة حالياً!")
        return
    
    formatted_list = "\n".join(f"{i+1}. {msg}" for i, msg in enumerate(symbols))
    await update.message.reply_text(f"📜 العملات الحالية:\n{formatted_list}")
async def add_message_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء عملية إضافة رسالة جديدة"""
    await update.message.reply_text(
        "✏️ الرجاء إدخال زوج العملات الجديد",
        reply_markup=ReplyKeyboardMarkup([["إلغاء ❌"]], resize_keyboard=True)
    )
    return ADD_MESSAGE
async def save_new_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حفظ الرسالة الجديدة في القائمة"""
    global last_update
    new_msg = update.message.text.strip().upper()
    if not re.match(r"^[A-Z]{3,10}/[A-Z]{3,10}$", new_msg):
        await update.message.reply_text(
            "⚠️ الصيغة غير صحيحة! مثال: BTC/USDT",
            reply_markup=main_keyboard
        )
        return ConversationHandler.END
    if new_msg in symbols:
        await update.message.reply_text(f"⚠️ الزوج {new_msg} موجود مسبقًا!", reply_markup=main_keyboard)
        return ConversationHandler.END
    try:
        ticker=exchange.fetch_ticker(new_msg)
        symbols.append(new_msg)
        now = datetime.now()
        last_update = now.strftime("%Y-%m-%d %H:%M:%S")
        await update.message.reply_text(f"✅ تمت إضافة العملة بنجاح!",reply_markup=main_keyboard)
    except ccxt.BadSymbol:  # إذا كان الزوج غير موجود
        await update.message.reply_text(f"⚠️ الزوج {new_msg} غير مدعوم!", reply_markup=main_keyboard)
    except Exception as e:
        await update.message.reply_text("❌ فشل الاتصال بالبورصة", reply_markup=main_keyboard)
    # عرض القائمة المحدثة
    await display_list(update, context)
    return ConversationHandler.END
async def delete_message_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء عملية حذف رسالة"""
    if not symbols:
        await update.message.reply_text("⚠️ القائمة فارغة لا يوجد ما يحذف!", reply_markup=main_keyboard)
        return ConversationHandler.END
    
    # عرض الرسائل المرقمة
    formatted_list = "\n".join(f"{i+1}. {msg}" for i, msg in enumerate(symbols))
    await update.message.reply_text(
        f"🔢 اختر رقم العملة للحذف:\n{formatted_list}",
        reply_markup=ReplyKeyboardMarkup([["إلغاء ❌"]], resize_keyboard=True)
    )
    return DELETE_MESSAGE
async def confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنفيذ عملية الحذف بناء على الرقم المدخل"""
    global last_update
    try:
        msg_num = int(update.message.text)
        if 1 <= msg_num <= len(symbols):
            deleted_msg = symbols.pop(msg_num-1)
            now = datetime.now()
            last_update = now.strftime("%Y-%m-%d %H:%M:%S")
            await update.message.reply_text(
                f"🗑️ تم حذف العملة:\n{deleted_msg}",
                reply_markup=main_keyboard
            )
            await display_list(update, context)
        else:
            await update.message.reply_text("⚠️ رقم غير صحيح!", reply_markup=main_keyboard)
    except ValueError:
        await update.message.reply_text("⚠️ الرجاء إدخال رقم فقط!", reply_markup=main_keyboard)
    
    return ConversationHandler.END
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء العملية الحالية"""
    await update.message.reply_text("تم الإلغاء", reply_markup=main_keyboard)
    return ConversationHandler.END
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
        message=message+"... (RW.) LU: "+last_update
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
    # معالج المحادثة للإضافة والحذف
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^إضافة زوج ➕$"), add_message_btn),
            MessageHandler(filters.Regex("^حذف زوج ❌$"), delete_message_btn),
        ],
        states={
            ADD_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^إلغاء ❌$"), save_new_message)],
            DELETE_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^إلغاء ❌$"), confirm_delete)],
        },
        fallbacks=[MessageHandler(filters.Regex("^إلغاء ❌$"), cancel)],
    )
    
    # تسجيل المعالجات
    app.add_handler(CommandHandler("cms", start))
    app.add_handler(MessageHandler(filters.Regex("^عرض الأزواج 📋$"), display_list))
    app.add_handler(conv_handler)
    print("bot now running......")
    app.run_polling()

if __name__ == "__main__":
    main()