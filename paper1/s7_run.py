# -*- coding: utf-8 -*-
# =====================================================================================
# S7 지역 집중과 신규 유입 (단일 셀, OpenAlex 호출 없음). 미실행 코드: QUICK=True로 먼저 시험.
# 사용: MODE="freeze"(규칙 동결, 데이터 미열람) -> MODE="run"(동결 해시 검증 후 분석)
# 입력: 02_S2/country_mass_long, 01_S1(wb_income_current/history, authorship_level, authorship_level_recovered),
#       analysis_data(F1, F2_risk_names, paper_author_long), 03_S3/L7_topic_grade, 00_S0/PREREG
# 산출: paper1/07_S7/*.csv, S7_meta.json. 해석은 '함께 움직인다'까지, '체제' 대신 '기간'.
# =====================================================================================
import json, hashlib, subprocess, warnings
from pathlib import Path
import numpy as np, pandas as pd, scipy.sparse as sp
from scipy.stats import spearmanr
from scipy.spatial.distance import jensenshannon
warnings.filterwarnings("ignore"); pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)

MODE = "run"      # "freeze" | "run"
QUICK = False         # True: 부트스트랩 B=50 (시험용, 파일명에 _QUICK)
COMMIT = True       # run 끝에서 True여야 git 커밋·태그

ROOT = Path.home() / "Research/Minnesota_Transport"
DATA, S0, S1, S2, S3, S7 = ROOT/"analysis_data/final", ROOT/"paper1/00_S0", ROOT/"paper1/01_S1", ROOT/"paper1/02_S2", ROOT/"paper1/03_S3", ROOT/"paper1/07_S7"
PAL = ROOT/"analysis_data/paper_author_long.csv"
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds")
sha_b = lambda b: hashlib.sha256(b).hexdigest(); sha_f = lambda p: sha_b(Path(p).read_bytes())
tf = lambda s: s.astype(str).str.strip().str.lower().isin(["1", "1.0", "true", "t", "yes"])
class Halt(Exception): pass
def git(*a): return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)

SPEC = dict(
    version=1, seed=2026, decision_status="모든 수치는 임의 출발값. S7 결과 열람 전에 동결. S5에서 체제 서사가 철회되어 '기간'으로만 비교.",
    periods={"P0709": [2007, 2009], "P1014": [2010, 2014], "P1519": [2015, 2019], "P2025": [2020, 2025]},
    period_note="국가 층 창이 2007년부터라 첫 기간이 3년(S4의 5개 기간과 다름). 마지막 기간은 6년(2025 부분연도·보유율 하락 후보).",
    main=dict(scheme="inv_n_authors", variant="main", sample="all", terr_merge=False, income="fixed"),
    grid=dict(scheme=["equal", "inv_n_authors", "first_last", "full_count"], variant=["main", "rec"], sample=["all", "fixed14"],
              terr_merge=[False, True], income=["fixed", "tv"]),
    terr_merge_map={"HK": "CN", "MO": "CN"}, top_k=5, active_mass_min=1.0,
    groups=["US", "CN", "HK_MO", "HIC_other", "UMC_other", "LMIC", "NOINC", "UNK"],
    group_rule="US, CN, HK+MO 별도, 나머지는 소득군(고정=wb_income_current, 시변=OGHIST 산정연도): HIC_other, UMC_other, LMIC(LMC+LIC), 소득군 없음=NOINC, 미상·구국가=UNK",
    stats=["top5_incl", "top5_known", "hhi_known", "cn_known", "us_known", "unk", "n_active", "theil_total", "theil_between", "theil_within_share"],
    theil="국가당 동일 가중 벤치마크 T=sum s ln(s N), N=그 구성의 알려진 국가 수(인구 가중 아님). 소득군 간/내 정확 분해, 항등식 점검 1e-9",
    direction_rule="주 구성과 방향이 다른 구성 비율 <= 0.25 (추세 Spearman 부호, 첫~마지막 기간 변화 부호). theil_*는 income 차원 포함, 그 외 통계는 income=fixed만 센다",
    bootstrap=dict(B=500, kind="논문 단위 Poisson(1) 가중(저널·공저 상관 미반영: 구간은 낙관적일 수 있음)"),
    author_layer=dict(id="name_norm(paper_author_long)", risk_variants=["base", "none"], base_weight="1/n_authors(F1 저자 수), 소속 국가 균등 분할",
                      roles="지속(두 기간 모두), 신규(t1에만, 첫 출판연도 >= t1 시작), 복귀(t1에만, 첫 출판연도 < t1 시작), 퇴출(t0에만)",
                      decomposition="Griliches-Regev 중점 분해를 지역군에 적용(적응, 재배분, 신규, 복귀, 퇴출)"),
    focus_topics=[88, 45, 69, 50, 0, 147, 38], top_change_n=10,
    interpretation="소속 국가는 국적이 아님. 지역 구성 변화는 함께 움직임의 기술이며 인과 아님. 복구 국가(rec)는 민감도.",
)
def spec_hash(s): return sha_b(json.dumps({k: v for k, v in s.items() if k not in ("sha256", "created", "refs")}, sort_keys=True, ensure_ascii=False).encode())

