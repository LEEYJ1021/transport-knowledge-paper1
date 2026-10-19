# -*- coding: utf-8 -*-
# PA-B2: 2020 변화의 표본 크기·저널 구성 아티팩트 분리. 미실행 코드.
# MODE: "freeze" -> "tag" -> (git push --follow-tags) -> "run"(QUICK=True: 오류 점검 전용) -> "run"(QUICK=False)
# S0~S8 판정 불변. 모든 산출물 [Post-hoc]. 판독 규칙은 PLAN_B2에 동결.
import sys, json, hashlib, subprocess, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore"); pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
MODE = "run"
QUICK = False

ROOT = Path.home() / "Research/Minnesota_Transport"; P1 = ROOT/"paper1"; PA = P1/"09_PA"; S5 = P1/"05_S5"; S3 = P1/"03_S3"
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds")
sha_b = lambda b: hashlib.sha256(b).hexdigest(); sha_f = lambda p: sha_b(Path(p).read_bytes())
git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
class Halt(Exception): pass
spec_hash = lambda s: sha_b(json.dumps({k: v for k, v in s.items() if k not in ("sha256", "created", "refs")}, sort_keys=True, ensure_ascii=False).encode())
V2P, BP = PA/"PA_0_PLAN_v2.json", PA/"PA_B2_PLAN.json"

PLAN_B2 = dict(
    version=1, seed=2026, parent="PA_0_PLAN_v2.json",
    status="사후 명세. PA-A1 run 1·2·탐색 결과를 본 뒤 작성. PA-B2 결과는 미열람. S0~S8 판정 불변.",
    caps=[3800, 3000], primary_cap=3800, B=200, focus_year=2020, window_pre=[2017, 2019], window_post=[2020, 2022], samples=["all", "fixed14", "within"],
    downsample="연도별 (저널x토픽) 셀 카운트에서 총 cap편을 비복원 추출(다변량 초기하). 연도 논문 수가 cap 이하이면 그대로. 저널 구성은 기대값상 유지",
    detector="s5_lib.detect(P, n, pen, kmax, minlen) 그대로. pen = c_primary*phi_s*(K-1)*log(T), S5_0_PREREG.json 값. 추출된 카운트로 s5_lib.sample_P 재계산",
    stats="(a) 2020 점프 J = ||가중평균(sqrt P)[2020,2023) - 가중평균(sqrt P)[2017,2020)||/sqrt(2), 가중치 4n (PA-A1과 동일), (b) 2020±1년 변화점 회수율, (c) R, (d) 변화점 연도 분포",
    reading="primary_cap에서 표본별 '유지' = (회수율>=0.80) AND (J 중앙값 >= 0.80*J_obs). 세 표본 모두 유지: '표본 크기 아티팩트 아님' / 일부: '혼재(표본 의존)' / 없음: '아티팩트 후보 확정'. cap=3000은 민감도로만 보고",
    descriptive="관측 자료 기술 1회: decomp_break(2017-19 대 2020-22)의 토픽 상위 10(저널 내/간), 2019->2020 저널별 논문 수 증가 상위 10",
    caveat="하향 추출은 표집 잡음을 늘려 J를 위로 편향시킬 수 있어 J만으로 판정하지 않음. 벌점은 S5 값 고정이라 추출 후 비용/벌점 비율이 달라짐. 검정은 논문 독립 가정",
    forbidden="결과를 본 뒤 cap·임계값·창 변경(변경 시 v2 계획으로 분리하고 사유 기록)")

def freeze():
    if not V2P.exists(): raise Halt("PA_0_PLAN_v2.json이 없습니다")
    h = spec_hash(PLAN_B2); print("PA-B2 계획 해시(예정)", h[:12])
    if BP.exists(): print("이미 동결:", "동일" if json.loads(BP.read_text(encoding="utf-8"))["sha256"] == h else "⛔ 다름"); return
    refs = {f.name: sha_f(f) for f in [V2P, S5/"S5_0_PREREG.json", P1/"s5_lib.py", PA/"PA_A1_v2_run2_power_curve.csv"] if f.exists()}
    BP.write_text(json.dumps(dict(PLAN_B2, created=now(), sha256=h, refs=refs), ensure_ascii=False, indent=1), encoding="utf-8")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as f:
        f.write(f"\n- {now()} | PA-B2 계획 동결(해시 {h[:12]}) | 사유: PA-A1 결과 열람 뒤의 사후 명세, B2 결과 미열람. QUICK 실행은 오류 점검 전용 | 본 결과 변경 여부: 없음\n")
    print("저장: PA_B2_PLAN.json")

