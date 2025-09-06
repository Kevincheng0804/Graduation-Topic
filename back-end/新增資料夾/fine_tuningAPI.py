import os
import json
import re
import time
import vertexai
from vertexai.generative_models import GenerativeModel
from google.oauth2 import service_account

def predict_with_endpoint(project_id: str, location: str, endpoint_id: str, credentials, prompt: str):
    """
    使用端點 ID 執行一次請求（支援 credentials 為 None 使用 ADC）。
    回傳生成文字（raw text）。
    """
    if credentials:
        vertexai.init(project=project_id, location=location, credentials=credentials)
    else:
        vertexai.init(project=project_id, location=location)
    endpoint_path = f"projects/{project_id}/locations/{location}/endpoints/{endpoint_id}"
    tuned_model = GenerativeModel(endpoint_path)
    response = tuned_model.generate_content(prompt)
    return response.text

def _extract_json_between_tokens(text, start="<<JSON_START>>", end="<<JSON_END>>"):
    m = re.search(re.escape(start) + r"(.*)" + re.escape(end), text, re.S)
    if m:
        body = m.group(1).strip()
    else:
        # fallback: try to extract last JSON array or object
        a = text.rfind("[")
        b = text.rfind("]")
        if a != -1 and b > a:
            body = text[a:b+1]
        else:
            a = text.rfind("{")
            b = text.rfind("}")
            body = text[a:b+1] if a != -1 and b > a else text
    return body

def intelligent_task_analysis(missions: list):
    """
    批次呼叫 Vertex AI endpoint，回傳一個 list of {"mission":..., "intelligence":...}。
    - 會自動嘗試從 my-key.json 讀取 credentials，找不到時使用 ADC。
    - 使用 start/end token、重試與 mission 補回機制以增加穩定性。
    """
    PROJECT_ID = "task-focus-4i2ic"
    LOCATION = "us-central1"
    ENDPOINT_ID = "4155910960923541504"

    key_path = "my-key.json"
    credentials = None
    if os.path.exists(key_path):
        try:
            credentials = service_account.Credentials.from_service_account_file(key_path)
        except Exception as e:
            print(f"⚠️ 載入金鑰失敗，將使用 ADC（若未設定會失敗）: {e}")

    # 構建批次 prompt（移除可能誤導的示例，明確要求保留原文字與順序，限制 label 集合）
    tasks_text = "\n".join(f"{i+1}. {m}" for i, m in enumerate(missions))
    prompt = f"""
You are a JSON-only classifier. Given the tasks below, return a JSON array between tokens <<JSON_START>> and <<JSON_END>>.
Each element must be an object with keys: "mission" (string) and "intelligence" (string).

Important (follow exactly):
- Do NOT rewrite, normalize, translate, or change any mission text — preserve the original mission strings exactly.
- Preserve the original order of the tasks and output exactly one object per input task.
- Use exactly one of the following allowed intelligence labels (in Chinese) for each task:
  ["語言智能","邏輯數理智能","空間智能","肢體動覺智能","音樂智能","人際關係智能","自省智能","自然辨識智能"]
- Output nothing except the JSON array between the tokens <<JSON_START>> and <<JSON_END>>.

Tasks:
{tasks_text}

Output exactly in this form and nothing else outside the tokens:

<<JSON_START>>
[
  {{ "mission": "原任務文字1", "intelligence": "自省智能" }},
  ...
]
<<JSON_END>>
"""

    max_retries = 2
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            raw = predict_with_endpoint(PROJECT_ID, LOCATION, ENDPOINT_ID, credentials, prompt)
            body = _extract_json_between_tokens(raw)
            parsed = json.loads(body)

            # 基本 schema 驗證
            if not isinstance(parsed, list):
                raise ValueError("parsed result is not a list")
            for obj in parsed:
                if not isinstance(obj, dict) or "mission" not in obj or "intelligence" not in obj:
                    raise ValueError("item missing required keys")

            # 若模型回傳的 mission 欄位為佔位符或數量不符，使用原始 missions 依序補回，保留 intelligence
            def is_placeholder(m):
                if not isinstance(m, str):
                    return True
                mm = m.strip().lower()
                return mm == "" or mm.startswith("task") or mm.startswith("example")

            need_fix = (len(parsed) != len(missions)) or any(is_placeholder(item.get("mission")) for item in parsed)
            if need_fix:
                print("⚠️ 模型回傳的 mission 欄位不可靠，使用輸入 missions 依序補回（保留模型提供的 intelligence）")
                fixed = []
                for i, orig in enumerate(missions):
                    intelligence = ""
                    if i < len(parsed) and isinstance(parsed[i], dict):
                        intelligence = parsed[i].get("intelligence", "") or ""
                    fixed.append({"mission": orig, "intelligence": intelligence})
                parsed = fixed

            print("\n--- 最終分析結果陣列 ---")
            print(json.dumps(parsed, ensure_ascii=False, indent=2))
            return parsed

        except Exception as e:
            last_exc = e
            print(f"⚠️ 解析或呼叫失敗（嘗試 {attempt}/{max_retries}）：{e}")
            time.sleep(1.5 * attempt)

    # 全部重試失敗
    raise RuntimeError(f"解析模型回傳失敗: {last_exc}")
