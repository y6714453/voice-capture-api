# main.py – קובץ מרכזי עם טיפול בהקלטות מימות המשיח והחזרת קובץ שמע

from flask import Flask, request
import requests
import os
import time
import subprocess
import speech_recognition as sr
import edge_tts
from requests_toolbelt.multipart.encoder import MultipartEncoder

app = Flask(__name__)

USERNAME = "0733181201"
PASSWORD = "6714453"
TOKEN = f"{USERNAME}:{PASSWORD}"

@app.route("/api-handler", methods=["GET", "POST"])
def handle_api():
    # שליפת נתיב ההקלטה והטלפון מהפרמטרים
    wav_path = request.args.get("stockname") or request.args.get("recording")
    phone = request.args.get("ApiPhone") or "unknown"
    print(f"\U0001F4E5 קיבלנו בקשה ממשתמש: {phone}")

    if not wav_path:
        return "no recording"

    # השהיה קלה כדי לוודא שהקובץ נשמר לפני שנוריד אותו
    time.sleep(2)

    os.makedirs("recordings", exist_ok=True)
    response = requests.get("https://www.call2all.co.il/ym/api/DownloadFile", params={
        "token": TOKEN,
        "path": wav_path
    })

    file_name = wav_path.split("/")[-1]
    input_path = os.path.join("recordings", file_name)

    with open(input_path, "wb") as f:
        f.write(response.content)

    if os.path.getsize(input_path) == 0:
        print("⚠️ הקובץ שהתקבל ריק")
        return "EMPTY_FILE"

    # המרת הקלטה לקובץ wav תקני
    converted_path = os.path.join("recordings", f"converted_{file_name}")
    subprocess.run(["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1", converted_path])

    # זיהוי דיבור
    r = sr.Recognizer()
    try:
        with sr.AudioFile(converted_path) as source:
            audio = r.record(source)
            text = r.recognize_google(audio, language="he-IL")
            print(f"\U0001F5E3️ זוהה טקסט: {text}")
    except Exception as e:
        print("❌ שגיאה בזיהוי דיבור:", e)
        return "RECOGNITION_ERROR"

    # יצירת תשובה קולית
    result_path = os.path.join("recordings", f"{phone[-5:]}.mp3")
    result_wav = os.path.join("recordings", f"{phone[-5:]}.wav")
    tts = edge_tts.Communicate(f"קיבלתם תוצאה עבור {text}", voice="he-IL-AvriNeural")
    await tts.save(result_path)
    subprocess.run(["ffmpeg", "-y", "-i", result_path, "-ar", "8000", "-ac", "1", result_wav])

    print(f"\U0001F3A4 נוצר קובץ השמעה: {result_wav}")
    return phone[-5:]  # כך ימות ישמיע את הקובץ בשם הזה

if __name__ == "__main__":
    import asyncio
    asyncio.run(app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000))))
