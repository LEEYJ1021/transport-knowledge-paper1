# -*- coding: utf-8 -*-
# PA-B8b: 미달 4개 도메인의 사전 v3으로 새 무작위 25편씩 뽑아 이중 코딩 시트 생성 + precision 채점. 판정은 하지 않고 구간만 보고. 미실행.
# 선행: 09_PA/PA_B8b_dict_v3.json 작성({"도메인": "정규식"} 4개). python3 pa_b8b.py freeze | tag | sheet | score
from pa_common import *
from pa_extra import *
DICT = PA/"PA_B8b_dict_v3.json"; SHEET = PA/"PA_B8b_sheet.csv"; FILLED = PA/"PA_B8b_sheet_filled.csv"
FAILS = ["electrification_env", "freight", "active_urban", "infrastructure"]
D3 = json.loads(DICT.read_text(encoding="utf-8")) if DICT.exists() else None
PLAN = dict(
    version=1, seed=2026, parent="PA_0_PLAN_v2.json",
    status="사후 명세(지침서 B8-2). 미달 4개 도메인 precision(0.76~0.84, n=25)과 오탐 패턴(예: active_urban의 accessibility) 열람 후 사전 v3 작성. 새 표본 결과 미열람. 사후 개정 사전이라 본 결과와 섞지 않음. S0~S8 판정 불변.",
    dict_v3=D3, domains=FAILS,
    sampling="분석 집합(F1에서 EXCLUDE_PIDS_FROZEN 제외, year>=2007, title 있음) 중 v3 정규식(re.I)이 제목에 매칭되는 논문에서 도메인별 25편을 seed 2026으로 비복원 추출. 이전 S8 검증 표본에 있던 pid는 제외(표본 파일은 08_S8/*sample*.csv의 pid 열). 시트 순서는 섞음",
    coding="coder1, coder2가 서로 보지 않고 각 논문 제목이 해당 도메인의 S8 정의에 속하는지 1/0으로 코딩. 불일치는 final 칸에 합의로 기록(일치하면 final도 같은 값). 코더 구성(저자 1인+제2코더)은 note에 기록",
    stats="도메인별 precision=mean(final)과 Wilson 95%, Cohen kappa(coder1, coder2), 불일치 수, 이전 v2 precision 병기. 도메인 합산도 병기",
    reading="통과/실패 판정 없음. 수치와 구간만 보고하며 S8 판정(2/6 통과)을 바꾸지 않음. 합산과 도메인별을 합치지 않음. 'v3으로 개정한 사전'임을 모든 표에 표기",
    caveat="n=25는 구간이 넓어 0.85 기준과 구분이 어려움(참 precision 0.80이어도 22편 이상 나올 확률 약 23%). 오탐 패턴을 보고 만든 사전이라 정밀도에 낙관 편향. recall은 추정하지 않음. 코더 독립성 한계 가능",
    forbidden="결과를 본 뒤 사전·표본·판독 변경(변경 시 v2 계획으로 분리)")

def load_pool():
    RXv = {d: re.compile(D3[d], re.I) for d in FAILS}
    F1 = pd.read_csv(DATA/"F1_papers.csv", low_memory=False); F1["pid"] = F1.pid.astype(str)
    exf = S0/"EXCLUDE_PIDS_FROZEN.csv"; log = pd.read_csv(S0/"FREEZE_LOG.csv"); last = log[log.file == exf.name].iloc[-1]
    if sha_f(exf) != last.sha256: raise Halt("EXCLUDE_PIDS_FROZEN.csv 해시 불일치")
    F = F1[~F1.pid.isin(set(pd.read_csv(exf, dtype=str, encoding="utf-8-sig").pid))].copy(); F = F[(F.year >= 2007) & F.title.notna()]
    return F, {d: F.title.str.contains(rx).values for d, rx in RXv.items()}

