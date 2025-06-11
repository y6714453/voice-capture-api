# main.py

from flask import Flask, request
import requests
import os
import subprocess
import speech_recognition as sr
import yfinance as yf
import time
from edge_tts import Communicate
import asyncio

app = Flask(__name__)

# פרטי גישה לימות המשיח
USERNAME = "0733181201"
PASSWORD = "6714453"
TOKEN = f"{USERNAME}:{PASSWORD}"

@app.route("/api-handler", methods=["GET"])
def handle_api():
    # קבלת פרטי הבקשה
    wav_path = request.args.get("stockname")  # לדוגמה: /9/006.wav
    phone = request.args.get("ApiPhone")
    print(f"📥 קיבלנו בקשה ממשתמש: {phone}")

    if not wav_path or not phone:
        print("❌ חסר פרמטר stockname או ApiPhone")
        return "בעיה זמנית"

    # יצירת נתיב מלא לקובץ בי־ימות
    full_path = "ivr2:" + wav_path

    # יצירת תיקיות אם לא קיימות
    os.makedirs("recordings", exist_ok=True)
    os.makedirs("output", exist_ok=True)

    # שמות קבצים לפי חמש ספרות אחרונות
    last_digits = phone[-5:]
    raw_path = f"recordings/{last_digits}.raw"
    fixed_path = f"recordings/{last_digits}_fixed.wav"
    result_path = f"output/{last_digits}.wav"

    # הורדת הקלטה
    response = requests.get("https://www.call2all.co.il/ym/api/DownloadFile", params={
        "token": TOKEN,
        "path": full_path
    })

    if response.status_code != 200 or not response.content:
        print("❌ שגיאה בהורדת ההקלטה מימות")
        return "בעיה זמנית"

    with open(raw_path, "wb") as f:
        f.write(response.content)

    # המרה ל-WAV תקני
    subprocess.run([
        "ffmpeg", "-y",
        "-i", raw_path,
        "-ar", "16000",
        "-ac", "1",
        "-acodec", "pcm_s16le",
        fixed_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # זיהוי דיבור
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(fixed_path) as source:
            audio = recognizer.record(source)
            text = recognizer.recognize_google(audio, language="he-IL")
            print(f"🔎 זוהה טקסט: {text}")
    except Exception as e:
        print(f"❌ שגיאה בזיהוי דיבור: {e}")
        return "בעיה זמנית"

    # חיפוש מניה
    try:
        ticker = yf.Ticker(text)
        info = ticker.info
        price = info.get("regularMarketPrice")
        if not price:
            raise Exception("אין מחיר")

        name = info.get("shortName", text)
        message = f"מניית {name} נסחרת במחיר של {price} דולר"
    except Exception as e:
        print(f"⚠️ שגיאה בשליפת מידע מהמניה: {e}")
        message = "לא נמצאו נתונים על המניה"

    # יצירת קובץ שמע
    try:
        tts = Communicate(text=message, voice="he-IL-HilaNeural")
        asyncio.run(tts.save(result_path))
        print(f"✅ נוצר קובץ שמע: {result_path}")
        return last_digits  # המערכת תנגן אותו לפי שם הקובץ
    except Exception as e:
        print(f"❌ שגיאה ביצירת קובץ שמע: {e}")
        return "בעיה זמנית"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
