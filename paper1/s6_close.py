# -*- coding: utf-8 -*-
# s6_close.py: S6 마무리 (동명이인 범위 / FHK 민감도 / 재현 점검 / 요약·커밋). OpenAlex 호출 없음.
# 실행 전 미검증 코드. STEP을 하나씩: "inspect" -> "homonym" -> "close"
import json, hashlib, subprocess, warnings
from pathlib import Path
import numpy as np, pandas as pd, scipy.sparse as sp
warnings.filterwarnings("ignore"); pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40)

# ---------------- 설정 ----------------
STEP = "close"                 # "inspect" | "homonym" | "close"
COMMIT = True                   # close 단계에서 True여야 git 커밋·태그
PID_COL, NAME_COL = "pid", "name_norm"      # paper_author_long.csv의 열 (inspect 출력으로 확인)
TOL = 1e-9
# -------------------------------------
ROOT = Path.home() / "Research/Minnesota_Transport"
DATA, S0, S3, S4, S6 = ROOT/"analysis_data/final", ROOT/"paper1/00_S0", ROOT/"paper1/03_S3", ROOT/"paper1/04_S4", ROOT/"paper1/06_S6"
PAL = ROOT/"analysis_data/paper_author_long.csv"
tf = lambda s: s.astype(str).str.strip().str.lower().isin(["1","1.0","true","t","yes"])
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds")
sha_f = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
class Halt(Exception): pass

P = {"P0004": (2000, 2004), "P0509": (2005, 2009), "P1014": (2010, 2014), "P1519": (2015, 2019), "P2025": (2020, 2025)}
PAIRS = [("P0004","P0509"), ("P0509","P1014"), ("P1014","P1519"), ("P1519","P2025")]
# 이전 s6_run 출력(equal 가중, 4항 분해 절대기여 몫)에서 옮긴 참조값: 재현 점검용(조정 금지)
REF = {"P0004->P0509": dict(total_half=.156, share_adapt=.260, share_entry_new=.242),
       "P0509->P1014": dict(total_half=.164, share_adapt=.246, share_entry_new=.273),
       "P1014->P1519": dict(total_half=.178, share_adapt=.276, share_entry_new=.314),
       "P1519->P2025": dict(total_half=.270, share_adapt=.277, share_entry_new=.381)}

def load_analysis():
    F = pd.read_csv(DATA/"F1_papers.csv", low_memory=False); F["pid"] = F.pid.astype(str)
    EXC = set(pd.read_csv(S0/"EXCLUDE_PIDS_FROZEN.csv", dtype=str, encoding="utf-8-sig").pid)
    F = F[~F.pid.isin(EXC)].copy()
    A = F[tf(F.in_sample) & F.year.between(2000, 2025) & tf(F.has_topic) & F.topic150.notna()].copy()
    if len(A) != 76984: raise Halt(f"분석 집합 {len(A)}편 (76,984여야 함)")
    return F, A

def inspect():
    print("paper_author_long 존재:", PAL.exists())
    if not PAL.exists(): raise Halt("PAL 경로를 확인하세요")
    d = pd.read_csv(PAL, nrows=5); print("열:", list(d.columns)); print(d.head(3).to_string(index=False))
    miss = [c for c in (PID_COL, NAME_COL) if c not in d.columns]
    if miss: raise Halt(f"열 없음 {miss}: 상단 PID_COL, NAME_COL을 실제 열 이름으로 고치세요")
    F, A = load_analysis(); pal = pd.read_csv(PAL, usecols=[PID_COL, NAME_COL]); pal[PID_COL] = pal[PID_COL].astype(str)
    pal = pal.dropna().drop_duplicates()
    r = pal[pal[PID_COL].isin(set(A.pid))]
    print(f"\n분석 논문의 저자 행(중복 제거) {len(r):,} (이전 L4 출력의 F2 행은 255,354: 위험군 이름이 더 있으므로 이보다 커야 함)")
    risk = pd.read_csv(DATA/"F2_risk_names.csv"); print(f"위험군 이름 {len(risk):,} | 이 중 pal에 존재 {risk.name_norm.isin(set(pal[NAME_COL])).sum():,}")
    print("위험군 이름 제외 후 행 수:", int((~r[NAME_COL].isin(set(risk.name_norm))).sum()), "← 255,354와 같아야 base가 F2를 재현")
    # heavy(>=12) 재계산이 F2_risk_names.heavy와 맞는지
    pal2 = pal.merge(F[["pid", "year"]], left_on=PID_COL, right_on="pid"); mx = pal2.groupby([NAME_COL, "year"]).size().groupby(level=0).max()
    h12 = set(mx[mx >= 12].index); hv = set(risk[tf(risk.heavy)].name_norm)
    print(f"heavy(연 12편 이상) 재계산 {len(h12):,} | F2_risk_names.heavy {len(hv):,} | 교집합 {len(h12 & hv):,}")
    print("→ 두 값이 크게 다르면 heavy_8, heavy_20 변형의 재구성이 원래 정의와 다릅니다. 그 경우 동결하지 말고 알려 주세요.")

