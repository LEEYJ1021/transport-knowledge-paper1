# -*- coding: utf-8 -*-
# PA-B4: F1+F3 이분 등급(통과 145개 토픽)으로 S5·S6 재추정. S4·응집도 지표는 제외(별도). 미실행 코드.
# MODE: "freeze" -> "tag" -> (git push --follow-tags) -> "run"(QUICK=True: 오류 점검 전용, 수치 미출력) -> "run"(QUICK=False)
# S0~S8 판정 불변. 모든 산출물 [Post-hoc].
import sys, json, hashlib, subprocess, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore"); pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40)
MODE = "tag"
QUICK = True

ROOT = Path.home() / "Research/Minnesota_Transport"; P1 = ROOT/"paper1"; PA = P1/"09_PA"; S3 = P1/"03_S3"; S5D = P1/"05_S5"; S6D = P1/"06_S6"
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds")
sha_b = lambda b: hashlib.sha256(b).hexdigest(); sha_f = lambda p: sha_b(Path(p).read_bytes())
git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
class Halt(Exception): pass
spec_hash = lambda s: sha_b(json.dumps({k: v for k, v in s.items() if k not in ("sha256", "created", "refs")}, sort_keys=True, ensure_ascii=False).encode())
V2P, BP = PA/"PA_0_PLAN_v2.json", PA/"PA_B4_PLAN.json"

PLAN = dict(
    version=1, seed=2026, parent="PA_0_PLAN_v2.json",
    status="사후 명세(PA-B4 중 S5·S6 재추정만). S3 요약의 'F2 제외 시 A 145개', L7 열 구조, s5_lib·s6_lib 소스, S5·S6·A2a 결과는 열람한 상태. PA-B4 결과 미열람. S4 재추정과 응집도·Jaccard 지표는 별도 계획(PA-B4b 등)으로 분리. S0~S8 판정 불변.",
    grade_def="L7_topic_grade.csv의 F1, F3 열(True=실패). 통과 = F1 False and F3 False. 재현 점검: 통과 토픽 정확히 145개",
    expectation_note="F1·F3 실패는 합쳐 4개 토픽뿐이라 결과가 거의 같을 것으로 예상(약한 시험). 이 예상은 설계 사실이며 판독 기준이 아님",
    s5=dict(samples=["all", "fixed14", "within"], detector="s5_lib.detect 그대로, pen=c_primary*phi_s*(K-1)*log(T), K=145, phi_s·c_primary·k_max·min_len는 S5_0_PREREG.json 값 고정(K 변경에 따른 phi 재계산 안 함)",
            data="s5_lib.load_counts()의 cnt에서 토픽 축을 145개로 부분집합. wbar는 S5와 같이 전체 cnt 기준",
            nulls="N1(gen_N1), N2(trend_probs를 부분 cnt에서 재계산 후 gen_N2), B=500, p=(1+#{null_R>=obs_R})/(1+B), 통과 규칙=N1·N2 모두 p<0.05 (S5와 동일)",
            reading="표본별 (a) 통과 여부가 S5(전 표본 실패)와 같은가, (b) S5 관측 변화점(S5_meta.json obs_breaks) 각각이 새 관측 변화점 ±1년 안에 있는가를 따로 보고. 둘 다 같으면 '등급 선택에 둔감', 아니면 '민감'(표본별 표기, 하나로 합치지 않음)"),
    s6=dict(setting="spec['main']과 s6_lib.make_pair 그대로, R을 ti가 통과 토픽 인덱스인 행으로 제한(S6의 topic='A'와 같은 방식). 쌍은 pairs_of(spec) 전부",
            stats="entry_share, adapt_share, entry_minus_adapt (PA-A2c·A2a와 같은 4항 분모, 진입=신규+복귀)",
            boot="저자 가중 Exp(1)을 원본 저자 전체에서 뽑고 부분 자료의 같은 저자에게 같은 값 적용(대응 부트스트랩), B=spec['B_boot'], delta=sub-orig의 백분위·basic 구간",
            reading="쌍별로 entry_minus_adapt의 |delta_obs|<=0.03 이고 부호 유지면 '둔감', 아니면 '민감'. 쌍별 표기, 합치지 않음. 구간은 병기만"),
    reproduce_check="(a) 통과 토픽 145개, (b) 전체 토픽 마스크에서 S5 관측 R이 regime_nulls.csv obs_R과 1e-3 이내, (c) S6 orig total_half가 renewal_decomposition.csv와 1e-6 이내, (d) orig entry_share가 PA_A2c_results.csv(mode=author)와 1e-6 이내, (e) 부분 자료 저자 집합이 원본의 부분집합",
    caveat="제외 토픽이 4개뿐이라 판별력이 약함. phi를 K=149 기준 S5 값으로 고정해 K=145에서 벌점 비율이 미세하게 어긋날 수 있음. 등급 자체의 타당성(F1·F3가 실제로 '좋은 토픽'을 가리는지)은 검증하지 않음",
    forbidden="결과를 본 뒤 통과 정의·B·판독 기준 변경(변경 시 v2 계획으로 분리하고 사유 기록)")

