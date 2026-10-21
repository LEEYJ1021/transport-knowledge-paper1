# -*- coding: utf-8 -*-
# PA-B7a: 임베딩 결측(has_topic 거짓) 논문에 대한 뒤집힘 배수 분석(S4 big 토픽 부호). 결정적 계산. 미실행 코드.
# MODE: "freeze" -> "tag" -> (git push --follow-tags) -> "run"(QUICK=True: 재현 점검과 기간별 결측률만) -> "run"(QUICK=False)
# S0~S8 판정 불변. 모든 산출물 [Post-hoc].
import json, hashlib, subprocess, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore"); pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
MODE = "run"
QUICK = False

ROOT = Path.home() / "Research/Minnesota_Transport"; P1 = ROOT/"paper1"; PA = P1/"09_PA"; S0, S3, S4 = P1/"00_S0", P1/"03_S3", P1/"04_S4"; DATA = ROOT/"analysis_data/final"
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds")
sha_b = lambda b: hashlib.sha256(b).hexdigest(); sha_f = lambda p: sha_b(Path(p).read_bytes())
tf = lambda s: s.astype(str).str.strip().str.lower().isin(["1", "1.0", "true", "t", "yes"])
git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
class Halt(Exception): pass
spec_hash = lambda s: sha_b(json.dumps({k: v for k, v in s.items() if k not in ("sha256", "created", "refs")}, sort_keys=True, ensure_ascii=False).encode())
V2P, BP = PA/"PA_0_PLAN_v2.json", PA/"PA_B7a_PLAN.json"

PLAN = dict(
    version=1, parent="PA_0_PLAN_v2.json",
    status="사후 명세(PA-B7 중 결측 경계 (1)만). S4 결과, s4_main.py 38~80행, 연도별 결측률(제외 목록 미적용 근사치 0.12~0.30)은 열람한 상태. PA-B7a 결과 미열람. 분류기 대입(B7b)과 저널x연도 IPW(B7c)는 별도 계획으로 분리(S4 missingness_sensitivity.csv와 중복 가능). S0~S8 판정 불변.",
    why_not_manski="순수 최악·최선(Manski) 경계는 결측 약 16%라 토픽 몫 경계 폭이 big 토픽 delta(0.01 안팎)보다 훨씬 커서 항상 0을 포함함. 정보가 없으므로 계산하지 않음",
    data="F1_papers.csv에서 EXCLUDE_PIDS_FROZEN 제외(FREEZE_LOG 해시 검증 없이 S4와 같은 파일 사용), in_sample 참, 연도 2000~2025. 분석 집합 F = has_topic 참 and topic150 있음(76,984편). 결측 집합 = 나머지. 기간·대비는 S4 동결 규칙의 periods, main_contrast",
    assumption="결측 논문의 같은 저널·같은 기간 안 토픽 비중 r_jt = k * s_jt (해당 토픽만, 나머지 토픽은 합이 1이 되도록 조정되나 집계에는 불필요). 결측 논문의 저널 분포는 관측 그대로. 전체 몫 = sum_j (n_j + k*m_j) s_jt / sum_j (n_j + m_j)",
    scenarios={"both": "두 기간 모두 배수 k", "only0": "앞 기간만 k, 뒤 기간 1", "only1": "앞 기간 1, 뒤 기간만 k"},
    grid_k=[0.5, 0.75, 1, 1.5, 2], plausible_range=[0.5, 2],
    scope="S4 big 토픽(topic_quadrants.csv의 big 참, 50개). 각 토픽의 delta_full(k) 부호가 관측 delta 부호와 같은지, 부호가 바뀌는 k*. big이 아닌 토픽의 big 전환과 4분면 라벨 변화는 토픽 간 결합 시나리오가 필요해 이번 범위에서 제외",
    stats="delta_full_base(k=1, 시나리오 공통, 저널 구성 보정만), 격자별 부호 유지 여부, 시나리오별 k*(선형 해, k<0이면 '없음')",
    reading="시나리오별로 격자 전체에서 부호가 유지되는 big 토픽 비율 >=0.90 '유지', 0.70~0.90 '부분', <0.70 '민감'. 시나리오를 합치지 않음. 임계값은 임의의 동결 사양",
    reproduce_check="(a) 분석 집합 76,984편, (b) 관측 delta가 topic_quadrants.csv와 1e-9 이내, (c) 동결 규칙 파일에서 main_contrast·periods를 읽을 수 있음. 하나라도 어긋나면 중단",
    caveat="k의 현실성 범위는 연구자 가정. 결측 논문이 저널 안에서도 무작위라는 k=1 기준과 저널 분포 고정 가정이 핵심. 결측 사유(임베딩 미보유)가 토픽과 무관하다는 보장 없음. 인과 해석 아님",
    forbidden="결과를 본 뒤 격자·범위·판독 임계값 변경(변경 시 v2 계획으로 분리하고 사유 기록)")

