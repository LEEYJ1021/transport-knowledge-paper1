# -*- coding: utf-8 -*-
# s4_close.py: S4 마무리. 새 분석 없음(D1 진단은 사후 읽기 전용). COMMIT=False로 먼저 실행.
import json, hashlib, subprocess, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore"); pd.set_option("display.width", 200)

COMMIT = True
ROOT = Path.home() / "Research/Minnesota_Transport"
DATA, S3, S4 = ROOT / "analysis_data/final", ROOT / "paper1/03_S3", ROOT / "paper1/04_S4"
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds")
sha_f = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
sha_b = lambda b: hashlib.sha256(b).hexdigest()
tf = lambda s: s.astype(str).str.strip().str.lower().isin(["1", "1.0", "true", "t", "yes"])
class Halt(Exception): pass

def main():
    spec = json.loads((S4 / "S4_0_PREREG.json").read_text(encoding="utf-8"))
    core = {k: v for k, v in spec.items() if k not in ("created", "sha256", "reference_hashes_at_freeze")}
    if sha_b(json.dumps(core, sort_keys=True, ensure_ascii=False).encode()) != spec["sha256"]: raise Halt("S4 동결 해시 불일치")
    meta = json.loads((S4 / "S4_meta.json").read_text(encoding="utf-8"))
    if meta["spec_sha256"] != spec["sha256"]: raise Halt("S4_meta가 다른 규칙 해시로 만들어졌습니다")
    for f, h in meta["outputs"].items():
        if sha_f(S4 / f) != h: raise Halt(f"{f}: 실행 시점과 해시가 다릅니다")
    need = ["keyword_turnover.csv", "rotation_index_periods.csv", "yearly_series_for_S5.csv",
            "heatmap_topic_venue_period.csv", "yearly_js_poolfloor_check.csv"]
    miss = [f for f in need if not (S4 / f).exists()]
    if miss: raise Halt(f"이월 항목 산출물 없음: {miss}")
    print(f"검증 통과: 본 계산 산출물·규칙 해시({spec['sha256'][:12]}) 일치, 이월 산출물 존재")

    # ---- D1 진단(사후, 읽기 전용) ----
    M = pd.read_csv(S4 / "topic_quadrants.csv"); topics = set(M.topic.astype(int))
    F6 = pd.read_csv(DATA / "F6_topics.csv"); F6["topic"] = F6.topic150.astype(int)
    F6 = F6[F6.topic.isin(topics)].set_index("topic")
    d1_all = set(F6.index[tf(F6.emerging)]); print(f"F6 emerging 유효 토픽 수 {len(d1_all)}")
    e = 1e-4; res = []
    for a, b in [("share_0509", "share_1519"), ("share_0509", "share_2025"), ("share_1519", "share_2025")]:
        for kind in ["diff", "logratio", "ratio"]:
            if kind == "diff": v = F6[b] - F6[a]
            elif kind == "logratio": v = np.log((F6[b] + e) / (F6[a] + e))
            else: v = F6[b] / F6[a].replace(0, np.nan)
            top = set(v.sort_values(ascending=False).head(14).index)
            res.append(dict(contrast=f"{a[6:]}->{b[6:]}", kind=kind,
                            jaccard_with_D1=round(len(top & d1_all) / len(top | d1_all), 2), overlap=len(top & d1_all)))
    R = pd.DataFrame(res).sort_values("jaccard_with_D1", ascending=False)
    print("\n[D1 진단]\n", R.to_string(index=False))
    best = R.iloc[0]
    print(f"가장 비슷한 조합: {best.contrast} {best.kind} (Jaccard {best.jaccard_with_D1}). 1.0이 아니면 F6 정의는 이것이 아닙니다(추정).")
    R.to_csv(S4 / "D1_diagnostic_posthoc.csv", index=False, encoding="utf-8-sig")

    # ---- 요약 ----
    A = M[M.grade == "A"]
    md = f"""# S4 최종 요약 ({now()})
- 규칙 해시 `{spec['sha256'][:12]}` (동결 후 변경 없음). 분석 집합 76,984편, 유효 토픽 149개.
- 4분면(전체): {M.quadrant.value_counts().to_dict()} | A등급: {A.quadrant.value_counts().to_dict()}
- 안정성: 전체 {meta['stability_all']}, A등급 {meta['stability_A']} (기준 0.70, 경계 통과). 결측 보정 라벨 유지 {meta['miss_keep_all']} / A {meta['miss_keep_A']} (AUC {meta['miss_auc']}).
- 4.1 키워드 Jaccard 중앙값 0.25 -> 0.33 -> 0.38 -> 0.43(인접 기간 쌍). 4.6 기간 회전 Spearman 0.91 -> 0.83 -> 0.76 -> 0.32.
- 4.6b: 풀 재표집 바닥에서 all 보정 JS > 0인 연도 22/25. 반분 바닥은 과대평가였음. 2007만 비유의.
- 고정 저널은 PREREG 14개 기준(F1.fixed_venue 15개와 불일치, JPT 2019 0편, 원인 미확인).
- D1 진단(사후): 가장 비슷한 조합 {best.contrast} {best.kind} (Jaccard {best.jaccard_with_D1}). 추정이며 판정 불변.
## 닫히지 않은 것
- 4.7 지속 저자 따라감 비율(S6 직전) / 출판 후 3년 고정 창 질 민감도 / 토픽 0, 147, 88, 45 카드 해석 메모
## 한계
질 라벨은 0.5 근처에서 불안정 / 안정성은 토픽 1~2개로 뒤집히는 경계값 / 분석 집합은 임베딩 보유 논문 83.9% / 인용은 단일 스냅샷 / 4.6b 재표집은 논문 독립 가정
"""
    (S4 / "S4_final_summary.md").write_text(md, encoding="utf-8")
    cl = S4 / "CHANGELOG_S4.md"
    if "S4 마무리" not in cl.read_text(encoding="utf-8"):
        with cl.open("a", encoding="utf-8") as f:
            f.write(f"- {now()} | S4 마무리: 산출물·규칙 해시 검증, D1 진단(사후, 읽기 전용), 요약·매니페스트 생성. 규칙·판정 변경 없음. 4.7과 3년 고정 창은 이월 | S4 | 산출물 완결\n")
    man = {p.name: sha_f(p) for p in sorted(S4.iterdir()) if p.is_file() and p.name != "S4_MANIFEST.json"}
    (S4 / "S4_MANIFEST.json").write_text(json.dumps(dict(at=now(), spec_sha256=spec["sha256"], files=man), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"매니페스트 {len(man)}개 파일")
    if not COMMIT: print("\n(COMMIT=False: git은 건드리지 않았습니다. 확인 후 COMMIT=True)"); return

    g = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
    tag = f"S4-final-{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    if g("tag", "-l", tag).stdout.strip(): raise Halt(f"태그 {tag}가 이미 있습니다")
    g("add", "--", "paper1/04_S4", "paper1/s4_6_rotation.py", "paper1/s4_6b_floor_check.py", "paper1/s4_1_keywords.py", "paper1/s4_close.py")
    c = g("commit", "-m", "S4 마무리: 4.1, 4.6, 4.6b, D1 진단, 매니페스트"); print((c.stdout or c.stderr).strip()[:300])
    g("tag", "-a", tag, "-m", "S4 final (4.7은 S6 직전으로 이월)"); print("태그:", tag)
    print("남은 변경:", g("status", "--short", "paper1/04_S4").stdout.strip() or "없음")

try: main()
except Halt as e: print(f"⛔ 중단: {e}")