# -*- coding: utf-8 -*-
# PA-B4c: 임베딩 응집도(토픽 안 평균 코사인)와 부트스트랩 Jaccard 10퍼센타일을 '더 변별적인 등급'으로 삼아 하위 10% 토픽을 제외하고 S5·S6 재추정(B4와 같은 틀). 미실행.
# 사용: python3 pa_b4c.py discover | freeze | tag | run [quick]
from pa_common import *
# ---- discover 출력으로 채울 것(동결 전). 비워 두면 freeze가 중단됨 ----
EMB_PATH = ""      # 예: "analysis_data/final/xxx_embeddings.npy" (ROOT 기준 상대경로, 행=논문)
PID_PATH = ""      # 위 행렬의 행 순서에 대응하는 pid 파일(.csv/.parquet), 열 이름은 PID_COL
PID_COL = "pid"
JAC_PATH = ""      # 선택: 토픽별 부트스트랩 반복 Jaccard 긴 형식(.csv, 열 topic, jaccard). 없으면 빈 문자열(Jaccard 부분 미수행 기록)

def discover():
    cand = [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts and "oa_raw" not in p.parts and ".ipynb_checkpoints" not in p.parts and re.search(r"emb|vector|jacc|boot", p.name, re.I) and p.suffix in (".npy", ".npz", ".csv", ".parquet", ".gz", ".json", ".md")]
    for p in sorted(cand)[:60]:
        info = ""
        try:
            if p.suffix == ".npy": info = f"shape {np.load(p, mmap_mode='r').shape}"
            elif p.suffix == ".csv": d = pd.read_csv(p, nrows=3); info = f"cols {list(d.columns)[:8]}"
        except Exception as e: info = f"읽기 실패 {str(e)[:40]}"
        print(f"{p.relative_to(ROOT)} | {p.stat().st_size/1e6:.1f}MB | {info}")
    print("\n[S3 파일 열]"); [print(f.name, list(pd.read_csv(f, nrows=1).columns)[:12]) for f in sorted(S3.glob("L*.csv"))]
    print("※ 임베딩 행렬·pid 파일·(있다면) 반복별 Jaccard 파일 경로를 위 상수에 채우세요.")
if len(sys.argv) > 1 and sys.argv[1] == "discover": discover(); sys.exit()

PLAN = dict(
    version=1, seed=2026, parent="PA_0_PLAN_v2.json",
    status="사후 명세(지침서 B4-2). B4·B4b 결과(F1·F3 제외 4개뿐이라 약한 시험), S3 요약 열람 상태. 결과 미열람. 응집도 파일 경로는 discover 출력으로 확정. 이전에 미수행으로 두었으나 연구자 요청으로 수행. S0~S8 판정 불변.",
    inputs=dict(emb=EMB_PATH, pid=PID_PATH, pid_col=PID_COL, jac=JAC_PATH),
    cohesion="토픽 t의 S4 분석 집합 논문 중 임베딩이 있는 논문(토픽당 최대 2000편 무작위 표집, seed 고정, 최소 5편)을 L2 정규화해 평균 쌍별 코사인=(||sum u||^2-n)/(n(n-1)). 하위 10%(올림) 토픽을 '저응집'으로 정의",
    jaccard_p10="JAC_PATH가 있으면 토픽별 반복 Jaccard의 10퍼센타일을 구해 하위 10% 토픽을 '불안정'으로 정의. 없으면 이 부분은 미수행으로 기록",
    reestimate="B4(pa_b4.py)와 같은 절차: S5는 통과 토픽만으로 s5_lib.detect(pen=c*phi*(K-1)*log T, K=통과 토픽 수), N1·N2 귀무 B=500, 통과 규칙 N1·N2 모두 p<0.05. S6은 R을 통과 토픽 행으로 제한한 주 설정, 대응 저자 부트스트랩 B=spec['B_boot'], entry_minus_adapt 변화",
    reading="S5: 표본별 (a) 통과 여부가 S5와 같은지, (b) S5 관측 변화점이 +-1년 안에서 유지되는지. S6: 쌍별 |변화|<=0.03이고 부호 유지면 '둔감'(B4와 같은 규칙, 첫 쌍은 원값이 0 근처라 부호가 바뀌기 쉬움). 제외 집합별로 따로 보고, 합치지 않음. 제외 토픽과 F1·F3 실패 4개·S3 등급의 겹침도 보고",
    reproduce_check="(a) 임베딩 행 수와 pid 파일 길이 일치, (b) 분석 집합 논문 중 임베딩이 있는 비율 >=0.95, (c) S5 관측 R이 regime_nulls.csv obs_R과 1e-3 이내, (d) S6 total_half·A2c entry_share 재현, 부분 자료 저자 집합이 원본의 부분집합",
    caveat="응집도는 임베딩 모델과 토픽 구성(대형 토픽의 평균 코사인이 낮아지는 경향)에 의존. 하위 10%는 임의 기준(동결). 등급의 타당성은 검증하지 않음. 제외 토픽이 약 15개라 B4보다 판별력이 크지만 여전히 부분집합 재추정",
    forbidden="결과를 본 뒤 하위 비율(10%)·표집 수·판독 변경(변경 시 v2 계획으로 분리하고 사유 기록)")

