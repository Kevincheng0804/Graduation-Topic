import numpy as np
import math
from scipy.optimize import milp, LinearConstraint, Bounds
from firebase import get_base_cost_from_firebase, db
from fine_tuningAPI import intelligent_task_analysis
import math
from firebase import get_tasks_from_firebase

def write_results_to_firebase(date_str, schedule_results):
    year, month, day = date_str.split("-")
    for idx, task in enumerate(schedule_results):
        try:
            db.collection("tasks").document(year) \
              .collection(month).document(day) \
              .collection("task_list").document(str(idx)) \
              .set(task, merge=True) 
            print(f"✅ 成功寫入任務 {idx} 資料")
        except Exception as e:
            print(f"❌ 寫入任務 {idx} 發生錯誤:", e)

def schedule_tasks(Ts, Te, durations, date_str, desc_list, fixed_list):#[IC]add fixed_list
    """接收參數並執行任務排程運算"""
    slots_per_hour = 12
    Ts_slots = int(Ts * slots_per_hour)
    Te_slots = int(Te * slots_per_hour)
    time_slots = Te_slots - Ts_slots + 1
    n = len(durations)
    total_slots = 24 * slots_per_hour
    fixed_list_len = len(fixed_list) #[IC]找有多少個任務

    intelligent_analysis_results = intelligent_task_analysis(desc_list)#分類8大智能(陣列形式)

    base_cost = get_base_cost_from_firebase(intelligent_analysis_results)#把分類完的陣列輸入去firebase去抓對應的疲勞度
    #目前不確定抓回來的樣子會長怎樣
    extended_cost = np.repeat(base_cost, slots_per_hour, axis=1)[:, :total_slots]

    if n > base_cost.shape[0]:
        repeat_times = math.ceil(n / base_cost.shape[0])
        C = np.tile(extended_cost, (repeat_times, 1))[:n, :]
    else:
        C = extended_cost[:n, :]

    num_vars = n * time_slots
    bounds = Bounds([0] * num_vars, [1] * num_vars)
    integrality = np.ones(num_vars, dtype=bool)

    #中間要抓firebase裡的固定行程的起始結束時間
    #if是要從firebase抓資料

    fixed_data=get_tasks_from_firebase(uid, date_str)



    A_eq, b_eq = [], []
    for i in range(n):
        row = [0] * num_vars
        for j in range(time_slots):
            if j + durations[i] <= time_slots:
                row[i * time_slots + j] = 1
        A_eq.append(row)
        b_eq.append(1)

    # A_ub, b_ub = [], []
    # for p in range(n):
    #     for q in range(p + 1, n):
    #         for jp in range(time_slots):
    #             if jp + durations[p] > time_slots:
    #                 continue
    #             Sp = Ts_slots + jp
    #             for jq in range(time_slots):
    #                 if jq + durations[q] > time_slots:
    #                     continue
    #                 Sq = Ts_slots + jq
    #                 if Sp < Sq + durations[q] and Sq < Sp + durations[p]:
    #                     row = [0] * num_vars
    #                     row[p * time_slots + jp] = 1
    #                     row[q * time_slots + jq] = 1
    #                     A_ub.append(row)
    #                     b_ub.append(1)
    A_ub = [[0] * num_vars for _ in range(time_slots)] 
    b_ub = [1] * time_slots  # 預設每個 slot 的容量是 1

    # 【【【修改 b_ub 來反映固定行程】】】
    for s in range(time_slots):
        if (Ts_slots + s) in occupied_slots: #[IC]occupied_slots是被佔用的slot
            b_ub[s] = 0 # 這個 slot 已經被佔用，容量變為 0

    # 填充 A_ub 矩陣
    var_idx = 0
    for i in range(n):
        for j in range(time_slots):
            if j + durations[i] <= time_slots:
                # 變數 x_ij 會佔用從 j 到 j + durations[i] - 1 的時段
                for t in range(durations[i]):
                    slot_idx = j + t
                    A_ub[slot_idx][var_idx] = 1 # 標記變數 var_idx 會使用 slot_idx
            var_idx += 1
#主公式
    c = []
    for i in range(n):
        for j in range(time_slots):
            if j + durations[i] > time_slots:
                c.append(1e6)
            else:
                total_cost = sum(C[i][Ts_slots + j + t] for t in range(durations[i]))
                c.append(total_cost)
    c = np.array(c)

    constraints = [LinearConstraint(A_eq, b_eq, b_eq)]
    if A_ub:
        constraints.append(LinearConstraint(A_ub, [-np.inf] * len(b_ub), b_ub))

    res = milp(c=c, constraints=constraints, bounds=bounds, integrality=integrality)

    if res.success:
        print(f"\n✅ 最佳解找到！（Ts={Ts:.2f}, Te={Te:.2f}）")
        X = res.x.reshape((n, time_slots))
        scheduled_tasks = []

        for i in range(n):
            for j in range(time_slots):
                if X[i][j] > 0.5:
                    start = Ts_slots + j
                    end = start + durations[i]
                    sh, sm = divmod(start * 5, 60)
                    eh, em = divmod(end * 5, 60)
                    start_str = f"{sh:02}:{sm:02}"
                    end_str = f"{eh:02}:{em:02}"
                    print(f"任務{i + 1}: {start_str} - {end_str}")
                    # 取得對應的 intelligence（若缺則空字串）
                    intelligence = ""
                    if i < len(intelligent_analysis_results) and isinstance(intelligent_analysis_results[i], dict):
                        intelligence = intelligent_analysis_results[i].get("intelligence", "") or ""
                    #是否有抓到(待確認)
                    scheduled_tasks.append({
                        "index": i,
                        "startTime": start_str,
                        "endTime": end_str,
                        "desc": desc_list[i] if i < len(desc_list) else "",
                        "intelligence": intelligence
                    })
                    break

        print("\n💰 最小總成本:", np.dot(c, res.x))
        write_results_to_firebase(date_str, scheduled_tasks)#最後寫入應多加智能種類需要測試
        return scheduled_tasks
    else:
        print("\n❌ 找不到可行解。")
        return None
def get_occupied_slots(fixed_list, Ts, slots_per_hour):
    occupied = set()
    for event in fixed_list:
        start_h, start_m = map(int, event['startTime'].split(':'))
        end_h, end_m = map(int, event['endTime'].split(':'))
        
        # 轉換為相對於 Ts 的 slot 索引
        start_slot = int(((start_h + start_m / 60) - Ts) * slots_per_hour)
        end_slot = int(((end_h + end_m / 60) - Ts) * slots_per_hour)
        
        # 把區間內所有 slot 加進集合
        for s in range(start_slot, end_slot):
            occupied.add(s)
    return occupied
