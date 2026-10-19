# -*- coding: utf-8 -*-
# PA-A1 v2 실행본 (패치판). 미실행 코드.
# MODE: "freeze2" -> "tag2" -> "a1"(동결 사양 그대로) -> "explore"(동결 밖 탐색적 확장, 별도 표기)
# 패치 내용 (동결 사양 PA_A1_V2 딕셔너리는 원본과 동일 -> spec 해시 불변):
#   P1. for/else + continue 버그 수정: 목표 점프 도달 불가 시 해당 (t*, delta) 전체를 NaN 처리하고 건너뜀
#   P2. 이분법 수렴 점검: 실현 점프 / 목표 비율을 기록하고 2% 초과 이탈이면 flag
#   P3. QUICK 모드는 오류 점검 전용: 재현 OK와 delta=0 기각률만 출력, 곡선·판독 규칙 출력 안 함
#   P4. explore 모드(동결 밖, [Post-hoc][Exploratory]): delta=0.25 추가, 연속 꺾은선(piecewise-linear) BIC
# 이 파일의 변경은 CHANGELOG에 '코드 오류 수정(사양 불변)'으로 기록할 것.
import sys, json, hashlib, subprocess, warnings, itertools
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore"); pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)

MODE = "a1"      # "freeze2" | "tag2" | "a1" | "explore"
QUICK = True          # True: 검정력 B=40, 오류 점검 전용(곡선 해석 금지)

ROOT = Path.home() / "Research/Minnesota_Transport"; P1 = ROOT/"paper1"; PA = P1/"09_PA"; S5 = P1/"05_S5"; S4 = P1/"04_S4"
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds")
sha_b = lambda b: hashlib.sha256(b).hexdigest(); sha_f = lambda p: sha_b(Path(p).read_bytes())
git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
class Halt(Exception): pass
spec_hash = lambda s: sha_b(json.dumps({k: v for k, v in s.items() if k not in ("sha256", "created", "refs")}, sort_keys=True, ensure_ascii=False).encode())
V1P, V2P = PA/"PA_0_PLAN.json", PA/"PA_0_PLAN_v2.json"

# ---- 동결 사양: 원본과 글자 단위로 동일해야 함 (수정 금지) ----
PA_A1_V2 = dict(
    window=[2000, 2025], samples=["all", "fixed14", "within"], delta_x=[0.5, 1, 2, 3], size_check_delta=0, t_star=[2008, 2012, 2015, 2020],
    B_power=200, alpha=0.05,
    detector="s5_lib.detect(P, n, pen, kmax=6, minlen=3) 그대로. pen = c*phi_s*(K-1)*log(T), c=1.0, phi_s는 S5_0_PREREG.json의 detection.phi. 표본은 s5_lib.sample_P(all, fixed14, within)",
    null="S5 N2 반복 분포(regime_nulls_reps.csv, null=N2, 표본별 B=500)를 그대로 사용. 판정은 S5와 같은 p=(1+#{null_R>=R})/(1+500) < 0.05 (재시뮬레이션 없음)",
    baseline="s5_lib.trend_probs(cnt)의 N2 추세 확률(저널x토픽 선형 추세)에 점프를 삽입. 관측 셀 크기, gen_N2로 다항 표집",
    injection="t* 이후(t>=t*) 모든 저널의 토픽 확률에 a*d를 더하고 0 절단 후 재정규화. d = 'all' 표본 관측 비중의 (2020 이후 평균 - 이전 평균). a는 'all' 표본에서 이등분법으로 정해 세 표본에 같은 계수를 씀",
    jump_def="J(t)=||가중평균(sqrt P)[t,t+3) - 가중평균(sqrt P)[t-3,t)||/sqrt(2) (가중치 4n, Hellinger 거리). 목표: J(주입)-J(N2 추세 기저)=delta*J_obs(2020, 'all', 관측). 표본별 실현 비율을 함께 보고",
    size_check="delta=0(점프 없음)에서 N2 반복 R의 기각률이 약 0.05인지 확인(검정 크기 점검)",
    secondary="변화점 위치 회수: 선택 변화점 중 t*±1년 이내가 있는 비율",
    reading="delta=1에서 t*별 검정력의 최솟값>=0.8: '이 크기의 점프가 있었다면 탐지했을 것이므로 N2 비통과는 연속 변화 증거'로 강화 / 중앙값<0.5: '체제 전환 여부 판정 불가(검정력 부족)'로 리프레이밍 / 그 사이: 어느 쪽도 쓰지 않고 곡선만 보고",
    reproduce_check="관측 R이 regime_nulls.csv의 obs_R(0.7595, 0.7755, 0.7033)과 0.001 이내로 재현되지 않으면 중단",
    bic_compare="관측 비중의 Hellinger 좌표 상위 5 PC에서 구간별 상수 대 구간별 선형, min_len 3, k<=6, BIC")

