# main.py

from flask import Flask, request
import requests
import os
import subprocess
import speech_recognition as sr
import yfinance as yf
import asyncio
from edge_tts import Communicate

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
    print(f"\U0001F4E5 קיבלנו בקשה ממשתמש: {phone}")

    if not wav_path or not phone:
        return "בעיה זמנית"

    # יצירת תיקיות
    os.makedirs("recordings", exist_ok=True)
    os.makedirs("output", exist_ok=True)

    last_digits = phone[-5:]
    raw_path = f"recordings/{last_digits}.raw"
    fixed_path = f"recordings/{last_digits}_fixed.wav"
    result_path = f"output/{last_digits}.wav"

    # הורדת ההקלטה
    response = requests.get("https://www.call2all.co.il/ym/api/DownloadFile", params={
        "token": TOKEN,
        "path": f"ivr2:{wav_path}"
    })

    if response.status_code != 200:
        print("❌ שגיאה בהורדת ההקלטה מימות")
        return "בעיה זמנית"

    with open(raw_path, "wb") as f:
        f.write(response.content)

    # המרה לפורמט תקני
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
    except Exception as e:
        print("⚠️ שגיאה בזיהוי דיבור:", e)
        return "בעיה זמנית"

    print(f"🔎 זוהה טקסט: {text}")

    # חיפוש מניה
    try:
        search = yf.Ticker(text)
        info = search.info
        price = info.get("regularMarketPrice")
        if not price:
            raise Exception("אין מחיר")
        message = f"מניית {info.get('shortName', text)} נסחרת במחיר של {price} דולר"
    except Exception as e:
        print("⚠️ שגיאה בשליפת מידע מהמניה:", e)
        message = "לא נמצאו נתונים על המניה"

    # יצירת קובץ שמע
    try:
        tts = Communicate(text=message, voice="he-IL-HilaNeural")
        asyncio.run(tts.save(result_path))
        print(f"✅ נוצר קובץ שמע: {result_path}")
    except Exception as e:
        print("❌ שגיאה ביצירת קובץ שמע:", e)
        return "בעיה זמנית"

    # העלאה לימות
    try:
        with open(result_path, 'rb') as f:
            upload_response = requests.post("https://www.call2all.co.il/ym/api/UploadFile", files={
                "file": (f"{last_digits}.wav", f)
            }, data={
                "token": TOKEN,
                "path": f"ivr2:/9/{last_digits}.wav"
            })

        if upload_response.status_code == 200 and "ok" in upload_response.text.lower():
            print(f"📤 קובץ {last_digits}.wav הועלה לימות המשיח")
            return last_digits
        else:
            print("❌ שגיאה בהעלאה לימות:", upload_response.text)
            return "בעיה זמנית"
    except Exception as e:
        print("❌ שגיאה כללית בהעלאה לימות:", e)
        return "בעיה זמנית"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
