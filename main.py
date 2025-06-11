# ייבוא ספריות נדרשות
from flask import Flask, request
import requests
import os
import edge_tts
import subprocess
import speech_recognition as sr
import pandas as pd
import yfinance as yf
from difflib import get_close_matches
from requests_toolbelt.multipart.encoder import MultipartEncoder

# יצירת האפליקציה בפלאסק
app = Flask(__name__)

# נתוני התחברות לימות המשיח
USERNAME = "0733181201"
PASSWORD = "6714453"
TOKEN = f"{USERNAME}:{PASSWORD}"

# טוען את רשימת המניות מתוך קובץ CSV
def load_stock_list(csv_path):
    df = pd.read_csv(csv_path)
    return dict(zip(df['hebrew_name'], zip(df['ticker'], df['type'])))

# מחפש התאמה קרובה לשם המניה מתוך הטקסט המוקלט
def get_best_match(query, stock_dict):
    matches = get_close_matches(query, stock_dict.keys(), n=1, cutoff=0.6)
    return matches[0] if matches else None

# שליפת נתוני מניה/מדד/מטבע מ־Yahoo Finance
def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        if hist.empty or len(hist) < 2:
            return None
        current_price = hist['Close'].iloc[-1]
        price_day = hist['Close'].iloc[-2]
        price_3mo = hist['Close'].iloc[-66] if len(hist) > 66 else price_day
        max_price = hist['Close'].max()
        return {
            'current': round(current_price, 2),
            'day': round((current_price - price_day) / price_day * 100, 2),
            '3mo': round((current_price - price_3mo) / price_3mo * 100, 2),
            'from_high': round((current_price - max_price) / max_price * 100, 2)
        }
    except:
        return None

# בניית טקסט קול עבור ההודעה למאזין
def format_text(name, ticker, data, stock_type):
    currency = "שקלים" if ticker.endswith(".TA") else "דולר"
    if stock_type == "מניה":
        return (
            f"נמצאה מניה בשם {name}. המניה נסחרת בשווי של {data['current']} {currency}. "
            f"מתחילת היום נרשמה {'עלייה' if data['day'] > 0 else 'ירידה'} של {abs(data['day'])} אחוז. "
            f"בשלושת החודשים האחרונים {'עלייה' if data['3mo'] > 0 else 'ירידה'} של {abs(data['3mo'])} אחוז. "
            f"המחיר הנוכחי רחוק מהשיא ב־{abs(data['from_high'])} אחוז."
        )
    elif stock_type == "מדד":
        return (
            f"נמצא מדד בשם {name}. המדד עומד כעת על {data['current']} נקודות. "
            f"מתחילת היום {'עלייה' if data['day'] > 0 else 'ירידה'} של {abs(data['day'])} אחוז. "
            f"בשלושת החודשים האחרונים {'עלייה' if data['3mo'] > 0 else 'ירידה'} של {abs(data['3mo'])} אחוז. "
            f"המדד רחוק מהשיא ב־{abs(data['from_high'])} אחוז."
        )
    elif stock_type == "מטבע":
        return (
            f"נמצא מטבע בשם {name}. המטבע שווה כעת {data['current']} דולר. "
            f"מתחילת היום {'עלייה' if data['day'] > 0 else 'ירידה'} של {abs(data['day'])} אחוז. "
            f"בשלושת החודשים האחרונים {'עלייה' if data['3mo'] > 0 else 'ירידה'} של {abs(data['3mo'])} אחוז. "
            f"המרחק מהשיא הוא {abs(data['from_high'])} אחוז."
        )
    else:
        return f"נמצא נייר ערך בשם {name}. המחיר הנוכחי הוא {data['current']} {currency}."

# פונקציה ליצירת קובץ MP3 מהטקסט
async def create_audio(text, filename="output.mp3"):
    communicate = edge_tts.Communicate(text, voice="he-IL-AvriNeural")
    await communicate.save(filename)

# המרת MP3 ל־WAV בפורמט תואם לימות
def convert_mp3_to_wav(mp3_file, wav_file):
    subprocess.run(["ffmpeg", "-y", "-i", mp3_file, "-ar", "8000", "-ac", "1", "-acodec", "pcm_s16le", wav_file])

# העלאת קובץ לימות לשלוחה מסוימת
def upload_to_yemot(local_file, remote_path):
    url = "https://www.call2all.co.il/ym/api/UploadFile"
    m = MultipartEncoder(
        fields={"token": TOKEN, "path": remote_path, "upload": (os.path.basename(local_file), open(local_file, 'rb'), 'audio/wav')}
    )
    requests.post(url, data=m, headers={'Content-Type': m.content_type})

# תמלול הקלטת אודיו
def transcribe_audio(filepath):
    r = sr.Recognizer()
    with sr.AudioFile(filepath) as source:
        audio = r.record(source)
    try:
        return r.recognize_google(audio, language="he-IL")
    except:
        return ""

# נקודת הכניסה של ימות - כאן ההקלטה מגיעה ונשלחת לעיבוד
@app.route("/api-handler", methods=["GET", "POST"])
def handle_api():
    # קבלת פרטים מהבקשה
    wav_path = request.args.get("stockname")
    phone = request.args.get("ApiPhone")

    if not wav_path or not phone:
        return "ERROR"

    # הורדת ההקלטה מימות
    response = requests.get("https://www.call2all.co.il/ym/api/DownloadFile", params={
        "token": TOKEN,
        "path": wav_path
    })

    # שמירת הקלטה בשם ייחודי
    last5 = phone[-5:]
    input_path = f"{last5}.wav"
    with open(input_path, "wb") as f:
        f.write(response.content)

    print(f"📥 קיבלנו בקשה ממשתמש: {phone}")

    # התחלת עיבוד
    recognized = transcribe_audio(input_path)
    stock_dict = load_stock_list("hebrew_stocks.csv")

    if recognized:
        best_match = get_best_match(recognized, stock_dict)
        if best_match:
            ticker, stock_type = stock_dict[best_match]
            data = get_stock_data(ticker)
            if data:
                text = format_text(best_match, ticker, data, stock_type)
            else:
                text = f"לא נמצאו נתונים עבור {best_match}"
        else:
            text = "לא זוהה נייר ערך תואם"
    else:
        text = "לא זוהה דיבור ברור"

    # יצירת קובץ שמע וטעינה לימות
    import asyncio
    mp3_name = f"{last5}.mp3"
    wav_name = f"{last5}.wav"
    asyncio.run(create_audio(text, mp3_name))
    convert_mp3_to_wav(mp3_name, wav_name)
    upload_to_yemot(wav_name, f"ivr2:/9/{last5}.wav")

    # מחזיר לימות את שם הקובץ כדי שישמיע למאזין
    return last5

# הפעלת האפליקציה (לריילווי / לוקאל)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
