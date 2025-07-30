import os

# 我們要測試的檔案路徑
file_path = r"C:\Users\davis\Specialize-in-research\Graduation-Topic\back-end\my-key.json"

print(f"正在嘗試讀取檔案: {file_path}")

# 檢查檔案是否存在
if os.path.exists(file_path):
    print("成功！os.path.exists() 找到了這個檔案。")
    try:
        # 嘗試打開並讀取檔案
        with open(file_path, 'r') as f:
            content = f.read()
        print("巨大成功！檔案不僅存在，而且可以被成功打開和讀取。")
    except Exception as e:
        print(f"致命錯誤！檔案存在，但無法被讀取。權限問題？錯誤：{e}")
else:
    print("致命錯誤！os.path.exists() 找不到這個檔案。系統層級的問題。")