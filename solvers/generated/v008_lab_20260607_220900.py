
def solve(input_text: str) -> list:
    try:
        eps = 1e-9
        rows_raw = []
        best = {}
        tasks_seen = {}
        for line_no, raw in enumerate(input_text.splitlines()):
            parts = raw.strip().split()
            if len(parts) < 4 or parts[0] == "task_id_list":
                continue
            task_key = parts[0].strip()
            courier_id = parts[1].strip()
            try:
                total_score = float(parts[2])
                willingness = float(parts[3])
            except Exception:
                continue
            tasks = tuple(t.strip() for t in task_key.split(",") if t.strip())
            if not tasks:
                continue
            task_count = len(tasks)
            expected_cost = willingness * total_score + (1.0 - willingness) * 100.0 * task_count
            benefit = 100.0 * task_count - expected_cost
            rec = [task_key, tasks, courier_id, expected_cost, benefit, total_score, willingness, task_count, line_no]
            key = (task_key, courier_id)
            old = best.get(key)
            if old is None or (expected_cost, line_no) < (old[3], old[8]):
                best[key] = rec
            for t in tasks:
                tasks_seen[t] = 1
        rows = list(best.values())
        if not rows:
            return []
        all_tasks = sorted(tasks_seen)
        by_task = {}
        by_key = {}
        by_courier = {}
        for i, row in enumerate(rows):
            by_key.setdefault(row[0], []).append(i)
            by_courier.setdefault(row[2], []).append(i)
            for t in row[1]:
                by_task.setdefault(t, []).append(i)
        for d in (by_task, by_key, by_courier):
            for key in d:
                d[key].sort(key=lambda i: (rows[i][3] / rows[i][7], rows[i][3], -rows[i][4], -rows[i][6], rows[i][0], rows[i][2]))

        def multi_cost(indices):
            if not indices:
                return 0.0
            tasks = rows[indices[0]][1]
            fail = 1.0
            weighted = 0.0
            denom = 0.0
            for idx in indices:
                p = rows[idx][6]
                if p < 0.0:
                    p = 0.0
                if p > 1.0:
                    p = 1.0
                fail *= (1.0 - p)
                weighted += p * rows[idx][5]
                denom += p
            done = 1.0 - fail
            accepted_score = weighted / denom if denom > eps else 100.0 * len(tasks)
            return done * accepted_score + (1.0 - done) * 100.0 * len(tasks)

        def row_gain(idx):
            return 100.0 * rows[idx][7] - multi_cost([idx])

        def clean(sol):
            used_c = {}
            covered = {}
            out = []
            for item in sol:
                if isinstance(item, int):
                    cand = [item]
                else:
                    cand = list(item)
                if not cand:
                    continue
                tasks = rows[cand[0]][1]
                bad = False
                seen_local = {}
                for idx in cand:
                    if idx < 0 or idx >= len(rows) or rows[idx][1] != tasks:
                        bad = True
                        break
                    c = rows[idx][2]
                    if c in used_c or c in seen_local:
                        bad = True
                        break
                    seen_local[c] = 1
                for t in tasks:
                    if t in covered:
                        bad = True
                        break
                if bad:
                    continue
                gain = 100.0 * len(tasks) - multi_cost(cand)
                if gain <= eps:
                    continue
                for idx in cand:
                    used_c[rows[idx][2]] = 1
                for t in tasks:
                    covered[t] = 1
                out.append(cand)
            return out

        def score_sol(sol):
            cleaned = clean(sol)
            covered = {}
            gain = 0.0
            for cand in cleaned:
                gain += 100.0 * len(rows[cand[0]][1]) - multi_cost(cand)
                for t in rows[cand[0]][1]:
                    covered[t] = 1
            return cleaned, gain, len(covered)

        def greedy(order):
            used_c = {}
            covered = {}
            sol = []
            for idx in order:
                row = rows[idx]
                if row[2] in used_c:
                    continue
                if any(t in covered for t in row[1]):
                    continue
                if row_gain(idx) <= eps:
                    continue
                sol.append([idx])
                used_c[row[2]] = 1
                for t in row[1]:
                    covered[t] = 1
            return sol

        def improve(sol):
            sol, best_gain, _ = score_sol(sol)
            for _ in range(3):
                changed = False
                used_c = {}
                covered = {}
                owner_c = {}
                owner_t = {}
                for pos, cand in enumerate(sol):
                    for idx in cand:
                        used_c[rows[idx][2]] = 1
                        owner_c[rows[idx][2]] = pos
                    for t in rows[cand[0]][1]:
                        covered[t] = 1
                        owner_t[t] = pos
                order = sorted(range(len(rows)), key=lambda i: (-row_gain(i), rows[i][3], rows[i][0], rows[i][2]))[:3500]
                for idx in order:
                    row = rows[idx]
                    conflicts = {}
                    if row[2] in owner_c:
                        conflicts[owner_c[row[2]]] = 1
                    for t in row[1]:
                        if t in owner_t:
                            conflicts[owner_t[t]] = 1
                    trial = []
                    for pos, cand in enumerate(sol):
                        if pos not in conflicts:
                            trial.append(cand)
                    trial.append([idx])
                    trial, gain, _ = score_sol(trial)
                    if gain > best_gain + eps:
                        sol = trial
                        best_gain = gain
                        changed = True
                        break
                if not changed:
                    break
            return sol

        orders = []
        orders.append(sorted(range(len(rows)), key=lambda i: (rows[i][3], -rows[i][4], rows[i][0], rows[i][2])))
        orders.append(sorted(range(len(rows)), key=lambda i: (rows[i][3] / rows[i][7], rows[i][3], -rows[i][4], rows[i][0], rows[i][2])))
        orders.append(sorted(range(len(rows)), key=lambda i: (-rows[i][4], rows[i][3], rows[i][0], rows[i][2])))
        orders.append(sorted(range(len(rows)), key=lambda i: (-rows[i][6], rows[i][3], -rows[i][4], rows[i][0], rows[i][2])))
        orders.append(sorted(range(len(rows)), key=lambda i: (rows[i][7], -rows[i][6], rows[i][3], rows[i][0], rows[i][2])))

        best_sol = []
        best_gain = -1.0
        for order in orders:
            sol = improve(greedy(order))
            sol, gain, _ = score_sol(sol)
            if gain > best_gain + eps:
                best_sol = sol
                best_gain = gain

        
        if len(all_tasks) <= 36:
            base = best_sol[:]
            for limit in (2, 3):
                trial = []
                used_extra = {}
                covered_keys = {}
                for cand in base:
                    task_key = rows[cand[0]][0]
                    if rows[cand[0]][7] == 1 and rows[cand[0]][6] < 0.62:
                        options = []
                        for idx in by_key.get(task_key, []):
                            if idx in cand:
                                options.append(idx)
                            elif rows[idx][2] not in used_extra and row_gain(idx) > -20.0:
                                options.append(idx)
                            if len(options) >= limit:
                                break
                        trial.append(options)
                        for idx in options:
                            used_extra[rows[idx][2]] = 1
                    else:
                        trial.append(cand)
                        for idx in cand:
                            used_extra[rows[idx][2]] = 1
                trial, gain, _ = score_sol(trial)
                if gain > best_gain + eps:
                    best_sol = trial
                    best_gain = gain
    

        result = []
        best_sol.sort(key=lambda cand: (rows[cand[0]][0].split(",")[0], rows[cand[0]][0], ",".join(rows[i][2] for i in cand)))
        for cand in best_sol:
            result.append((rows[cand[0]][0], [rows[i][2] for i in cand]))
        return result
    except Exception:
        return []
