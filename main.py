from flask import Flask, request
import requests
import os
import speech_recognition as sr
import pandas as pd
import yfinance as yf
from difflib import get_close_matches
import re

app = Flask(__name__)

# הגדרת טוקן לימות המשיח
USERNAME = "0733181201"
PASSWORD = "6714453"
TOKEN = f"{USERNAME}:{PASSWORD}"

# טוען את הרשימה מהמילון
def normalize(text):
    return re.sub(r'[^א-תa-zA-Z0-9 ]', '', text).lower().strip()

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
    return matches[0] if matches else None

def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        if hist.empty or len(hist) < 2:
            return None
        current = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[-2]
        week = hist['Close'].iloc[-6] if len(hist) > 6 else prev
        mo3 = hist['Close'].iloc[-66] if len(hist) > 66 else prev
        year = hist['Close'].iloc[0]
        high = hist['Close'].max()
        return {
            'current': round(current, 2),
            'day': round((current - prev) / prev * 100, 2),
            'week': round((current - week) / week * 100, 2),
            'mo3': round((current - mo3) / mo3 * 100, 2),
            'year': round((current - year) / year * 100, 2),
            'from_high': round((current - high) / high * 100, 2)
        }
    except:
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

    if "מניה" in typ:
        return f"נמצאה מניה בשם {name}. נסחרת בשווי של {data['current']} {currency}. {d} {w} {m} {y} {h}"
    elif "מדד" in typ:
        return f"נמצא מדד בשם {name}. עומד על {data['current']} נקודות. {d} {w} {m} {y} {h}"
    elif "קריפטו" in typ:
        return f"נמצא מטבע בשם {name}. שווי נוכחי של {data['current']} דולר. {d} {w} {m} {y} {h}"
    return f"נמצא נייר ערך בשם {name}. מחיר נוכחי: {data['current']} {currency}."

@app.route("/api-handler", methods=["POST"])
def handle_api():
    # שליפת ההקלטה מימות
    path = request.args.get("stockname")
    if not path:
        return "לא נשלח קובץ תקין"

    url = "https://www.call2all.co.il/ym/api/DownloadFile"
    params = {
        "token": TOKEN,
        "path": f"ivr2:{path}"
    }

    r = requests.get(url, params=params)
    if r.status_code != 200:
        return "הקובץ לא התקבל"

    with open("temp.wav", "wb") as f:
        f.write(r.content)

    # תמלול
    try:
        r = sr.Recognizer()
        with sr.AudioFile("temp.wav") as source:
            audio = r.record(source)
        text = r.recognize_google(audio, language="he-IL")
    except:
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
