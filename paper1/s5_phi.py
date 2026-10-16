# -*- coding: utf-8 -*-
# s5_phi.py: 벌점 과분산 계수 phi를 귀무(N0, N1)에서만 추정. 관측 자료의 변화점은 계산하지 않는다(동결 전 실행용).
# phi = max(1, N1에서 k=1 비용의 중앙값 / ((T-1)(K-1))). N0 값은 참고용으로 같이 저장.
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from s5_lib import *

B = 300
rng = np.random.default_rng(2026)
cnt, venues, topics, fixed_v = load_counts(); wbar = cnt.sum((0, 2)) / cnt.sum()
K, T = len(topics), len(YEARS); out = {}
for s in SAMPLES:
    r = {}
    for nm, g in [("N0", gen_N0), ("N1", gen_N1)]:
        v = []
        for _ in range(B):
            P, n = sample_P(g(cnt, rng), fixed_v, wbar, s)
            v.append(seg_costs(np.sqrt(P), 4.0 * n)[0, T] / ((T - 1) * (K - 1)))
        r[nm] = round(float(np.median(v)), 4)
    r["phi"] = max(1.0, r["N1"]); out[s] = r
    print(s, r)
S5.mkdir(parents=True, exist_ok=True)
(S5 / "S5_phi.json").write_text(json.dumps(dict(B=B, seed=2026, at=now(), phi=out), indent=1), encoding="utf-8")
print("저장: S5_phi.json (이 값을 s5_0_freeze.py가 읽어 동결)")
