# -*- coding: utf-8 -*-
# PA-C1: 마지막 쌍(P1519->P2025)에서 중국 소속 저자를 제외해도 진입 우세가 유지되는가. 미실행 코드.
# MODE: "freeze" -> "tag" -> (git push --follow-tags) -> "run"(QUICK=True: 오류 점검 전용, 결과 수치 미출력) -> "run"(QUICK=False)
# S0~S8 판정 불변. 모든 산출물 [Post-hoc].
import sys, json, hashlib, subprocess, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore"); pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40)
MODE = "tag"
QUICK = True

ROOT = Path.home() / "Research/Minnesota_Transport"; P1 = ROOT/"paper1"; PA = P1/"09_PA"; S0, S1, S6D, S7D = P1/"00_S0", P1/"01_S1", P1/"06_S6", P1/"07_S7"
DATA = ROOT/"analysis_data/final"; PAL = ROOT/"analysis_data/paper_author_long.csv"
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds")
sha_b = lambda b: hashlib.sha256(b).hexdigest(); sha_f = lambda p: sha_b(Path(p).read_bytes())
tf = lambda s: s.astype(str).str.strip().str.lower().isin(["1", "1.0", "true", "t", "yes"])
git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
class Halt(Exception): pass
spec_hash = lambda s: sha_b(json.dumps({k: v for k, v in s.items() if k not in ("sha256", "created", "refs")}, sort_keys=True, ensure_ascii=False).encode())
V2P, BP = PA/"PA_0_PLAN_v2.json", PA/"PA_C1_PLAN.json"

PLAN = dict(
    version=1, seed=2026, parent="PA_0_PLAN_v2.json",
    status="사후 명세. S6·S7 결과, Pair·load_all·author_rows 소스, PA-A2a·A2b·A2c·C2 결과, authorship_level 열 형식(2글자 코드 100%, 빈 값 약 5%)은 열람한 상태. PA-C1 결과 미열람. 시나리오를 3개로 둔 이유: 중국 소속 진입 저자만 빼면 진입 질량이 기계적으로 줄어 강한 시험이 되고, 모든 역할에서 빼는 b_all이 더 공정한 대조이기 때문. S0~S8 판정 불변.",
    target="마지막 쌍 P1519->P2025만(S6·S7 기간이 일치하는 유일한 쌍). S6 주 설정 spec['main']과 s6_lib.make_pair 그대로",
    cn_def="2020~2025 출판 저자 중 CN(HK·MO 제외) 질량/알려진 국가 질량(UNK, ZZ_former 제외) >= 0.5. 질량=논문당 1/n_authors를 소속 국가 수로 균등 분할(S7 author_rows와 동일, 위험군 이름 제외, cs_main). 알려진 질량 0이면 비해당",
    scenarios={"a_new": "CN 소속 and 역할 E_new인 저자의 모든 행 제거", "a_entrants": "CN 소속 and 역할 E_new 또는 E_ret인 저자의 모든 행 제거", "b_all": "CN 소속 저자를 모든 역할에서 모든 기간 행 제거"},
    stats="entry_share, adapt_share, entry_minus_adapt (4항 분모, 진입=신규+복귀: PA-A2c와 동일)",
    boot="저자 가중 wa~Exp(1)을 원본 저자 전체에서 뽑아 제외 후 같은 저자에게 같은 값(대응 부트스트랩), B=spec['B_boot'], 역할은 재표집에서 고정. 보고: delta(sub-orig) 백분위·basic 구간, 제외 후 수준의 백분위·basic 구간",
    reading="시나리오별로 entry_minus_adapt의 obs_sub>0 이고 제외 후 수준의 basic 구간 하한>0이면 '진입 우세 유지', 아니면 '유지 안 됨'. 시나리오를 합치지 않음. 변화량 delta는 병기만",
    diagnostics="역할별(P, E_new, E_ret, X_final, X_gap) 저자 수·CN 소속 저자 비율·질량 비중(P·E는 후기 질량, X는 전기 질량). 총 CN 소속 이름 수",
    reproduce_check="(a) 직접 만든 P2025 CN 질량 몫이 s7_author_group_decomp.csv(variant=base, pair=P1519->P2025, group=CN)의 share1과 1e-6 이내, (b) orig total_half가 renewal_decomposition.csv와 1e-6 이내, (c) orig entry_share가 PA_A2c_results.csv(mode=author)와 1e-6 이내, (d) 제외 후 저자 집합이 원본의 부분집합",
    caveat="분류는 inv_n_authors(S7), 분해는 S6 주 설정 가중이라 혼합임. 소속은 국적이 아님. 이름 기반 식별 한계 그대로. 복구 국가(countries_rec) 미사용. 마지막 쌍 하나만 대상이며 b_all은 퇴출 저자(2020-25 비출판)를 판정할 수 없어 대칭이 완전하지 않음",
    forbidden="결과를 본 뒤 CN 정의(0.5)·시나리오·B·판독 기준 변경(변경 시 v2 계획으로 분리하고 사유 기록)")

