# main.py

from flask import Flask, request
import requests
import os
import subprocess
import speech_recognition as sr
import yfinance as yf
import time
from edge_tts import Communicate
from pydub import AudioSegment

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

    if not wav_path:
        return "ERROR"

    # יצירת תיקיות אם לא קיימות
    os.makedirs("recordings", exist_ok=True)
    os.makedirs("output", exist_ok=True)

    # שם הקובץ לפי חמש ספרות אחרונות
    last_digits = phone[-5:]
    raw_path = f"recordings/{last_digits}.raw"
    fixed_path = f"recordings/{last_digits}_fixed.wav"
    result_path = f"output/{last_digits}.wav"

    # הורדת ההקלטה מימות
    response = requests.get("https://www.call2all.co.il/ym/api/DownloadFile", params={
        "token": TOKEN,
        "path": wav_path
    })

    if response.status_code != 200:
        return "ERROR"

    with open(raw_path, "wb") as f:
        f.write(response.content)

    # המרת ההקלטה לפורמט קריא
    subprocess.run([
        "ffmpeg", "-y",
        "-i", raw_path,
        "-ar", "16000",
        "-ac", "1",
        "-acodec", "pcm_s16le",
        fixed_path
    ])

    # זיהוי דיבור
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(fixed_path) as source:
            audio = recognizer.record(source)
            text = recognizer.recognize_google(audio, language="he-IL")
    except:
        return "בעיה זמנית"

    print(f"🔎 זוהה טקסט: {text}")

    # חיפוש מניה
    try:
        search = yf.Ticker(text)
        info = search.info
        price = info.get("regularMarketPrice")
        if not price:
            raise Exception("אין נתונים")

        message = f"מניית {info.get('shortName', text)} נסחרת במחיר של {price} דולר"
    except:
        message = "לא נמצאו נתונים על המניה"

    # המרת טקסט לדיבור ושמירה לקובץ
    try:
        tts = Communicate(text=message, voice="he-IL-HilaNeural")
        import asyncio
        asyncio.run(tts.save(result_path))
        return last_digits
    except:
        return "בעיה זמנית"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