def freeze():
    if not V2P.exists(): raise Halt("PA_0_PLAN_v2.json이 없습니다")
    h = spec_hash(PLAN); print("PA-B4 계획 해시(예정)", h[:12])
    if BP.exists(): print("이미 동결:", "동일" if json.loads(BP.read_text(encoding="utf-8"))["sha256"] == h else "⛔ 다름"); return
    refs = {f.name: sha_f(f) for f in [V2P, S3/"L7_topic_grade.csv", S5D/"S5_0_PREREG.json", S5D/"regime_nulls.csv", S5D/"S5_meta.json", P1/"s5_lib.py", P1/"s6_lib.py", S6D/"renewal_decomposition.csv", PA/"PA_A2c_results.csv"] if f.exists()}
    BP.write_text(json.dumps(dict(PLAN, created=now(), sha256=h, refs=refs), ensure_ascii=False, indent=1), encoding="utf-8")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as f:
        f.write(f"\n- {now()} | PA-B4 계획 동결(해시 {h[:12]}) | 사유: F1+F3 이분 등급(145개) 재추정, S5·S6만(S4·응집도는 별도). 제외 토픽이 4개뿐이라 약한 시험임을 명시. PA-B4 결과 미열람. QUICK은 수치 미출력 | 본 결과 변경 여부: 없음\n")
    print("저장: PA_B4_PLAN.json")

def tag():
    if not BP.exists(): raise Halt("먼저 freeze")
    t = f"PA-B4-plan-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    if git("tag", "-l", t).stdout.strip(): print("이미 있음:", t); return
    r = git("add", "--", "paper1/09_PA/PA_B4_PLAN.json", "paper1/09_PA/PA_CHANGELOG.md", "paper1/pa_b4.py"); print("add", r.returncode, r.stderr.strip())
    r = git("commit", "-m", "PA-B4 plan freeze (before execution)"); print("commit", r.returncode, (r.stdout + r.stderr)[:200])
    r = git("tag", "-a", t, "-m", "PA-B4 plan"); print("tag", r.returncode, r.stderr.strip()); print("※ 이어서 git push --follow-tags")