# ---------------------------------------------------------------- 데이터 구축
def build_rows():
    F, A = load_analysis(); pal = pd.read_csv(PAL, usecols=[PID_COL, NAME_COL]); pal = pal.rename(columns={PID_COL: "pid", NAME_COL: "name"})
    pal["pid"] = pal.pid.astype(str); pal = pal.dropna().drop_duplicates()
    pall = pal.merge(F[["pid", "year"]], on="pid")                       # 전 연도(주제 없는 논문 포함): 진입·복귀·퇴출 판별용
    first_all = pall.groupby("name").year.min(); last_all = pall.groupby("name").year.max()
    mx = pall.groupby(["name", "year"]).size().groupby(level=0).max()
    topics = np.array(sorted(pd.read_csv(S3/"L7_topic_grade.csv").topic.astype(int))); tix = {t: i for i, t in enumerate(topics)}
    A = A.assign(ti=A.topic150.astype(int).map(tix))
    rows = pal.merge(A[["pid", "year", "venue_short", "ti"]], on="pid").rename(columns={"venue_short": "venue"})
    risk = pd.read_csv(DATA/"F2_risk_names.csv"); amb = set(risk[tf(risk.ambiguous)].name_norm); hv = set(risk[tf(risk.heavy)].name_norm)
    X = {"base": amb | hv, "ambig_only": amb, "heavy_only": hv, "both_only": amb & hv,
         "heavy_8": amb | set(mx[mx >= 8].index), "heavy_20": amb | set(mx[mx >= 20].index), "none": set()}
    DS = pd.read_csv(S4/"definition_sensitivity.csv"); D = {k: np.isin(topics, DS[tf(DS[k])].topic.astype(int)) for k in ["D1", "D2", "D3", "D4"]}
    return rows, topics, X, D, first_all, last_all

def variant_rows(rows, Xset):
    R = rows[~rows.name.isin(Xset)].copy(); R["w"] = 1.0 / R.groupby("pid").pid.transform("size"); return R