def tag():
    if not BP.exists(): raise Halt("먼저 freeze")
    t = f"PA-B2-plan-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    if git("tag", "-l", t).stdout.strip(): print("이미 있음:", t); return
    r = git("add", "--", "paper1/09_PA/PA_B2_PLAN.json", "paper1/09_PA/PA_CHANGELOG.md"); print("add", r.returncode, r.stderr.strip())
    r = git("commit", "-m", "PA-B2 plan freeze (before execution)"); print("commit", r.returncode, (r.stdout + r.stderr)[:200])
    r = git("tag", "-a", t, "-m", "PA-B2 plan"); print("tag", r.returncode, r.stderr.strip()); print("※ 이어서 git push --follow-tags (실행 전 외부 타임스탬프)")

def run():
    if not BP.exists(): raise Halt("먼저 freeze")
    sp = json.loads(BP.read_text(encoding="utf-8"))
    if sp["sha256"] != spec_hash(sp) or sp["sha256"] != spec_hash(PLAN_B2): raise Halt("동결 파일과 현재 계획이 다릅니다(사후 변경 금지)")
    if not git("tag", "-l", "PA-B2-plan-*").stdout.strip(): raise Halt("tag 단계를 먼저 실행하세요")
    sys.path.insert(0, str(P1)); import s5_lib as L
    sfx = "_QUICK" if QUICK else ""; B = 20 if QUICK else PLAN_B2["B"]; rng = np.random.default_rng(int(PLAN_B2["seed"]))
    s5 = json.loads((S5/"S5_0_PREREG.json").read_text(encoding="utf-8")); D = s5["detection"]; PHI = {k: v["phi"] for k, v in D["phi"].items()}
    C0, KMAX, MINLEN = D["c_primary"], D["k_max"], D["min_len"]
    cnt, venues, topics, fixed_v = L.load_counts(); wbar = cnt.sum((0, 2))/cnt.sum(); T, V, K = cnt.shape; YEARS = np.asarray(L.YEARS); SAM = PLAN_B2["samples"]; f = PLAN_B2["focus_year"]
    pen = lambda s: C0*PHI[s]*(K-1)*np.log(T); i20 = int(np.where(YEARS == f)[0][0]); pre, post = PLAN_B2["window_pre"], PLAN_B2["window_post"]
    def J(P, n, it, ):   # PA-A1과 동일 정의(3년 창)
        X, w = np.sqrt(P), 4.0*n; a, b = slice(max(0, it-3), it), slice(it, it+3)
        m = lambda sl: np.average(X[sl], axis=0, weights=w[sl]) if w[sl].sum() > 0 else X[sl].mean(0)
        return float(np.linalg.norm(m(b) - m(a))/np.sqrt(2))
    def detect_s(c_arr, s):
        P, n = L.sample_P(c_arr, fixed_v, wbar, s); return L.detect(P, n, pen(s), KMAX, MINLEN), P, n
    # 관측 재현 점검(S5와 R 일치)
    OBS = {}; ref = pd.read_csv(S5/"regime_nulls.csv")
    for s in SAM:
        d, P, n = detect_s(cnt, s); r0 = float(ref[(ref["null"] == "N2") & (ref["sample"] == s)].obs_R.iloc[0])
        if abs(d["R"] - r0) > 1e-3: raise Halt(f"S5 관측 R 재현 실패({s}): {d['R']:.4f} vs {r0:.4f}")
        OBS[s] = dict(J=J(P, n, i20), R=d["R"], breaks=[int(YEARS[b]) for b in d["br"]])
    print("[관측 재현 OK]", {s: (round(v["J"], 4), v["breaks"]) for s, v in OBS.items()})
    # ---- 관측 기술 통계 1회 ----
    a0, a1, b1 = pre[0]-int(YEARS[0]), post[0]-int(YEARS[0]), post[1]+1-int(YEARS[0])
    wi, bt, tot = L.decomp_break(cnt, a0, a1, b1)
    names = {}
    try:
        Cd = pd.read_csv(S3/"topic_evidence_cards.csv"); col = [c for c in Cd.columns if c.lower() in ("name", "label", "topic_name", "top_terms", "top10", "keywords")]
        if col: names = dict(zip(Cd.topic.astype(int), Cd[col[0]].astype(str).str.slice(0, 60)))
    except Exception as e: print("※ 카드 이름 생략:", str(e)[:80])
    gA = set(pd.read_csv(S3/"L7_topic_grade.csv").pipe(lambda g: g[g[[c for c in g.columns if "grade" in c.lower()][0]].astype(str).str.upper().str.strip() == "A"]).topic.astype(int))
    top = np.argsort(-np.abs(tot))[:10]
    TP = pd.DataFrame([dict(rank=r+1, topic=int(topics[i]), name=names.get(int(topics[i]), ""), delta=tot[i], within_journal=wi[i], between_journal=bt[i], grade_A=int(topics[i]) in gA) for r, i in enumerate(top)])
    print(f"\n[Post-hoc] {pre[0]}-{pre[1]} 대 {post[0]}-{post[1]} 토픽 변화 상위 10\n", TP.round(4).to_string(index=False))
    print(f"저널 간 성분 비중(전 토픽 절대합): {np.abs(bt).sum()/(np.abs(wi).sum()+np.abs(bt).sum()):.3f}")
    nv = cnt.sum(2); ip = int(np.where(YEARS == f-1)[0][0]); dv = nv[i20] - nv[ip]
    VG = pd.DataFrame(dict(venue=venues, fixed14=fixed_v, n_prev=nv[ip], n_focus=nv[i20], delta=dv, share_of_total_delta=dv/dv.sum())).sort_values("delta", ascending=False)
    print(f"\n[Post-hoc] {f-1}->{f} 저널별 논문 수 증가 상위 10 (전체 증가 {int(dv.sum())})\n", VG.head(10).round(3).to_string(index=False))
    TP.to_csv(PA/f"PA_B2_observed_topics{sfx}.csv", index=False, encoding="utf-8-sig"); VG.to_csv(PA/f"PA_B2_venue_growth{sfx}.csv", index=False, encoding="utf-8-sig")
    # ---- 하향 추출 복제 ----
    def cap_counts(c, cap):
        out = c.copy()
        for y in range(T):
            flat = c[y].ravel().astype(np.int64)
            if flat.sum() > cap: out[y] = rng.multivariate_hypergeometric(flat, cap, method="marginals").reshape(V, K)
        return out
    R_ = []
    for cap in PLAN_B2["caps"]:
        for b in range(B):
            cc = cap_counts(cnt, cap)
            for s in SAM:
                d, P, n = detect_s(cc, s); yrs = [int(YEARS[x]) for x in d["br"]]
                R_.append(dict(cap=cap, rep=b, sample=s, J=J(P, n, i20), R=d["R"], k=d["k"], hit=any(abs(y-f) <= 1 for y in yrs), breaks=str(yrs)))
        print(f"  cap={cap} 완료")
    RP = pd.DataFrame(R_); RP.to_csv(PA/f"PA_B2_cap_replicates{sfx}.csv", index=False, encoding="utf-8-sig")
    SM = RP.groupby(["cap", "sample"]).agg(J_med=("J", "median"), J_q05=("J", lambda x: x.quantile(.05)), J_q95=("J", lambda x: x.quantile(.95)), R_med=("R", "median"), hit_rate=("hit", "mean"), k_mode=("k", lambda x: x.mode().iloc[0])).reset_index()
    SM["J_obs"] = SM["sample"].map(lambda s: OBS[s]["J"]); SM["J_ratio"] = SM.J_med/SM.J_obs; SM.to_csv(PA/f"PA_B2_summary{sfx}.csv", index=False, encoding="utf-8-sig")
    print("\n[Post-hoc] PA-B2 하향 추출 요약\n", SM.round(3).to_string(index=False))
    if QUICK:
        print("\n[QUICK] 오류 점검 전용: 위 수치를 해석하거나 판독 규칙을 적용하지 마세요(B=20, v2 계획 사유 방지)."); return
    pr = SM[SM.cap == PLAN_B2["primary_cap"]].set_index("sample"); keep = {s: bool(pr.loc[s, "hit_rate"] >= 0.80 and pr.loc[s, "J_ratio"] >= 0.80) for s in SAM}
    print("\n[동결 판독, cap=%d]" % PLAN_B2["primary_cap"], {s: ("유지" if v else "실패") for s, v in keep.items()})
    print("→", "표본 크기 아티팩트 아님" if all(keep.values()) else ("혼재(표본 의존)" if any(keep.values()) else "아티팩트 후보 확정"))
    print("※ J는 표집 잡음으로 위로 편향될 수 있고, 판독은 PLAN_B2의 규칙을 코드로 옮긴 것입니다. S5 판정(체제 서사 철회)은 바꾸지 않습니다.")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as fh:
        fh.write(f"- {now()} | PA-B2 실행 | 정의: PA_B2_PLAN {sp['sha256'][:12]} | 결과: PA_B2_*.csv | 본 결과 변경 여부: 없음\n")

try: {"freeze": freeze, "tag": tag, "run": run}[MODE]()
except Halt as e: print(f"⛔ 중단: {e}")