def freeze():
    if not V2P.exists(): raise Halt("PA_0_PLAN_v2.json이 없습니다")
    h = spec_hash(PLAN); print("PA-C1 계획 해시(예정)", h[:12])
    if BP.exists(): print("이미 동결:", "동일" if json.loads(BP.read_text(encoding="utf-8"))["sha256"] == h else "⛔ 다름"); return
    refs = {f.name: sha_f(f) for f in [V2P, S7D/"S7_0_PREREG.json", S7D/"s7_author_group_decomp.csv", P1/"s6_lib.py", P1/"s7_run.py", S6D/"renewal_decomposition.csv", PA/"PA_A2c_results.csv"] if f.exists()}
    BP.write_text(json.dumps(dict(PLAN, created=now(), sha256=h, refs=refs), ensure_ascii=False, indent=1), encoding="utf-8")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as f:
        f.write(f"\n- {now()} | PA-C1 계획 동결(해시 {h[:12]}) | 사유: 중국 소속 저자 제외 후 진입 우세 유지 여부(S6xS7 연결), 시나리오 3개. PA-C1 결과 미열람. QUICK은 결과 수치 미출력 | 본 결과 변경 여부: 없음\n")
    print("저장: PA_C1_PLAN.json")

def tag():
    if not BP.exists(): raise Halt("먼저 freeze")
    t = f"PA-C1-plan-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    if git("tag", "-l", t).stdout.strip(): print("이미 있음:", t); return
    r = git("add", "--", "paper1/09_PA/PA_C1_PLAN.json", "paper1/09_PA/PA_CHANGELOG.md", "paper1/pa_c1.py"); print("add", r.returncode, r.stderr.strip())
    r = git("commit", "-m", "PA-C1 plan freeze (before execution)"); print("commit", r.returncode, (r.stdout + r.stderr)[:200])
    r = git("tag", "-a", t, "-m", "PA-C1 plan"); print("tag", r.returncode, r.stderr.strip()); print("※ 이어서 git push --follow-tags")

