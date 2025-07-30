import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds
import json

def solve_schedule(ts_hour: float, te_hour: float, durations_slots: list[int]):
    # 每小時有12個5分鐘格子
    slots_per_hour = 12
    # 將小時轉為5分鐘格子
    Ts_slots = int(ts_hour * slots_per_hour)
    Te_slots = int(te_hour * slots_per_hour)
    time_slots = Te_slots - Ts_slots + 1
    n = len(durations_slots)

    # 假設每天24小時，總共24*12=288個5分鐘格子
    total_slots = 24 * slots_per_hour
    # 成本矩陣：假設每小時成本均勻分佈到12個5分鐘格子
    base_cost = np.array([
        [6, 4, 3, 1, 5, 2, 4, 3, 1, 5, 2, 4, 3, 1, 5, 2, 4, 3, 1, 5, 2, 4, 3, 1],
        [3, 1, 2, 4, 3, 3, 1, 2, 4, 3, 3, 1, 2, 4, 3, 3, 1, 2, 4, 3, 3, 1, 2, 4],
        [4, 3, 1, 2, 5, 4, 3, 1, 2, 5, 4, 3, 1, 2, 5, 4, 3, 1, 2, 5, 4, 3, 1, 2]
    ])
    # 擴展成本到5分鐘格子
    extended_cost = np.repeat(base_cost, slots_per_hour, axis=1)
    # 若任務數超過3，複製成本模板
    C = np.tile(extended_cost, (int(np.ceil(n / 3)), 1))[:n, :]

    num_vars = n * time_slots
    bounds = Bounds(0.0, 1.0)  # since all variables are bounded between 0 and 1
    integrality = np.ones(num_vars, dtype=bool)

    if time_slots <= 0 or any(d <= 0 for d in durations_slots):
        return {"success": False, "message": "時間範圍或任務持續時間不合法。"}

    # 每個任務只能選一個合法起始時間
    A_eq = np.zeros((n, num_vars))
    for i in range(n):
        # 任務i可以開始的時間點
        num_valid_starts = time_slots - durations_slots[i] + 1
        if num_valid_starts <= 0:
             return {"success": False, "message": f"任務 {i+1} (長度: {durations_slots[i]*5}分鐘) 太長，無法放入指定時間範圍內。"}
        start_idx = i * time_slots
        end_idx = start_idx + num_valid_starts
        A_eq[i, start_idx:end_idx] = 1
    b_eq = np.ones(n)

    # 任務間不可重疊
    A_ub = []
    for p in range(n):
        for q in range(p+1, n):
            dp, dq = durations_slots[p], durations_slots[q]
            for jp in range(time_slots - dp + 1):
                for jq in range(time_slots - dq + 1):
                    # 檢查時間區間 [jp, jp+dp) 和 [jq, jq+dq) 是否重疊
                    if jp < jq + dq and jq < jp + dp:
                        row = np.zeros(num_vars)
                        row[p * time_slots + jp] = 1
                        row[q * time_slots + jq] = 1
                        A_ub.append(row)
    
    constraints = [LinearConstraint(A_eq, b_eq, b_eq)]
    if A_ub:
        A_ub_np = np.array(A_ub)
        b_ub = np.ones(len(A_ub_np))
        constraints.append(LinearConstraint(A_ub_np, -np.inf, b_ub))

    # 目標函數：成本加總
    c = np.full(num_vars, 1e9) # 用一個很大的數值代表非法起始點
    for i in range(n):
        for j in range(time_slots - durations_slots[i] + 1):
            start_abs = Ts_slots + j
            end_abs = start_abs + durations_slots[i]
            total_cost = np.sum(C[i, start_abs:end_abs])
            c[i * time_slots + j] = total_cost

    # MILP 求解
    res = milp(c=c, constraints=constraints, bounds=bounds, integrality=integrality)

    if res.success and res.x is not None:
        X = res.x.reshape((n, time_slots))
        schedule_results = []

        for i in range(n):
            if np.sum(X[i, :]) > 0.5: # 確保任務有被排程
                start_j = np.argmax(X[i, :])
                start_slots = Ts_slots + start_j
                end_slots = start_slots + durations_slots[i]
                
                start_hour, start_min_rem = divmod(start_slots * 5, 60)
                end_hour, end_min_rem = divmod(end_slots * 5, 60)
                
                schedule_results.append({
                    "task_id": i + 1,
                    "start_time": f"{start_hour:02d}:{start_min_rem:02d}",
                    "end_time": f"{end_hour:02d}:{end_min_rem:02d}"
                })

        return {
            "success": True,
            "message": f"最佳解找到！(Ts={ts_hour:.2f}h, Te={te_hour:.2f}h)",
            "schedule": schedule_results,
            "total_cost": float(res.fun)
        }
    else:
        return {"success": False, "message": "找不到可行的排程解。", "schedule": None, "total_cost": None}

# ----------- 使用者輸入部分 -----------

try:
    Ts = float(input("請輸入 Ts（起始時間，單位：小時，例如 8.5 表示 8:30）："))
    Te = float(input("請輸入 Te（結束時間，單位：小時，例如 17.25 表示 17:15）："))
    if not (0 <= Ts <= 24 and 0 <= Te <= 24 and Ts <= Te):
        raise ValueError("Ts/Te 輸入不合法")

    n = int(input("請輸入任務數量 n："))
    durations = []
    for i in range(n):
        d = float(input(f"請輸入任務 {i+1} 的持續時間（單位：分鐘，例如 30 表示 30分鐘）："))
        if d <= 0 or d % 5 != 0:
            raise ValueError("持續時間必須為5分鐘的倍數且為正數")
        durations.append(int(d // 5))  # 轉為5分鐘格子
    
    # 呼叫重構後的函式
    result_dict = solve_schedule(Ts, Te, durations)
    
    # 將結果字典轉換為格式化的 JSON 字串並印出
    # indent=2 讓 JSON 輸出更容易閱讀
    json_output = json.dumps(result_dict, indent=2, ensure_ascii=False)
    print(json_output)

except Exception as e:
    error_output = json.dumps({"success": False, "message": f"輸入或執行時發生錯誤: {e}"}, indent=2, ensure_ascii=False)
    print(error_output)