from flask import Flask, request
import requests
import os
import speech_recognition as sr
import pandas as pd
import yfinance as yf
from difflib import get_close_matches
import re

app = Flask(__name__)

USERNAME = "0733181201"
PASSWORD = "6714453"
TOKEN = f"{USERNAME}:{PASSWORD}"

def normalize(text):
    return re.sub(r'[^א-תa-zA-Z0-9]', '', text).lower()

def load_stock_list(path="hebrew_stocks.csv"):
    print("📄 טוען קובץ hebrew_stocks.csv...")
    df = pd.read_csv(path)
    print(f"✅ נטענו {len(df)} שורות מהמילון")
    return {
        normalize(row['hebrew_name']): {
            'display_name': row['display_name'],
            'ticker': row['ticker'],
            'type': row['type']
        }
        for _, row in df.iterrows()
    }

stock_dict = load_stock_list()

def get_best_match(query, stock_dict):
    norm_query = normalize(query)
    matches = get_close_matches(norm_query, stock_dict.keys(), n=1, cutoff=0.6)
    if matches:
        print(f"🎯 זוהתה התאמה: {matches[0]}")
    else:
        print("❌ לא נמצאה התאמה לשם שנאמר")
    return matches[0] if matches else None

def get_stock_data(ticker):
    print(f"📊 טוען נתונים עבור הסימבול: {ticker}")
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        if hist.empty or len(hist) < 2:
            print("⚠️ לא מספיק נתונים היסטוריים")
            return None
        current = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[-2]
        week = hist['Close'].iloc[-6] if len(hist) > 6 else prev
        mo3 = hist['Close'].iloc[-66] if len(hist) > 66 else prev
        year = hist['Close'].iloc[0]
        high = hist['Close'].max()
        print("✅ נתונים היסטוריים נשלפו בהצלחה")
        return {
            'current': round(current, 2),
            'day': round((current - prev) / prev * 100, 2),
            'week': round((current - week) / week * 100, 2),
            'mo3': round((current - mo3) / mo3 * 100, 2),
            'year': round((current - year) / year * 100, 2),
            'from_high': round((current - high) / high * 100, 2)
        }
    except Exception as e:
        print(f"❌ שגיאה בשליפת נתונים: {e}")
        return None

def format_text(stock_info, data):
    name = stock_info['display_name']
    ticker = stock_info['ticker']
    typ = stock_info['type']
    currency = "שקלים" if ticker.endswith(".TA") else "דולר"

    d = f"מתחילת היום נרשמה {'עלייה' if data['day'] > 0 else 'ירידה'} של {abs(data['day'])} אחוז."
    w = f"מתחילת השבוע נרשמה {'עלייה' if data['week'] > 0 else 'ירידה'} של {abs(data['week'])} אחוז."
    m = f"בשלושת החודשים האחרונים נרשמה {'עלייה' if data['mo3'] > 0 else 'ירידה'} של {abs(data['mo3'])} אחוז."
    y = f"מתחילת השנה נרשמה {'עלייה' if data['year'] > 0 else 'ירידה'} של {abs(data['year'])} אחוז."
    h = f"המחיר הנוכחי רחוק מהשיא ב־{abs(data['from_high'])} אחוז."

    text = f"{name}. {d} {w} {m} {y} {h}"
    print("📢 טקסט מוכן להקראה:")
    print(text)
    return text

@app.route("/api-handler", methods=["GET"])
def handle_api():
    print("\n📞 התקבלה בקשת API מימות")
    path = request.args.get("stockname")
    if not path:
        print("❌ לא נשלח stockname מהבקשה")
        return "לא התקבל נתיב הקלטה"

    print(f"📁 נתיב הקלטה שהתקבל: {path}")

    url = "https://www.call2all.co.il/ym/api/DownloadFile"
    params = {"token": TOKEN, "path": f"ivr2:{path}"}
    r = requests.get(url, params=params)

    if r.status_code != 200:
        print("❌ שגיאה בהורדת הקובץ מימות")
        return "שגיאה בהורדת הקובץ"

    with open("temp.wav", "wb") as f:
        f.write(r.content)
    print("✅ הקובץ נשמר בהצלחה כ־temp.wav")

    try:
        recognizer = sr.Recognizer()
        with sr.AudioFile("temp.wav") as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio, language="he-IL")
        print(f"🗣️ זיהוי דיבור: {text}")
    except Exception as e:
        print(f"❌ שגיאת תמלול: {e}")
        return "לא זוהה דיבור ברור"

    match = get_best_match(text, stock_dict)
    if not match:
        return "לא זוהתה מניה מתאימה"

    stock_info = stock_dict[match]
    data = get_stock_data(stock_info['ticker'])
    if not data:
        return "לא נמצאו נתונים עדכניים"

    return format_text(stock_info, data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
