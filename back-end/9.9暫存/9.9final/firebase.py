import numpy as np
import firebase_admin
from firebase_admin import credentials, firestore

# Firebase 初始化（只執行一次）
cred = credentials.Certificate("/home/improj/jack_FastAPI/task-focus-4i2ic-3d473316080f.json")
firebase_admin.initialize_app(cred)
db = firestore.client()
def get_base_cost_from_firebase(analysis_results: list):
    """
    從 Firebase 根據任務分析結果讀取多個成本資料，回傳 numpy 2D array。
    支援 analysis_results 中 intelligence 為單一中文字串或字串陣列。
    若多個任務指向相同 intelligence，輸出會保留多個相同的 rows（但只會實際 fetch 一次）。
    """
    CHINESE_TO_DOC_SUFFIX = {
        "語言智能": "linguistic",
        "邏輯數理智能": "logical",
        "空間智能": "spatial",
        "肢體動覺智能": "bodily_kinesthetic",
        "音樂智能": "musical",
        "人際關係智能": "interpersonal",
        "自省智能": "intrapersonal",
        "自然辨識智能": "naturalistic"
    }

    costs = []
    cache = {}  # doc_name -> values list（快取，避免重複 fetch）

    for result in analysis_results:
        intelligence_field = result.get("intelligence")
        if not intelligence_field:
            raise ValueError(f"❌ 任務 '{result.get('mission')}' 的分析結果缺少 'intelligence' 欄位")

        types = intelligence_field if isinstance(intelligence_field, (list, tuple)) else [intelligence_field]

        for itype in types:
            if not isinstance(itype, str):
                raise ValueError(f"❌ 不支援的 intelligence 類型: {type(itype)}")

            key = itype.strip()
            if key.startswith("fatigue_"):
                suffix = key[len("fatigue_"):].lower()
            else:
                suffix = CHINESE_TO_DOC_SUFFIX.get(key)
                if suffix is None:
                    suffix = key.lower()

            doc_name = f"fatigue_{suffix}"

            # 若已快取，直接重複使用（保留多筆輸出）
            if doc_name in cache:
                values = cache[doc_name]
                costs.append(values)
                continue

            # 否則從 Firestore 取一次並快取
            doc_ref = fs_db.collection("users").document("testUser") \
                        .collection("fatigue_logs").document(doc_name)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                if 'values' in data and isinstance(data['values'], list):
                    values = [round(float(v), 1) for v in data['values']]
                    cache[doc_name] = values
                    costs.append(values)
                else:
                    raise ValueError(f"❌ 文件 '{doc_name}' 的 'values' 欄位不存在或格式錯誤")
            else:
                raise ValueError(f"❌ Firebase 文件 '{doc_name}' 不存在")

    if not costs:
        raise ValueError("❌ 未能從 Firebase 獲取任何成本資料")

    return np.array(costs)

#[IC] 新增函式，從 Firebase 抓取指定日期的固定行程，並過濾與指定時間段有交集的任務
def get_tasks_from_firebase(date_str: str, Ts: str, Te: str):
    """
    從 Firebase 抓取指定使用者 (uid) 在 date_str (YYYY-MM-DD) 的固定行程，
    並只回傳與 Ts ~ Te (HH:MM) 有交集的任務。
    """

    tasks = []

    # 解析 Ts / Te 成小時 (float)
    Ts_h, Ts_m = map(int, Ts.split(":"))
    Te_h, Te_m = map(int, Te.split(":"))
    Ts_f = Ts_h + Ts_m / 60
    Te_f = Te_h + Te_m / 60

    # 拆解日期
    year, month, day = date_str.split("-")
    tasks_ref = fs_db.collection("Tasks").document("uid") \
                    .collection("task_list").document(f"{year}-{month}-{day}") \
                    .collection("tasks")

    docs = tasks_ref.stream()

    for doc in docs:
        data = doc.to_dict()
        if not data or not data.get("Fixed_schedule", False):
            continue  # 只保留固定行程

        # 轉換 startTime / endTime 成小時 (float)
        start_h, start_m = map(int, data.get("startTime", "00:00").split(":"))
        end_h, end_m = map(int, data.get("endTime", "00:00").split(":"))
        start_time = start_h + start_m / 60
        end_time = end_h + end_m / 60

        # 判斷是否和 Ts~Te 有交集
        if end_time <= Ts_f or start_time >= Te_f:
            continue

        # 修正交集範圍
        adj_start = max(start_time, Ts_f)
        adj_end = min(end_time, Te_f)

        # 時間轉回 HH:MM 格式
        adj_start_h, adj_start_m = divmod(int(adj_start * 60), 60)
        adj_end_h, adj_end_m = divmod(int(adj_end * 60), 60)

        task = {
            "Fixed_schedule": True,
            "desc": data.get("desc", ""),
            "endTime": f"{adj_end_h:02d}:{adj_end_m:02d}",
            "index": data.get("index", 0),
            "intelligence": data.get("intelligence", ""),
            "startTime": f"{adj_start_h:02d}:{adj_start_m:02d}"
        }
        tasks.append(task)

    return tasks
