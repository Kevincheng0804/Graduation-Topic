import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds

def schedule_tasks(Ts, Te, durations):
    n = len(durations)
    time_slots = Te - Ts + 1

    # 假設成本矩陣C為每個任務對應24小時預設成本（實務上你可以自行擴充/自訂）
    base_cost = np.array([
        [6, 4, 3, 1, 5, 2, 4, 3, 1, 5, 2, 4, 3, 1, 5, 2, 4, 3, 1, 5, 2, 4, 3, 1],
        [3, 1, 2, 4, 3, 3, 1, 2, 4, 3, 3, 1, 2, 4, 3, 3, 1, 2, 4, 3, 3, 1, 2, 4],
        [4, 3, 1, 2, 5, 4, 3, 1, 2, 5, 4, 3, 1, 2, 5, 4, 3, 1, 2, 5, 4, 3, 1, 2]
    ])

    # 若任務超過3個，複製成本模板
    if n > 3:
        C = np.tile(base_cost, (n, 1))[:n, :]
    else:
        C = base_cost[:n, :]

    num_vars = n * time_slots
    bounds = Bounds([0]*num_vars, [1]*num_vars)
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
                Sp = Ts + jp
                for jq in range(time_slots):
                    if jq + dq > time_slots:
                        continue
                    Sq = Ts + jq
                    if Sp < Sq + dq and Sq < Sp + dp:
                        row = [0]*num_vars
                        row[p*time_slots + jp] = 1
                        row[q*time_slots + jq] = 1
                        A_ub.append(row)
                        b_ub.append(1)

    # 目標函數：成本加總（非法起始給高成本）
    c = []
    for i in range(n):
        for j in range(time_slots):
            if j + durations[i] > time_slots:
                c.append(1e6)
            else:
                total_cost = sum(C[i][Ts + j + t] for t in range(durations[i]))
                c.append(total_cost)
    c = np.array(c)

    A_eq = np.array(A_eq)
    b_eq = np.array(b_eq)
    A_ub = np.array(A_ub)
    b_ub = np.array(b_ub)

    # MILP 求解
    res = milp(
        c=c,
        constraints=[
            LinearConstraint(A_eq, b_eq, b_eq),  # type: ignore
            LinearConstraint(A_ub, np.full(len(b_ub), -np.inf), b_ub)  # type: ignore
        ],
        bounds=bounds,
        integrality=integrality
    )

    if res.success:
        print(f"\n✅ 最佳解找到！（Ts={Ts}, Te={Te}）")
        X = res.x.reshape((n, time_slots))
        print("🔢 任務起始排程（X）：")
        print(np.round(X))

        occupancy = np.zeros((n, time_slots))
        for i in range(n):
            for j in range(time_slots):
                if X[i][j] > 0.5:
                    for t in range(durations[i]):
                        occupancy[i][j + t] = 1
        print("\n📅 任務時間佔用情況（每列為任務，每欄為時間段）：")
        print(occupancy)

        print("\n💰 最小總成本:", np.dot(c, res.x))
    else:
        print("\n❌ 找不到可行解。")

# ----------- 使用者輸入部分 -----------

try:
    Ts = int(input("請輸入 Ts（起始時間格，0~23）："))
    Te = int(input("請輸入 Te（結束時間格，0~23）："))
    if not (0 <= Ts <= 23 and 0 <= Te <= 23 and Ts <= Te):
        raise ValueError("Ts/Te 輸入不合法")

    n = int(input("請輸入任務數量 n："))
    durations = []
    for i in range(n):
        d = int(input(f"請輸入任務 {i+1} 的持續時間（小時）："))
        durations.append(d)

    schedule_tasks(Ts, Te, durations)

except Exception as e:
    print("❌ 輸入錯誤：", e)