def reestimate(ptop, quick, rng):
    import s5_lib as L5, s6_lib as S
    s5 = json.loads((S5D/"S5_0_PREREG.json").read_text(encoding="utf-8")); D = s5["detection"]; PHI = {k: v["phi"] for k, v in D["phi"].items()}
    C0, KMAX, MINLEN, ALPHA = D["c_primary"], D["k_max"], D["min_len"], s5["nulls"]["alpha"]; Bn = 20 if quick else 500
    cnt, venues, topics, fixed_v = L5.load_counts(); wbar = cnt.sum((0, 2))/cnt.sum(); T = len(L5.YEARS); YEARS = np.asarray(L5.YEARS); SAM = s5["samples"]; tmask = np.isin(topics, list(ptop)); Ku = int(tmask.sum())
    det = lambda c, s, Kuse: (lambda Pn: L5.detect(Pn[0], Pn[1], C0*PHI[s]*(Kuse - 1)*np.log(T), KMAX, MINLEN))(L5.sample_P(c, fixed_v, wbar, s))
    ref = pd.read_csv(S5D/"regime_nulls.csv"); ref = ref[ref["null"] == "N2"].set_index("sample")
    for s in SAM:
        if abs(det(cnt, s, len(topics))["R"] - float(ref.loc[s, "obs_R"])) > 1e-3: raise Halt(f"S5 관측 R 재현 실패({s})")
    cs = cnt[:, :, tmask]; obs = {s: det(cs, s, Ku) for s in SAM}; P2 = L5.trend_probs(cs); NR = {"N1": {s: [] for s in SAM}, "N2": {s: [] for s in SAM}}
    for b in range(Bn):
        for nm, cc in (("N1", L5.gen_N1(cs, rng)), ("N2", L5.gen_N2(cs, P2, rng))):
            for s in SAM: NR[nm][s].append(det(cc, s, Ku)["R"])
    meta = json.loads((S5D/"S5_meta.json").read_text(encoding="utf-8")); rows5 = []
    for s in SAM:
        yrs = [int(YEARS[x]) for x in obs[s]["br"]]; pv = {nm: (1 + float((np.array(NR[nm][s]) >= obs[s]["R"]).sum()))/(1 + Bn) for nm in NR}; kept = [L5.near(y, yrs, 1) for y in meta["obs_breaks"][s]]
        rows5.append(dict(sample=s, K=Ku, obs_R=obs[s]["R"], breaks=str(yrs), s5_breaks=str(meta["obs_breaks"][s]), p_N1=pv["N1"], p_N2=pv["N2"], passed_new=max(pv.values()) < ALPHA, passed_s5=bool(meta["null_pass"][s]), all_breaks_kept=all(kept), B=Bn))
    spec = S.load_spec(); L = S.load_all(spec); M = spec["main"]; PAIRS = S.pairs_of(spec); half = S.half; R = L["R"]
    ok_ti = np.where(np.isin(L["topics"], list(ptop)))[0]; L2 = dict(L); L2["R"] = R[R.ti.isin(ok_ti)]
    ref6 = pd.read_csv(S6D/"renewal_decomposition.csv"); ref6 = ref6[(ref6.scheme == M["scheme"]) & (ref6.variant == "all_venues")].set_index("pair")
    a2c = pd.read_csv(PA/"PA_A2c_results.csv"); a2c = a2c[(a2c["mode"] == "author") & (a2c.stat == "entry_share")].set_index("pair")
    B6 = 20 if quick else int(spec["B_boot"]); lo_q, hi_q = spec["ci"]; STATS = ["entry_share", "adapt_share", "entry_minus_adapt"]
    def stats(d):
        h = {t: half(d[t]) for t in ["adapt", "realloc", "entry", "exit"]}; tot = sum(h.values()); return dict(entry_share=h["entry"]/tot, adapt_share=h["adapt"]/tot, entry_minus_adapt=(h["entry"] - h["adapt"])/tot)
    rows6 = []
    for p0, p1 in PAIRS:
        name = f"{p0}->{p1}"; Pa = S.make_pair(L, p0, p1, M["scheme"], M["venue"], M["topic"], M["hom"]); Pb = S.make_pair(L2, p0, p1, M["scheme"], M["venue"], M["topic"], M["hom"]); da, db = Pa.decompose(), Pb.decompose(); oa, ob = stats(da), stats(db)
        if abs(half(da["total"]) - float(ref6.loc[name, "total_half"])) > 1e-6 or abs(oa["entry_share"] - float(a2c.loc[name, "obs"])) > 1e-6: raise Halt(f"S6/A2c 재현 실패({name})")
        idx = np.searchsorted(Pa.aids, Pb.aids)
        if not (idx < len(Pa.aids)).all() or not (Pa.aids[idx] == Pb.aids).all(): raise Halt(f"부분 자료 저자 집합이 원본의 부분집합이 아님({name})")
        bs = []
        for _ in range(B6):
            wa = rng.exponential(size=Pa.nA); sa = stats(Pa.decompose(Pa.m0*wa[Pa.a0], Pa.m1*wa[Pa.a1])); wb = wa[idx]; sb = stats(Pb.decompose(Pb.m0*wb[Pb.a0], Pb.m1*wb[Pb.a1])); bs.append({s: sb[s] - sa[s] for s in STATS})
        bs = pd.DataFrame(bs)
        for s in STATS:
            dl = ob[s] - oa[s]; ql, qh = np.percentile(bs[s], [lo_q, hi_q]); rows6.append(dict(pair=name, stat=s, obs_orig=oa[s], obs_sub=ob[s], delta=dl, pct_lo=ql, pct_hi=qh, B=B6))
    return pd.DataFrame(rows5), pd.DataFrame(rows6)

