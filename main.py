from flask import Flask, request
import requests
import os

app = Flask(__name__)

# שים כאן את הטוקן שלך מימות המשיח
USERNAME = "0733181201"
PASSWORD = "6714453"
TOKEN = f"{USERNAME}:{PASSWORD}"

@app.route("/api-handler", methods=["GET", "POST"])
def handle_api():
    wav_path = request.args.get("recording")
    phone = request.args.get("ApiPhone")

    if not wav_path:
        return "no recording"

    # יצירת תיקיית הקלטות אם לא קיימת
    os.makedirs("recordings", exist_ok=True)

    # שליפת קובץ מימות
    response = requests.get("https://www.call2all.co.il/ym/api/DownloadFile", params={
        "token": TOKEN,
        "path": wav_path
    })

    file_name = wav_path.split("/")[-1]
    save_path = os.path.join("recordings", file_name)

    with open(save_path, "wb") as f:
        f.write(response.content)

    print(f"הוקלט מ: {phone} → שמור בשם: {file_name}")
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