def freeze():
    S7.mkdir(parents=True, exist_ok=True); h = spec_hash(SPEC); p = S7/"S7_0_PREREG.json"
    print("S7-0 해시(예정)", h[:12])
    if p.exists():
        old = json.loads(p.read_text(encoding="utf-8")); print("이미 동결됨:", "동일" if old["sha256"] == h else "⛔ 다름(새 버전으로 분리하고 CHANGELOG에 사유)"); return
    refs = {}
    for f in [S2/"S2_PREREG_ADDENDUM.json", S1/"RECOVERY_RULES_PREREG.json", S1/"TERRITORY_RULES.md", S3/"L7_topic_grade.csv", S0/"PREREG.json"]:
        if f.exists(): refs[f.name] = sha_f(f)
    for n in ["country_mass_long.parquet", "country_mass_long.csv.gz"]:
        if (S2/n).exists(): refs[n] = sha_f(S2/n)
    p.write_text(json.dumps(dict(SPEC, created=now(), sha256=h, refs=refs), ensure_ascii=False, indent=1), encoding="utf-8")
    (S7/"CHANGELOG_S7.md").write_text(f"# CHANGELOG S7\n\n- {now()} | S7-0 동결(해시 {h[:12]}): 기간 4개, 구성 격자(가중치4 x 변형2 x 표본2 x 영토2 x 소득2), Theil(동일 가중), 부트스트랩 B=500, 저자 층 역할 정의. "
                                      f"S1~S6 산출물은 이미 열람한 상태에서 동결(S2의 C4 부호표·상위5개국 중간 결과를 본 뒤). 모든 수치는 임의 출발값 | S7 설계 | S7 전체\n", encoding="utf-8")
    print("저장: S7_0_PREREG.json | 참조 해시", list(refs))