def build_v2():
    if not V1P.exists(): raise Halt("v1 계획(PA_0_PLAN.json)이 없습니다")
    v1 = json.loads(V1P.read_text(encoding="utf-8"))
    if v1["sha256"] != spec_hash(v1): raise Halt("v1 해시 불일치")
    p = {k: v for k, v in v1.items() if k not in ("sha256", "created", "refs")}
    p.update(version=2, supersedes_sha256=v1["sha256"], pa_a1=PA_A1_V2,
             decision_status="v1 동결 후 PA-A1 실행 전에, S5 원본 탐지기·구간(2000~2025)·N2 반복분포로 교체. PA-A1 검정력·BIC 결과는 미열람. 단, S5의 N2 반복 분포(요약 통계)와 s5_lib 소스는 열람한 상태. 나머지 PA 항목·규칙은 v1과 동일.",
             change_reason="v1의 PA-A1은 자체 대체 탐지기(2007~2025)였고 S5와 통계가 달라 '같은 CCTV로 시험'이 되지 않음.")
    return p, v1

def freeze2():
    p, v1 = build_v2(); h = spec_hash(p); print("PA-0 v2 해시(예정)", h[:12], "| v1", v1["sha256"][:12])
    if V2P.exists(): print("이미 동결:", "동일" if json.loads(V2P.read_text(encoding="utf-8"))["sha256"] == h else "⛔ 다름"); return
    refs = {f.name: sha_f(f) for f in [V1P, S5/"S5_0_PREREG.json", S5/"regime_nulls_reps.csv", S5/"regime_nulls.csv", P1/"s5_lib.py", P1/"s5_detect.py", S4/"yearly_venue_topic_counts.npy"] if f.exists()}
    V2P.write_text(json.dumps(dict(p, created=now(), sha256=h, refs=refs), ensure_ascii=False, indent=1), encoding="utf-8")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as f:
        f.write(f"- {now()} | PA-0 v2 동결(해시 {h[:12]}) | 사유: v1 대체 탐지기가 S5와 달랐음. PA-A1 결과 미열람 | 본 결과 변경 여부: 없음\n")
    print("저장: PA_0_PLAN_v2.json")

def tag2():
    if not V2P.exists(): raise Halt("먼저 freeze2")
    t = f"PA-0-plan-v2-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    if git("tag", "-l", t).stdout.strip(): print("이미 있음:", t); return
    r = git("add", "--", "paper1/09_PA"); print("add", r.returncode, r.stderr.strip())
    r = git("commit", "-m", "PA-0 plan v2 (PA-A1 detector -> S5 original, before execution)"); print("commit", r.returncode, (r.stdout + r.stderr)[:200])
    r = git("tag", "-a", t, "-m", "PA-0 plan v2"); print("tag", r.returncode, r.stderr.strip())
    print("※ 이어서 git push --follow-tags 로 원격 타임스탬프를 확보하세요.")