def run():
    if not BP.exists(): raise Halt("먼저 freeze")
    sp = json.loads(BP.read_text(encoding="utf-8"))
    if sp["sha256"] != spec_hash(sp) or sp["sha256"] != spec_hash(PLAN): raise Halt("동결 파일과 현재 계획이 다릅니다")
    if not git("tag", "-l", "PA-C1-plan-*").stdout.strip(): raise Halt("tag 단계를 먼저 실행하세요")
    sys.path.insert(0, str(P1)); import s6_lib as S
    spec = S.load_spec(); L = S.load_all(spec); M = spec["main"]; half = S.half; R = L["R"]
    sfx = "_QUICK" if QUICK else ""; B = 20 if QUICK else int(spec["B_boot"]); lo_q, hi_q = spec["ci"]; rng = np.random.default_rng(int(PLAN["seed"]))
    p0, p1 = "P1519", "P2025"; name = f"{p0}->{p1}"; a_, b_ = spec["periods"][p1]
    # ---- S7 방식 저자-국가 행 (2020~2025) ----
    F1 = pd.read_csv(DATA/"F1_papers.csv", low_memory=False); F1["pid"] = F1.pid.astype(str)
    exf = S0/"EXCLUDE_PIDS_FROZEN.csv"; log = pd.read_csv(S0/"FREEZE_LOG.csv"); last = log[log.file == exf.name].iloc[-1]
    if sha_f(exf) != last.sha256: raise Halt("EXCLUDE_PIDS_FROZEN.csv 해시 불일치")
    F = F1[~F1.pid.isin(set(pd.read_csv(exf, dtype=str, encoding="utf-8-sig").pid))].copy()
    pal = pd.read_csv(PAL, usecols=["pid", "author_pos", "name_norm"], dtype={"pid": str}).dropna().drop_duplicates(["pid", "author_pos"])
    pq = S1/"authorship_level.parquet"; A = pd.read_parquet(pq) if pq.exists() else pd.read_csv(S1/"authorship_level.csv.gz")
    A["pid"] = A.pid.astype(str); A["countries"] = A.countries.fillna(""); A["n"] = A.groupby("pid")["rank"].transform("size"); A["author_pos"] = A["rank"] + 1
    A = A.merge(pal, on=["pid", "author_pos"], how="left").dropna(subset=["name_norm"]); A = A.merge(F[["pid", "year"]], on="pid", how="inner")
    risk = pd.read_csv(DATA/"F2_risk_names.csv"); RISK = set(risk[tf(risk.ambiguous) | tf(risk.heavy)].name_norm)
    A = A[~A.name_norm.isin(RISK) & A.year.between(a_, b_)]
    s = A.countries.where(A.countries != "", "UNK").str.split("|"); k = s.str.len().values
    X = pd.DataFrame({"name": np.repeat(A.name_norm.values, k), "w": np.repeat((1.0/A.n.values)/k, k), "country": np.concatenate(s.values)})
    cn_mass = float(X.w[X.country == "CN"].sum()/X.w.sum()); ref7 = pd.read_csv(S7D/"s7_author_group_decomp.csv"); ref7 = ref7[(ref7.variant == "base") & (ref7.pair == name) & (ref7.group == "CN")]
    if len(ref7) != 1 or abs(cn_mass - float(ref7.share1.iloc[0])) > 1e-6: raise Halt(f"S7 CN 질량 몫 재현 실패: {cn_mass:.8f} vs {ref7.share1.tolist()}")
    unk = X.country.isin(["UNK", "ZZ_former"]); known = X[~unk].groupby("name").w.sum(); cn = X[X.country == "CN"].groupby("name").w.sum()
    sh = (cn.reindex(known.index).fillna(0.0)/known).where(known > 0); CNSET = set(sh[sh >= 0.5].index)
    print(f"[재현 OK] S7 CN 질량 몫 | CN 소속 이름 수 {len(CNSET):,} (설계 점검)")
    # ---- S6 쌍과 역할 ----
    Pa = S.make_pair(L, p0, p1, M["scheme"], M["venue"], M["topic"], M["hom"]); da = Pa.decompose(); half_ = half
    ref6 = pd.read_csv(S6D/"renewal_decomposition.csv"); ref6 = ref6[(ref6.scheme == M["scheme"]) & (ref6.variant == "all_venues")].set_index("pair")
    a2c = pd.read_csv(PA/"PA_A2c_results.csv"); a2c = a2c[(a2c["mode"] == "author") & (a2c.stat == "entry_share")].set_index("pair")
    STATS = ["entry_share", "adapt_share", "entry_minus_adapt"]
    def stats(d):
        h = {t: half_(d[t]) for t in ["adapt", "realloc", "entry", "exit"]}; tot = sum(h.values())
        return dict(entry_share=h["entry"]/tot, adapt_share=h["adapt"]/tot, entry_minus_adapt=(h["entry"] - h["adapt"])/tot)
    oa = stats(da)
    if abs(half_(da["total"]) - float(ref6.loc[name, "total_half"])) > 1e-6: raise Halt("S6 관측 재현 실패")
    if abs(oa["entry_share"] - float(a2c.loc[name, "obs"])) > 1e-6: raise Halt("PA-A2c entry_share 재현 실패")
    aid_of = R.drop_duplicates("ai").set_index("ai").aid; names = aid_of.loc[Pa.aids].values; isCN = pd.Series(names).isin(CNSET).values; role = Pa.role
    masks = {"a_new": isCN & (role == "E_new"), "a_entrants": isCN & np.isin(role, ["E_new", "E_ret"]), "b_all": isCN}
    PB, IDX, OB = {}, {}, {}
    for sc, mk in masks.items():
        L2 = dict(L); L2["R"] = R[~R.aid.isin(set(names[mk]))]; Pb = S.make_pair(L2, p0, p1, M["scheme"], M["venue"], M["topic"], M["hom"])
        idx = np.searchsorted(Pa.aids, Pb.aids)
        if not (idx < len(Pa.aids)).all() or not (Pa.aids[idx] == Pb.aids).all(): raise Halt(f"{sc}: 제외 후 저자 집합이 원본의 부분집합이 아님")
        PB[sc], IDX[sc], OB[sc] = Pb, idx, stats(Pb.decompose())
    # ---- 역할별 진단 ----
    mass0 = np.bincount(Pa.a0, Pa.m0, Pa.nA)/Pa.m0.sum(); mass1 = np.bincount(Pa.a1, Pa.m1, Pa.nA)/Pa.m1.sum(); roles = []
    for r in ["P", "E_new", "E_ret", "X_final", "X_gap"]:
        m = role == r; ms = mass0 if r.startswith("X") else mass1
        roles.append(dict(pair=name, role=r, n_authors=int(m.sum()), cn_author_share=float(isCN[m].mean()) if m.any() else np.nan, mass=float(ms[m].sum()), cn_mass_share=float(ms[m & isCN].sum()/ms[m].sum()) if ms[m].sum() > 0 else np.nan))
    # ---- 대응 부트스트랩 ----
    bs = {sc: [] for sc in masks}
    for _ in range(B):
        wa = rng.exponential(size=Pa.nA); sa = stats(Pa.decompose(Pa.m0*wa[Pa.a0], Pa.m1*wa[Pa.a1]))
        for sc, Pb in PB.items():
            wb = wa[IDX[sc]]; sb = stats(Pb.decompose(Pb.m0*wb[Pb.a0], Pb.m1*wb[Pb.a1])); bs[sc].append(dict(**{f"sub_{x}": sb[x] for x in STATS}, **{f"d_{x}": sb[x] - sa[x] for x in STATS}))
    rows = []
    for sc in masks:
        D = pd.DataFrame(bs[sc])
        for x in STATS:
            o_s, o_o = OB[sc][x], oa[x]; dl = o_s - o_o; ql, qh = np.percentile(D[f"d_{x}"], [lo_q, hi_q]); sl, sh_ = np.percentile(D[f"sub_{x}"], [lo_q, hi_q])
            rows.append(dict(pair=name, scenario=sc, stat=x, n_removed_authors=int(masks[sc].sum()), obs_orig=o_o, obs_sub=o_s, delta=dl, d_pct_lo=ql, d_pct_hi=qh, d_basic_lo=2*dl - qh, d_basic_hi=2*dl - ql,
                             sub_pct_lo=sl, sub_pct_hi=sh_, sub_basic_lo=2*o_s - sh_, sub_basic_hi=2*o_s - sl, n_authors_sub=int(PB[sc].nA), B=B))
    RS, RO = pd.DataFrame(rows), pd.DataFrame(roles)
    RS.to_csv(PA/f"PA_C1_results{sfx}.csv", index=False, encoding="utf-8-sig"); RO.to_csv(PA/f"PA_C1_roles{sfx}.csv", index=False, encoding="utf-8-sig")
    if QUICK: print("\n[QUICK] 오류 없이 완료. 결과 수치는 출력하지 않음(_QUICK 파일을 열어 해석하지 마세요)."); return
    print("\n[Post-hoc] PA-C1 결과\n", RS.round(4).to_string(index=False)); print("\n[Post-hoc] 역할별 CN 소속 비중\n", RO.round(4).to_string(index=False))
    k_ = RS[RS.stat == "entry_minus_adapt"].copy(); k_["kept"] = (k_.obs_sub > 0) & (k_.sub_basic_lo > 0)
    print("\n[동결 판독] entry_minus_adapt\n", k_[["scenario", "n_removed_authors", "obs_orig", "obs_sub", "delta", "sub_pct_lo", "sub_pct_hi", "sub_basic_lo", "kept"]].round(4).to_string(index=False))
    print("※ 마지막 쌍만. 시나리오를 합치지 않음. 소속은 국적 아님. S0~S8 판정 불변.")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as fh:
        fh.write(f"- {now()} | PA-C1 실행 | 정의: PA_C1_PLAN {sp['sha256'][:12]} | 결과: PA_C1_results.csv, PA_C1_roles.csv | 본 결과 변경 여부: 없음\n")

try: {"freeze": freeze, "tag": tag, "run": run}[MODE]()
except Halt as e: print(f"⛔ 중단: {e}")