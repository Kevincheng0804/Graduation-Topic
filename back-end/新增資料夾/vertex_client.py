import os
import datetime
import vertexai
from vertexai.preview.generative_models import GenerativeModel
from google.oauth2 import service_account

# ====== 初始化 Vertex AI ======
def init_vertex_ai_client(project_id: str, location: str, key_path: str = "my-key.json"):
    credentials = None
    if os.path.exists(key_path):
        try:
            credentials = service_account.Credentials.from_service_account_file(key_path)
            print("✅ 已載入 my-key.json 認證")
        except Exception as e:
            print(f"⚠️ 載入金鑰失敗，將使用 ADC: {e}")
    else:
        print("⚠️ 未找到 my-key.json，將使用 ADC")

    try:
        vertexai.init(project=project_id, location=location, credentials=credentials)
        print("✅ Vertex AI 初始化成功")
    except Exception as e:
        print(f"❌ Vertex AI 初始化失敗: {e}")
        return None

    return True


# ====== 連接到 Endpoint 模型 ======
def connect_to_model():
    PROJECT_ID = "task-focus-4i2ic"
    LOCATION = "us-central1"
    ENDPOINT_ID = "8467368732316925952"

    endpoint_path = f"projects/{PROJECT_ID}/locations/{LOCATION}/endpoints/{ENDPOINT_ID}"
    try:
        model = GenerativeModel(endpoint_path)
        print("✅ 成功連接到端點:", endpoint_path)
        return model
    except Exception as e:
        print(f"❌ 連接到端點失敗: {e}")
        return None


# ====== 發問邏輯 ======
def ask_vertex_ai(model: GenerativeModel, question: str):
    today = datetime.date.today()
    year, month, day = today.year, today.month, today.day

    format_instructions = f"""
今天的日期是 {year} 年 {month} 月 {day} 日。
你是一個行程規劃助手，請根據使用者需求，並輸出一份行程計劃。

要求：
1. 開頭要有一句推薦理由。
2. 計劃必須嚴格遵循以下 JSON 格式：

計劃:
{{ 
  "計畫名稱": "<例如：跑步1Km一周計畫>", 
  "行程": [
    {{
      "事件": "<事件名稱>",
      "年分": 2025,
      "月份": 8,
      "日期": 21,
      "持續時間": 30,  # 單位：分鐘
      "多元智慧領域": "<只能選以下之一：語文、邏輯數學、空間、音樂、身體動覺、人際、內省、自然>"
    }}
  ]
}}

3. 行程必須從「明天」開始，往後最多安排 7 天，不可超過一個月。
4. 每個事件必須有確切的年、月、日，以及「持續時間」(分鐘)。
5. 如果使用者的問題不是關於行程規劃，請回答：「這個問題超出我的行程規劃範圍。」
"""

    response = model.generate_content(f"{format_instructions}\n使用者需求: {question}")
    return response.text