# ------------------------------ 공통 컨텍스트 ------------------------------
def make_ctx():
    if not V2P.exists(): raise Halt("먼저 freeze2와 tag2")
    p, _ = build_v2(); sp = json.loads(V2P.read_text(encoding="utf-8"))
    if sp["sha256"] != spec_hash(sp) or sp["sha256"] != spec_hash(p): raise Halt("동결 파일과 현재 계획이 다릅니다(사후 변경 금지)")
    if not git("tag", "-l", "PA-0-plan-v2-*").stdout.strip(): raise Halt("tag2를 먼저 실행하세요(동결 태그 없음)")
    sys.path.insert(0, str(P1)); import s5_lib as L
    cfg = PA_A1_V2; rng = np.random.default_rng(int(p["seed"]))
    s5 = json.loads((S5/"S5_0_PREREG.json").read_text(encoding="utf-8")); D = s5["detection"]; PHI = {k: v["phi"] for k, v in D["phi"].items()}
    C0, KMAX, MINLEN = D["c_primary"], D["k_max"], D["min_len"]
    cnt, venues, topics, fixed_v = L.load_counts(); wbar = cnt.sum((0, 2))/cnt.sum(); T, K = len(L.YEARS), len(topics); YEARS = np.asarray(L.YEARS); SAM = cfg["samples"]
    pen = lambda s: C0*PHI[s]*(K-1)*np.log(T)
    def detect_s(c_arr, s):
        P, n = L.sample_P(c_arr, fixed_v, wbar, s); return L.detect(P, n, pen(s), KMAX, MINLEN), P, n
    NR = pd.read_csv(S5/"regime_nulls_reps.csv"); N2 = {s: NR[(NR["null"] == "N2") & (NR["sample"] == s)].R.values for s in SAM}; OBSR = pd.read_csv(S5/"regime_nulls.csv")
    p_of = lambda s, R: (1 + float((N2[s] >= R).sum()))/(1 + len(N2[s]))
    info = []
    for s in SAM:
        d, P, n = detect_s(cnt, s); ref = float(OBSR[(OBSR["null"] == "N2") & (OBSR["sample"] == s)].obs_R.iloc[0])
        if abs(d["R"] - ref) > 1e-3: raise Halt(f"S5 관측 R 재현 실패({s}): {d['R']:.4f} vs {ref:.4f}")
        info.append(dict(sample=s, obs_R=d["R"], obs_k=d["k"], obs_breaks=[int(YEARS[b]) for b in d["br"]], N2_B=len(N2[s]), N2_q95=float(np.quantile(N2[s], .95)), p_N2=p_of(s, d["R"])))
    print("[관측 재현 OK: S5와 R 일치]\n", pd.DataFrame(info).round(4).to_string(index=False))
    def J(P, n, it):
        X, w = np.sqrt(P), 4.0*n; a, b = slice(max(0, it-3), it), slice(it, it+3)
        m = lambda sl: np.average(X[sl], axis=0, weights=w[sl]) if w[sl].sum() > 0 else X[sl].mean(0)
        return float(np.linalg.norm(m(b) - m(a))/np.sqrt(2))
    i20 = int(np.where(YEARS == 2020)[0][0]); Pall, _ = L.sample_P(cnt, fixed_v, wbar, "all")
    Jobs = {s: J(*L.sample_P(cnt, fixed_v, wbar, s), i20) for s in SAM}; d_vec = Pall[i20:].mean(0) - Pall[:i20].mean(0)
    P2 = L.trend_probs(cnt); n_cell = cnt.sum(2).astype(float); print("\n관측 2020 점프(Hellinger, 3년 창):", {k: round(v, 4) for k, v in Jobs.items()})
    def inject(a, it):
        Q = P2.copy(); Q[it:] = np.clip(Q[it:] + a*d_vec[None, None, :], 1e-9, None); return Q/Q.sum(2, keepdims=True)
    jump_exp = lambda Q, s, it: J(*L.sample_P(Q*n_cell[:, :, None], fixed_v, wbar, s), it)
    return dict(p=p, sp=sp, cfg=cfg, rng=rng, L=L, cnt=cnt, fixed_v=fixed_v, wbar=wbar, T=T, YEARS=YEARS, SAM=SAM, detect_s=detect_s, p_of=p_of, info=info,
                Jobs=Jobs, P2=P2, inject=inject, jump_exp=jump_exp, d_vec=d_vec, MINLEN=MINLEN, KMAX=KMAX)

def run_reps(c, Q, kind, ts, dx, a, ratio, Bp, rows, conv_flag=""):
    hits = {s: [] for s in c["SAM"]}; rej = {s: [] for s in c["SAM"]}; Rs = {s: [] for s in c["SAM"]}
    for _ in range(Bp):
        cc = c["L"].gen_N2(c["cnt"], Q, c["rng"])
        for s in c["SAM"]:
            d, _, _ = c["detect_s"](cc, s); Rs[s].append(d["R"]); rej[s].append(c["p_of"](s, d["R"]) < c["cfg"]["alpha"])
            hits[s].append(any(abs(int(c["YEARS"][b]) - ts) <= 1 for b in d["br"]) if ts else np.nan)
    for s in c["SAM"]:
        rows.append(dict(kind=kind, sample=s, t_star=ts, delta_x=dx, a=a, power=float(np.mean(rej[s])), R_mean=float(np.mean(Rs[s])),
                         hit_near_tstar=float(np.nanmean(hits[s])) if ts else np.nan, J_extra_ratio=(ratio or {}).get(s, np.nan), conv_flag=conv_flag, B=Bp))