def freeze():
    if not V2P.exists(): raise Halt("PA_0_PLAN_v2.json이 없습니다")
    h = spec_hash(PLAN); print("PA-B7a 계획 해시(예정)", h[:12])
    if BP.exists(): print("이미 동결:", "동일" if json.loads(BP.read_text(encoding="utf-8"))["sha256"] == h else "⛔ 다름"); return
    refs = {f.name: sha_f(f) for f in [V2P, S4/"topic_quadrants.csv", P1/"s4_main.py", DATA/"F1_papers.csv"] if f.exists()}
    BP.write_text(json.dumps(dict(PLAN, created=now(), sha256=h, refs=refs), ensure_ascii=False, indent=1), encoding="utf-8")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as f:
        f.write(f"\n- {now()} | PA-B7a 계획 동결(해시 {h[:12]}) | 사유: 결측 경계를 Manski 대신 뒤집힘 배수로 설계. 연도별 결측률(제외 미적용 근사)과 S4 코드 일부 열람 상태, PA-B7a 결과 미열람. QUICK은 재현 점검과 기간별 결측률만 | 본 결과 변경 여부: 없음\n")
    print("저장: PA_B7a_PLAN.json")

def tag():
    if not BP.exists(): raise Halt("먼저 freeze")
    t = f"PA-B7a-plan-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    if git("tag", "-l", t).stdout.strip(): print("이미 있음:", t); return
    r = git("add", "--", "paper1/09_PA/PA_B7a_PLAN.json", "paper1/09_PA/PA_CHANGELOG.md", "paper1/pa_b7a.py"); print("add", r.returncode, r.stderr.strip())
    r = git("commit", "-m", "PA-B7a plan freeze (before execution)"); print("commit", r.returncode, (r.stdout + r.stderr)[:200])
    r = git("tag", "-a", t, "-m", "PA-B7a plan"); print("tag", r.returncode, r.stderr.strip()); print("※ 이어서 git push --follow-tags")

def find_key(o, key):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key: return v
            r = find_key(v, key)
            if r is not None: return r