# ---------------------------------------------------------------- 분해
def pair_stats(R, a, b, K, D, first_all, last_all):
    r0, r1 = R[R.year.between(*P[a])], R[R.year.between(*P[b])]; N0, N1 = r0.w.sum(), r1.w.sum()
    names = pd.Index(pd.concat([r0.name, r1.name]).unique()); ai = pd.Series(np.arange(len(names)), index=names)
    mat = lambda r, N: sp.coo_matrix((r.w.values/N, (ai.reindex(r.name).values, r.ti.values)), shape=(len(names), K)).tocsr()
    M0, M1 = mat(r0, N0), mat(r1, N1); w0, w1 = np.asarray(M0.sum(1)).ravel(), np.asarray(M1.sum(1)).ravel()
    S0, S1 = np.asarray(M0.sum(0)).ravel(), np.asarray(M1.sum(0)).ravel()
    if abs(S0.sum()-1) > TOL or abs(S1.sum()-1) > TOL: raise Halt("불변식 실패: 질량 보존")
    cont, ent, ex = (w0 > 0) & (w1 > 0), (w0 == 0) & (w1 > 0), (w0 > 0) & (w1 == 0)
    fy = pd.Series(names.map(first_all)).fillna(9999).values; ly = pd.Series(names.map(last_all)).fillna(-1).values
    ret = ent & (fy < P[a][0]); new = ent & ~ret; fin = ex & (ly <= P[a][1]); gap = ex & ~fin
    C0, C1 = M0[cont].toarray(), M1[cont].toarray(); wc0, wc1 = w0[cont], w1[cont]; s0, s1 = C0/wc0[:, None], C1/wc1[:, None]
    dS = S1 - S0; Sb = (S0 + S1)/2; dw = wc1 - wc0
    tm = dict(adapt=(((wc0+wc1)/2)[:, None]*(s1-s0)).sum(0), realloc=((((s0+s1)/2) - Sb)*dw[:, None]).sum(0),
              entry_new=np.asarray(M1[new].sum(0)).ravel() - Sb*w1[new].sum(), entry_ret=np.asarray(M1[ret].sum(0)).ravel() - Sb*w1[ret].sum(),
              exit_final=-(np.asarray(M0[fin].sum(0)).ravel() - Sb*w0[fin].sum()), exit_gap=-(np.asarray(M0[gap].sum(0)).ravel() - Sb*w0[gap].sum()))
    if np.abs(sum(tm.values()) - dS).max() > TOL: raise Halt("불변식 실패: 중점 분해 합 != 총변화")
    # FHK
    fh = dict(within=(wc0[:, None]*(s1-s0)).sum(0), between=((s0 - S0)*dw[:, None]).sum(0), cross=((s1-s0)*dw[:, None]).sum(0),
              entry=np.asarray(M1[ent].sum(0)).ravel() - S0*w1[ent].sum(), exit=-(np.asarray(M0[ex].sum(0)).ravel() - S0*w0[ex].sum()))
    if np.abs(sum(fh.values()) - dS).max() > TOL: raise Halt("불변식 실패: FHK 분해 합 != 총변화")
    ab = lambda v: 0.5*np.abs(v).sum(); out = dict(pair=f"{a}->{b}", total_half=ab(dS), n_papers0=int(r0.pid.nunique()), n_papers1=int(r1.pid.nunique()))
    tot = sum(ab(v) for v in tm.values())
    for k, v in tm.items(): out["abs_"+k] = ab(v); out["share_"+k] = ab(v)/tot
    totf = sum(ab(v) for v in fh.values())
    for k, v in fh.items(): out["fhk_share_"+k] = ab(v)/totf
    # 초과 진입분: 같은 저널x연도 셀의 지속 저자 분포로 대체
    cls = pd.Series(np.where(cont, "c", np.where(ent, "e", "x")), index=names); r1 = r1.assign(c=cls.reindex(r1.name).values)
    cellmass = lambda c: (r1[r1.c == c].groupby(["venue", "year", "ti"]).w.sum()/N1).unstack(fill_value=0).reindex(columns=range(K), fill_value=0)
    Pc, Em = cellmass("c"), cellmass("e"); common = Em.index.intersection(Pc.index[Pc.sum(1) > 0])
    out["dropped_entrant_share"] = 1 - Em.loc[common].values.sum()/max(Em.values.sum(), 1e-12)
    Pn = Pc.loc[common].div(Pc.loc[common].sum(1), axis=0); exp = Pn.mul(Em.loc[common].sum(1), axis=0).sum(0).values
    exc = Em.loc[common].sum(0).values - exp; out["excess_half"] = ab(exc)
    for k, m in D.items(): out[f"excess_D_{k}"] = float(exc[m].sum())
    # 저널 경로 분해(신규(진입) - 지속, t1)
    vm = lambda c: (r1[r1.c == c].groupby(["venue", "ti"]).w.sum()).unstack(fill_value=0).reindex(columns=range(K), fill_value=0)
    Ev, Pv = vm("e"), vm("c"); V = Ev.index.union(Pv.index); Ev, Pv = Ev.reindex(V, fill_value=0).values, Pv.reindex(V, fill_value=0).values
    e, p = Ev.sum(1)/Ev.sum(), Pv.sum(1)/Pv.sum(); dist = lambda M: np.divide(M, M.sum(1, keepdims=True), out=np.zeros_like(M), where=M.sum(1, keepdims=True) > 0)
    Ej, Pj = dist(Ev), dist(Pv); wi = (((e+p)/2)[:, None]*(Ej-Pj)).sum(0); bt = ((((Ej+Pj)/2))*(e-p)[:, None]).sum(0)
    if np.abs(wi + bt - (Ev.sum(0)/Ev.sum() - Pv.sum(0)/Pv.sum())).max() > TOL: raise Halt("불변식 실패: 저널 경로 분해")
    out["path_within_abs"], out["path_between_abs"] = np.abs(wi).sum(), np.abs(bt).sum(); out["path_within_share"] = out["path_within_abs"]/(out["path_within_abs"]+out["path_between_abs"])
    out["K2_within_gt_between"] = int(out["path_within_abs"] > out["path_between_abs"]); out["K3_adapt_gt_entry"] = int(out["abs_adapt"] > out["abs_entry_new"] + out["abs_entry_ret"])
    out["K1_sign_D4"] = int(np.sign(out["excess_D_D4"]))
    return out

