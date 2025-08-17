import numpy as np
import firebase_admin
from firebase_admin import credentials, firestore

# Firebase 初始化（只執行一次）
cred = credentials.Certificate("C:/pydata/test/task-focus-4i2ic-3d473316080f.json")
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
            doc_ref = db.collection("users").document("testUser") \
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
