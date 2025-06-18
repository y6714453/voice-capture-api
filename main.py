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
    df = pd.read_csv(path)
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
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        if hist.empty or len(hist) < 2:
            return None
        current = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[-2]
        change_day = round((current - prev) / prev * 100, 2)
        return {
            'current': round(current, 2),
            'day': change_day
        }
    except:
        return None

def safe_text(text):
    return text.replace("&", " ו").replace('"', "").replace("'", "")

def format_short_text(stock_info, data):
    name = stock_info['display_name']
    typ = stock_info['type']
    current = data['current']
    change = data['day']
    direction = "עלייה" if change > 0 else "ירידה"
    change = abs(change)

    if "מדד" in typ:
        text = f"נמצא מדד בשם {name}. המדד עומד על {current} נקודות. מתחילת היום נרשמה {direction} של {change} אחוז."
    elif "מניה" in typ:
        text = f"נמצאה מניה בשם {name}. המניה שווה {current} דולר. מתחילת היום נרשמה {direction} של {change} אחוז."
    elif "קריפטו" in typ:
        text = f"נמצא מטבע בשם {name}. שווי המטבע {current} דולר. מתחילת היום נרשמה {direction} של {change} אחוז."
    else:
        text = f"נמצא נייר ערך בשם {name}. השווי הוא {current}. נרשמה {direction} של {change} אחוז."

    print("📢 תגובת טקסט לימות:")
    print(text)
    return safe_text(text)

@app.route("/api-handler", methods=["GET"])
def handle_api():
    print("\n📞 התקבלה בקשת API מימות")
    path = request.args.get("stockname")
    if not path:
        print("❌ stockname חסר")
        return "לא התקבל קובץ מהמערכת"

    print(f"📁 הקובץ שהתקבל: {path}")

    url = "https://www.call2all.co.il/ym/api/DownloadFile"
    params = {"token": TOKEN, "path": f"ivr2:{path}"}
    r = requests.get(url, params=params)

    if r.status_code != 200:
        print("❌ שגיאה בהורדת הקובץ")
        return "לא התקבלה הקלטה תקינה"

    with open("temp.wav", "wb") as f:
        f.write(r.content)
    print("✅ נשמר קובץ temp.wav")

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
        return "לא נמצאו נתונים למדד"

    return format_short_text(stock_info, data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