def run():
    if not BP.exists(): raise Halt("먼저 freeze")
    sp = json.loads(BP.read_text(encoding="utf-8"))
    if sp["sha256"] != spec_hash(sp) or sp["sha256"] != spec_hash(PLAN): raise Halt("동결 파일과 현재 계획이 다릅니다")
    if not git("tag", "-l", "PA-B4-plan-*").stdout.strip(): raise Halt("tag 단계를 먼저 실행하세요")
    sys.path.insert(0, str(P1)); import s5_lib as L5; import s6_lib as S
    sfx = "_QUICK" if QUICK else ""; rng = np.random.default_rng(int(PLAN["seed"]))
    # ---- 통과 토픽 ----
    G = pd.read_csv(S3/"L7_topic_grade.csv", encoding="utf-8-sig"); bl = lambda s: s.astype(str).str.strip().str.lower().isin(["true", "1", "1.0"])
    ptop = set(G[~bl(G.F1) & ~bl(G.F3)].topic.astype(int))
    if len(ptop) != 145: raise Halt(f"통과 토픽 수 재현 실패: {len(ptop)} (145여야 함)")
    # ================= S5 =================
    s5 = json.loads((S5D/"S5_0_PREREG.json").read_text(encoding="utf-8")); D = s5["detection"]; PHI = {k: v["phi"] for k, v in D["phi"].items()}
    C0, KMAX, MINLEN, ALPHA = D["c_primary"], D["k_max"], D["min_len"], s5["nulls"]["alpha"]; B = 20 if QUICK else 500
    cnt, venues, topics, fixed_v = L5.load_counts(); wbar = cnt.sum((0, 2))/cnt.sum(); T = len(L5.YEARS); YEARS = np.asarray(L5.YEARS); SAM = PLAN["s5"]["samples"]
    tmask = np.isin(topics, list(ptop))
    if int(tmask.sum()) != 145: raise Halt(f"topics_order와 통과 토픽 불일치: {int(tmask.sum())}")
    def det(c_arr, s, Kuse):
        P, n = L5.sample_P(c_arr, fixed_v, wbar, s); return L5.detect(P, n, C0*PHI[s]*(Kuse-1)*np.log(T), KMAX, MINLEN)
    ref = pd.read_csv(S5D/"regime_nulls.csv"); ref = ref[ref["null"] == "N2"].set_index("sample")
    for s in SAM:
        if abs(det(cnt, s, len(topics))["R"] - float(ref.loc[s, "obs_R"])) > 1e-3: raise Halt(f"S5 관측 R 재현 실패({s})")
    print("[재현 OK] S5 관측 R(전체 토픽), 통과 토픽 145개")
    cs = cnt[:, :, tmask]; obs = {s: det(cs, s, 145) for s in SAM}
    P2 = L5.trend_probs(cs); NR = {"N1": {s: [] for s in SAM}, "N2": {s: [] for s in SAM}}
    for b in range(B):
        for nm, gen in (("N1", lambda: L5.gen_N1(cs, rng)), ("N2", lambda: L5.gen_N2(cs, P2, rng))):
            cc = gen()
            for s in SAM: NR[nm][s].append(det(cc, s, 145)["R"])
        if (b+1) % 100 == 0: print(f"  S5 귀무 {b+1}/{B}")
    meta = json.loads((S5D/"S5_meta.json").read_text(encoding="utf-8")); ob0 = meta["obs_breaks"]; rows5 = []
    for s in SAM:
        yrs = [int(YEARS[x]) for x in obs[s]["br"]]; pv = {nm: (1 + float((np.array(NR[nm][s]) >= obs[s]["R"]).sum()))/(1 + B) for nm in NR}
        passed = max(pv.values()) < ALPHA; kept = [L5.near(y, yrs, 1) for y in ob0[s]]
        rows5.append(dict(sample=s, K=145, obs_R=obs[s]["R"], obs_k=obs[s]["k"], breaks=str(yrs), s5_breaks=str(ob0[s]), s5_breaks_kept_pm1=str(kept), p_N1=pv["N1"], p_N2=pv["N2"], passed_new=passed, passed_s5=bool(meta["null_pass"][s]),
                          same_verdict=(passed == bool(meta["null_pass"][s])), all_breaks_kept=all(kept), B=B))
    R5 = pd.DataFrame(rows5); R5.to_csv(PA/f"PA_B4_s5_results{sfx}.csv", index=False, encoding="utf-8-sig"); print("  S5 완료")
    # ================= S6 =================
    spec = S.load_spec(); L = S.load_all(spec); M = spec["main"]; PAIRS = S.pairs_of(spec); half = S.half; R = L["R"]
    ok_ti = np.where(np.isin(L["topics"], list(ptop)))[0]
    if len(ok_ti) != 145: raise Halt(f"S6 토픽 인덱스 수 불일치: {len(ok_ti)}")
    L2 = dict(L); L2["R"] = R[R.ti.isin(ok_ti)]
    ref6 = pd.read_csv(S6D/"renewal_decomposition.csv"); ref6 = ref6[(ref6.scheme == M["scheme"]) & (ref6.variant == "all_venues")].set_index("pair")
    a2c = pd.read_csv(PA/"PA_A2c_results.csv"); a2c = a2c[(a2c["mode"] == "author") & (a2c.stat == "entry_share")].set_index("pair")
    B6 = 20 if QUICK else int(spec["B_boot"]); lo_q, hi_q = spec["ci"]; STATS = ["entry_share", "adapt_share", "entry_minus_adapt"]
    def stats(d):
        h = {t: half(d[t]) for t in ["adapt", "realloc", "entry", "exit"]}; tot = sum(h.values())
        return dict(entry_share=h["entry"]/tot, adapt_share=h["adapt"]/tot, entry_minus_adapt=(h["entry"] - h["adapt"])/tot)
    rows6 = []
    for p0, p1 in PAIRS:
        name = f"{p0}->{p1}"; Pa = S.make_pair(L, p0, p1, M["scheme"], M["venue"], M["topic"], M["hom"]); Pb = S.make_pair(L2, p0, p1, M["scheme"], M["venue"], M["topic"], M["hom"])
        da, db = Pa.decompose(), Pb.decompose(); oa, ob = stats(da), stats(db)
        if abs(half(da["total"]) - float(ref6.loc[name, "total_half"])) > 1e-6: raise Halt(f"S6 관측 재현 실패({name})")
        if abs(oa["entry_share"] - float(a2c.loc[name, "obs"])) > 1e-6: raise Halt(f"PA-A2c entry_share 재현 실패({name})")
        idx = np.searchsorted(Pa.aids, Pb.aids)
        if not (idx < len(Pa.aids)).all() or not (Pa.aids[idx] == Pb.aids).all(): raise Halt(f"부분 자료 저자 집합이 원본의 부분집합이 아님({name})")
        bs = []
        for _ in range(B6):
            wa = rng.exponential(size=Pa.nA); sa = stats(Pa.decompose(Pa.m0*wa[Pa.a0], Pa.m1*wa[Pa.a1])); wb = wa[idx]; sb = stats(Pb.decompose(Pb.m0*wb[Pb.a0], Pb.m1*wb[Pb.a1]))
            bs.append({s: sb[s] - sa[s] for s in STATS})
        bs = pd.DataFrame(bs)
        for s in STATS:
            dl = ob[s] - oa[s]; ql, qh = np.percentile(bs[s], [lo_q, hi_q])
            rows6.append(dict(pair=name, stat=s, obs_orig=oa[s], obs_sub=ob[s], delta=dl, boot_median=float(bs[s].median()), pct_lo=ql, pct_hi=qh, basic_lo=2*dl - qh, basic_hi=2*dl - ql,
                              n_rows_orig=int(len(R[R.period.isin([p0, p1])])), n_rows_sub=int(len(L2["R"][L2["R"].period.isin([p0, p1])])), n_authors_orig=int(Pa.nA), n_authors_sub=int(Pb.nA), B=B6))
        print(f"  S6 {name} 완료")
    R6 = pd.DataFrame(rows6); R6.to_csv(PA/f"PA_B4_s6_results{sfx}.csv", index=False, encoding="utf-8-sig")
    if QUICK: print("\n[QUICK] 오류 없이 완료. 수치는 출력하지 않음(_QUICK 파일을 열어 해석하지 마세요)."); return
    print("\n[Post-hoc] PA-B4 S5 재추정(145개 토픽)\n", R5.round(4).to_string(index=False))
    print("\n[Post-hoc] PA-B4 S6 재추정(145개 토픽 대 전체)\n", R6.round(4).to_string(index=False))
    k = R6[R6.stat == "entry_minus_adapt"].copy(); k["insensitive"] = (np.sign(k.obs_sub) == np.sign(k.obs_orig)) & (k.delta.abs() <= 0.03)
    print("\n[동결 판독] S5 표본별 (통과 여부 동일, 변화점 유지):\n", R5[["sample", "same_verdict", "all_breaks_kept"]].to_string(index=False))
    print("[동결 판독] S6 entry_minus_adapt\n", k[["pair", "obs_orig", "obs_sub", "delta", "pct_lo", "pct_hi", "insensitive"]].round(4).to_string(index=False))
    print("※ 제외 토픽 4개뿐인 약한 시험. 쌍·표본별로 따로 읽고 합치지 않음. S0~S8 판정 불변.")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as fh:
        fh.write(f"- {now()} | PA-B4 실행 | 정의: PA_B4_PLAN {sp['sha256'][:12]} | 결과: PA_B4_s5_results.csv, PA_B4_s6_results.csv | 본 결과 변경 여부: 없음\n")

try: {"freeze": freeze, "tag": tag, "run": run}[MODE]()
except Halt as e: print(f"⛔ 중단: {e}")