def run():
    p = S7/"S7_0_PREREG.json"
    if not p.exists(): raise Halt("먼저 MODE='freeze'로 동결하세요")
    sp_ = json.loads(p.read_text(encoding="utf-8"))
    if spec_hash(sp_) != sp_["sha256"] or sp_["sha256"] != spec_hash(SPEC): raise Halt("동결 파일과 현재 SPEC이 다릅니다(사후 변경 금지)")
    print(f"동결 검증 통과 {sp_['sha256'][:12]} | QUICK={QUICK}")
    rng = np.random.default_rng(int(SPEC["seed"])); sfx = "_QUICK" if QUICK else ""
    PER = {k: tuple(v) for k, v in SPEC["periods"].items()}; YP = {y: k for k, (a, b) in PER.items() for y in range(a, b+1)}
    GROUPS = SPEC["groups"]; TM = SPEC["terr_merge_map"]; TOPK = SPEC["top_k"]; AMIN = SPEC["active_mass_min"]; mn = SPEC["main"]
    FIXED = set(json.loads((S0/"PREREG.json").read_text(encoding="utf-8"))["event"]["fixed_venues"]); assert len(FIXED) == 14
    cur = pd.read_csv(S1/"wb_income_current.csv", keep_default_na=False); cur = cur[(cur.income != "INX") & (cur.region != "NA")]
    INC_FIXED = dict(zip(cur.iso2, cur.income))
    H = pd.read_csv(S1/"wb_income_history.csv", keep_default_na=False); INC_TV = {(a, int(b)): c for a, b, c in zip(H.iso2, H.year, H.income)}
    inc_of = lambda c, y, m: (lambda v: v if v in ("HIC", "UMC", "LMC", "LIC") else "NOINC")(INC_FIXED.get(c) if m == "fixed" else INC_TV.get((c, y)))
    def grp_of(c, y, m="fixed"):
        if c in ("UNK", "ZZ_former"): return "UNK"
        if c in ("US", "CN"): return c
        if c in ("HK", "MO"): return "HK_MO"
        return {"HIC": "HIC_other", "UMC": "UMC_other", "LMC": "LMIC", "LIC": "LMIC"}.get(inc_of(c, y, m), "NOINC")
    def add_group(d, m="fixed"):
        u = d[["country", "year"]].drop_duplicates(); u["g"] = [grp_of(c, y, m) for c, y in zip(u.country, u.year)]; return d.merge(u, on=["country", "year"], how="left")

    # ---------- 입력 ----------
    pm = S2/"country_mass_long.parquet"
    M = pd.read_parquet(pm) if pm.exists() else pd.read_csv(S2/"country_mass_long.csv.gz", dtype={"pid": str})
    M["pid"] = M.pid.astype(str); M = M[M.year >= 2007]
    print(f"질량표 {len(M):,}행 | scheme {sorted(M.scheme.unique())} | variant {sorted(M.variant.unique())}")
    for sc in ["equal", "inv_n_authors", "first_last"]:       # 불변식: 논문당 질량 합 1
        s = M[(M.scheme == sc) & (M.variant == "main")].groupby("pid").w.sum()
        if not np.allclose(s, 1.0): raise Halt(f"불변식 실패: {sc} 논문당 질량 합 != 1")
    print("불변식 통과: 논문당 질량 합 = 1 (equal, inv_n_authors, first_last)")
    pools = {(sc, v): d for (sc, v), d in M.groupby(["scheme", "variant"])}

    def prep(sc, v, sample, terr):
        d = pools[(sc, v)]
        if sample == "fixed14": d = d[d.venue_short.isin(FIXED)]
        d = d[["year", "country", "w"]]
        if terr: d = d.assign(country=d.country.replace(TM))
        return d.groupby(["year", "country"], as_index=False).w.sum()

    def theil_parts(s, gi, ng):
        N = len(s); nz = s > 0; T = float((s[nz]*np.log(s[nz]*N)).sum()); sg = np.bincount(gi, weights=s, minlength=len(ng)); ok = sg > 0
        Tb = float((sg[ok]*np.log(sg[ok]*N/ng[ok])).sum()); Tw = 0.0
        for g in np.where(ok)[0]:
            m = (gi == g) & nz; r = s[m]/sg[g]; Tw += sg[g]*float((r*np.log(r*ng[g])).sum())
        if abs(T - Tb - Tw) > 1e-9: raise Halt("불변식 실패: Theil 분해 항등식")
        return T, Tb, Tw
    INC_IDX = {"HIC": 0, "UMC": 1, "LMC": 2, "LIC": 3, "NOINC": 4}
    def stats_of(vec, cols, y, imode):
        unk = np.isin(cols, ["UNK", "ZZ_former"]); kn = np.where(unk, 0.0, vec); kt = kn.sum(); tot = vec.sum()
        if kt <= 0: return {}
        top = np.sort(kn)[::-1][:TOPK].sum(); s = (kn/kt)[~unk]; kc = cols[~unk]
        gi = np.array([INC_IDX[inc_of(c, y, imode)] for c in kc]); ng = np.bincount(gi, minlength=5).astype(float)
        T, Tb, Tw = theil_parts(s, gi, ng)
        return dict(top5_incl=top/tot, top5_known=top/kt, hhi_known=float(((kn/kt)**2).sum()), cn_known=float(kn[cols == "CN"].sum()/kt), us_known=float(kn[cols == "US"].sum()/kt),
                    unk=float(1 - kt/tot), n_active=int((kn >= AMIN).sum()), theil_total=T, theil_between=Tb, theil_within_share=Tw/T if T > 0 else np.nan)
    def stats_table(d, imode):
        G = d.pivot_table(index="year", columns="country", values="w", aggfunc="sum", fill_value=0); cols = np.array(G.columns)
        Y = pd.DataFrame([dict(year=int(y), **stats_of(v.values, cols, int(y), imode)) for y, v in G.iterrows()])
        Pp = pd.DataFrame([dict(period=k, **stats_of(G.loc[a:b].sum(0).values, cols, (a+b)//2, imode)) for k, (a, b) in PER.items()])
        return Y, Pp, G

    # ---------- 7.1 구성 격자: 가중치 x 변형 x 표본 x 영토 x 소득 ----------
    G_ = SPEC["grid"]; Yl, Pl, SG = [], [], []; mainG = None
    for sc in G_["scheme"]:
        for v in G_["variant"]:
            for sample in G_["sample"]:
                for terr in G_["terr_merge"]:
                    d = prep(sc, v, sample, terr)
                    for im in G_["income"]:
                        Y, Pp, G = stats_table(d, im); cfg = dict(scheme=sc, variant=v, sample=sample, terr_merge=terr, income=im)
                        Yl.append(Y.assign(**cfg)); Pl.append(Pp.assign(**cfg))
                        for st in SPEC["stats"]:
                            y = Y[st].astype(float); a = Pp.set_index("period")[st]
                            SG.append(dict(**cfg, stat=st, rho=spearmanr(Y.year, y)[0], slope=float(np.polyfit(Y.year, y, 1)[0]), delta_first_last=float(a["P2025"]-a["P0709"]),
                                           sign_trend=int(np.sign(spearmanr(Y.year, y)[0])), sign_delta=int(np.sign(a["P2025"]-a["P0709"]))))
                        if (sc, v, sample, terr, im) == (mn["scheme"], mn["variant"], mn["sample"], mn["terr_merge"], mn["income"]): mainG = G
    Y_all, P_all, S_all = pd.concat(Yl), pd.concat(Pl), pd.DataFrame(SG)
    Y_all.to_csv(S7/f"s7_yearly_stats{sfx}.csv", index=False, encoding="utf-8-sig"); P_all.to_csv(S7/f"s7_period_stats{sfx}.csv", index=False, encoding="utf-8-sig"); S_all.to_csv(S7/f"s7_trend_signs{sfx}.csv", index=False, encoding="utf-8-sig")
    mc = lambda df: (df.scheme == mn["scheme"]) & (df.variant == mn["variant"]) & (df["sample"] == mn["sample"]) & (df.terr_merge == mn["terr_merge"]) & (df.income == mn["income"])
    print("\n[주 구성 기간별 통계]\n", P_all[mc(P_all)][["period"] + SPEC["stats"]].round(4).to_string(index=False))
    rows = []
    for st in SPEC["stats"]:
        d = S_all[S_all.stat == st]
        if not st.startswith("theil"): d = d[d.income == "fixed"]
        b = d[mc(d)].iloc[0]
        for kind in ["sign_trend", "sign_delta"]:
            for samp, g in [("전체 구성", d), ("표본=all", d[d["sample"] == "all"]), ("표본=fixed14", d[d["sample"] == "fixed14"])]:
                rows.append(dict(stat=st, kind=kind, subset=samp, main_sign=int(b[kind]), n=len(g), frac_diff=float((g[kind] != b[kind]).mean()), rho_min=g.rho.min(), rho_max=g.rho.max(),
                                 delta_min=g.delta_first_last.min(), delta_max=g.delta_first_last.max()))
    DS = pd.DataFrame(rows); DS["pass_le_0.25"] = DS.frac_diff <= SPEC["direction_rule"] and True if False else DS.frac_diff <= 0.25
    DS.to_csv(S7/f"s7_direction_split{sfx}.csv", index=False, encoding="utf-8-sig")
    print("\n[방향 갈림 비율: 전체 구성 기준]\n", DS[DS.subset == "전체 구성"].round(3).to_string(index=False))
    print("※ 연도 19개 Spearman은 |rho|<0.46이면 부호가 불안정합니다. 부호 일치와 함께 rho·변화량 범위(위 표)를 같이 보고하세요.")

    # ---------- 부트스트랩(주 구성, 영토 별도, 소득 고정): 기간별 통계와 차이의 구간 ----------
    B = 50 if QUICK else int(SPEC["bootstrap"]["B"]); boot_rows = []
    for sample in ["all", "fixed14"]:
        d = pools[(mn["scheme"], mn["variant"])]
        if sample == "fixed14": d = d[d.venue_short.isin(FIXED)]
        pid_c = d.pid.astype("category"); cc = d.country.astype("category"); cols = np.array(cc.cat.categories)
        X = sp.csr_matrix((d.w.values, (pid_c.cat.codes.values, cc.cat.codes.values)), shape=(len(pid_c.cat.categories), len(cols))); XT = X.T.tocsr()
        py = d.groupby("pid").year.first().reindex(pid_c.cat.categories).values; pmask = {k: ((py >= a) & (py <= b)).astype(float) for k, (a, b) in PER.items()}
        gcol = {k: np.array([grp_of(c, (a+b)//2) for c in cols]) for k, (a, b) in PER.items()}
        def pstats(v):
            out = {}
            for k, (a, b) in PER.items():
                vec = XT @ (v*pmask[k]); st = stats_of(vec, cols, (a+b)//2, "fixed")
                for g in GROUPS: st[f"share_{g}"] = float(vec[gcol[k] == g].sum()/vec.sum())
                out[k] = st
            return out
        obs = pstats(np.ones(X.shape[0])); keys = list(obs["P0709"].keys()); arr = {k: {s: [] for s in keys} for k in PER}
        for _ in range(B):
            r = pstats(rng.poisson(1.0, X.shape[0]).astype(float))
            for k in PER:
                for s in keys: arr[k][s].append(r[k].get(s, np.nan))
        pairs = [("P0709", "P1014"), ("P1014", "P1519"), ("P1519", "P2025"), ("P0709", "P2025")]
        for s in keys:
            for k in PER:
                x = np.array(arr[k][s], float); boot_rows.append(dict(sample=sample, stat=s, what=k, obs=obs[k].get(s), lo=np.nanpercentile(x, 2.5), med=np.nanmedian(x), hi=np.nanpercentile(x, 97.5)))
            for a, b in pairs:
                x = np.array(arr[b][s], float) - np.array(arr[a][s], float); boot_rows.append(dict(sample=sample, stat=s, what=f"{a}->{b}", obs=obs[b].get(s)-obs[a].get(s), lo=np.nanpercentile(x, 2.5), med=np.nanmedian(x), hi=np.nanpercentile(x, 97.5)))
    BT = pd.DataFrame(boot_rows); BT.to_csv(S7/f"s7_bootstrap{sfx}.csv", index=False, encoding="utf-8-sig")
    print(f"\n[부트스트랩 B={B}: 첫~마지막 기간 변화(P0709->P2025), 구간이 0을 포함하지 않는 통계]")
    z = BT[BT.what == "P0709->P2025"]; z = z.assign(excl0=(z.lo > 0) | (z.hi < 0)); print(z[["sample", "stat", "obs", "lo", "hi", "excl0"]].round(4).to_string(index=False))

    # ---------- 신규 국가 진입(창 안, 좌측 절단 표시) ----------
    kn = [c for c in mainG.columns if c not in ("UNK", "ZZ_former")]; ent = []
    for c in kn:
        act = mainG[c][mainG[c] >= AMIN]
        if len(act): fy = int(act.index.min()); ent.append(dict(country=c, first_active_year=fy, left_censored=(fy == 2007), income_fixed=inc_of(c, 2016, "fixed"), total_mass=float(mainG[c].sum())))
    E = pd.DataFrame(ent).sort_values("first_active_year"); E["period"] = E.first_active_year.map(YP); E.to_csv(S7/f"s7_country_entry{sfx}.csv", index=False, encoding="utf-8-sig")
    print("\n[기간별 신규 활성 국가 수(2007 첫 해 제외, 소득군별)]\n", E[~E.left_censored].groupby(["period", "income_fixed"]).size().unstack(fill_value=0).to_string())

    # ---------- 저널 통제: 지역군 몫 변화의 저널 내/간 정확 분해 ----------
    d = add_group(pools[(mn["scheme"], mn["variant"])][["year", "venue_short", "country", "w"]]); d["per"] = d.year.map(YP)
    tab = d.groupby(["per", "venue_short", "g"]).w.sum().unstack(fill_value=0).reindex(columns=GROUPS, fill_value=0); jr = []
    keys_p = list(PER)
    for a, b in zip(keys_p[:-1], keys_p[1:]):
        T0, T1 = tab.loc[a], tab.loc[b]; V = T0.index.union(T1.index); T0, T1 = T0.reindex(V, fill_value=0), T1.reindex(V, fill_value=0)
        n0, n1 = T0.sum(1).values, T1.sum(1).values; w0, w1 = n0/n0.sum(), n1/n1.sum()
        s0 = np.divide(T0.values, n0[:, None], out=np.zeros(T0.shape), where=n0[:, None] > 0); s1 = np.divide(T1.values, n1[:, None], out=np.zeros(T1.shape), where=n1[:, None] > 0)
        wi = (((w0+w1)/2)[:, None]*(s1-s0)).sum(0); bt = (((s0+s1)/2)*(w1-w0)[:, None]).sum(0); tot = (w1[:, None]*s1).sum(0) - (w0[:, None]*s0).sum(0)
        if np.abs(wi+bt-tot).max() > 1e-9: raise Halt("불변식 실패: 저널 내/간 분해")
        for i, g in enumerate(GROUPS): jr.append(dict(pair=f"{a}->{b}", group=g, delta=tot[i], within_journal=wi[i], between_journal=bt[i], between_share=abs(bt[i])/(abs(wi[i])+abs(bt[i])+1e-15)))
    JR = pd.DataFrame(jr); JR.to_csv(S7/f"s7_journal_control{sfx}.csv", index=False, encoding="utf-8-sig"); print("\n[저널 통제: 지역군 몫 변화]\n", JR.round(4).to_string(index=False))

    # ---------- 7.2 저자 층: 신규 저자의 지역 구성 + 지역군 분해 ----------
    F = load_F1X(); pal = pd.read_csv(PAL, usecols=["pid", "author_pos", "name_norm"], dtype={"pid": str}).dropna().drop_duplicates(["pid", "author_pos"])
    first = pal.merge(F[["pid", "year"]], on="pid").groupby("name_norm").year.min()
    A = pd.read_parquet(S1/"authorship_level.parquet") if (S1/"authorship_level.parquet").exists() else pd.read_csv(S1/"authorship_level.csv.gz")
    A["pid"] = A.pid.astype(str); A["countries"] = A.countries.fillna(""); Rr = pd.read_csv(S1/"authorship_level_recovered.csv.gz", dtype={"pid": str}); Rr["countries_rec"] = Rr.countries_rec.fillna("")
    A = A.merge(Rr[["pid", "rank", "countries_rec"]], on=["pid", "rank"], how="left"); A["countries_rec"] = A.countries_rec.fillna("")
    A["cs_main"] = A.countries; A["cs_rec"] = np.where((A.countries == "") & (A.countries_rec != ""), A.countries_rec, A.countries)
    A["n"] = A.groupby("pid")["rank"].transform("size"); A["author_pos"] = A["rank"] + 1
    A = A.merge(pal, on=["pid", "author_pos"], how="left"); print(f"\n저자 행 {len(A):,} | 이름 매칭 실패 {A.name_norm.isna().mean():.2%} (제외, 질량 손실로 보고)"); A = A.dropna(subset=["name_norm"])
    A = A.merge(F[["pid", "year", "venue_short", "has_topic", "topic150", "in_sample"]], on="pid", how="inner")
    tops = np.array(sorted(pd.read_csv(S3/"L7_topic_grade.csv").topic.astype(int))); tix = {t: i for i, t in enumerate(tops)}; K = len(tops)
    A["ti"] = np.where(tf(A.has_topic) & A.topic150.notna(), A.topic150.fillna(-1).astype(int).map(lambda t: tix.get(t, -1)), -1)
    risk = pd.read_csv(DATA/"F2_risk_names.csv"); RISK = set(risk[tf(risk.ambiguous) | tf(risk.heavy)].name_norm)
    gi_map = {g: i for i, g in enumerate(GROUPS)}

    def author_rows(cscol, variant):
        R = A if variant == "none" else A[~A.name_norm.isin(RISK)]
        s = R[cscol].where(R[cscol] != "", "UNK").str.split("|"); k = s.str.len().values
        X = pd.DataFrame({"name": np.repeat(R.name_norm.values, k), "year": np.repeat(R.year.values, k), "ti": np.repeat(R.ti.values, k), "w": np.repeat((1.0/R.n.values)/k, k),
                          "country": np.concatenate(s.values)})
        X = add_group(X); X["gi"] = X.g.map(gi_map).astype(int); X["per"] = X.year.map(YP); return X
    def amat(r, idx, N): return sp.coo_matrix((r.w.values/N, (idx.get_indexer(r.name), r.gi.values)), shape=(len(idx), len(GROUPS))).tocsr()
    def decomp5(M0, M1, en, er):
        w0, w1 = np.asarray(M0.sum(1)).ravel(), np.asarray(M1.sum(1)).ravel(); S0_, S1_ = np.asarray(M0.sum(0)).ravel(), np.asarray(M1.sum(0)).ravel(); Sb = (S0_+S1_)/2
        cont, ex = (w0 > 0) & (w1 > 0), (w0 > 0) & (w1 == 0); C0, C1 = M0[cont].toarray(), M1[cont].toarray(); a0, a1 = w0[cont], w1[cont]; s0, s1 = C0/a0[:, None], C1/a1[:, None]
        tm = dict(adapt=(((a0+a1)/2)[:, None]*(s1-s0)).sum(0), realloc=((((s0+s1)/2)-Sb)*(a1-a0)[:, None]).sum(0),
                  entry_new=np.asarray(M1[en].sum(0)).ravel()-Sb*w1[en].sum(), entry_ret=np.asarray(M1[er].sum(0)).ravel()-Sb*w1[er].sum(),
                  exit=-(np.asarray(M0[ex].sum(0)).ravel()-Sb*w0[ex].sum()))
        if np.abs(sum(tm.values())-(S1_-S0_)).max() > 1e-9: raise Halt("불변식 실패: 지역군 5항 분해")
        return tm, S0_, S1_, w0, w1, cont, ex
    rows_comp, rows_dec, rows_path = [], [], []
    for variant, cscol in [("base", "cs_main"), ("none", "cs_main"), ("base_rec", "cs_rec")]:
        R = author_rows(cscol, "none" if variant == "none" else "base")
        if abs(R.w.sum() - (A if variant == "none" else A[~A.name_norm.isin(RISK)]).eval("1.0/n").sum()) > 1e-6: raise Halt("불변식 실패: 저자 질량 보존")
        for a, b in zip(keys_p[:-1], keys_p[1:]):
            r0, r1 = R[R.per == a], R[R.per == b]; N0, N1 = r0.w.sum(), r1.w.sum(); idx = pd.Index(pd.concat([r0.name, r1.name]).unique())
            M0, M1 = amat(r0, idx, N0), amat(r1, idx, N1); fy = idx.map(first).fillna(9999).values
            w0, w1 = np.asarray(M0.sum(1)).ravel(), np.asarray(M1.sum(1)).ravel(); en_all = (w0 == 0) & (w1 > 0); er = en_all & (fy < PER[b][0]); en = en_all & ~er
            tm, S0_, S1_, w0, w1, cont, ex = decomp5(M0, M1, en, er)
            for i, g in enumerate(GROUPS):
                rows_dec.append(dict(variant=variant, pair=f"{a}->{b}", group=g, share0=S0_[i], share1=S1_[i], delta=S1_[i]-S0_[i], **{k: v[i] for k, v in tm.items()}))
            roles = {"continuing_t1": (M1[cont], w1[cont]), "new_t1": (M1[en], w1[en]), "returning_t1": (M1[er], w1[er]), "exit_t0": (M0[ex], w0[ex])}
            for rn, (Mx, wx) in roles.items():
                v = np.asarray(Mx.sum(0)).ravel(); rows_comp.append(dict(variant=variant, pair=f"{a}->{b}", role=rn, mass=float(wx.sum()), authors=int(Mx.shape[0]), **{f"share_{g}": v[i]/v.sum() for i, g in enumerate(GROUPS)}))
            if variant != "base": continue
            q0, q1 = r1[r1.ti >= 0], None   # 신규 대 지속 저자의 토픽 분포 경로 분해(t1, 지역군 경유)
            role = pd.Series(np.where(~idx.isin([]), "x", "x"), index=idx); cm = pd.Series(cont, index=idx); nm = pd.Series(en, index=idx)
            q = q0.assign(c=cm.reindex(q0.name).values, e=nm.reindex(q0.name).values)
            mk = lambda m: sp.coo_matrix((q[m].w.values, (q[m].gi.values, q[m].ti.values)), shape=(len(GROUPS), K)).toarray()
            Ev, Pv = mk(q.e.values.astype(bool)), mk(q.c.values.astype(bool))
            if Ev.sum() > 0 and Pv.sum() > 0:
                e, p_ = Ev.sum(1)/Ev.sum(), Pv.sum(1)/Pv.sum(); dist = lambda Z: np.divide(Z, Z.sum(1, keepdims=True), out=np.zeros_like(Z), where=Z.sum(1, keepdims=True) > 0)
                Ej, Pj = dist(Ev), dist(Pv); wi_ = (((e+p_)/2)[:, None]*(Ej-Pj)).sum(0); bt_ = (((Ej+Pj)/2)*(e-p_)[:, None]).sum(0); gap = Ev.sum(0)/Ev.sum()-Pv.sum(0)/Pv.sum()
                if np.abs(wi_+bt_-gap).max() > 1e-9: raise Halt("불변식 실패: 신규-지속 지역 경로 분해")
                for j, t in enumerate(tops): rows_path.append(dict(pair=f"{a}->{b}", topic=int(t), gap=gap[j], within_region=wi_[j], between_region=bt_[j]))
    CO, DC, PA = pd.DataFrame(rows_comp), pd.DataFrame(rows_dec), pd.DataFrame(rows_path)
    CO.to_csv(S7/f"s7_entrant_composition{sfx}.csv", index=False, encoding="utf-8-sig"); DC.to_csv(S7/f"s7_author_group_decomp{sfx}.csv", index=False, encoding="utf-8-sig"); PA.to_csv(S7/f"s7_entrant_topic_path{sfx}.csv", index=False, encoding="utf-8-sig")
    print("\n[신규·지속·복귀·퇴출 저자의 지역 몫 (base)]\n", CO[CO.variant == "base"].round(3).to_string(index=False))
    print("\n[지역군 몫 변화의 5항 분해 (base, 지역군별)]\n", DC[DC.variant == "base"].round(4).to_string(index=False))
    print("※ 신규(first_year>=t1 시작)와 복귀(이전 출판)를 분리. 'none' 변형은 위험군 제외 영향, 'base_rec'은 국가 복구 영향(민감도).")
    ab = PA.assign(aw=PA.within_region.abs(), ab=PA.between_region.abs()).groupby("pair")[["aw", "ab"]].sum(); ab["between_abs_share"] = ab.ab/(ab.aw+ab.ab); print("\n[신규-지속 토픽 차이의 지역 간 성분 비중(절대합)]\n", ab.round(3).to_string())

    # ---------- 토픽 변화의 지역 간/내 정확 분해(논문 단위 국가 질량, 두 표본) ----------
    tp = F[tf(F.has_topic) & F.topic150.notna()][["pid", "topic150"]]; tp = tp.assign(ti=tp.topic150.astype(int).map(tix)); print(f"토픽 매핑 실패(제외) {tp.ti.isna().sum():,}편 / {len(tp):,}편"); tp = tp.dropna(subset=["ti"]).assign(ti=lambda x: x.ti.astype(int)); rt = []
    for sample in ["all", "fixed14"]:
        d = pools[(mn["scheme"], mn["variant"])]
        if sample == "fixed14": d = d[d.venue_short.isin(FIXED)]
        d = d.merge(tp[["pid", "ti"]], on="pid", how="inner"); d = add_group(d[["year", "country", "w", "ti"]]); d["per"] = d.year.map(YP); d["gi"] = d.g.map(gi_map).astype(int); d = d.dropna(subset=["per"])
        cube = {k: np.zeros((len(GROUPS), K)) for k in PER}
        for k, g in d.groupby("per"): np.add.at(cube[k], (g.gi.values, g.ti.values), g.w.values)
        for a, b in zip(keys_p[:-1], keys_p[1:]):
            c0, c1 = cube[a], cube[b]; n0, n1 = c0.sum(1), c1.sum(1); w0, w1 = n0/n0.sum(), n1/n1.sum()
            s0 = np.divide(c0, n0[:, None], out=np.zeros_like(c0), where=n0[:, None] > 0); s1 = np.divide(c1, n1[:, None], out=np.zeros_like(c1), where=n1[:, None] > 0)
            wi = ((w0+w1)/2)[:, None]*(s1-s0); bt = ((s0+s1)/2)*(w1-w0)[:, None]; tot = (w1[:, None]*s1).sum(0)-(w0[:, None]*s0).sum(0)
            if np.abs(wi.sum(0)+bt.sum(0)-tot).max() > 1e-9: raise Halt("불변식 실패: 토픽 지역 분해")
            sel = set(np.argsort(-np.abs(tot))[:SPEC["top_change_n"]]) | {tix[t] for t in SPEC["focus_topics"] if t in tix}
            for j in sorted(sel):
                gc = wi[:, j]+bt[:, j]; top = int(np.argmax(np.abs(gc)))
                rt.append(dict(sample=sample, pair=f"{a}->{b}", topic=int(tops[j]), delta=tot[j], within_region=wi[:, j].sum(), between_region=bt[:, j].sum(), between_share=abs(bt[:, j].sum())/(abs(wi[:, j].sum())+abs(bt[:, j].sum())+1e-15),
                               top_group=GROUPS[top], top_group_contrib=gc[top], **{f"c_{g}": gc[i] for i, g in enumerate(GROUPS)}))
    RT = pd.DataFrame(rt); RT.to_csv(S7/f"s7_topic_region_decomp{sfx}.csv", index=False, encoding="utf-8-sig")
    print("\n[초점 토픽의 지역 기여 (표본=all)]\n", RT[(RT["sample"] == "all") & RT.topic.isin(SPEC["focus_topics"])][["pair", "topic", "delta", "within_region", "between_region", "top_group", "top_group_contrib"]].round(4).to_string(index=False))
    print("※ 88·45(전기모터), 69(텐서)가 특정 지역 유입으로 설명되는지는 top_group과 기여 크기로 판정. 인과 아님.")

    # ---------- 기록 ----------
    outs = sorted(f.name for f in S7.glob(f"s7_*{sfx}.csv"))
    meta = dict(spec_sha256=sp_["sha256"], at=now(), quick=QUICK, B=B, outputs={f: sha_f(S7/f) for f in outs}); (S7/f"S7_meta{sfx}.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    if not QUICK:
        with (S7/"CHANGELOG_S7.md").open("a", encoding="utf-8") as f:
            f.write(f"- {now()} | S7 본 실행(규칙 해시 {sp_['sha256'][:12]}, 판정 변경 없음): 구성 격자 {len(G_['scheme'])*len(G_['variant'])*len(G_['sample'])*len(G_['terr_merge'])*len(G_['income'])}개, 부트스트랩 B={B}, 저자 층 변형 base/none/base_rec | S7 | S8\n")
        if COMMIT:
            fl = ["paper1/07_S7"] + (["paper1/s7_run.py"] if (ROOT/"paper1/s7_run.py").exists() else []); tag = f"S7-results-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
            if git("tag", "-l", tag).stdout.strip(): raise Halt(f"태그 {tag} 이미 있음")
            r = git("add", "--", *fl);  r.returncode and (_ for _ in ()).throw(Halt(f"git add 실패: {r.stderr.strip()}"))
            r = git("commit", "-m", "S7 results (frozen rules)"); r.returncode and (_ for _ in ()).throw(Halt(f"git commit 실패: {(r.stdout+r.stderr)[:300]}"))
            r = git("tag", "-a", tag, "-m", "S7"); r.returncode and (_ for _ in ()).throw(Halt(f"git tag 실패: {r.stderr.strip()}")); print("커밋·태그:", tag)
    print("\n저장 완료:", len(outs), "개 파일")

def load_F1X():
    F1 = pd.read_csv(DATA/"F1_papers.csv", low_memory=False); F1["pid"] = F1.pid.astype(str)
    exf = S0/"EXCLUDE_PIDS_FROZEN.csv"; log = pd.read_csv(S0/"FREEZE_LOG.csv"); last = log[log.file == exf.name].iloc[-1]
    if sha_f(exf) != last.sha256: raise Halt("EXCLUDE_PIDS_FROZEN.csv 해시 불일치")
    return F1[~F1.pid.isin(set(pd.read_csv(exf, dtype=str, encoding="utf-8-sig").pid))].copy()

try: {"freeze": freeze, "run": run}[MODE]()
except Halt as e: print(f"⛔ 중단: {e}")