def run(quick, sp):
    if not (EMB_PATH and PID_PATH): raise Halt("EMB_PATH·PID_PATH가 비어 있음(discover 출력으로 채운 뒤 새 동결)")
    sys.path.insert(0, str(P1)); F, Mi, topics, venues = analysis_sets(); rng = np.random.default_rng(int(PLAN["seed"]))
    E = np.load(ROOT/EMB_PATH, mmap_mode="r"); pp = ROOT/PID_PATH; pid = (pd.read_parquet(pp) if pp.suffix == ".parquet" else pd.read_csv(pp, dtype=str))[PID_COL].astype(str).values
    if len(pid) != E.shape[0]: raise Halt(f"임베딩 행 {E.shape[0]} != pid 길이 {len(pid)}")
    pos = {p: i for i, p in enumerate(pid)}; F["ei"] = F.pid.map(pos); cov = float(F.ei.notna().mean())
    if cov < 0.95: raise Halt(f"분석 집합 중 임베딩 보유 비율 {cov:.3f} < 0.95")
    coh = {}
    for t in topics:
        ix = F.loc[F.topic == t, "ei"].dropna().astype(int).values
        if len(ix) < 5: coh[int(t)] = np.nan; continue
        if len(ix) > 2000: ix = rng.choice(ix, 2000, replace=False)
        X = np.asarray(E[np.sort(ix)], float); X /= np.linalg.norm(X, axis=1, keepdims=True) + 1e-12; n = len(X); coh[int(t)] = float((np.linalg.norm(X.sum(0))**2 - n)/(n*(n - 1)))
    C = pd.Series(coh); k10 = int(np.ceil(0.10*C.notna().sum())); low_c = set(C.dropna().nsmallest(k10).index.astype(int))
    G = pd.read_csv(S3/"L7_topic_grade.csv", encoding="utf-8-sig").set_index("topic"); f13 = set(G.index[bl(G.F1) | bl(G.F3)].astype(int))
    sets = {"cohesion_low10": low_c}
    if JAC_PATH:
        J = pd.read_csv(ROOT/JAC_PATH); p10 = J.groupby("topic").jaccard.quantile(0.10); sets["jaccard_p10_low10"] = set(p10.nsmallest(int(np.ceil(0.10*len(p10)))).index.astype(int))
    print(f"[재현 OK] 임베딩 보유 비율 {cov:.3f} | 응집도 하위 10% {len(low_c)}개, F1·F3 실패 4개와 겹침 {len(low_c & f13)}개 | Jaccard p10 {'있음' if JAC_PATH else '파일 없음(미수행)'}")
    if quick:
        for nm, ex in sets.items(): reestimate(set(map(int, topics)) - ex, True, rng); print(f"  {nm} 점검 완료")
        print("[QUICK] 오류 점검만. 결과 수치는 출력하지 않음."); return
    pd.DataFrame(dict(topic=C.index, cohesion=C.values, low10=C.index.isin(low_c), grade=[G.grade.get(t, "") for t in C.index], f1f3_fail=C.index.isin(f13))).to_csv(PA/"PA_B4c_cohesion.csv", index=False, encoding="utf-8-sig")
    for nm, ex in sets.items():
        R5, R6 = reestimate(set(map(int, topics)) - ex, False, rng); R5.to_csv(PA/f"PA_B4c_{nm}_s5.csv", index=False, encoding="utf-8-sig"); R6.to_csv(PA/f"PA_B4c_{nm}_s6.csv", index=False, encoding="utf-8-sig")
        k = R6[R6.stat == "entry_minus_adapt"].copy(); k["insensitive"] = (np.sign(k.obs_sub) == np.sign(k.obs_orig)) & (k.delta.abs() <= 0.03)
        print(f"\n[Post-hoc] PA-B4c {nm}: 제외 {len(ex)}개 {sorted(ex)}\n[S5]\n", R5.round(4).to_string(index=False), "\n[S6 entry_minus_adapt]\n", k.round(4).to_string(index=False))
        print("[동결 판독] S5 통과 판정 동일·변화점 유지:", R5[["sample"]].assign(same=R5.passed_new == R5.passed_s5, kept=R5.all_breaks_kept).to_dict("records"))
    if not JAC_PATH: print("※ Jaccard 반복값 파일이 없어 p10 등급은 미수행(S3 저장값은 중앙값뿐).")
    print("※ 응집도 기준은 임베딩 모델·토픽 크기에 의존. 제외 집합별로 따로 읽고 합치지 않음. S0~S8 판정 불변.")

def _freeze_guard():
    if len(sys.argv) > 1 and sys.argv[1] == "freeze" and not (EMB_PATH and PID_PATH): print("⛔ 중단: EMB_PATH·PID_PATH를 먼저 채우세요(discover 출력 확인)"); sys.exit()
_freeze_guard()
run_pa("B4c", PLAN, run, [S3/"L7_topic_grade.csv", S5D/"S5_0_PREREG.json", S5D/"S5_meta.json", PA/"PA_B4_PLAN.json"], "더 변별적인 토픽 등급(응집도·Jaccard p10)으로 S5·S6 재추정(지침서 B4-2)")