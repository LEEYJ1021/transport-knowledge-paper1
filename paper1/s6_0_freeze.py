# -*- coding: utf-8 -*-
# s6_0_freeze.py (v2): S6-0 동결. FREEZE=False로 점검 → True로 동결.
import json, subprocess, hashlib
from pathlib import Path
ROOT = Path.home() / "Research/Minnesota_Transport"
DATA, S2, S4, S5, S6 = ROOT/"analysis_data/final", ROOT/"paper1/02_S2", ROOT/"paper1/04_S4", ROOT/"paper1/05_S5", ROOT/"paper1/06_S6"; S6.mkdir(parents=True, exist_ok=True)
FREEZE = True
# ---- 실제 파일 구성에 맞춘 설정 ----
FILES = dict(papers="F1_papers.csv", author_paper="F2_author_paper.csv", authors="F4_authors.csv",   # analysis_data/final
             ipw="paper_ipw.csv.gz", alpha="alpha_flags.csv")                                         # paper1/02_S2
COLS = dict(pid=["pid"], aid=["name_norm"], n_authors=["n_authors"], position=["author_pos"])
IPW_MODEL = "A"          # paper_ipw.csv.gz의 model 값. S4 결측 보정(AUC 0.733)과 같은 모델인지 확인 후 동결
SCHEMES = ["equal", "inv_n_authors", "first_last", "full_count"]   # equal = F2.w(위험군 제외 후 1/남은 저자 수)
PERIODS = {"P0004": [2000, 2004], "P0509": [2005, 2009], "P1014": [2010, 2014], "P1519": [2015, 2019], "P2025": [2020, 2025]}  # S4 동결 기간
MAIN = dict(scheme="equal", venue="all", topic="all", hom="baseline", defn="D4")                # 제안: multiverse 기준 설정
CIRCULAR = {"D1": ["P0509", "P2025"], "D2": ["P0509", "P2025"], "D3": ["P0509", "P2025"], "D4": ["P1519", "P2025"]}
N_ANALYSIS = 76984

spec = dict(
    stage="S6-0", note="S5 산출물(변화점, 귀무 결과) 열람 후 동결. 결과를 보고 설정을 바꾸지 않는다. 구간은 S4 동결 기간(체제 아님).",
    seed=2026, data_end=2025, n_analysis=N_ANALYSIS, periods=PERIODS, files=FILES, cols=COLS, ipw_model=IPW_MODEL, schemes=SCHEMES,
    venue_sets=["all", "fixed14"], topic_sets=["all", "A"], defs=["D1", "D2", "D3", "D4"], main=MAIN, circular=CIRCULAR,
    B_boot=2000, B_perm=1000, ci=[2.5, 97.5], follow_min_papers=3, follow_splits=20,
    homonym="F2는 위험군(ambiguous/heavy) 이름을 이미 제외한 자료라 위험군 변형은 baseline뿐. 변형 7종 범위는 제외 전 자료가 없어 이 코드로는 산출 불가",
    key_vars={"K1": "초과 진입분(정의 D 토픽 합)의 부호", "K2": "신규-지속 gap의 저널 내 절대합 > 저널 간 절대합", "K3": "적응 항 절대기여 > 진입 항 절대기여"},
    pass_criteria={"direction_split_max": 0.25, "invariant_tol": 1e-9, "perm_excess_near_zero": "관측 초과분이 순열 분포 안(백분위 5~95)이 아니면 보고"},
    decomposition="Griliches-Regev 중점(적응·재배분·진입(신규+복귀)·퇴출(최종+공백))", bootstrap="저자×논문 Exp(1) 곱셈 가중(공저 연결성분 부트스트랩 미사용)",
    permutation="저널×연도 셀 안에서 저자-논문 행 단위로 지속/진입 라벨 섞기", fdr="검정 묶음: 기간 쌍 4 × 항 4 = 16 (BH q=0.05, 사용 시)")
refs = {"F1": DATA/FILES["papers"], "F2": DATA/FILES["author_paper"], "F4": DATA/FILES["authors"], "S2_ipw": S2/FILES["ipw"], "S2_alpha": S2/FILES["alpha"],
        "S5_PREREG": S5/"S5_0_PREREG.json", "S4_PREREG": S4/"S4_0_PREREG.json", "S4_definition": S4/"definition_sensitivity.csv"}
spec["ref_hashes"] = {k: (hashlib.sha256(f.read_bytes()).hexdigest()[:12] if f.exists() else "MISSING") for k, f in refs.items()}
print("참조 해시:", spec["ref_hashes"])
if "MISSING" in spec["ref_hashes"].values(): print("⛔ 누락 파일이 있습니다. 동결하지 마세요.")
try:
    import pandas as pd
    I = pd.read_csv(S2/FILES["ipw"], usecols=["model", "w_ipw", "has_topic"]); print("IPW 모델별 요약(S4 가중치 범위 0.86~1.94와 비교):")
    print(I[I.has_topic.astype(str).str.lower().isin(["1", "true"])].groupby("model").w_ipw.agg(["count", "min", "max", "mean"]).round(3).to_string())
except Exception as e: print("※ IPW 점검 생략:", e)
h = hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]; print("S6-0 해시(예정)", h)
if not FREEZE: print("(점검만)"); raise SystemExit
assert "MISSING" not in spec["ref_hashes"].values(), "누락 파일이 있어 동결 중단"
spec["hash"] = h; (S6 / "S6_0_PREREG.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
(S6 / "CHANGELOG_S6.md").open("a", encoding="utf-8").write(f"- 2026-10-16 | S6-0 동결 {h}: S5 산출물 열람 후 동결, 결과를 보고 설정을 바꾸지 않음, 구간은 S4 동결 기간(체제 아님), 위험군은 F2에서 이미 제외(변형 범위 산출 불가) | S6-0 | S6\n")
def run(cmd):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0: print("⛔", " ".join(cmd), "\n", r.stdout, r.stderr); raise SystemExit(1)
    return r.stdout
run(["git", "add", "paper1/06_S6", "paper1/s6_lib.py", "paper1/s6_0_freeze.py", "paper1/s6_run.py"])
run(["git", "commit", "-m", "S6-0 freeze"]); run(["git", "tag", "S6-0-freeze-2026-10-16"]); print(run(["git", "log", "--oneline", "-2"]))