def sheet(sp):
    if SHEET.exists(): raise Halt("시트가 이미 있음(덮어쓰지 않음)")
    F, pos = load_pool(); prev = set()
    for f in sorted(S8.glob("coder[12].csv")):
        d = pd.read_csv(f, dtype={"pid": str}, encoding="utf-8-sig")
        if "pid" in d.columns: prev |= set(d.pid); print("이전 표본 제외:", f.name, len(d))
    if not prev and "noprev" not in sys.argv: raise Halt("08_S8에서 이전 검증 표본(*sample*.csv, pid 열)을 찾지 못함. 위치 확인 또는 'sheet noprev'")
    rng = np.random.default_rng(int(PLAN["seed"])); rows = []
    for d in FAILS:
        P = F[pos[d] & ~F.pid.isin(prev)]; print(f"  {d}: v3 양성 {int(pos[d].sum()):,}, 제외 후 {len(P):,}")
        if len(P) < 25: raise Halt(f"{d}: 후보 25편 미만")
        for _, r in P.iloc[rng.choice(len(P), 25, replace=False)].iterrows(): rows.append(dict(domain=d, pid=r.pid, year=int(r.year), title=r.title, coder1="", coder2="", final="", note=""))
    S_ = pd.DataFrame(rows).sample(frac=1, random_state=int(PLAN["seed"])).reset_index(drop=True); S_.insert(0, "item_id", range(1, len(S_) + 1)); S_.to_csv(SHEET, index=False, encoding="utf-8-sig")
    cl(f"PA-B8b 시트 생성 | {SHEET.name} 해시 {sha_f(SHEET)[:12]}, 도메인별 25편(총 100), 코딩 칸 비어 있음, 이전 표본 제외 {len(prev)}편 | 본 결과 변경: 없음")
    print("저장:", SHEET, "→ coder1·coder2를 각자 채우고 final 합의 후 PA_B8b_sheet_filled.csv로 저장")

def score(sp):
    if not (SHEET.exists() and FILLED.exists()): raise Halt("PA_B8b_sheet.csv와 PA_B8b_sheet_filled.csv가 모두 필요")
    a = pd.read_csv(SHEET, encoding="utf-8-sig"); b = pd.read_csv(FILLED, encoding="utf-8-sig"); key = ["item_id", "domain", "pid"]
    if len(b) != 100 or not a[key].astype(str).equals(b[key].astype(str)): raise Halt("채워진 시트가 원본과 다름")
    for c in ["coder1", "coder2", "final"]:
        b[c] = pd.to_numeric(b[c], errors="coerce")
        if not b[c].isin([0, 1]).all(): raise Halt(f"{c}는 0/1이어야 함(빈 칸 있음)")
    if not (b.final[b.coder1 == b.coder2] == b.coder1[b.coder1 == b.coder2]).all(): raise Halt("일치한 항목의 final이 코더 값과 다름")
    prev = pd.read_csv(S8/"domain_precision_recall.csv").set_index("domain"); rows = []
    def kappa(x, y):
        po = (x == y).mean(); pe = x.mean()*y.mean() + (1 - x.mean())*(1 - y.mean()); return (po - pe)/(1 - pe) if pe < 1 else np.nan
    for d, g in list(b.groupby("domain")) + [("ALL", b)]:
        k, n = int(g.final.sum()), len(g); lo, hi = wilson(k, n)
        rows.append(dict(domain=d, n=n, precision_v3=k/n, lo=lo, hi=hi, kappa=kappa(g.coder1, g.coder2), n_disagree=int((g.coder1 != g.coder2).sum()), precision_v2=float(prev.loc[d, "precision"]) if d in prev.index else np.nan))
    out = pd.DataFrame(rows); out.to_csv(PA/"PA_B8b_results.csv", index=False, encoding="utf-8-sig")
    print("\n[Post-hoc] PA-B8b (사후 개정 사전 v3, 통과/실패 판정 없음)\n", out.round(3).to_string(index=False))
    print("※ n=25는 구간이 넓음. 오탐 패턴을 본 사전이라 낙관 편향. S8 판정(2/6) 불변.")
    cl(f"PA-B8b 채점 | 정의: PA_B8b_PLAN {sp['sha256'][:12]} | 결과: PA_B8b_results.csv, 채워진 시트 해시 {sha_f(FILLED)[:12]} | 본 결과 변경 여부: 없음")

if len(sys.argv) > 1 and sys.argv[1] == "freeze" and D3 is None: print("⛔ 중단: 09_PA/PA_B8b_dict_v3.json을 먼저 작성하세요"); sys.exit()
if not special("B8b", PLAN, {"sheet": sheet, "score": score}):
    run_pa("B8b", PLAN, lambda q, s: print("이 항목은 sheet → (수작업 코딩) → score 모드를 쓰세요"), [DICT, S8/"domain_precision_recall.csv", P1/"pa_extra.py"], "사전 v3(사후 개정)과 새 25편 이중 코딩(지침서 B8-2)")