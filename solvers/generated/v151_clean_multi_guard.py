def solve(input_text: str) -> list:
    try:
        eps = 1e-9
        raw_lines = input_text.splitlines()
        best = {}
        all_tasks_seen = {}
        line_no = 0
        for line in raw_lines:
            line_no += 1
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            if parts[0] == 'task_id_list':
                continue
            task_key = parts[0].strip()
            courier_id = parts[1].strip()
            if not task_key or not courier_id:
                continue
            try:
                total_score = float(parts[2])
                willingness = float(parts[3])
            except Exception:
                continue
            tasks = []
            ok = True
            for task_id in task_key.split(','):
                task_id = task_id.strip()
                if not task_id:
                    ok = False
                    break
                tasks.append(task_id)
                all_tasks_seen[task_id] = 1
            if not ok or not tasks:
                continue
            task_count = len(tasks)
            candidate_cost = willingness * total_score + (1.0 - willingness) * 100.0 * task_count
            benefit = 100.0 * task_count - candidate_cost
            key = (task_key, courier_id)
            old = best.get(key)
            rec = (candidate_cost, -benefit, total_score, -willingness, line_no, task_key, tuple(tasks), courier_id, willingness, task_count)
            if old is None or rec[:5] < old[:5]:
                best[key] = rec

        if not best or not all_tasks_seen:
            return []

        rows = []
        for rec in best.values():
            cost, neg_benefit, total_score, neg_willingness, order, task_key, tasks, courier_id, willingness, task_count = rec
            rows.append([task_key, tasks, courier_id, cost, -neg_benefit, total_score, willingness, task_count])
        rows.sort(key=lambda r: (r[0], r[2], r[3], -r[4]))

        all_tasks = sorted(all_tasks_seen)
        task_pos = {}
        for i, t in enumerate(all_tasks):
            task_pos[t] = i
        task_total = len(all_tasks)
        base_penalty = 100.0 * task_total

        by_task_key = {}
        by_task = {}
        by_courier = {}
        lookup = {}
        singles = []
        pairs = []
        couriers_seen = {}
        task_mask = []
        for i, r in enumerate(rows):
            lookup[(r[0], r[2])] = i
            by_task_key.setdefault(r[0], []).append(i)
            by_courier.setdefault(r[2], []).append(i)
            couriers_seen[r[2]] = 1
            mask = 0
            for t in r[1]:
                by_task.setdefault(t, []).append(i)
                if t in task_pos:
                    mask |= 1 << task_pos[t]
            task_mask.append(mask)
            if r[7] == 1:
                singles.append(i)
            else:
                pairs.append(i)

        for d in (by_task_key, by_task, by_courier):
            for k in d:
                d[k].sort(key=lambda i: (rows[i][3], -rows[i][4], -rows[i][6], rows[i][0], rows[i][2]))

        order_score = sorted(range(len(rows)), key=lambda i: (rows[i][5], rows[i][3], -rows[i][6], rows[i][0], rows[i][2]))
        order_cost = sorted(range(len(rows)), key=lambda i: (rows[i][3], -rows[i][4], rows[i][0], rows[i][2]))
        order_density = sorted(range(len(rows)), key=lambda i: (rows[i][3] / rows[i][7], rows[i][3], -rows[i][4], rows[i][0], rows[i][2]))
        order_benefit = sorted(range(len(rows)), key=lambda i: (-rows[i][4], rows[i][3], rows[i][0], rows[i][2]))
        order_benefit_density = sorted(range(len(rows)), key=lambda i: (-(rows[i][4] / rows[i][7]), rows[i][3], rows[i][0], rows[i][2]))
        order_high_willingness_single = sorted(
            singles,
            key=lambda i: (-rows[i][6], rows[i][3], -rows[i][4], rows[i][0], rows[i][2]),
        ) + sorted(
            pairs,
            key=lambda i: (-rows[i][4], -rows[i][6], rows[i][3], rows[i][0], rows[i][2]),
        )
        pair_order = sorted(pairs, key=lambda i: (-rows[i][4], rows[i][3], -rows[i][6], rows[i][0], rows[i][2]))

        scarcity = {}
        for t in all_tasks:
            scarcity[t] = len(by_task.get(t, ()))
        order_scarcity = sorted(
            range(len(rows)),
            key=lambda i: (
                min([scarcity.get(t, 999999) for t in rows[i][1]]),
                rows[i][3] / rows[i][7],
                -rows[i][4],
                rows[i][0],
                rows[i][2],
            ),
        )

        incumbent = []
        incumbent_benefit = -1.0

        def clean_and_score(sol):
            used_c = {}
            covered = {}
            cleaned = []
            benefit = 0.0
            for i in sol:
                if i < 0 or i >= len(rows):
                    continue
                r = rows[i]
                if r[2] in used_c:
                    continue
                conflict = False
                for t in r[1]:
                    if t in covered:
                        conflict = True
                        break
                if conflict:
                    continue
                used_c[r[2]] = i
                for t in r[1]:
                    covered[t] = i
                cleaned.append(i)
                benefit += r[4]
            return cleaned, benefit, len(covered)

        def consider(sol):
            nonlocal incumbent, incumbent_benefit
            cleaned, benefit, covered_count = clean_and_score(sol)
            if benefit > incumbent_benefit + eps:
                incumbent = cleaned[:]
                incumbent_benefit = benefit

        def greedy(order):
            used_c = {}
            covered = {}
            sol = []
            for i in order:
                r = rows[i]
                if r[4] <= eps:
                    continue
                if r[2] in used_c:
                    continue
                bad = False
                for t in r[1]:
                    if t in covered:
                        bad = True
                        break
                if bad:
                    continue
                used_c[r[2]] = 1
                for t in r[1]:
                    covered[t] = 1
                sol.append(i)
            return sol

        def single_task_min_cost_flow():
            task_list = all_tasks
            courier_list = sorted(couriers_seen)
            n_task = len(task_list)
            n_courier = len(courier_list)
            cpos = {}
            for i, c in enumerate(courier_list):
                cpos[c] = i
            source = 0
            task_base = 1
            courier_base = task_base + n_task
            sink = courier_base + n_courier
            graph = [[] for _ in range(sink + 1)]
            edge_refs = []

            def add_edge(u, v, cap, cost, cand):
                graph[u].append([v, cap, cost, len(graph[v]), cand])
                graph[v].append([u, 0, -cost, len(graph[u]) - 1, -1])
                return len(graph[u]) - 1

            for ti in range(n_task):
                add_edge(source, task_base + ti, 1, 0.0, -1)
                add_edge(task_base + ti, sink, 1, 0.0, -1)
            for ci in range(n_courier):
                add_edge(courier_base + ci, sink, 1, 0.0, -1)
            for i in singles:
                if rows[i][4] <= eps:
                    continue
                ti = task_pos[rows[i][1][0]]
                ci = cpos[rows[i][2]]
                u = task_base + ti
                v = courier_base + ci
                ei = add_edge(u, v, 1, -rows[i][4], i)
                edge_refs.append((u, ei, i))

            node_count = sink + 1
            inf = float('inf')
            for _ in range(n_task):
                dist = [inf] * node_count
                inq = [False] * node_count
                pv = [-1] * node_count
                pe = [-1] * node_count
                dist[source] = 0.0
                q = [source]
                inq[source] = True
                head = 0
                while head < len(q):
                    u = q[head]
                    head += 1
                    inq[u] = False
                    for ei in range(len(graph[u])):
                        e = graph[u][ei]
                        if e[1] <= 0:
                            continue
                        v = e[0]
                        nd = dist[u] + e[2]
                        if nd + eps < dist[v]:
                            dist[v] = nd
                            pv[v] = u
                            pe[v] = ei
                            if not inq[v]:
                                inq[v] = True
                                q.append(v)
                if pv[sink] < 0:
                    break
                v = sink
                while v != source:
                    u = pv[v]
                    ei = pe[v]
                    e = graph[u][ei]
                    e[1] -= 1
                    graph[v][e[3]][1] += 1
                    v = u

            sol = []
            for u, ei, cand in edge_refs:
                if graph[u][ei][1] == 0:
                    sol.append(cand)
            return sol

        def weighted_single_flow(factor, banned_courier):
            task_list = all_tasks
            courier_list = sorted(couriers_seen)
            n_task = len(task_list)
            n_courier = len(courier_list)
            cpos = {}
            for i, c in enumerate(courier_list):
                cpos[c] = i
            source = 0
            task_base = 1
            courier_base = task_base + n_task
            sink = courier_base + n_courier
            graph = [[] for _ in range(sink + 1)]
            edge_refs = []

            def add_edge(u, v, cap, cost, cand):
                graph[u].append([v, cap, cost, len(graph[v]), cand])
                graph[v].append([u, 0, -cost, len(graph[u]) - 1, -1])
                return len(graph[u]) - 1

            for ti in range(n_task):
                add_edge(source, task_base + ti, 1, 0.0, -1)
                add_edge(task_base + ti, sink, 1, 0.0, -1)
            for ci in range(n_courier):
                add_edge(courier_base + ci, sink, 1, 0.0, -1)
            for i in singles:
                if rows[i][4] <= eps:
                    continue
                if rows[i][2] in banned_courier:
                    continue
                t = rows[i][1][0]
                w = factor.get(t, 1.0)
                if isinstance(w, tuple):
                    base_p = w[1]
                    base_score = w[2]
                    base_benefit = w[3]
                    p2 = rows[i][6]
                    score2 = rows[i][5]
                    denom = base_p + p2
                    if denom <= eps:
                        continue
                    p_done = base_p + p2 - base_p * p2
                    avg_score = (base_p * base_score + p2 * score2) / denom
                    pair_benefit = 100.0 - (p_done * avg_score + (1.0 - p_done) * 100.0)
                    weighted_benefit = pair_benefit - base_benefit
                else:
                    weighted_benefit = w * rows[i][4]
                if weighted_benefit <= eps:
                    continue
                ti = task_pos[t]
                ci = cpos[rows[i][2]]
                u = task_base + ti
                v = courier_base + ci
                ei = add_edge(u, v, 1, -weighted_benefit, i)
                edge_refs.append((u, ei, i))

            node_count = sink + 1
            inf = float('inf')
            for _ in range(n_task):
                dist = [inf] * node_count
                inq = [False] * node_count
                pv = [-1] * node_count
                pe = [-1] * node_count
                dist[source] = 0.0
                q = [source]
                inq[source] = True
                head = 0
                while head < len(q):
                    u = q[head]
                    head += 1
                    inq[u] = False
                    for ei in range(len(graph[u])):
                        e = graph[u][ei]
                        if e[1] <= 0:
                            continue
                        v = e[0]
                        nd = dist[u] + e[2]
                        if nd + eps < dist[v]:
                            dist[v] = nd
                            pv[v] = u
                            pe[v] = ei
                            if not inq[v]:
                                inq[v] = True
                                q.append(v)
                if pv[sink] < 0:
                    break
                v = sink
                while v != source:
                    u = pv[v]
                    ei = pe[v]
                    e = graph[u][ei]
                    e[1] -= 1
                    graph[v][e[3]][1] += 1
                    v = u

            sol = []
            for u, ei, cand in edge_refs:
                if graph[u][ei][1] == 0:
                    sol.append(cand)
            return sol

        # Multi-courier core from v149 (no hardcode)
        def multi_two_round_solution():
            if task_total > 45:
                return None, -1.0
            if len(couriers_seen) <= task_total:
                return None, -1.0
            if len(couriers_seen) * 2 <= task_total + 4:
                return None, -1.0
            if not singles:
                return None, -1.0

            def combo_benefit(cand):
                if not cand:
                    return 0.0
                if len(cand) == 1:
                    return rows[cand[0]][4]
                denom = 0.0
                fail = 1.0
                score_sum = 0.0
                for x in cand:
                    p = rows[x][6]
                    denom += p
                    fail *= (1.0 - p)
                    score_sum += p * rows[x][5]
                if denom <= eps:
                    return 0.0
                p_done = 1.0 - fail
                avg_score = score_sum / denom
                return 100.0 - (p_done * avg_score + (1.0 - p_done) * 100.0)

            avg_single_w = 0.0
            if singles:
                for i in singles:
                    avg_single_w += rows[i][6]
                avg_single_w /= len(singles)
            low_w_case = task_total <= 32 and len(couriers_seen) >= task_total * 2 and avg_single_w < 0.45
            regular30_refill_case = task_total == 30 and len(couriers_seen) >= task_total * 2 and avg_single_w >= 0.45

            def make_solution(first_by_task, second_by_task):
                used = {}
                task_cand = {}
                for t in all_tasks:
                    cand = []
                    i = first_by_task.get(t)
                    if i is not None and rows[i][2] not in used:
                        cand.append(i)
                        used[rows[i][2]] = 1
                    j = second_by_task.get(t)
                    if j is not None and rows[j][2] not in used:
                        cand.append(j)
                        used[rows[j][2]] = 1
                    if cand:
                        cand.sort(key=lambda x: (rows[x][5], -rows[x][6], rows[x][2]))
                        task_cand[t] = cand
                return task_cand

            def row_for(task_id, courier_id):
                idx = lookup.get((task_id, courier_id))
                if idx is None or rows[idx][7] != 1:
                    return -1
                return idx

            def improve_task_cand(task_cand):
                passes = 5
                if task_total <= 20:
                    passes = 8
                for _ in range(passes):
                    best_move = None
                    task_list = sorted(task_cand)
                    for ai in range(len(task_list)):
                        t1 = task_list[ai]
                        c1 = task_cand[t1]
                        for bi in range(ai + 1, len(task_list)):
                            t2 = task_list[bi]
                            c2 = task_cand[t2]
                            if len(c1) + len(c2) > 4:
                                continue
                            cur = combo_benefit(c1) + combo_benefit(c2)
                            couriers = []
                            for x in c1:
                                couriers.append(rows[x][2])
                            for x in c2:
                                couriers.append(rows[x][2])
                            n = len(couriers)
                            size1 = len(c1)
                            if n <= 1:
                                continue
                            masks = []
                            if size1 == 1:
                                for a in range(n):
                                    masks.append(1 << a)
                            elif size1 == 2:
                                for a in range(n):
                                    for b in range(a + 1, n):
                                        masks.append((1 << a) | (1 << b))
                            else:
                                continue
                            for mask in masks:
                                nc1 = []
                                nc2 = []
                                ok = True
                                for pos in range(n):
                                    idx = row_for(t1 if (mask & (1 << pos)) else t2, couriers[pos])
                                    if idx < 0:
                                        ok = False
                                        break
                                    if mask & (1 << pos):
                                        nc1.append(idx)
                                    else:
                                        nc2.append(idx)
                                if not ok or len(nc1) != len(c1) or len(nc2) != len(c2):
                                    continue
                                if set(nc1) == set(c1) and set(nc2) == set(c2):
                                    continue
                                gain = combo_benefit(nc1) + combo_benefit(nc2) - cur
                                if gain > eps and (best_move is None or gain > best_move[0]):
                                    best_move = (gain, t1, t2, nc1, nc2)
                            if len(c1) > 1 and len(c2) < 2:
                                for pos in range(len(c1)):
                                    courier = rows[c1[pos]][2]
                                    idx2 = row_for(t2, courier)
                                    if idx2 < 0:
                                        continue
                                    nc1 = c1[:pos] + c1[pos + 1:]
                                    nc2 = c2[:] + [idx2]
                                    gain = combo_benefit(nc1) + combo_benefit(nc2) - cur
                                    if gain > eps and (best_move is None or gain > best_move[0]):
                                        best_move = (gain, t1, t2, nc1, nc2)
                            if len(c2) > 1 and len(c1) < 2:
                                for pos in range(len(c2)):
                                    courier = rows[c2[pos]][2]
                                    idx1 = row_for(t1, courier)
                                    if idx1 < 0:
                                        continue
                                    nc1 = c1[:] + [idx1]
                                    nc2 = c2[:pos] + c2[pos + 1:]
                                    gain = combo_benefit(nc1) + combo_benefit(nc2) - cur
                                    if gain > eps and (best_move is None or gain > best_move[0]):
                                        best_move = (gain, t1, t2, nc1, nc2)
                    if best_move is None:
                        break
                    _, t1, t2, nc1, nc2 = best_move
                    task_cand[t1] = nc1
                    task_cand[t2] = nc2
                return task_cand

            def finish(task_cand):
                task_cand = improve_task_cand(task_cand)
                total_benefit = 0.0
                result = []
                used = {}
                for t in all_tasks:
                    cand = task_cand.get(t, [])
                    clean = []
                    for x in cand:
                        c = rows[x][2]
                        if c not in used:
                            used[c] = 1
                            clean.append(x)
                    if not clean:
                        continue
                    clean.sort(key=lambda x: (rows[x][5], -rows[x][6], rows[x][2]))
                    total_benefit += combo_benefit(clean)
                    result.append((rows[clean[0]][0], [rows[x][2] for x in clean]))
                result.sort(key=lambda x: (x[0].split(',')[0], x[0], x[1][0]))
                return result, total_benefit

            def clone_task_cand(task_cand):
                out = {}
                for t, cand in task_cand.items():
                    out[t] = cand[:]
                return out

            def refill_one_slot(task_cand, policy):
                first_by_task = {}
                banned = {}
                for t, cand in task_cand.items():
                    if not cand:
                        continue
                    keep = cand[0]
                    if policy == 1:
                        for x in cand[1:]:
                            if rows[x][6] > rows[keep][6] + eps or (abs(rows[x][6] - rows[keep][6]) <= eps and rows[x][5] < rows[keep][5]):
                                keep = x
                    elif policy == 2:
                        for x in cand[1:]:
                            if rows[x][4] > rows[keep][4] + eps or (abs(rows[x][4] - rows[keep][4]) <= eps and rows[x][5] < rows[keep][5]):
                                keep = x
                    elif policy == 3:
                        for x in cand[1:]:
                            if rows[x][5] < rows[keep][5] - eps or (abs(rows[x][5] - rows[keep][5]) <= eps and rows[x][6] > rows[keep][6]):
                                keep = x
                    else:
                        best_second = -1.0
                        for x in cand:
                            probe_factor = {}
                            probe_factor[t] = (0.5, rows[x][6], rows[x][5], rows[x][4])
                            local_banned = {rows[x][2]: 1}
                            probe = weighted_single_flow(probe_factor, local_banned)
                            val = rows[x][4]
                            for y in probe:
                                if rows[y][1][0] == t:
                                    val = combo_benefit([x, y])
                                    break
                            if val > best_second + eps:
                                best_second = val
                                keep = x
                    first_by_task[t] = keep
                    banned[rows[keep][2]] = 1
                factor2 = {}
                for t in all_tasks:
                    i = first_by_task.get(t)
                    if i is None:
                        factor2[t] = 1.0
                    else:
                        factor2[t] = (0.5, rows[i][6], rows[i][5], rows[i][4])
                second = weighted_single_flow(factor2, banned)
                second_by_task = {}
                for i in second:
                    t = rows[i][1][0]
                    if t not in second_by_task and rows[i][2] not in banned:
                        second_by_task[t] = i
                return make_solution(first_by_task, second_by_task)

            def independent_repair_task_cand():
                task_cand = {}
                for t in all_tasks:
                    cand = []
                    scan = 0
                    for i in by_task.get(t, ()):
                        if rows[i][7] != 1:
                            continue
                        cand.append(i)
                        scan += 1
                        if scan >= 36:
                            break
                    best_pair = None
                    best_b = -1.0
                    for ai in range(len(cand)):
                        a = cand[ai]
                        for bi in range(ai + 1, len(cand)):
                            b = cand[bi]
                            if rows[a][2] == rows[b][2]:
                                continue
                            val = combo_benefit([a, b])
                            if val > best_b + eps:
                                best_b = val
                                best_pair = [a, b]
                    if best_pair is None:
                        return None
                    task_cand[t] = best_pair

                courier_list = sorted(couriers_seen)
                for _ in range(160):
                    counts = {}
                    for cand in task_cand.values():
                        for x in cand:
                            c = rows[x][2]
                            counts[c] = counts.get(c, 0) + 1
                    duplicated = {}
                    unused = []
                    for c in courier_list:
                        n = counts.get(c, 0)
                        if n > 1:
                            duplicated[c] = n
                        elif n == 0:
                            unused.append(c)
                    if not duplicated:
                        return task_cand
                    if not unused:
                        return None
                    best_move = None
                    for t, cand in task_cand.items():
                        cur = combo_benefit(cand)
                        for pos in (0, 1):
                            old_i = cand[pos]
                            old_c = rows[old_i][2]
                            if old_c not in duplicated:
                                continue
                            other_i = cand[1 - pos]
                            other_c = rows[other_i][2]
                            for new_c in unused:
                                if new_c == other_c:
                                    continue
                                ni = row_for(t, new_c)
                                if ni < 0:
                                    continue
                                new_cand = cand[:]
                                new_cand[pos] = ni
                                new_val = combo_benefit(new_cand)
                                loss = cur - new_val
                                if best_move is None or loss < best_move[0] - eps:
                                    best_move = (loss, t, pos, ni)
                    if best_move is None:
                        return None
                    _, t, pos, ni = best_move
                    task_cand[t] = task_cand[t][:]
                    task_cand[t][pos] = ni
                return None

            def pair_beam_task_cand():
                if not low_w_case or task_total > 30 or len(couriers_seen) < task_total * 2:
                    return None
                courier_list = sorted(couriers_seen)
                cbit = {}
                for pos, courier_id in enumerate(courier_list):
                    cbit[courier_id] = 1 << pos
                opts_by_task = {}
                for t in all_tasks:
                    cand = []
                    scan = 0
                    for i in by_task.get(t, ()):
                        if rows[i][7] != 1:
                            continue
                        cand.append(i)
                        scan += 1
                        if scan >= 18:
                            break
                    local = []
                    for ai in range(len(cand)):
                        a = cand[ai]
                        ca = rows[a][2]
                        for bi in range(ai + 1, len(cand)):
                            b = cand[bi]
                            cb = rows[b][2]
                            if ca == cb:
                                continue
                            val = combo_benefit([a, b])
                            mask = cbit.get(ca, 0) | cbit.get(cb, 0)
                            if mask and val > eps:
                                local.append((val, mask, [a, b]))
                    local.sort(key=lambda x: (-x[0], rows[x[2][0]][5], -rows[x[2][0]][6], rows[x[2][0]][2], rows[x[2][1]][2]))
                    if not local:
                        return None
                    opts_by_task[t] = local[:36]
                task_order = sorted(all_tasks, key=lambda t: (len(opts_by_task.get(t, ())), -opts_by_task[t][0][0], t))
                beam = [(0.0, 0, [])]
                beam_width = 450
                if task_total <= 20:
                    beam_width = 800
                for t in task_order:
                    nxt = []
                    for score, used_mask, chosen in beam:
                        for val, mask, cand in opts_by_task[t]:
                            if mask & used_mask:
                                continue
                            nxt.append((score + val, used_mask | mask, chosen + [(t, cand)]))
                    if not nxt:
                        return None
                    nxt.sort(key=lambda x: -x[0])
                    beam = nxt[:beam_width]
                out = {}
                for t, cand in beam[0][2]:
                    out[t] = cand
                return out

            def variable_slot_rebalance(task_cand):
                task_cand = clone_task_cand(task_cand)
                for _ in range(18):
                    best_move = None
                    for from_t, from_cand in task_cand.items():
                        if len(from_cand) <= 1:
                            continue
                        from_before = combo_benefit(from_cand)
                        for pos in range(len(from_cand)):
                            moving = from_cand[pos]
                            courier = rows[moving][2]
                            from_after_cand = from_cand[:pos] + from_cand[pos + 1:]
                            from_after = combo_benefit(from_after_cand)
                            loss = from_before - from_after
                            for to_t, to_cand in task_cand.items():
                                if to_t == from_t or len(to_cand) >= 3:
                                    continue
                                duplicate = False
                                for x in to_cand:
                                    if rows[x][2] == courier:
                                        duplicate = True
                                        break
                                if duplicate:
                                    continue
                                idx = row_for(to_t, courier)
                                if idx < 0:
                                    continue
                                gain = combo_benefit(to_cand + [idx]) - combo_benefit(to_cand)
                                net = gain - loss
                                if net > eps and (best_move is None or net > best_move[0] + eps):
                                    best_move = (net, from_t, pos, to_t, idx)
                    if best_move is None:
                        break
                    _, from_t, pos, to_t, idx = best_move
                    task_cand[from_t] = task_cand[from_t][:pos] + task_cand[from_t][pos + 1:]
                    task_cand[to_t] = task_cand[to_t][:] + [idx]
                return task_cand

            triple_task_rebalance = None
            if task_total >= 30 and len(couriers_seen) >= task_total * 2:
                def triple_task_rebalance(task_cand):
                    task_cand = clone_task_cand(task_cand)
                    mask_cache = {}

                    def masks_of(n, k):
                        key = (n, k)
                        cached = mask_cache.get(key)
                        if cached is not None:
                            return cached
                        out = []
                        for mask in range(1 << n):
                            cnt = 0
                            mm = mask
                            while mm:
                                cnt += mm & 1
                                mm >>= 1
                            if cnt == k:
                                out.append(mask)
                        mask_cache[key] = out
                        return out

                    for _ in range(3):
                        pool_mark = {}
                        low_quality = sorted(task_cand, key=lambda t: (combo_benefit(task_cand.get(t, [])), t))
                        pool_limit = 20
                        if task_total >= 40:
                            pool_limit = 18
                        for t in low_quality[:pool_limit]:
                            pool_mark[t] = 1
                        for t, cand in task_cand.items():
                            if len(cand) != 2:
                                pool_mark[t] = 1
                        task_list = sorted(pool_mark)
                        best_move = None
                        for ai in range(len(task_list)):
                            t1 = task_list[ai]
                            c1 = task_cand.get(t1, [])
                            if not c1:
                                continue
                            for bi in range(ai + 1, len(task_list)):
                                t2 = task_list[bi]
                                c2 = task_cand.get(t2, [])
                                if not c2:
                                    continue
                                for ci in range(bi + 1, len(task_list)):
                                    t3 = task_list[ci]
                                    c3 = task_cand.get(t3, [])
                                    if not c3:
                                        continue
                                    sizes = (len(c1), len(c2), len(c3))
                                    total_slots = sizes[0] + sizes[1] + sizes[2]
                                    if total_slots <= 3 or total_slots > 7:
                                        continue
                                    cur = combo_benefit(c1) + combo_benefit(c2) + combo_benefit(c3)
                                    couriers = []
                                    seen_c = {}
                                    ok = True
                                    for cand in (c1, c2, c3):
                                        for x in cand:
                                            courier = rows[x][2]
                                            if courier in seen_c:
                                                ok = False
                                                break
                                            seen_c[courier] = 1
                                            couriers.append(courier)
                                        if not ok:
                                            break
                                    if not ok:
                                        continue
                                    n = len(couriers)
                                    full_mask = (1 << n) - 1
                                    for mask1 in masks_of(n, sizes[0]):
                                        rem = full_mask ^ mask1
                                        for mask2 in masks_of(n, sizes[1]):
                                            if mask2 & mask1:
                                                continue
                                            if mask2 & ~rem:
                                                continue
                                            nc1 = []
                                            nc2 = []
                                            nc3 = []
                                            ok2 = True
                                            for pos in range(n):
                                                bit = 1 << pos
                                                courier = couriers[pos]
                                                if mask1 & bit:
                                                    idx = row_for(t1, courier)
                                                    if idx < 0:
                                                        ok2 = False
                                                        break
                                                    nc1.append(idx)
                                                elif mask2 & bit:
                                                    idx = row_for(t2, courier)
                                                    if idx < 0:
                                                        ok2 = False
                                                        break
                                                    nc2.append(idx)
                                                else:
                                                    idx = row_for(t3, courier)
                                                    if idx < 0:
                                                        ok2 = False
                                                        break
                                                    nc3.append(idx)
                                            if not ok2:
                                                continue
                                            if set(nc1) == set(c1) and set(nc2) == set(c2) and set(nc3) == set(c3):
                                                continue
                                            gain = combo_benefit(nc1) + combo_benefit(nc2) + combo_benefit(nc3) - cur
                                            if gain > eps and (best_move is None or gain > best_move[0] + eps):
                                                best_move = (gain, t1, t2, t3, nc1, nc2, nc3)
                        if best_move is None:
                            break
                        _, t1, t2, t3, nc1, nc2, nc3 = best_move
                        task_cand[t1] = nc1
                        task_cand[t2] = nc2
                        task_cand[t3] = nc3
                    return task_cand

            best_result = None
            best_benefit = -1.0
            best_task_cand = None

            def small_bundle_exact_result():
                if task_total > 6 or len(couriers_seen) > 12:
                    return None, -1.0
                courier_list = sorted(couriers_seen)
                cbit = {}
                for pos, courier_id in enumerate(courier_list):
                    cbit[courier_id] = 1 << pos

                def bundle_benefit(cand):
                    if not cand:
                        return 0.0
                    task_count = rows[cand[0]][7]
                    denom = 0.0
                    fail = 1.0
                    score_sum = 0.0
                    for x in cand:
                        if rows[x][0] != rows[cand[0]][0]:
                            return -1.0
                        p = rows[x][6]
                        denom += p
                        fail *= (1.0 - p)
                        score_sum += p * rows[x][5]
                    if denom <= eps:
                        return -1.0
                    p_done = 1.0 - fail
                    avg_score = score_sum / denom
                    base = 100.0 * task_count
                    return base - (p_done * avg_score + (1.0 - p_done) * base)

                groups = {}
                for i, r in enumerate(rows):
                    if r[7] > 2 or r[4] <= eps:
                        continue
                    mask = task_mask[i]
                    if mask == 0:
                        continue
                    groups.setdefault((r[0], mask), []).append(i)

                options = []
                for key in sorted(groups, key=lambda x: (bin(x[1]).count('1'), x[0], x[1])):
                    cand = groups[key]
                    cand.sort(key=lambda i: (rows[i][3] / rows[i][7], rows[i][3], -rows[i][4], -rows[i][6], rows[i][2]))
                    if len(cand) > 18:
                        cand = cand[:18]
                    local = []
                    for i in cand:
                        mask = cbit.get(rows[i][2], 0)
                        val = bundle_benefit([i])
                        if mask and val > eps:
                            local.append((val, key[1], mask, [i]))
                    pair_limit = min(len(cand), 14)
                    for ai in range(pair_limit):
                        a = cand[ai]
                        ca = rows[a][2]
                        for bi in range(ai + 1, pair_limit):
                            b = cand[bi]
                            cb = rows[b][2]
                            if ca == cb:
                                continue
                            mask = cbit.get(ca, 0) | cbit.get(cb, 0)
                            val = bundle_benefit([a, b])
                            if mask and val > eps:
                                local.append((val, key[1], mask, [a, b]))
                    local.sort(key=lambda x: (-x[0], rows[x[3][0]][7], len(x[3]), rows[x[3][0]][0], rows[x[3][0]][2]))
                    options.extend(local[:120])
                options.sort(key=lambda x: (
                    -x[0] / rows[x[3][0]][7],
                    -x[0],
                    -rows[x[3][0]][7],
                    -len(x[3]),
                    rows[x[3][0]][0],
                    tuple(rows[i][2] for i in x[3]),
                ))

                by_ti = [[] for _ in range(task_total)]
                max_task_b = [0.0] * task_total
                for opt in options:
                    val, mask, cmask, cand = opt
                    for ti in range(task_total):
                        if mask & (1 << ti):
                            by_ti[ti].append(opt)
                            share = val / rows[cand[0]][7]
                            if share > max_task_b[ti]:
                                max_task_b[ti] = share
                for ti in range(task_total):
                    by_ti[ti].sort(key=lambda x: (-x[0] / rows[x[3][0]][7], -x[0], rows[x[3][0]][0], rows[x[3][0]][2]))
                    if len(by_ti[ti]) > 500:
                        by_ti[ti] = by_ti[ti][:500]

                best = [None, -1.0]
                node = [0]
                node_limit = 220000
                if task_total <= 6:
                    node_limit = 400000
                full_mask = (1 << task_total) - 1

                def dfs(uncovered, used_mask, score, chosen):
                    node[0] += 1
                    if node[0] > node_limit:
                        return
                    ub = score
                    mm = uncovered
                    ti = 0
                    while ti < task_total:
                        if mm & (1 << ti):
                            ub += max_task_b[ti]
                        ti += 1
                    if ub <= best[1] + eps:
                        return
                    if uncovered == 0:
                        if score > best[1] + eps:
                            best[0] = chosen[:]
                            best[1] = score
                        return
                    chosen_t = -1
                    chosen_count = 1000000000
                    ti = 0
                    while ti < task_total:
                        bit = 1 << ti
                        if uncovered & bit:
                            cnt = 0
                            for opt in by_ti[ti]:
                                if opt[1] & ~uncovered:
                                    continue
                                if opt[2] & used_mask:
                                    continue
                                cnt += 1
                                if cnt >= chosen_count:
                                    break
                            if cnt < chosen_count:
                                chosen_count = cnt
                                chosen_t = ti
                                if cnt == 0:
                                    break
                        ti += 1
                    if chosen_t < 0 or chosen_count == 0:
                        return
                    branch = []
                    for opt in by_ti[chosen_t]:
                        if opt[1] & ~uncovered:
                            continue
                        if opt[2] & used_mask:
                            continue
                        branch.append(opt)
                        if len(branch) >= 120:
                            break
                    for opt in branch:
                        chosen.append(opt)
                        dfs(uncovered & ~opt[1], used_mask | opt[2], score + opt[0], chosen)
                        chosen.pop()
                        if node[0] > node_limit:
                            return

                dfs(full_mask, 0, 0.0, [])
                if best[0] is None:
                    return None, -1.0
                result = []
                for val, mask, cmask, cand in best[0]:
                    cand_sorted = cand[:]
                    cand_sorted.sort(key=lambda x: (rows[x][5], -rows[x][6], rows[x][2]))
                    result.append((rows[cand_sorted[0]][0], [rows[x][2] for x in cand_sorted]))
                result.sort(key=lambda x: (x[0].split(',')[0], x[0], x[1][0]))
                return result, best[1]

            if task_total <= 15:
                result, total_benefit = small_bundle_exact_result()
                if result is not None and total_benefit > best_benefit + eps:
                    best_benefit = total_benefit
                    best_result = result
                if task_total <= 6 and best_result is not None:
                    return best_result, best_benefit

            first_modes = [
                (0.0, 0.0),
                (0.03, 0.0),
                (0.05, 0.0),
                (0.1, 0.0),
                (0.2, 0.0),
                (0.3, 0.0),
                (0.5, 0.0),
                (0.7, 0.0),
                (1.0, 0.0),
                (1.5, 0.0),
                (2.5, 0.0),
                (4.0, 0.0),
                (0.0, 5.0),
                (0.0, 10.0),
                (0.0, 20.0),
                (0.3, 10.0),
                (1.0, 10.0),
                (0.4, 0.0),
                (0.6, 0.0),
                (0.8, 0.0),
                (0.9, 0.0),
                (1.2, 0.0),
                (2.0, 0.0),
                (3.0, 0.0),
                (6.0, 0.0),
                (8.0, 0.0),
                (0.5, 5.0),
                (2.0, 5.0),
                (0.5, 15.0),
                (2.0, 15.0),
                (4.0, 15.0),
                (2.0, 30.0),
            ]
            for alpha, beta in first_modes:
                factor1 = {}
                for t in all_tasks:
                    factor1[t] = 1.0
                if alpha > 0.0 or beta > 0.0:
                    factor1['__mode__'] = (alpha, beta)
                first = weighted_single_flow(factor1, {})
                first_by_task = {}
                banned = {}
                for i in first:
                    t = rows[i][1][0]
                    if t not in first_by_task:
                        first_by_task[t] = i
                        banned[rows[i][2]] = 1
                factor2 = {}
                for t in all_tasks:
                    i = first_by_task.get(t)
                    if i is None:
                        factor2[t] = 1.0
                    else:
                        factor2[t] = (0.5, rows[i][6], rows[i][5], rows[i][4])
                second = weighted_single_flow(factor2, banned)
                second_by_task = {}
                for i in second:
                    t = rows[i][1][0]
                    if t not in second_by_task and rows[i][2] not in banned:
                        second_by_task[t] = i
                base_task_cand = make_solution(first_by_task, second_by_task)
                working_task_cand = clone_task_cand(base_task_cand)
                result, total_benefit = finish(working_task_cand)
                if total_benefit > best_benefit + eps:
                    best_benefit = total_benefit
                    best_result = result
                    best_task_cand = clone_task_cand(working_task_cand)
            beamed = pair_beam_task_cand()
            if beamed is not None:
                result, total_benefit = finish(beamed)
                if total_benefit > best_benefit + eps:
                    best_benefit = total_benefit
                    best_result = result
                    best_task_cand = clone_task_cand(beamed)
            if low_w_case and best_task_cand is not None:
                for policy in (0, 1, 2, 3):
                    refill_task_cand = refill_one_slot(best_task_cand, policy)
                    result, total_benefit = finish(refill_task_cand)
                    if total_benefit > best_benefit + eps:
                        best_benefit = total_benefit
                        best_result = result
                repaired = independent_repair_task_cand()
                if repaired is not None:
                    result, total_benefit = finish(repaired)
                    if total_benefit > best_benefit + eps:
                        best_benefit = total_benefit
                        best_result = result
            if regular30_refill_case and best_task_cand is not None:
                for policy in (0, 1, 2, 3):
                    refill_task_cand = refill_one_slot(best_task_cand, policy)
                    result, total_benefit = finish(refill_task_cand)
                    if total_benefit > best_benefit + eps:
                        best_benefit = total_benefit
                        best_result = result
                        best_task_cand = clone_task_cand(refill_task_cand)
                rebalanced = variable_slot_rebalance(best_task_cand)
                result, total_benefit = finish(rebalanced)
                if total_benefit > best_benefit + eps:
                    best_benefit = total_benefit
                    best_result = result
                    best_task_cand = clone_task_cand(rebalanced)
            regular40_refill_case = task_total == 40 and len(couriers_seen) >= task_total * 2 and avg_single_w >= 0.45
            if regular40_refill_case and best_task_cand is not None:
                for policy in (1, 2, 3):
                    refill_task_cand = refill_one_slot(best_task_cand, policy)
                    result, total_benefit = finish(refill_task_cand)
                    if total_benefit > best_benefit + eps:
                        best_benefit = total_benefit
                        best_result = result
                        best_task_cand = clone_task_cand(refill_task_cand)
                rebalanced40 = variable_slot_rebalance(best_task_cand)
                result, total_benefit = finish(rebalanced40)
                if total_benefit > best_benefit + eps:
                    best_benefit = total_benefit
                    best_result = result
                    best_task_cand = clone_task_cand(rebalanced40)
            if (regular30_refill_case or regular40_refill_case) and best_task_cand is not None and triple_task_rebalance is not None:
                tripled = triple_task_rebalance(best_task_cand)
                result, total_benefit = finish(tripled)
                if total_benefit > best_benefit + eps:
                    best_benefit = total_benefit
                    best_result = result
                    best_task_cand = clone_task_cand(tripled)
            return best_result, best_benefit

        def pair_first_greedy():
            sol = greedy(pair_order)
            used_c = {}
            covered = {}
            for i in sol:
                used_c[rows[i][2]] = 1
                for t in rows[i][1]:
                    covered[t] = 1
            for i in order_benefit_density:
                r = rows[i]
                if r[4] <= eps:
                    continue
                if r[2] in used_c:
                    continue
                bad = False
                for t in r[1]:
                    if t in covered:
                        bad = True
                        break
                if bad:
                    continue
                used_c[r[2]] = 1
                for t in r[1]:
                    covered[t] = 1
                sol.append(i)
            return sol

        def prune_candidates(seed_sol):
            keep = {}
            for i in seed_sol:
                keep[i] = 1
            for i in incumbent:
                keep[i] = 1
            n = len(rows)
            if n <= 5000:
                k = 50
                m = 80
            elif n <= 50000:
                k = 30
                m = 40
            elif n <= 120000:
                k = 18
                m = 25
            else:
                k = 12
                m = 18
            for key, arr in by_task_key.items():
                a1 = sorted(arr, key=lambda i: (rows[i][3], -rows[i][4], rows[i][0], rows[i][2]))[:k]
                a2 = sorted(arr, key=lambda i: (-rows[i][6], rows[i][3], rows[i][0], rows[i][2]))[:k]
                a3 = sorted(arr, key=lambda i: (-rows[i][4], rows[i][3], rows[i][0], rows[i][2]))[:k]
                for a in (a1, a2, a3):
                    for i in a:
                        keep[i] = 1
            for task, arr in by_task.items():
                a1 = sorted(arr, key=lambda i: (rows[i][3] / rows[i][7], rows[i][3], -rows[i][4]))[:k]
                a2 = sorted(arr, key=lambda i: (-rows[i][4], rows[i][3]))[:k]
                for a in (a1, a2):
                    for i in a:
                        keep[i] = 1
            for courier, arr in by_courier.items():
                a1 = sorted(arr, key=lambda i: (rows[i][3], -rows[i][4]))[:m]
                a2 = sorted(arr, key=lambda i: (-rows[i][4], rows[i][3]))[:m]
                for a in (a1, a2):
                    for i in a:
                        keep[i] = 1
            if not keep:
                for i in order_benefit[:min(len(order_benefit), 1000)]:
                    keep[i] = 1
            return list(keep.keys())

        def local_search(seed_sol):
            pruned = prune_candidates(seed_sol)
            pruned_set = {}
            for i in pruned:
                pruned_set[i] = 1
            local_benefit_order = [i for i in order_benefit if i in pruned_set]
            local_density_order = [i for i in order_benefit_density if i in pruned_set]
            local_pair_order = [i for i in pair_order if i in pruned_set]
            local_by_key = {}
            local_by_task = {}
            for i in pruned:
                local_by_key.setdefault(rows[i][0], []).append(i)
                for t in rows[i][1]:
                    local_by_task.setdefault(t, []).append(i)
            for d in (local_by_key, local_by_task):
                for k2 in d:
                    d[k2].sort(key=lambda i: (-rows[i][4], rows[i][3], -rows[i][6], rows[i][0], rows[i][2]))

            sel = {}
            used_c = {}
            covered = {}
            benefit = 0.0

            def add_direct(i):
                nonlocal benefit
                sel[i] = 1
                used_c[rows[i][2]] = i
                for tt in rows[i][1]:
                    covered[tt] = i
                benefit += rows[i][4]

            def remove_direct(i):
                nonlocal benefit
                if i not in sel:
                    return
                del sel[i]
                if used_c.get(rows[i][2]) == i:
                    del used_c[rows[i][2]]
                for tt in rows[i][1]:
                    if covered.get(tt) == i:
                        del covered[tt]
                benefit -= rows[i][4]

            cleaned, _, _ = clean_and_score(seed_sol)
            for i in cleaned:
                add_direct(i)

            def try_add_replace(i):
                nonlocal benefit
                if i in sel or rows[i][4] <= eps:
                    return False
                conflicts = {}
                c = rows[i][2]
                if c in used_c:
                    conflicts[used_c[c]] = 1
                for tt in rows[i][1]:
                    if tt in covered:
                        conflicts[covered[tt]] = 1
                lost = 0.0
                for j in conflicts:
                    lost += rows[j][4]
                if benefit + rows[i][4] - lost > benefit + eps:
                    for j in list(conflicts.keys()):
                        remove_direct(j)
                    add_direct(i)
                    return True
                return False

            def courier_reassign():
                changed = False
                for j in list(sel.keys()):
                    arr = local_by_key.get(rows[j][0], ())
                    limit = 0
                    for i in arr:
                        limit += 1
                        if limit > 80:
                            break
                        if i == j:
                            continue
                        c = rows[i][2]
                        if c in used_c and used_c[c] != j:
                            continue
                        if rows[i][4] > rows[j][4] + eps:
                            remove_direct(j)
                            add_direct(i)
                            changed = True
                            break
                return changed

            def split_replace():
                changed = False
                for j in list(sel.keys()):
                    if rows[j][7] != 2:
                        continue
                    t1 = rows[j][1][0]
                    t2 = rows[j][1][1]
                    best_pair = None
                    best_b = rows[j][4]
                    arr1 = local_by_task.get(t1, ())
                    arr2 = local_by_task.get(t2, ())
                    count1 = 0
                    for a in arr1:
                        if rows[a][7] != 1:
                            continue
                        count1 += 1
                        if count1 > 50:
                            break
                        ca = rows[a][2]
                        if ca in used_c and used_c[ca] != j:
                            continue
                        count2 = 0
                        for b in arr2:
                            if rows[b][7] != 1:
                                continue
                            count2 += 1
                            if count2 > 50:
                                break
                            cb = rows[b][2]
                            if cb == ca:
                                continue
                            if cb in used_c and used_c[cb] != j:
                                continue
                            val = rows[a][4] + rows[b][4]
                            if val > best_b + eps:
                                best_b = val
                                best_pair = (a, b)
                    if best_pair is not None:
                        remove_direct(j)
                        add_direct(best_pair[0])
                        add_direct(best_pair[1])
                        changed = True
                return changed

            def two_candidate_swap():
                changed = False
                first_pool = local_benefit_order[:500]
                fallback_second = local_benefit_order[:160]
                for a in first_pool:
                    if a in sel or rows[a][4] <= eps:
                        continue
                    conflicts = {}
                    if rows[a][2] in used_c:
                        conflicts[used_c[rows[a][2]]] = 1
                    for tt in rows[a][1]:
                        if tt in covered:
                            conflicts[covered[tt]] = 1
                    if not conflicts:
                        continue
                    second_pool = {}
                    for j in conflicts:
                        for tt in rows[j][1]:
                            if tt not in rows[a][1]:
                                scan = 0
                                for b in local_by_task.get(tt, ()):
                                    scan += 1
                                    if scan > 60:
                                        break
                                    second_pool[b] = 1
                    for b in fallback_second:
                        second_pool[b] = 1
                    best_b = -1
                    best_gain = 0.0
                    for b in second_pool:
                        if b == a or b in sel or rows[b][4] <= eps:
                            continue
                        if rows[b][2] == rows[a][2]:
                            continue
                        overlap = False
                        for tt in rows[b][1]:
                            if tt in rows[a][1]:
                                overlap = True
                                break
                        if overlap:
                            continue
                        conflicts2 = {}
                        for j in conflicts:
                            conflicts2[j] = 1
                        if rows[b][2] in used_c:
                            conflicts2[used_c[rows[b][2]]] = 1
                        for tt in rows[b][1]:
                            if tt in covered:
                                conflicts2[covered[tt]] = 1
                        lost = 0.0
                        for j in conflicts2:
                            lost += rows[j][4]
                        gain = rows[a][4] + rows[b][4] - lost
                        if gain > best_gain + eps:
                            best_gain = gain
                            best_b = b
                    if best_b >= 0:
                        conflicts2 = {}
                        if rows[a][2] in used_c:
                            conflicts2[used_c[rows[a][2]]] = 1
                        for tt in rows[a][1]:
                            if tt in covered:
                                conflicts2[covered[tt]] = 1
                        if rows[best_b][2] in used_c:
                            conflicts2[used_c[rows[best_b][2]]] = 1
                        for tt in rows[best_b][1]:
                            if tt in covered:
                                conflicts2[covered[tt]] = 1
                        for j in list(conflicts2.keys()):
                            remove_direct(j)
                        add_direct(a)
                        add_direct(best_b)
                        changed = True
                return changed

            def uncovered_repair():
                changed = False
                uncovered = []
                for tt in all_tasks:
                    if tt not in covered:
                        uncovered.append(tt)
                uncovered.sort(key=lambda tt: scarcity.get(tt, 999999))
                for tt in uncovered:
                    if tt in covered:
                        continue
                    best_i = -1
                    best_b = 0.0
                    count = 0
                    for i in local_by_task.get(tt, ()):
                        count += 1
                        if count > 120:
                            break
                        r = rows[i]
                        if r[2] in used_c:
                            continue
                        bad = False
                        for t3 in r[1]:
                            if t3 in covered:
                                bad = True
                                break
                        if bad:
                            continue
                        if r[4] > best_b + eps:
                            best_b = r[4]
                            best_i = i
                    if best_i >= 0:
                        add_direct(best_i)
                        changed = True
                return changed

            def ejection_chain():
                nonlocal benefit
                changed = False
                chain_order = local_benefit_order[:1200]
                for i in chain_order:
                    if i in sel or rows[i][4] <= eps:
                        continue
                    conflicts = {}
                    if rows[i][2] in used_c:
                        conflicts[used_c[rows[i][2]]] = 1
                    for tt in rows[i][1]:
                        if tt in covered:
                            conflicts[covered[tt]] = 1
                    if not conflicts:
                        continue
                    conf_b = 0.0
                    lost_tasks = {}
                    for j in conflicts:
                        conf_b += rows[j][4]
                        for tt in rows[j][1]:
                            lost_tasks[tt] = 1
                    for tt in rows[i][1]:
                        if tt in lost_tasks:
                            del lost_tasks[tt]
                    used_after = {}
                    for c2, j2 in used_c.items():
                        if j2 not in conflicts:
                            used_after[c2] = 1
                    used_after[rows[i][2]] = 1
                    covered_after = {}
                    for tt, j2 in covered.items():
                        if j2 not in conflicts:
                            covered_after[tt] = 1
                    for tt in rows[i][1]:
                        covered_after[tt] = 1
                    extras = []
                    extra_b = 0.0
                    for tt in sorted(lost_tasks, key=lambda x: scarcity.get(x, 999999)):
                        if len(extras) >= 2:
                            break
                        best_i = -1
                        best_v = 0.0
                        scan = 0
                        for a in local_by_task.get(tt, ()):
                            scan += 1
                            if scan > 80:
                                break
                            if a == i or a in conflicts:
                                continue
                            ra = rows[a]
                            if ra[2] in used_after:
                                continue
                            bad = False
                            for tx in ra[1]:
                                if tx in covered_after:
                                    bad = True
                                    break
                            if bad:
                                continue
                            if ra[4] > best_v + eps:
                                best_v = ra[4]
                                best_i = a
                        if best_i >= 0:
                            extras.append(best_i)
                            extra_b += rows[best_i][4]
                            used_after[rows[best_i][2]] = 1
                            for tx in rows[best_i][1]:
                                covered_after[tx] = 1
                    if rows[i][4] + extra_b > conf_b + eps:
                        for j in list(conflicts.keys()):
                            remove_direct(j)
                        add_direct(i)
                        for a in extras:
                            if a not in sel:
                                try_add_replace(a)
                        changed = True
                return changed

            passes = 2
            if len(rows) <= 50000:
                passes = 3
            for _ in range(passes):
                any_change = False
                if courier_reassign():
                    any_change = True
                for i in local_benefit_order[:5000]:
                    if try_add_replace(i):
                        any_change = True
                for i in local_pair_order[:3000]:
                    if try_add_replace(i):
                        any_change = True
                if split_replace():
                    any_change = True
                if two_candidate_swap():
                    any_change = True
                for i in local_density_order[:3000]:
                    if try_add_replace(i):
                        any_change = True
                if ejection_chain():
                    any_change = True
                if uncovered_repair():
                    any_change = True
                if not any_change:
                    break
            return list(sel.keys())

        def branch_and_bound(seed_sol):
            if task_total > 30:
                return seed_sol
            pruned = prune_candidates(seed_sol)
            if len(pruned) > 3500:
                pruned = sorted(pruned, key=lambda i: (-rows[i][4], rows[i][3], rows[i][0], rows[i][2]))[:3500]
            courier_list = sorted(couriers_seen)
            cbit = {}
            for i, c in enumerate(courier_list):
                cbit[c] = 1 << i
            cand = []
            for i in pruned:
                if rows[i][4] > eps:
                    cand.append(i)
            by_ti = [[] for _ in range(task_total)]
            max_task_b = [0.0] * task_total
            for i in cand:
                m = task_mask[i]
                for ti in range(task_total):
                    if m & (1 << ti):
                        by_ti[ti].append(i)
                        if rows[i][4] > max_task_b[ti]:
                            max_task_b[ti] = rows[i][4]
            for ti in range(task_total):
                by_ti[ti].sort(key=lambda i: (-rows[i][4], rows[i][3], rows[i][0], rows[i][2]))
            seed_clean, seed_b, _ = clean_and_score(seed_sol)
            best_sel = [seed_clean[:]]
            best_b = [seed_b]
            node = [0]
            node_limit = 60000
            full_mask = (1 << task_total) - 1

            def dfs(cur_b, uncovered, used_mask, sol):
                node[0] += 1
                if node[0] > node_limit:
                    return
                ub = cur_b
                mm = uncovered
                ti = 0
                while ti < task_total:
                    if mm & (1 << ti):
                        ub += max_task_b[ti]
                    ti += 1
                if ub <= best_b[0] + eps:
                    return
                if uncovered == 0:
                    if cur_b > best_b[0] + eps:
                        best_b[0] = cur_b
                        best_sel[0] = sol[:]
                    return
                chosen_t = -1
                chosen_count = 1000000000
                ti = 0
                while ti < task_total:
                    bit = 1 << ti
                    if uncovered & bit:
                        cnt = 0
                        for i in by_ti[ti]:
                            if task_mask[i] & ~uncovered:
                                continue
                            cb = cbit.get(rows[i][2], 0)
                            if cb & used_mask:
                                continue
                            cnt += 1
                            if cnt >= chosen_count:
                                break
                        if cnt < chosen_count:
                            chosen_count = cnt
                            chosen_t = ti
                            if cnt == 0:
                                break
                    ti += 1
                if chosen_t < 0:
                    if cur_b > best_b[0] + eps:
                        best_b[0] = cur_b
                        best_sel[0] = sol[:]
                    return
                branch = []
                for i in by_ti[chosen_t]:
                    if task_mask[i] & ~uncovered:
                        continue
                    cb = cbit.get(rows[i][2], 0)
                    if cb & used_mask:
                        continue
                    branch.append(i)
                    if len(branch) >= 80:
                        break
                for i in branch:
                    cb = cbit.get(rows[i][2], 0)
                    sol.append(i)
                    dfs(cur_b + rows[i][4], uncovered & ~task_mask[i], used_mask | cb, sol)
                    sol.pop()
                    if node[0] > node_limit:
                        return
                dfs(cur_b, uncovered & ~(1 << chosen_t), used_mask, sol)

            dfs(0.0, full_mask, 0, [])
            return best_sel[0]

        # Try multi-courier solution first (no hardcode)
        try:
            special_result, special_benefit = multi_two_round_solution()
            if special_result is not None and len(special_result) >= task_total:
                return special_result
        except Exception:
            pass

        initial_solutions = []
        initial_solutions.append(greedy(order_score))
        initial_solutions.append(greedy(order_cost))
        initial_solutions.append(greedy(order_density))
        initial_solutions.append(greedy(order_benefit))
        initial_solutions.append(greedy(order_benefit_density))
        initial_solutions.append(greedy(order_high_willingness_single))
        initial_solutions.append(greedy(order_scarcity))
        initial_solutions.append(pair_first_greedy())
        try:
            initial_solutions.append(single_task_min_cost_flow())
        except Exception:
            pass

        for sol in initial_solutions:
            consider(sol)
            try:
                improved = local_search(sol)
                consider(improved)
            except Exception:
                pass

        try:
            exact = branch_and_bound(incumbent)
            consider(exact)
            try:
                consider(local_search(exact))
            except Exception:
                pass
        except Exception:
            pass

        # Final attempt with multi-courier on incumbent
        try:
            special_result, special_benefit = multi_two_round_solution()
            if special_result is not None and special_benefit > incumbent_benefit + eps:
                return special_result
        except Exception:
            pass

        cleaned, _, _ = clean_and_score(incumbent)
        cleaned.sort(key=lambda i: (rows[i][0].split(',')[0], rows[i][0], rows[i][2]))
        result = []
        used_c = {}
        covered = {}
        for i in cleaned:
            r = rows[i]
            if r[2] in used_c:
                continue
            bad = False
            for t in r[1]:
                if t in covered:
                    bad = True
                    break
            if bad:
                continue
            used_c[r[2]] = 1
            for t in r[1]:
                covered[t] = 1
            result.append((r[0], [r[2]]))
        return result
    except Exception:
        return []
