from pulp import LpProblem, LpMaximize, LpVariable, lpSum, value, LpStatus
from datetime import datetime, timedelta

# ===============================
# 一、使用者輸入任務資料
# ===============================
today = datetime.today().date()
tasks = []  # 每個任務記錄： (任務名稱, 持續時間（小時）, 固定時間 or None, 優先度)
while True:
    task_name = input("請輸入任務名稱（或輸入 'done' 結束輸入）：")
    if task_name.lower() == 'done':
        break

    try:
        duration = int(input("請輸入該任務的持續時間（小時）："))
    except ValueError:
        print("請輸入有效的數字。")
        continue

    # 固定時間：格式為 "HH-MM"，表示任務必須在該整點時間開始（例如 09-10 表示必須在 09:00 開始）
    fixed_time_input = input("請輸入固定時間（格式 HH-MM，若無則按 Enter 跳過）：")
    if fixed_time_input:
        try:
            start_str, end_str = fixed_time_input.split('-')
            fixed_start = datetime.combine(today, datetime.strptime(start_str, "%H").time())
            fixed_end = datetime.combine(today, datetime.strptime(end_str, "%H").time())
            fixed_time = (fixed_start, fixed_end)
        except Exception as e:
            print("固定時間格式錯誤，請依照 HH-MM 格式輸入。")
            continue
    else:
        fixed_time = None

    # 優先度：選填 1~5，若未填則預設為 5
    priority_input = input("請輸入優先度（1~5，選填，預設5）：")
    if priority_input.strip() == "":
        priority = 5
    else:
        try:
            priority = int(priority_input)
            if priority < 1 or priority > 5:
                print("優先度必須在 1 到 5 之間，將設為預設值 5。")
                priority = 5
        except ValueError:
            print("優先度輸入錯誤，將設為預設值 5。")
            priority = 5

    tasks.append((task_name, duration, fixed_time, priority))

if not tasks:
    print("沒有輸入任何任務，結束程式。")
    exit()

# ===============================
# 二、模型參數設定（以小時計算）
# ===============================
# 一天有 24 小時，0～23 分別代表 00:00～23:00 的整點開始時間
num_hours = 24

# 定義時間區段（以「整點」作為界定）以及對應分數：
#   00:00 ~ 07:00：小時 0 ~ 7，得分 1
#   08:00 ~ 13:00：小時 8 ~ 13，得分 10
#   14:00 ~ 20:00：小時 14 ~ 20，得分 9
#   21:00 ~ 23:00：小時 21 ~ 23，得分 5
segments = {
    0: {"lower": 0,  "upper": 7,  "score": 1},
    1: {"lower": 8,  "upper": 13, "score": 10},
    2: {"lower": 14, "upper": 20, "score": 9},
    3: {"lower": 21, "upper": 23, "score": 5},
}

# ===============================
# 三、建立 MILP 模型
# ===============================
prob = LpProblem("Task_Scheduling", LpMaximize)
n_tasks = len(tasks)

# (1) 任務開始時間變數 x[i]：整數型，代表任務 i 的開始小時 (0~23)
x = { i: LpVariable(f"x_{i}", lowBound=0, upBound=num_hours-1, cat="Integer")
      for i in range(n_tasks) }

# (2) 二元變數 y[(i, seg)]：代表任務 i 是否被安排在區段 seg 中
y = { (i, seg): LpVariable(f"y_{i}_{seg}", cat="Binary")
      for i in range(n_tasks) for seg in segments }

# 每個任務必須只分配到一個區段
for i in range(n_tasks):
    prob += lpSum([ y[(i, seg)] for seg in segments ]) == 1

# Big-M 參數（以小時計），這裡 M 可取 24
M = num_hours

# (3) 連結 x 與 y：若 y[(i, seg)] = 1，則 x[i] 必須落在該區段內
for i in range(n_tasks):
    for seg, seg_info in segments.items():
        lower = seg_info["lower"]
        upper = seg_info["upper"]
        prob += x[i] >= lower - M * (1 - y[(i, seg)])
        prob += x[i] <= upper + M * (1 - y[(i, seg)])

# (4) 處理固定時間任務：若任務有固定時間，則強制 x[i] 為該整點（使用 fixed_start.hour）
for i, (name, duration, fixed_time, priority) in enumerate(tasks):
    if fixed_time is not None:
        fixed_hour = fixed_time[0].hour  # 固定開始小時
        prob += x[i] == fixed_hour
        assigned_seg = None
        for seg, seg_info in segments.items():
            if seg_info["lower"] <= fixed_hour <= seg_info["upper"]:
                assigned_seg = seg
                break
        if assigned_seg is not None:
            for seg in segments:
                if seg == assigned_seg:
                    prob += y[(i, seg)] == 1
                else:
                    prob += y[(i, seg)] == 0

# (5) 引入二元排序變數 delta[(i,j)] (僅對 i<j 定義)
# delta[(i,j)] = 1 表示任務 i 排在任務 j 之前；否則任務 j 在 i 之前
delta = { (i, j): LpVariable(f"delta_{i}_{j}", cat="Binary")
          for i in range(n_tasks) for j in range(i+1, n_tasks) }

# (6) 不重疊及排序約束
for i in range(n_tasks):
    for j in range(i+1, n_tasks):
        duration_i = tasks[i][1]  # 持續時間 (小時)
        duration_j = tasks[j][1]
        # 非重疊約束（利用 Big M 與 delta）
        prob += x[i] + duration_i <= x[j] + M*(1 - delta[(i,j)])
        prob += x[j] + duration_j <= x[i] + M*(delta[(i,j)])
        
        # 若兩任務皆為彈性（無固定時間），依據優先度強制排序：
        if tasks[i][2] is None and tasks[j][2] is None:
            if tasks[i][3] < tasks[j][3]:
                prob += delta[(i,j)] == 1  # 較高優先度（數字較小）的必須在前
            elif tasks[i][3] > tasks[j][3]:
                prob += delta[(i,j)] == 0
        # 若其中一個任務為固定，不額外強制依優先度排序

# (7) 目標函數：最大化所有任務落入區段的總分數
prob += lpSum([ segments[seg]["score"] * y[(i, seg)]
                for i in range(n_tasks) for seg in segments ])

# ===============================
# 四、求解模型並輸出結果
# ===============================
prob.solve()

print(f"\n求解狀態：{LpStatus[prob.status]}")
if LpStatus[prob.status] == "Optimal":
    print("\n最佳排程結果：")
    tasks_with_start = []
    for i in range(n_tasks):
        start_hour = int(value(x[i]))
        end_hour = start_hour + tasks[i][1]
        seg_score = sum(segments[seg]["score"] * value(y[(i, seg)]) for seg in segments)
        tasks_with_start.append((i, tasks[i][0], start_hour, end_hour, tasks[i][3], seg_score))
    tasks_with_start.sort(key=lambda item: item[2])
    for i, name, st, et, prio, score in tasks_with_start:
        print(f"{name} 任務 (優先度 {prio})：{st:02d}:00 - {et:02d}:00 (區段分數: {score})")
else:
    print("未找到最佳解，請檢查約束條件或重新調整輸入資料。") 

