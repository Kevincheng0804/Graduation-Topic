import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds

def schedule_tasks(Ts, Te, durations):
    # 每小時有12個5分鐘格子
    slots_per_hour = 12
    # 將小時轉為5分鐘格子
    Ts_slots = int(Ts * slots_per_hour)
    Te_slots = int(Te * slots_per_hour)
    time_slots = Te_slots - Ts_slots + 1
    n = len(durations)

    # 假設每天24小時，總共24*12=288個5分鐘格子
    total_slots = 24 * slots_per_hour
    # 成本矩陣：假設每小時成本均勻分佈到12個5分鐘格子
    base_cost = np.array([
        [6, 4, 3, 1, 5, 2, 4, 3, 1, 5, 2, 4, 3, 1, 5, 2, 4, 3, 1, 5, 2, 4, 3, 1],
        [3, 1, 2, 4, 3, 3, 1, 2, 4, 3, 3, 1, 2, 4, 3, 3, 1, 2, 4, 3, 3, 1, 2, 4],
        [4, 3, 1, 2, 5, 4, 3, 1, 2, 5, 4, 3, 1, 2, 5, 4, 3, 1, 2, 5, 4, 3, 1, 2]
    ])
    # 擴展成本到5分鐘格子
    extended_cost = np.repeat(base_cost, slots_per_hour, axis=1)[:, :total_slots]
    # 若任務數超過3，複製成本模板
    if n > 3:
        C = np.tile(extended_cost, (n, 1))[:n, :]
    else:
        C = extended_cost[:n, :]

    num_vars = n * time_slots
    bounds = Bounds(0.0, 1.0)  # since all variables are bounded between 0 and 1
    integrality = np.ones(num_vars, dtype=bool)

    # 每個任務只能選一個合法起始時間
    A_eq = []
    b_eq = []
    for i in range(n):
        row = [0]*num_vars
        for j in range(time_slots):
            if j + durations[i] <= time_slots:
                row[i*time_slots + j] = 1
        A_eq.append(row)
        b_eq.append(1)
    A_eq = np.array(A_eq)
    b_eq = np.array(b_eq)

    # 任務間不可重疊
    A_ub = []
    b_ub = []
    for p in range(n):
        for q in range(p+1, n):
            dp = durations[p]
            dq = durations[q]
            for jp in range(time_slots):
                if jp + dp > time_slots:
                    continue
                Sp = Ts_slots + jp
                for jq in range(time_slots):
                    if jq + dq > time_slots:
                        continue
                    Sq = Ts_slots + jq
                    if Sp < Sq + dq and Sq < Sp + dp:
                        row = [0]*num_vars
                        row[p*time_slots + jp] = 1
                        row[q*time_slots + jq] = 1
                        A_ub.append(row)
                        b_ub.append(1)
    A_ub = np.array(A_ub)
    b_ub = np.array(b_ub)

    # 目標函數：成本加總
    c = []
    for i in range(n):
        for j in range(time_slots):
            if j + durations[i] > time_slots:
                c.append(1e6)
            else:
                total_cost = sum(C[i][Ts_slots + j + t] for t in range(durations[i]))
                c.append(total_cost)
    c = np.array(c)

    # MILP 求解
    res = milp(
        c=c,
        constraints=[
            LinearConstraint(A_eq, b_eq[0], b_eq[0]),  # since all b_eq values are 1
            LinearConstraint(A_ub, -float('inf'), 1.0)  # since all b_ub values are 1
        ],
        bounds=bounds,
        integrality=integrality
    )

    if res.success:
        print(f"\n✅ 最佳解找到！（Ts={Ts:.2f}小時, Te={Te:.2f}小時）")
        X = res.x.reshape((n, time_slots))

        # 顯示排程結果
        print("\n📅 任務排程結果：")
        for i in range(n):
            for j in range(time_slots):
                if X[i][j] > 0.5:
                    start_slots = Ts_slots + j
                    end_slots = start_slots + durations[i]
                    # 轉回小時和分鐘
                    start_hour = start_slots // slots_per_hour
                    start_min = (start_slots % slots_per_hour) * 5
                    end_hour = end_slots // slots_per_hour
                    end_min = (end_slots % slots_per_hour) * 5
                    print(f"任務 {i+1}: {start_hour:02d}:{start_min:02d} - {end_hour:02d}:{end_min:02d}")
                    break

        # 計算佔用情況
        occupancy = np.zeros((n, time_slots))
        for i in range(n):
            for j in range(time_slots):
                if X[i][j] > 0.5:
                    for t in range(durations[i]):
                        occupancy[i][j + t] = 1
        print("\n📊 任務時間佔用情況（每列為任務，每欄為5分鐘格子）：")
        print(occupancy)

        print("\n💰 最小總成本:", np.dot(c, res.x))
    else:
        print("\n❌ 找不到可行解。")

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

    schedule_tasks(Ts, Te, durations)

except Exception as e:
    print("❌ 輸入錯誤：", e)