# main.py

from flask import Flask, request
import requests
import os
import asyncio
import edge_tts
import speech_recognition as sr
import pandas as pd
import yfinance as yf
from difflib import get_close_matches
import subprocess

app = Flask(__name__)

# הגדרות ימות המשיח
USERNAME = "0733181201"
PASSWORD = "6714453"
TOKEN = f"{USERNAME}:{PASSWORD}"

# טוען את רשימת המניות מקובץ CSV
stock_dict = dict()
if os.path.exists("hebrew_stocks.csv"):
    df = pd.read_csv("hebrew_stocks.csv")
    stock_dict = dict(zip(df['hebrew_name'], zip(df['ticker'], df['type'])))

@app.route("/api-handler", methods=["GET"])
def handle_api():
    wav_path = request.args.get("stockname")
    phone = request.args.get("ApiPhone")

    if not wav_path:
        return "no recording"

    print(f"📥 קיבלנו בקשה ממשתמש: {phone}")
    os.makedirs("recordings", exist_ok=True)

    # הורדת קובץ ההקלטה מימות
    response = requests.get("https://www.call2all.co.il/ym/api/DownloadFile", params={
        "token": TOKEN,
        "path": wav_path
    })

    input_path = "recordings/input.wav"
    with open(input_path, "wb") as f:
        f.write(response.content)

    # תמלול קולי
    r = sr.Recognizer()
    with sr.AudioFile(input_path) as source:
        audio = r.record(source)

    try:
        recognized = r.recognize_google(audio, language="he-IL")
        print(f"🗣️ זיהוי דיבור: {recognized}")
    except:
        recognized = ""
        print("❌ לא זוהה דיבור ברור")

    # חיפוש מניה
    best_match = get_best_match(recognized)
    if best_match:
        ticker, stock_type = stock_dict[best_match]
        data = get_stock_data(ticker)
        if data:
            text = format_text(best_match, ticker, data, stock_type)
        else:
            text = f"לא נמצאו נתונים עבור {best_match}"
    else:
        text = "לא זוהה נייר ערך תואם"

    # יצירת קובץ שמע על פי 5 ספרות אחרונות של המספר
    output_name = phone[-5:] + ".wav"
    result_path = f"output/{output_name}"
    os.makedirs("output", exist_ok=True)
    asyncio.run(create_audio(text, "temp.mp3"))
    convert_mp3_to_wav("temp.mp3", result_path)

    print(f"🎧 קובץ מוכן: {result_path}")
    return phone[-5:]  # זה השם שיושמע למאזין (ימות ישמיע output/xxxxx.wav)

# פונקציה לחיפוש שם מניה בהתאמה קרובה
def get_best_match(query):
    matches = get_close_matches(query, stock_dict.keys(), n=1, cutoff=0.6)
    return matches[0] if matches else None

# שליפת נתוני מניה מ־Yahoo Finance
def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        if hist.empty or len(hist) < 2:
            return None
        current = hist['Close'].iloc[-1]
        day = hist['Close'].iloc[-2]
        week = hist['Close'].iloc[-6] if len(hist) > 6 else day
        three_months = hist['Close'].iloc[-66] if len(hist) > 66 else day
        year = hist['Close'].iloc[0]
        max_price = hist['Close'].max()
        return {
            'current': round(current, 2),
            'day': round((current - day) / day * 100, 2),
            'week': round((current - week) / week * 100, 2),
            '3mo': round((current - three_months) / three_months * 100, 2),
            'year': round((current - year) / year * 100, 2),
            'from_high': round((current - max_price) / max_price * 100, 2)
        }
    except:
        return None

# יצירת טקסט להקראה
def format_text(name, ticker, data, stock_type):
    currency = "שקלים" if ticker.endswith(".TA") else "דולר"
    if stock_type == "מניה":
        return f"נמצאה מניה בשם {name}. שווי נוכחי {data['current']} {currency}. שינוי יומי: {abs(data['day'])} אחוז {'עלייה' if data['day'] > 0 else 'ירידה'}."
    elif stock_type == "מדד":
        return f"נמצא מדד בשם {name}. ערך נוכחי {data['current']}. שינוי יומי: {abs(data['day'])} אחוז {'עלייה' if data['day'] > 0 else 'ירידה'}."
    elif stock_type == "קריפטו":
        return f"נמצא מטבע {name}. ערך נוכחי {data['current']} דולר. שינוי יומי: {abs(data['day'])} אחוז {'עלייה' if data['day'] > 0 else 'ירידה'}."
    return f"{name}, {data['current']} {currency}"

# יצירת קובץ MP3 עם edge-tts
async def create_audio(text, filename):
    tts = edge_tts.Communicate(text, voice="he-IL-AvriNeural")
    await tts.save(filename)

# המרת MP3 ל־WAV שמתאים לימות
def convert_mp3_to_wav(mp3_file, wav_file):
    subprocess.run([
        "ffmpeg", "-y",
        "-i", mp3_file,
        "-ar", "8000",
        "-ac", "1",
        "-acodec", "pcm_s16le",
        wav_file
    ])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
