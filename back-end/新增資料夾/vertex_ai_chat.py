"""import json
from google.oauth2 import service_account
from google import genai

def init_vertex_ai(key_path: str, project_id: str, location: str):
    creds = service_account.Credentials.from_service_account_file(key_path)
    client = genai.Client(
        vertexai=True,
        project=project_id,
        location=location,
        credentials=creds
    )
    return client

def is_schedule_related(message: str) -> bool:

    keywords = ["行程", "安排", "規劃", "日程", "時間表", "schedule", "任務", "排程"]
    return any(kw in message for kw in keywords)

def chat_with_ai(client, user_message: str):
    if not is_schedule_related(user_message):
        return "⚠️ 抱歉，我只回答跟行程安排相關的問題。"

    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=f"你是一個行程助理，只回答行程安排的問題。\n\n使用者的問題：{user_message}"
    )
    return response.text

if __name__ == "__main__":
    KEY_PATH = "2330747a-f4fd-431b-b7f4-239a55c05843.json"
    PROJECT_ID = "task-focus-4i2ic"
    LOCATION = "us-central1"

    client = init_vertex_ai(KEY_PATH, PROJECT_ID, LOCATION)

    print("🗓️ 行程助手已啟動，只回答行程安排相關的問題 (輸入 exit 結束)")
    while True:
        msg = input("你: ")
        if msg.lower() in ["exit", "quit"]:
            break
        reply = chat_with_ai(client, msg)
        print("AI:", reply)
"""