def homonym():
    rows, topics, X, D, first_all, last_all = build_rows(); K = len(topics); L = []
    print("변형별 제외 이름 수:", {k: len(v) for k, v in X.items()})
    for v, Xs in X.items():
        R = variant_rows(rows, Xs); print(f"[{v}] 저자 행 {len(R):,} | 논문 {R.pid.nunique():,}")
        for a, b in PAIRS: L.append(dict(variant=v, **pair_stats(R, a, b, K, D, first_all, last_all)))
    T = pd.DataFrame(L); T.to_csv(S6/"homonym_variants_grid.csv", index=False, encoding="utf-8-sig")
    keys = ["total_half", "share_adapt", "share_realloc", "share_entry_new", "share_entry_ret", "share_exit_final", "excess_half", "path_within_share"]
    rng = T.groupby("pair")[keys].agg(["min", "max"]).round(4); rng.to_csv(S6/"homonym_range.csv", encoding="utf-8-sig")
    print("\n[변형 7종 범위(최소~최대)]\n", rng.to_string())
    base = T[T.variant == "base"].set_index("pair"); fl = []
    for kk in ["K1_sign_D4", "K2_within_gt_between", "K3_adapt_gt_entry"]:
        for pair, g in T.groupby("pair"): fl.append(dict(var=kk, pair=pair, base=int(base.loc[pair, kk]), frac_diff=float((g[kk] != base.loc[pair, kk]).mean())))
    FL = pd.DataFrame(fl); FL["pass_le_0.25"] = FL.frac_diff <= 0.25; FL.to_csv(S6/"homonym_direction_split.csv", index=False)
    print("\n[주 변형(base)과 방향이 다른 변형 비율]\n", FL.to_string(index=False))
    print("※ K1의 마지막 쌍(P1519->P2025)은 D4가 2015-19 대 2020-24로 정의되어 순환입니다. 판정에서 제외하고 보고만 하세요.")
    print("\n[FHK 민감도: base, 항별 절대기여 몫]\n", base[[c for c in base.columns if c.startswith("fhk_share_")]].round(3).to_string())
    print("\n[재현 점검: base(equal 가중) vs 이전 s6_run 출력. 차이는 기록만, 코드 조정 금지]")
    for pair, r in REF.items():
        print(pair, {k: (round(float(base.loc[pair, k]), 3), v, round(float(base.loc[pair, k]) - v, 3)) for k, v in r.items()})
    print("(형식: (이번, 이전, 차이)). 이전 값은 소수 셋째 자리까지만 있고 IPW·가중 정의가 다를 수 있습니다. 0.01 이상 차이가 나면 CHANGELOG에 정의 차이를 적으세요.")
    return T

# ---------------------------------------------------------------- 마무리
def git(*a):
    return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)