def run():
    if not BP.exists(): raise Halt("먼저 freeze")
    sp = json.loads(BP.read_text(encoding="utf-8"))
    if sp["sha256"] != spec_hash(sp) or sp["sha256"] != spec_hash(PLAN): raise Halt("동결 파일과 현재 계획이 다릅니다")
    if not git("tag", "-l", "PA-B7a-plan-*").stdout.strip(): raise Halt("tag 단계를 먼저 실행하세요")
    sfx = "_QUICK" if QUICK else ""
    spec = None
    for f in sorted(P1.glob("0[0-4]_*/*PREREG*.json")):
        j = json.loads(f.read_text(encoding="utf-8")); mc, pr = find_key(j, "main_contrast"), find_key(j, "periods")
        if mc and pr and all(k in pr for k in mc): spec = (f.name, mc, pr); break
    if spec is None: raise Halt("main_contrast와 periods를 가진 S4 동결 규칙 파일을 찾지 못함")
    fname, (c0, c1), PR = spec; P = {k: tuple(v) for k, v in PR.items()}; print(f"[규칙 파일] {fname} | main_contrast {c0}->{c1} | {P[c0]}, {P[c1]}")
    W = pd.read_csv(DATA/"F1_papers.csv", low_memory=False); W["pid"] = W.pid.astype(str)
    EXC = set(pd.read_csv(S0/"EXCLUDE_PIDS_FROZEN.csv", dtype=str, encoding="utf-8-sig").pid)
    W = W[~W.pid.isin(EXC) & tf(W.in_sample) & W.year.between(2000, 2025)].copy(); W["ht"] = tf(W.has_topic) & W.topic150.notna()
    F, Mi = W[W.ht].copy(), W[~W.ht].copy()
    if len(F) != 76984: raise Halt(f"분석 집합 재현 실패: {len(F)} (76984여야 함)")
    F["topic"] = F.topic150.astype(int)
    topics = np.array(sorted(pd.read_csv(S3/"L7_topic_grade.csv").topic.astype(int))); venues = np.array(sorted(F.venue_short.unique()))
    dropped = int((~Mi.venue_short.isin(venues)).sum()); Mi = Mi[Mi.venue_short.isin(venues)]
    def pm(lo, hi):
        d, m = F[F.year.between(lo, hi)], Mi[Mi.year.between(lo, hi)]
        C = pd.crosstab(d.venue_short, d.topic).reindex(index=venues, columns=topics, fill_value=0).values.astype(float)
        n = C.sum(1); s = np.divide(C, n[:, None], out=np.zeros_like(C), where=n[:, None] > 0)
        mm = m.groupby("venue_short").size().reindex(venues, fill_value=0).values.astype(float)
        a = C.sum(0); b = (mm[:, None]*s).sum(0); return dict(a=a, b=b, n=n.sum(), m=mm.sum(), Nf=n.sum() + mm.sum())
    A0, A1 = pm(*P[c0]), pm(*P[c1])
    Q = pd.read_csv(S4/"topic_quadrants.csv").set_index("topic"); delta_obs = A1["a"]/A1["n"] - A0["a"]/A0["n"]
    if np.abs(delta_obs - Q.loc[topics, "delta"].values).max() > 1e-9: raise Halt("관측 delta가 topic_quadrants.csv와 다름")
    miss = pd.DataFrame([dict(period=c, n_obs=int(x["n"]), n_missing=int(x["m"]), miss_rate=x["m"]/x["Nf"]) for c, x in ((c0, A0), (c1, A1))])
    print("[재현 OK] 분석 집합 76,984, 관측 delta | 결측 중 분석 저널 밖으로 제외된 논문", dropped); print("[기간별 결측률(설계 정보)]\n", miss.round(4).to_string(index=False))
    if QUICK: print("\n[QUICK] 재현 점검과 기간별 결측률만 출력. 결과 통계는 계산·출력하지 않음."); return
    f0, f1 = (lambda k0, k1: (A1["a"] + k1*A1["b"])/A1["Nf"] - (A0["a"] + k0*A0["b"])/A0["Nf"])
    ff = lambda k0, k1: (A1["a"] + k1*A1["b"])/A1["Nf"] - (A0["a"] + k0*A0["b"])/A0["Nf"]
    base = ff(1, 1); big = Q.loc[topics, "big"].values.astype(bool); sgn = np.sign(delta_obs); K = PLAN["grid_k"]
    scen = {"both": lambda k: ff(k, k), "only0": lambda k: ff(k, 1), "only1": lambda k: ff(1, k)}
    kstar = {"both": -(A1["a"]/A1["Nf"] - A0["a"]/A0["Nf"])/(A1["b"]/A1["Nf"] - A0["b"]/A0["Nf"]),
             "only0": ((A1["a"] + A1["b"])/A1["Nf"] - A0["a"]/A0["Nf"])/(A0["b"]/A0["Nf"]), "only1": ((A0["a"] + A0["b"])/A0["Nf"] - A1["a"]/A1["Nf"])/(A1["b"]/A1["Nf"])}
    R = pd.DataFrame(dict(topic=topics, grade=Q.loc[topics, "grade"].values, quadrant=Q.loc[topics, "quadrant"].values, big=big, delta=delta_obs, delta_full_base=base, sign_base_kept=np.sign(base) == sgn))
    for nm, fn in scen.items():
        keep = np.column_stack([np.sign(fn(k)) == sgn for k in K]); R[f"kept_all_{nm}"] = keep.all(1)
        with np.errstate(all="ignore"): ks = kstar[nm]
        R[f"kstar_{nm}"] = np.where(np.isfinite(ks) & (ks >= 0), ks, np.nan)
    R.to_csv(PA/"PA_B7a_results.csv", index=False, encoding="utf-8-sig"); miss.to_csv(PA/"PA_B7a_missing_by_period.csv", index=False, encoding="utf-8-sig")
    B = R[R.big]; print(f"\n[Post-hoc] PA-B7a big 토픽 {len(B)}개 | k=1(저널 구성 보정만) 부호 유지 {int(B.sign_base_kept.sum())}개")
    out = []
    for nm in scen:
        share = float(B[f"kept_all_{nm}"].mean()); v = "유지" if share >= 0.90 else ("부분" if share >= 0.70 else "민감")
        ks = B[f"kstar_{nm}"]; out.append(dict(scenario=nm, kept_share=share, n_not_kept=int((~B[f"kept_all_{nm}"]).sum()), kstar_min=ks.min(), kstar_median=ks.median(), n_kstar_in_range=int(((ks >= 0.5) & (ks <= 2)).sum()), 판독=v))
    O = pd.DataFrame(out); print("\n[동결 판독]\n", O.round(3).to_string(index=False)); O.to_csv(PA/"PA_B7a_summary.csv", index=False, encoding="utf-8-sig")
    print("\n[부호 유지 실패 big 토픽]\n", B[~B[[f"kept_all_{n}" for n in scen]].all(1)][["topic", "grade", "quadrant", "delta", "delta_full_base", "kstar_both", "kstar_only0", "kstar_only1"]].round(4).to_string(index=False))
    print("※ 결측 분포에 대한 가정(k)에 의존하는 민감도이며 경계가 아님. 시나리오를 합치지 않음. S0~S8 판정 불변.")
    with (PA/"PA_CHANGELOG.md").open("a", encoding="utf-8") as fh:
        fh.write(f"- {now()} | PA-B7a 실행 | 정의: PA_B7a_PLAN {sp['sha256'][:12]} | 결과: PA_B7a_*.csv | 본 결과 변경 여부: 없음\n")

try: {"freeze": freeze, "tag": tag, "run": run}[MODE]()
except Halt as e: print(f"⛔ 중단: {e}")