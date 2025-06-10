from flask import Flask, request, send_file
import requests
import os
import subprocess
import speech_recognition as sr
import pandas as pd
import yfinance as yf
from difflib import get_close_matches
import edge_tts

app = Flask(__name__)

USERNAME = "0733181201"
PASSWORD = "6714453"
TOKEN = f"{USERNAME}:{PASSWORD}"

# Load stock list once
stock_dict = {}
def load_stock_list():
    global stock_dict
    df = pd.read_csv("hebrew_stocks.csv")
    stock_dict = dict(zip(df['hebrew_name'], zip(df['ticker'], df['type'])))

load_stock_list()

@app.route("/api-handler", methods=["GET", "POST"])
def handle_api():
    wav_path = request.args.get("recording")
    phone = request.args.get("ApiPhone")

    if not wav_path:
        return "no recording"

    os.makedirs("recordings", exist_ok=True)
    os.makedirs("output", exist_ok=True)

    response = requests.get("https://www.call2all.co.il/ym/api/DownloadFile", params={
        "token": TOKEN,
        "path": wav_path
    })

    file_name = wav_path.split("/")[-1]
    local_path = os.path.join("recordings", file_name)

    with open(local_path, "wb") as f:
        f.write(response.content)

    log_message = f"📞 הקלטה מ-{phone} נשמרה בשם {file_name}"
    print(log_message)
    with open("log.txt", "a", encoding="utf-8") as log:
        log.write(log_message + "\n")

    # Convert to text
    recognized = transcribe_audio(local_path)
    if not recognized:
        return tts_response("לא הצלחנו לזהות את שם המניה שנאמר")

    best_match = get_best_match(recognized)
    if not best_match:
        return tts_response("לא נמצאה מניה מתאימה")

    ticker, stock_type = stock_dict[best_match]
    data = get_stock_data(ticker)
    if not data:
        return tts_response("לא נמצאו נתונים עדכניים על המניה")

    text = format_text(best_match, ticker, data, stock_type)

    # Create audio file
    audio_path = "output/output.wav"
    create_audio(text, "output/output.mp3")
    convert_mp3_to_wav("output/output.mp3", audio_path)

    # Return play_url to Yemot
    server_url = request.url_root.strip("/")
    return f"play_url={server_url}/audio/output.wav"

@app.route("/audio/output.wav")
def serve_audio():
    return send_file("output/output.wav", mimetype="audio/wav")

def transcribe_audio(filepath):
    r = sr.Recognizer()
    with sr.AudioFile(filepath) as source:
        audio = r.record(source)
    try:
        return r.recognize_google(audio, language="he-IL")
    except:
        return ""

def get_best_match(query):
    matches = get_close_matches(query, stock_dict.keys(), n=1, cutoff=0.6)
    return matches[0] if matches else None

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

def format_text(name, ticker, data, stock_type):
    currency = "שקלים" if ticker.endswith(".TA") else "דולר"
    if stock_type.startswith("מניה"):
        return (
            f"נמצאה מניה בשם {name}. המניה נסחרת בשווי של {data['current']} {currency}. "
            f"היום {('עלייה' if data['day'] > 0 else 'ירידה')} של {abs(data['day'])} אחוז. "
            f"בשלושת החודשים {('עלייה' if data['3mo'] > 0 else 'ירידה')} של {abs(data['3mo'])} אחוז. "
            f"והמחיר הנוכחי רחוק מהשיא ב־{abs(data['from_high'])} אחוז."
        )
    elif stock_type == "מדד":
        return (
            f"נמצא מדד בשם {name}. ערכו כעת {data['current']} נקודות. "
            f"היום {('עלייה' if data['day'] > 0 else 'ירידה')} של {abs(data['day'])} אחוז. "
            f"בשלושת החודשים {('עלייה' if data['3mo'] > 0 else 'ירידה')} של {abs(data['3mo'])} אחוז. "
            f"והמדד רחוק מהשיא ב־{abs(data['from_high'])} אחוז."
        )
    else:
        return (
            f"נמצא נכס בשם {name}. ערכו כעת {data['current']} {currency}. "
            f"היום {('עלייה' if data['day'] > 0 else 'ירידה')} של {abs(data['day'])} אחוז. "
            f"בשלושת החודשים {('עלייה' if data['3mo'] > 0 else 'ירידה')} של {abs(data['3mo'])} אחוז. "
            f"והוא רחוק מהשיא ב־{abs(data['from_high'])} אחוז."
        )

def create_audio(text, filename):
    communicate = edge_tts.Communicate(text, voice="he-IL-AvriNeural")
    import asyncio
    asyncio.run(communicate.save(filename))

def convert_mp3_to_wav(mp3_file, wav_file):
    subprocess.run(["ffmpeg", "-y", "-i", mp3_file, "-ar", "8000", "-ac", "1", "-acodec", "pcm_s16le", wav_file])

def tts_response(message):
    create_audio(message, "output/output.mp3")
    convert_mp3_to_wav("output/output.mp3", "output/output.wav")
    server_url = request.url_root.strip("/")
    return f"play_url={server_url}/audio/output.wav"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
