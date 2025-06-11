from flask import Flask, request
import requests
import os
import subprocess
import speech_recognition as sr
import yfinance as yf

app = Flask(__name__)

# פרטי גישה לימות המשיח
USERNAME = "0733181201"
PASSWORD = "6714453"
TOKEN = f"{USERNAME}:{PASSWORD}"

@app.route("/api-handler", methods=["POST"])
def handle_api():
    # שליפת פרמטרים
    wav_path = request.args.get("stockname")
    phone = request.args.get("ApiPhone")
    print(f"📥 בקשה ממשתמש: {phone}")

    if not wav_path or not phone:
        return "בעיה זמנית"

    # יצירת תיקיות
    os.makedirs("recordings", exist_ok=True)

    last_digits = phone[-5:]
    raw_path = f"recordings/{last_digits}.raw"
    fixed_path = f"recordings/{last_digits}_fixed.wav"

    # הורדת ההקלטה
    response = requests.get("https://www.call2all.co.il/ym/api/DownloadFile", params={
        "token": TOKEN,
        "path": f"ivr2:{wav_path}"
    })

    if response.status_code != 200:
        print("❌ שגיאה בהורדת ההקלטה")
        return "בעיה זמנית"

    with open(raw_path, "wb") as f:
        f.write(response.content)

    # המרה לפורמט תקני WAV
    subprocess.run([
        "ffmpeg", "-y",
        "-i", raw_path,
        "-ar", "16000",
        "-ac", "1",
        "-acodec", "pcm_s16le",
        fixed_path
    ])

    # תמלול דיבור
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(fixed_path) as source:
            audio = recognizer.record(source)
            text = recognizer.recognize_google(audio, language="he-IL")
    except Exception as e:
        print("⚠️ שגיאת תמלול:", e)
        return "001"  # תשובה שתגרום לימות להשמיע 001.wav

    print(f"🔎 זוהה טקסט: {text}")

    # חיפוש מניה
    try:
        stock = yf.Ticker(text)
        info = stock.info
        price = info.get("regularMarketPrice")
        if not price:
            raise Exception("אין מחיר")
        name = info.get("shortName", text)
        return "001"  # תשובה שמובילה להשמעת 001.wav
    except Exception as e:
        print("⚠️ שגיאה בחיפוש מניה:", e)
        return "001"  # גם בשגיאה נשמיע את אותו קובץ

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