def power_grid(c, deltas, Bp, rows):
    """P1, P2 반영: 도달 불가면 NaN 행 후 건너뜀. 수렴 오차 flag 기록."""
    for ts in c["cfg"]["t_star"]:
        it = int(np.where(c["YEARS"] == ts)[0][0]); base = {s: c["jump_exp"](c["P2"], s, it) for s in c["SAM"]}
        for dx in deltas:
            target = dx*c["Jobs"]["all"]; lo, hi = 0.0, 1.0/np.abs(c["d_vec"]).max(); reached = False
            for _ in range(6):
                if c["jump_exp"](c["inject"](hi, it), "all", it) - base["all"] >= target: reached = True; break
                hi *= 2
            if not reached:
                for s in c["SAM"]: rows.append(dict(kind="power", sample=s, t_star=ts, delta_x=dx, power=np.nan, conv_flag="unreachable"))
                continue
            for _ in range(40):
                mid = (lo + hi)/2; lo, hi = (mid, hi) if c["jump_exp"](c["inject"](mid, it), "all", it) - base["all"] < target else (lo, mid)
            Q = c["inject"](hi, it); ratio = {s: (c["jump_exp"](Q, s, it) - base[s])/c["Jobs"][s] for s in c["SAM"]}
            achieved = (c["jump_exp"](Q, "all", it) - base["all"])/target
            flag = "" if abs(achieved - 1) <= 0.02 else f"conv_off({achieved:.3f})"
            run_reps(c, Q, "power", ts, dx, hi, ratio, Bp, rows, flag)
        print(f"  t*={ts} 완료")

def size_check(c, Bp, rows):
    run_reps(c, c["P2"], "size_check", 0, 0, 0.0, None, Bp, rows)
    print("[검정 크기 점검 delta=0: 기각률(약 0.05여야 함)]", {r["sample"]: round(r["power"], 3) for r in rows if r["kind"] == "size_check"})

# ------------------------------ BIC ------------------------------
def pcs(c, s, npc=5):
    P, _ = c["L"].sample_P(c["cnt"], c["fixed_v"], c["wbar"], s); Z = np.sqrt(P); Z = Z - Z.mean(0)
    U, sv, _ = np.linalg.svd(Z, full_matrices=False); return (U*sv)[:, :npc]
def bic_step(c, Y, lin):   # 동결 사양: 구간별 상수 대 구간별 선형(불연속 허용)
    T, N, M = c["T"], Y.size, c["MINLEN"]; R = np.full((T+1, T+1), np.inf)
    for a_ in range(T+1):
        for b_ in range(a_+M, T+1):
            y = Y[a_:b_]; x = np.arange(b_-a_); A = np.c_[np.ones_like(x), x] if lin else np.ones((len(x), 1)); R[a_, b_] = ((y - A @ np.linalg.lstsq(A, y, rcond=None)[0])**2).sum()
    best = np.full((c["KMAX"]+1, T+1), np.inf); best[0, 0] = 0
    for k in range(1, c["KMAX"]+1): best[k] = np.min(best[k-1][:, None] + R, axis=0)
    return [dict(model="linear" if lin else "constant", k=k, rss=best[k, T], bic=N*np.log(best[k, T]/N + 1e-12) + (k*5*(2 if lin else 1) + (k-1))*np.log(N)) for k in range(1, c["KMAX"]+1) if np.isfinite(best[k, T])]
def bic_continuous(c, Y, kmax_bp=4):   # 탐색적: 연속 꺾은선(힌지) 모형, 꺾임 수 0..kmax_bp, 꺾임 간격>=MINLEN
    T, N, M = c["T"], Y.size, c["MINLEN"]; t = np.arange(T, dtype=float); out = []
    for kb in range(0, kmax_bp+1):
        best = (np.inf, None)
        for bps in itertools.combinations(range(M, T-M+1), kb):
            if any(b2-b1 < M for b1, b2 in zip(bps[:-1], bps[1:])): continue
            A = np.c_[np.ones(T), t, *[np.maximum(t-b, 0) for b in bps]]; rss = ((Y - A @ np.linalg.lstsq(A, Y, rcond=None)[0])**2).sum()
            if rss < best[0]: best = (rss, bps)
        out.append(dict(model="piecewise_linear_continuous", k=kb+1, rss=best[0], bic=N*np.log(best[0]/N + 1e-12) + 5*(2+kb)*np.log(N), breakpoints=[int(c["YEARS"][b]) for b in best[1]]))
    return out

