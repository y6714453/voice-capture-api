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
    wav_path = request.args.get("stockname")
    phone = request.args.get("ApiPhone")
    print(f"📥 קיבלנו בקשה ממשתמש: {phone}")

    if not wav_path or not phone:
        print("❌ חסר stockname או ApiPhone בבקשה")
        return "בעיה זמנית"

    # יצירת תיקיות
    os.makedirs("recordings", exist_ok=True)
    os.makedirs("output", exist_ok=True)

    # שם קובץ ייחודי לפי חמש ספרות אחרונות
    last_digits = phone[-5:]
    raw_path = f"recordings/{last_digits}.raw"
    fixed_path = f"recordings/{last_digits}_fixed.wav"
    result_path = f"output/{last_digits}.wav"

    # הורדת הקובץ מימות
    try:
        response = requests.get("https://www.call2all.co.il/ym/api/DownloadFile", params={
            "token": TOKEN,
            "path": wav_path
        })
        if response.status_code != 200:
            print("❌ שגיאה בהורדת ההקלטה מימות")
            return "בעיה זמנית"

        with open(raw_path, "wb") as f:
            f.write(response.content)
        print(f"✅ נשמר הקובץ הגולמי: {raw_path}")
    except Exception as e:
        print(f"❌ שגיאה בהורדה: {e}")
        return "בעיה זמנית"

    # המרה ל-wav
    try:
        result = subprocess.run([
            "./bin/ffmpeg", "-y",
            "-i", raw_path,
            "-ar", "16000",
            "-ac", "1",
            "-acodec", "pcm_s16le",
            fixed_path
        ], capture_output=True)

        print("🛠️ FFmpeg Output:")
        print(result.stdout.decode())
        print(result.stderr.decode())

        if not os.path.exists(fixed_path):
            print("❌ קובץ WAV לא נוצר")
            return "בעיה זמנית"
        else:
            print(f"✅ נוצר קובץ WAV תקני: {fixed_path}")
    except Exception as e:
        print(f"❌ שגיאה בהמרת ffmpeg: {e}")
        return "בעיה זמנית"

    # זיהוי דיבור
    try:
        recognizer = sr.Recognizer()
        with sr.AudioFile(fixed_path) as source:
            audio = recognizer.record(source)
            text = recognizer.recognize_google(audio, language="he-IL")
        print(f"🔎 זוהה טקסט: {text}")
    except Exception as e:
        print(f"❌ שגיאה בזיהוי קולי: {e}")
        return "בעיה זמנית"

    # חיפוש מניה
    try:
        search = yf.Ticker(text)
        info = search.info
        price = info.get("regularMarketPrice")
        if not price:
            raise Exception("אין נתונים")

        message = f"מניית {info.get('shortName', text)} נסחרת במחיר של {price} דולר"
    except Exception as e:
        print(f"⚠️ לא נמצאו נתונים: {e}")
        message = "לא נמצאו נתונים על המניה"

    # יצירת קובץ שמע
    try:
        tts = Communicate(text=message, voice="he-IL-HilaNeural")
        asyncio.run(tts.save(result_path))
        print(f"📤 נוצר קובץ שמע: {result_path}")
        return last_digits
    except Exception as e:
        print(f"❌ שגיאה בהקראת טקסט: {e}")
        return "בעיה זמנית"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
