import os
import vertexai
# 這是你找到的、已被證明可以成功運作的導入路徑
from vertexai.tuning import sft  
# 我們新增這個，這是官方範例中用來呼叫模型的類別
from vertexai.generative_models import GenerativeModel

from google.oauth2 import service_account

def predict_with_our_model_final_version(project_id: str, location: str, tuning_job_id: str, credentials, user_question: str):
    """
    使用已被證明的環境和認證，通過 list() 方法來獲取模型並執行預測。
    """
    # 1. 初始化 Vertex AI，使用和成功範本完全一樣的方式
    vertexai.init(project=project_id, location=location, credentials=credentials)
    print("环境初始化成功，准备进行模型预测...")

    # --- 關鍵修改：我們不再使用 get()，而是使用 list() 來尋找 ---
    print(f"正在列出所有微调作业，以寻找 ID: {tuning_job_id}")
    
    all_tuning_jobs = sft.SupervisedTuningJob.list()
    
    our_job = None
    for job in all_tuning_jobs:
        # job.resource_name 的格式是 'projects/.../tuningJobs/JOB_ID'
        if tuning_job_id in job.resource_name:
            our_job = job
            break # 找到了就跳出迴圈
    
    if not our_job:
        raise RuntimeError(f"致命错误：在专案的所有微调作业中，都找不到 ID 为 {tuning_job_id} 的作业。")
    
    print(f"成功在列表中找到了我们的微调作业: {our_job.resource_name}")
    # ------------------------------------------------------------------
    
    # 3. 從找到的作業物件中自動獲取其部署的端點名稱
    tuned_model_endpoint_name = our_job.tuned_model_endpoint_name
    print(f"成功获取到模型端点名称: {tuned_model_endpoint_name}")

    # 4. 使用端點名稱來實例化模型
    tuned_model = GenerativeModel(tuned_model_endpoint_name)

    # 5. 準備輸入內容並呼叫 API
    print("\n正在向模型发送请求...")
    response = tuned_model.generate_content(user_question)

    # 6. 返回結果
    return response.text

# --- 執行你的程式 ---
if __name__ == "__main__":
    PROJECT_ID = "task-focus-4i2ic" 
    LOCATION = "us-central1"
    TUNING_JOB_ID = "9068812123970207744" 
    MY_QUESTION = "分析數據"

    try:
        # --- 認證：我們只做一次，這是所有操作的基礎 ---
        key_path = "my-key.json"
        if not os.path.exists(key_path):
            raise FileNotFoundError(f"错误：找不到金钥档案 '{key_path}'。")
        
        credentials = service_account.Credentials.from_service_account_file(key_path)

        # --- 現在，執行我們新的預測函式 ---
        prediction = predict_with_our_model_final_version(PROJECT_ID, LOCATION, TUNING_JOB_ID, credentials, MY_QUESTION)

        print("\n--- 最终结果 ---")
        print("模型的回答:")
        print(prediction)

    except Exception as e:
        print(f"\n发生了未预期的错误: {e}")
        import traceback
        traceback.print_exc()