# ------------------------------ 모드 ------------------------------
def a1():
    c = make_ctx(); sfx = "_QUICK" if QUICK else ""; Bp = 40 if QUICK else c["cfg"]["B_power"]; rows = []
    size_check(c, Bp, rows)
    if QUICK:
        print("\n[QUICK] 오류 점검 전용: 재현 OK와 delta=0 기각률만 확인. 곡선·판독 규칙은 본 실행(QUICK=False)에서만 해석(v3 방지).")
        power_grid(c, [1], 8, rows)   # 코드 경로 점검용 최소 실행, 결과 출력 안 함
        return
    power_grid(c, c["cfg"]["delta_x"], Bp, rows)
    PW = pd.DataFrame(rows); pw = PW[PW.kind == "power"]
    print("\n[Post-hoc] PA-A1 검정력(S5 N2 기준)\n", pw.pivot_table(index=["sample", "t_star"], columns="delta_x", values="power").round(2).to_string())
    print("\n[수렴 flag]\n", pw[pw.conv_flag.fillna("") != ""][["sample", "t_star", "delta_x", "conv_flag"]].drop_duplicates().to_string(index=False) or "없음")
    print("\n[표본별 실현 점프 비율(delta=1)]\n", pw[pw.delta_x == 1].pivot_table(index="sample", columns="t_star", values="J_extra_ratio").round(2).to_string())
    one = pw[pw.delta_x == 1].groupby("sample").power.agg(["min", "median"]).round(2); print("\n[delta=1 요약]\n", one.to_string())
    for s, r in one.iterrows(): print(f"  {s}: 사전 판독 → " + ("강화(연속 변화 증거)" if r["min"] >= 0.8 else ("리프레이밍(판정 불가)" if r["median"] < 0.5 else "곡선으로만 보고")))
    bic = []
    for s in c["SAM"]:
        Y = pcs(c, s); bic += [dict(sample=s, **r) for lin in (False, True) for r in bic_step(c, Y, lin)]
    BC = pd.DataFrame(bic); print("\n[Post-hoc] BIC 최솟값(상수 대 선형; 자기상관으로 과분할 가능, 보조 지표)\n", BC.loc[BC.groupby(["sample", "model"]).bic.idxmin()].round(1).to_string(index=False))
    PW.to_csv(PA/"PA_A1_v2_power_curve.csv", index=False, encoding="utf-8-sig"); pd.DataFrame(c["info"]).to_csv(PA/"PA_A1_v2_observed.csv", index=False, encoding="utf-8-sig"); BC.to_csv(PA/"PA_A1_v2_bic.csv", index=False, encoding="utf-8-sig")
    print("\n※ 검정력은 '관측 2020 점프 방향의 점프'에 한정. S0~S8 판정 불변.")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as f:
        f.write(f"- {now()} | PA-A1(v2) | 정의: PA_0_PLAN_v2 {c['sp']['sha256'][:12]} | 코드 패치(사양 불변): for/else 버그 수정, 수렴 flag, QUICK 해석 금지 | 결과: PA_A1_v2_*.csv | 본 결과 변경 여부: 없음\n")

def explore():
    """동결 밖 탐색적 확장. 모든 산출물·표 제목에 [Post-hoc][Exploratory]. 본 판독 규칙에 쓰지 않음."""
    c = make_ctx(); Bp = 40 if QUICK else c["cfg"]["B_power"]; sfx = "_QUICK" if QUICK else ""; rows = []
    print("[Post-hoc][Exploratory] 작은 점프(0.25x) 검정력")
    power_grid(c, [0.25], Bp, rows); PW = pd.DataFrame(rows)
    print(PW[PW.kind == "power"].pivot_table(index=["sample", "t_star"], columns="delta_x", values="power").round(2).to_string())
    bic = []
    for s in c["SAM"]:
        Y = pcs(c, s); bic += [dict(sample=s, **r) for r in bic_continuous(c, Y)]
    BC = pd.DataFrame(bic); print("\n[Post-hoc][Exploratory] 연속 꺾은선 BIC(꺾임 수 0~4)\n", BC.drop(columns="rss").round(1).to_string(index=False))
    PW.to_csv(PA/f"PA_A1_v2_EXPLORATORY_power025{sfx}.csv", index=False, encoding="utf-8-sig"); BC.to_csv(PA/f"PA_A1_v2_EXPLORATORY_bic_continuous{sfx}.csv", index=False, encoding="utf-8-sig")
    if not QUICK:
        with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as f:
            f.write(f"- {now()} | PA-A1(v2) 탐색적 확장 | 정의: 동결 밖(delta=0.25, 연속 꺾은선 BIC), 판독 규칙에 미사용 | 결과: PA_A1_v2_EXPLORATORY_*.csv | 본 결과 변경 여부: 없음\n")

try: {"freeze2": freeze2, "tag2": tag2, "a1": a1, "explore": explore}[MODE]()
except Halt as e: print(f"⛔ 중단: {e}")
