# -*- coding: utf-8 -*-
# PA-B6b: 이름 빈도 상위 구간에서 50쌍을 뽑아 동일인 여부 수작업 판정(시트 생성 + 채점). 미실행.
# python3 pa_b6b.py freeze | tag | sheet | score     (tag 뒤 git push --follow-tags)
from pa_common import *
from pa_extra import *
SHEET = PA/"PA_B6b_sheet.csv"; FILLED = PA/"PA_B6b_sheet_filled.csv"
PLAN = dict(
    version=1, seed=2026, parent="PA_0_PLAN_v2.json",
    status="사후 명세(지침서 B6-2). 판정 전 시트 생성, 판정 결과 미열람. 연구자 1인 판정. S0~S8 판정 불변.",
    population="F2_author_paper.csv(위험군 제외 상태, 분석 논문)에서 name_norm별 행 수 >= 10인 이름 중, 연도 차이 5년 이상인 논문 쌍을 만들 수 있는 이름",
    sampling="이름 50개를 seed 2026으로 비복원 무작위 추출. 이름마다 논문 쌍 1개: 연도 차이 >=5인 논문 쌍 중 무작위 1개. 시트는 이름 순서를 무작위 섞음",
    sheet="pair_id, name_norm, 논문 A·B의 pid·연도·저널·제목·공저자(최대 6명), same_person(1=동일인, 0=다른 사람, ?=판정 불가), note. 판정 칸 비워서 생성. 소속은 자료에 있는 경우만(없으면 공란)",
    stats="n_same, n_diff, n_unsure; 미탐지 동명이인 비율 = n_diff/(n_diff+n_same)와 Wilson 95%; 판정 불가를 모두 다른 사람/모두 동일인으로 본 경계",
    reading="수치와 구간만 보고. 임계값 없음. 연구자 1인 판정이라는 한계를 함께 표기",
    caveat="이름 단위 표본이며 다작 이름에 치우침(행 10편 이상). 논문 쌍 1개는 이름 전체의 혼합 정도를 과소·과대 추정할 수 있음. 위험군 이름은 모집단에서 이미 빠져 있음. 판정은 제목·공저자·저널 정보에 의존하며 오판 가능",
    forbidden="결과를 본 뒤 표본·판정 규칙 변경(변경 시 v2 계획으로 분리)")

def sheet(sp):
    if SHEET.exists(): raise Halt("시트가 이미 있음(덮어쓰지 않음). 새로 만들려면 v2 계획으로 분리")
    F2 = pd.read_csv(DATA/"F2_author_paper.csv", encoding="utf-8-sig", low_memory=False); F2["pid"] = F2.pid.astype(str)
    F1 = pd.read_csv(DATA/"F1_papers.csv", low_memory=False); F1["pid"] = F1.pid.astype(str); title = F1.drop_duplicates("pid").set_index("pid").title
    rng = np.random.default_rng(int(PLAN["seed"])); cnt = F2.groupby("name_norm").size(); names = sorted(cnt[cnt >= 10].index)
    pairs = {}
    for nm in names:
        d = F2[F2.name_norm == nm].drop_duplicates("pid")[["pid", "year", "venue_short"]].values
        ok = [(i, j) for i in range(len(d)) for j in range(len(d)) if d[j][1] - d[i][1] >= 5]
        if ok: pairs[nm] = (d, ok)
    pool = sorted(pairs); print(f"이름 행 수>=10: {len(names):,} | 5년 이상 쌍 가능: {len(pool):,}")
    if len(pool) < 50: raise Halt("모집단이 50개 미만")
    pick = list(rng.choice(pool, 50, replace=False)); rng.shuffle(pick); rows = []
    co = F2.groupby("pid").name_norm.apply(list)
    for k, nm in enumerate(pick, 1):
        d, ok = pairs[nm]; i, j = ok[int(rng.integers(len(ok)))]; r = dict(pair_id=k, name_norm=nm)
        for tag, x in (("A", d[i]), ("B", d[j])):
            pid = str(x[0]); r.update({f"pid_{tag}": pid, f"year_{tag}": int(x[1]), f"venue_{tag}": x[2], f"title_{tag}": title.get(pid, ""), f"coauthors_{tag}": "; ".join([n for n in co.get(pid, []) if n != nm][:6])})
        r.update(same_person="", note=""); rows.append(r)
    pd.DataFrame(rows).to_csv(SHEET, index=False, encoding="utf-8-sig")
    cl(f"PA-B6b 시트 생성 | {SHEET.name} 해시 {sha_f(SHEET)[:12]}, 50쌍, 판정 칸 비어 있음 | 본 결과 변경: 없음")
    print("저장:", SHEET, "→ same_person 칸을 채워 PA_B6b_sheet_filled.csv로 저장하세요(1/0/?)")

def score(sp):
    if not (SHEET.exists() and FILLED.exists()): raise Halt("PA_B6b_sheet.csv와 PA_B6b_sheet_filled.csv가 모두 필요")
    a = pd.read_csv(SHEET, encoding="utf-8-sig"); b = pd.read_csv(FILLED, encoding="utf-8-sig")
    key = ["pair_id", "name_norm", "pid_A", "pid_B"]
    if len(b) != 50 or not a[key].astype(str).equals(b[key].astype(str)): raise Halt("채워진 시트가 원본 시트와 다름(행·키 변경 금지)")
    v = b.same_person.astype(str).str.strip().str.replace(".0", "", regex=False)
    if not v.isin(["1", "0", "?"]).all(): raise Halt("same_person은 1, 0, ? 중 하나여야 함(빈 칸 있음)")
    ns, nd, nu = int((v == "1").sum()), int((v == "0").sum()), int((v == "?").sum()); n = ns + nd; lo, hi = wilson(nd, n)
    lo_b, _ = wilson(nd, n + nu); _, hi_b = wilson(nd + nu, n + nu)
    out = pd.DataFrame([dict(n_same=ns, n_diff=nd, n_unsure=nu, undetected_homonym_rate=nd/n if n else np.nan, lo=lo, hi=hi, bound_lo_if_unsure_same=lo_b, bound_hi_if_unsure_diff=hi_b)])
    out.to_csv(PA/"PA_B6b_results.csv", index=False, encoding="utf-8-sig"); print("\n[Post-hoc] PA-B6b\n", out.round(4).T.to_string(header=False))
    print("※ 연구자 1인 판정, 다작 이름 표본. 수치만 보고. S0~S8 판정 불변.")
    cl(f"PA-B6b 채점 | 정의: PA_B6b_PLAN {sp['sha256'][:12]} | 결과: PA_B6b_results.csv, 채워진 시트 해시 {sha_f(FILLED)[:12]} | 본 결과 변경 여부: 없음")

if not special("B6b", PLAN, {"sheet": sheet, "score": score}):
    run_pa("B6b", PLAN, lambda q, s: print("이 항목은 sheet → (수작업) → score 모드를 쓰세요"), [DATA/"F2_author_paper.csv", P1/"pa_extra.py"], "위험군 선별이 놓친 동명이인 비율의 수작업 추정(지침서 B6-2)")