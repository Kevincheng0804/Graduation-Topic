import requests
import math
from datetime import datetime

def get_user_input():
    try:
        url = "https://941009b92a2b.ngrok-free.app/api/latest"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        print("✅ 從 API 取得資料：", data)

        Ts_hour, Ts_minute = map(int, data["Ts"].split(":"))
        Te_hour, Te_minute = map(int, data["Te"].split(":"))
        Ts = Ts_hour + Ts_minute / 60
        Te = Te_hour + Te_minute / 60

        if Te <= Ts:
            Te += 24

        durations = [math.ceil(d / 5) for d in data["k"]]

        if "n" in data and len(durations) != data["n"]:
            print("⚠️ 任務數量n與k長度不符")

        date_str = data.get("taskDate")
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")

        desc_list = data.get("desc", [""] * len(durations))  

        return Ts, Te, durations, date_str, desc_list

    except Exception as e:
        print("❌ 取得或解析 API 資料失敗：", e)
        return None, None, None, None, None

