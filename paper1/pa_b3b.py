# -*- coding: utf-8 -*-
# PA-B3b: D1(=F6.emerging; 2005-09 대 2015-19, r>=3 & s1>=0.005)의 이질성을 구간·규칙으로 분리. 지침서 D1'(구간 재구성)는 전제가 어긋나 대체. 결정적. 미실행.
from pa_common import *
PLAN = dict(
    version=1, parent="PA_0_PLAN_v2.json",
    status="사후 명세. s4_main.py L116-119로 D1~D4 정의(D1=r=(s1+1e-4)/(s0+1e-4)>=3 and s1>=0.005, 구간 2005-09 대 2015-19; D2=주 대비 평활 로그 비율 상위 14; D3=주 대비 Δs 상위 14; D4=민감도 대비 Δs 상위 14), B3a 결과 열람. 결과 미열람. 지침서의 D1'는 D1이 이미 그 구간이라 의미 없어 구간/규칙 분리 변형 3종으로 대체. S0~S8 판정 불변.",
    shares="S4 분석 집합 F(76,984편)에서 기간별 토픽 비중(pa_b7a와 동일 계산). 주 대비·기간은 S4 동결 규칙 파일에서 읽음. 비중 기준은 topic_quadrants.csv의 delta와 일치(F6_topics의 F2 기준 비중과 다름)",
    variants={"D1_rule": "D1 구간(2005-09 대 2015-19)에서 D2 규칙(평활 로그 비율 상위 14, 평활 eps=1e-4)", "D1_rule_ds": "D1 구간에서 D3 규칙(Δs 상위 14)", "D1_interval": "주 대비 구간에서 D1 규칙(r>=3 and s1>=0.005, eps=1e-4)"},
    stats="변형별 토픽 수, 저장된 D1~D4(definition_sensitivity.csv)와의 쌍별 Jaccard, 원 D1과 변형 각각의 D2·D3·D4에 대한 평균 Jaccard",
    reading="원 D1의 (D2,D3,D4) 평균 Jaccard 대비 D1_rule/D1_rule_ds가 더 크면 '규칙 차이가 이질성의 주원인', D1_interval이 더 크면 '구간 차이가 주원인'으로 방향만 기술. 임계값·판정 없음. 둘 다 크거나 작으면 그대로 기술",
    reproduce_check="(a) 관측 delta가 topic_quadrants.csv와 1e-9 이내, (b) 재계산 D3(주 대비 Δs 상위 14, 안정 정렬)가 저장 D3와 집합 일치(불일치 시 중단), (c) 정보용: 재계산 D1·D2와 저장 D1·D2의 Jaccard(F1 기준이라 완전 일치하지 않을 수 있음, 중단 조건 아님)",
    caveat="D2 평활 방식과 D4(민감도 대비)는 미확인이라 D2는 정보용 재현, D4는 저장값만 사용. 31개 합집합 밖 토픽도 변형에 포함. 정의 차이의 설명이며 신생 토픽의 타당성 검증이 아님",
    forbidden="결과를 본 뒤 변형·eps·판독 변경(변경 시 v2 계획으로 분리하고 사유 기록)")

def run(quick, sp):
    DS = pd.read_csv(S4/"definition_sensitivity.csv", encoding="utf-8-sig"); ks = ["D1", "D2", "D3", "D4"]
    for k in ks: DS[k] = bl(DS[k])
    st = {k: set(DS.topic[DS[k]].astype(int)) for k in ks}
    c0, c1, P = periods(); fnd = lambda a, b: next((k for k, v in P.items() if tuple(v) == (a, b)), None)
    k09, k19 = fnd(2005, 2009), fnd(2015, 2019)
    if not (k09 and k19): raise Halt(f"periods에서 2005-09/2015-19를 찾지 못함: {P}")
    F, Mi, topics, venues = analysis_sets(); pos = {int(t): i for i, t in enumerate(topics)}; fi = F.topic.map(pos).astype(int).values
    sh = lambda lo, hi: (lambda m: np.bincount(fi[m], minlength=len(topics))/m.sum())(F.year.between(lo, hi).values)
    s0, s1 = sh(*P[c0]), sh(*P[c1]); Q = pd.read_csv(S4/"topic_quadrants.csv").set_index("topic")
    if np.abs((s1 - s0) - Q.loc[topics, "delta"].values).max() > 1e-9: raise Halt("관측 delta가 topic_quadrants.csv와 다름")
    top14 = lambda x: set(topics[np.argsort(-x, kind="stable")[:14]].astype(int)); eps = 1e-4
    lr = lambda a, b: np.log((b + eps)/(a + eps))
    D3 = top14(s1 - s0)
    if D3 != st["D3"]: raise Halt(f"재계산 D3가 저장 D3와 다름(차이 {sorted(D3 ^ st['D3'])}): 정의 재확인 필요")
    a09, a19 = sh(*P[k09]), sh(*P[k19]); D1re = set(topics[((a19 + eps)/(a09 + eps) >= 3) & (a19 >= 0.005)].astype(int)); D2re = top14(lr(s0, s1))
    J = lambda a, b: len(a & b)/len(a | b) if (a | b) else np.nan
    print(f"[재현 OK] delta, 재계산 D3=저장 D3 | 정보: 재계산 D1 n={len(D1re)} Jaccard(저장 D1)={J(D1re, st['D1']):.2f}, 재계산 D2 Jaccard(저장 D2)={J(D2re, st['D2']):.2f}")
    if quick: print("[QUICK] 재현 점검만."); return
    V = {"D1_rule": top14(lr(a09, a19)), "D1_rule_ds": top14(a19 - a09), "D1_interval": set(topics[((s1 + eps)/(s0 + eps) >= 3) & (s1 >= 0.005)].astype(int))}
    allsets = {**st, **V}; names = list(allsets)
    JM = pd.DataFrame([[J(allsets[a], allsets[b]) for b in names] for a in names], index=names, columns=names)
    mean_vs = {nm: float(np.mean([J(allsets[nm], st[k]) for k in ["D2", "D3", "D4"]])) for nm in ["D1"] + list(V)}
    sz = pd.DataFrame({"n": {k: len(v) for k, v in allsets.items()}}); JM.to_csv(PA/"PA_B3b_jaccard.csv", encoding="utf-8-sig"); sz.to_csv(PA/"PA_B3b_sizes.csv", encoding="utf-8-sig")
    pd.DataFrame([dict(set=k, topics=sorted(v)) for k, v in V.items()]).to_csv(PA/"PA_B3b_variant_topics.csv", index=False, encoding="utf-8-sig")
    print("\n[Post-hoc] 정의·변형 크기\n", sz.T.to_string()); print("\n[Post-hoc] 쌍별 Jaccard\n", JM.round(2).to_string())
    print("\n[Post-hoc] D2·D3·D4와의 평균 Jaccard:", {k: round(v, 3) for k, v in mean_vs.items()})
    for v in V: print(f"  {v}: 원 D1 대비 {'더 큼' if mean_vs[v] > mean_vs['D1'] else '더 작거나 같음'} ({mean_vs[v]:.3f} vs {mean_vs['D1']:.3f})")
    print("※ 방향만 기술. 변형은 사후 정의. S0~S8 판정 불변.")

run_pa("B3b", PLAN, run, [S4/"definition_sensitivity.csv", S4/"topic_quadrants.csv", P1/"s4_main.py"], "D1 이질성의 구간·규칙 분리(지침서 D1' 대체)")