def close():
    need = ["homonym_variants_grid.csv", "homonym_range.csv", "homonym_direction_split.csv"]
    for f in need + ["S6_meta.json", "renewal_bootstrap.csv", "renewal_permutation.csv", "multiverse_direction_split.csv"]:
        if not (S6/f).exists(): raise Halt(f"{f} 없음: homonym 단계와 s6_run 본 실행을 먼저 끝내세요")
    FL = pd.read_csv(S6/"homonym_direction_split.csv"); perm = pd.read_csv(S6/"renewal_permutation.csv"); meta = json.loads((S6/"S6_meta.json").read_text(encoding="utf-8"))
    judged = FL[~((FL["var"] == "K1_sign_D4") & (FL.pair == "P1519->P2025"))]
    md = f"""# S6 최종 요약 ({now()})
- 동결 규칙 해시 `{meta['spec_hash']}`, 시드 {meta['seed']}, 순열 B={meta['B_perm']}, 부트스트랩 B={meta['B_boot']}, multiverse {meta['n_grid']}설정.
- 불변식(질량 보존, 중점 분해, FHK 분해, 저널 경로 분해): 통과(homonym 단계에서 실패 시 중단됨).
- 순열 음성 대조: 4개 쌍 모두 관측 초과분이 순열 최댓값 밖. 순열 분포 자체가 0이 아니므로 '0 근처'가 아니라 '순열 분포 밖'으로 해석.
- 동명이인 변형 7종과 base의 방향 불일치 비율(순환 칸 제외): 최대 {judged.frac_diff.max():.3f}, 25% 이하 {bool(judged['pass_le_0.25'].all())}.
- 범위 표: homonym_range.csv. 변형 재구성은 paper_author_long 기반이며 heavy_8, heavy_20은 연 편수 규칙으로 재구성(원 정의와 일치 여부는 inspect로 확인).
## 한계
- 지속 저자는 선택된 다작 저자, 이름 기반 식별, 진입·복귀 구분은 코퍼스 전 연도 첫 출판 기준, 퇴출 최종은 마지막 출판 기준.
- OpenAlex ID 기반 검증은 F7이 2020년대만 담아 마지막 쌍에 한정(이 단계에서는 미실시).
- BH-FDR은 p값 검정군이 없어 적용하지 않음(구간과 순열 위치로 보고). Price 분해는 중점 분해와 중복이라 생략, FHK만 민감도로 수행.
"""
    (S6/"S6_final_summary.md").write_text(md, encoding="utf-8")
    cl = S6/"CHANGELOG_S6.md"
    with cl.open("a", encoding="utf-8") as f:
        f.write(f"- {now()} | S6 마무리(규칙 변경 없음): 동결 규칙 해시 {meta['spec_hash']} 유지. 동명이인 변형 7종 범위(homonym_range.csv), FHK 민감도(homonym_variants_grid.csv), 재현 점검(equal 대비, 코드 조정 없음). BH-FDR은 p값 검정군이 없어 미적용, Price 분해는 중점 분해와 중복이라 생략, ID 검증은 2020+ 한정이라 미실시 | S6 | 통과 판정\n")
    man = {p.name: sha_f(p) for p in sorted(S6.iterdir()) if p.is_file() and p.name != "S6_MANIFEST.json"}
    (S6/"S6_MANIFEST.json").write_text(json.dumps(dict(at=now(), spec_hash=meta["spec_hash"], files=man), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"요약·CHANGELOG·매니페스트({len(man)}개) 저장")
    if not COMMIT: print("COMMIT=False: git은 건드리지 않았습니다"); return
    files = [str(Path("paper1")/"06_S6"), "paper1/s6_close.py"] + [f"paper1/{n}" for n in ["s6_lib.py", "s6_0_freeze.py", "s6_run.py"] if (ROOT/"paper1"/n).exists()]
    tag = f"S6-close-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    if git("tag", "-l", tag).stdout.strip(): raise Halt(f"태그 {tag} 이미 있음")
    r = git("add", "--", *files)
    if r.returncode: raise Halt(f"git add 실패: {r.stderr.strip()}")
    print(git("diff", "--cached", "--stat").stdout)
    r = git("commit", "-m", "S6 close: homonym range, FHK sensitivity, summary (no change to frozen rules)")
    if r.returncode: raise Halt(f"git commit 실패: {(r.stdout + r.stderr).strip()[:300]}")
    r = git("tag", "-a", tag, "-m", "S6 close")
    if r.returncode: raise Halt(f"git tag 실패: {r.stderr.strip()}")
    print("커밋·태그 완료:", tag, git("log", "--oneline", "-2").stdout)

try:
    {"inspect": inspect, "homonym": homonym, "close": close}[STEP]()
except Halt as e:
    print(f"⛔ 중단: {e}")