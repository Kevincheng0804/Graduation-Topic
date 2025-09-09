from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from main import schedule_tasks            # 呼叫排程主要邏輯（main.py）
from user_input import get_user_input      # 目前未使用，但保留為未來擴充
import logging
import math
import datetime
import json        # 解析 Vertex AI 回傳的 JSON 部分
from pydantic import BaseModel
from vertex_client import init_vertex_ai_client, connect_to_model, ask_vertex_ai

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# 定義 POST /api/submit 所需的資料結構
class InputData(BaseModel):
    taskDate: str       # 任務日期字串（YYYY-MM-DD）
    Ts: str             # 起始時間字串（HH:MM）
    Te: str             # 結束時間字串（HH:MM）
    n: int              # 任務數量（目前未直接使用，但可做驗證）
    k: List[int]        # 每個任務的持續時間（單位為分鐘）
    desc: List[str]     # 每個任務的描述（用於智能分析與寫入 Firebase）
    #[IC]
    fixed:List[bool]  # 每個任務是否為固定任務（True/False）

# 用來儲存最近一次上傳的原始資料，供 GET /api/latest 查詢
latest_data: Optional[InputData] = None

@app.get("/")
async def root():
    # 根路由，回傳簡短說明
    return {"message": "後端運行中。請使用 POST /api/submit 傳送資料"}

@app.get("/api/submit")
async def submit_get():
    # 用於測試或說明的 GET 端點
    return {"message": "請用 POST 傳送 JSON：{taskDate, Ts, Te, n, k, desc}"}

@app.post("/api/submit")
async def submit_and_compute(data: InputData):
    """
    接收前端傳來的 JSON，負責：
    - 解析時間字串 Ts, Te 為小時浮點數（若 Te <= Ts 則視為跨日加 24 小時）
    - 把持續時間 k（分鐘）轉為以 5 分鐘為單位的 slot（math.ceil(d / 5)）
    - 呼叫 schedule_tasks 執行排程並把結果寫入 Firebase（schedule_tasks 會處理智能分析與寫入）
    """
    global latest_data
    latest_data = data
    logging.info(f"✅ 接收到資料: {data.dict()}")

    try:
        # 將接收到的資料送到 get_user_input 處理（你也可以直接拆開不用 get_user_input）
        Ts_hour, Ts_minute = map(int, data.Ts.split(":"))
        Te_hour, Te_minute = map(int, data.Te.split(":"))
        Ts = Ts_hour + Ts_minute / 60
        Te = Te_hour + Te_minute / 60
        if Te <= Ts:
            # 若結束時間小於等於起始時間，視為跨日
            Te += 24

        # 把分鐘轉成以 5 分鐘為單位的 slots（整數）
        durations = [math.ceil(d / 5) for d in data.k]

        # 若沒有傳入 taskDate，使用現在日期
        date_str = data.taskDate or datetime.now().strftime("%Y-%m-%d")

        # 呼叫排程主程式（會把結果寫入 Firebase）
        schedule_tasks(Ts, Te, durations, date_str, data.desc,data.fixed)#[IC]add data.fixed

        return {"success": True, "message": "✅ 任務成功排程並寫入 Firebase"}

    except Exception as e:
        logging.error(f"❌ 錯誤: {e}")
        return {"success": False, "error": str(e)}
    
@app.get("/api/latest")
async def get_latest_data():
    # 回傳最近一次上傳的原始資料（未經排程處理）
    if latest_data is None:
        return {"message": "尚未有任何上傳的資料"}
    return latest_data.dict()

# 以下為 Vertex AI 相關的擴充功能
class AskRequest(BaseModel):
    question: str

@app.on_event("startup")
def startup_event():
    """
    應用啟動時初始化 Vertex AI client 與模型連線。
    - PROJECT_ID / LOCATION 可視需求改為環境變數或設定檔
    - 若初始化或連線失敗，拋出例外以便早期發現問題
    """
    PROJECT_ID = "task-focus-4i2ic"
    LOCATION = "us-central1"

    if init_vertex_ai_client(PROJECT_ID, LOCATION):
        global model
        model = connect_to_model()
        if not model:
            raise RuntimeError("無法連接到模型")
    else:
        raise RuntimeError("初始化 Vertex AI 失敗")

@app.post("/dick/ask")
def ask_api(req: AskRequest):
    """
    向 Vertex AI 詢問問題並嘗試解析回傳中包含的 JSON：
    - ask_vertex_ai 回傳的字串預期包含一段文字說明，接著是一個 JSON 物件
    - 程式會抓出第一個 '{' 到最後一個 '}' 作為 JSON 範圍，解析後回傳
    - recommendation 為 JSON 之前的文字（若有）
    注意：此解析方法較為脆弱，建議在可能情況下要求模型只回傳 JSON 或用更嚴謹的分隔符號
    """
    try:
        answer = ask_vertex_ai(model, req.question)
    
        # 嘗試抽取 JSON 部分（從第一個 { 到最後一個 }）
        start_idx = answer.find("{")
        end_idx = answer.rfind("}") + 1
        if start_idx == -1 or end_idx == -1:
            raise HTTPException(status_code=500, detail="找不到 JSON 部分")
        
        plan_json = json.loads(answer[start_idx:end_idx])

        # 推薦理由就是 JSON 前面的文字
        recommendation = answer[:start_idx].strip()

        return {
            "status": "ok",
            "recommendation": recommendation,
            "result": plan_json
        }

    except Exception as e:
        # 將發生的任何錯誤轉成 HTTP 500 回傳
        raise HTTPException(status_code=500, detail=str(e))