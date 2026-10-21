# -*- coding: utf-8 -*-
# PA-B7c: 저널x연도 셀 사후층화 가중(관측 논문에 (관측+결측)/관측 가중)으로 S4 big 토픽 부호·라벨과 S5 변화점을 재점검. 결정적. 미실행.
from pa_common import *
PLAN = dict(
    version=1, parent="PA_0_PLAN_v2.json",
    status="사후 명세(지침서 B7-3의 단순화). S4 IPW(라벨 유지 0.98), B7a·B7b 결과, s5_lib 소스 열람 상태. 결과 미열람. S4의 IPW 모델은 아님. 이전에 보류했으나 연구자 요청으로 수행. S0~S8 판정 불변.",
    weights="저널 j x 연도 t 셀 w_jt=(n_obs+n_miss)/n_obs (n_obs>0일 때; 결측은 분석 저널 안의 has_topic 거짓 논문). 셀 안 토픽 분포는 관측과 같다고 가정하는 사후층화로, 2007년 하락 같은 연도별 결측률 변화를 직접 보정",
    labels="가중 카운트로 주 대비 delta_ipw 계산, big 컷은 전체 149토픽 |delta_ipw|의 2/3 분위로 재계산, quality_high는 topic_quadrants.csv 고정, 라벨은 s4_main.py label()과 같은 규칙(총변화 기준)",
    changepoints="s5_lib.sample_P에 가중 카운트(cnt*w)를 넣고 s5_lib.detect를 S5 값(pen=c_primary*phi*(K-1)*log(T), phi·k_max·min_len 고정)으로 실행. 귀무 시뮬레이션은 하지 않고 관측 변화점과 R만 보고",
    reading="(1) 원 big 50개 중 부호 유지 비율 >=0.90 '유지', 0.70~0.90 '부분', <0.70 '민감'. (2) 원 big의 같은 라벨 유지율 >=0.95 '둔감', 아니면 '민감'. (3) 표본별로 S5 관측 변화점 각각이 가중 후 변화점 ±1년 안에 있는가를 보고(판정 없음). 세 가지를 합치지 않음",
    reproduce_check="(a) 셀 관측 카운트가 yearly_venue_topic_counts.npy의 저널·연도 합과 일치, (b) 관측 delta가 topic_quadrants.csv와 1e-9 이내이고 재계산 라벨이 quadrant와 일치, (c) 가중 없는 detect의 R이 regime_nulls.csv obs_R과 1e-3 이내",
    caveat="셀 안 토픽 분포가 같다는 가정(저널 내 무작위 결측, B7a의 k=1과 같은 가정이나 연도 단위). 가중으로 유효 표본 크기가 늘어 S5 벌점 대비 비용 비율이 달라짐(변화점 이동이 탐지기 설정 효과일 수 있음). 결측 사유가 토픽과 무관하다는 보장 없음",
    forbidden="결과를 본 뒤 가중·임계값 변경(변경 시 v2 계획으로 분리하고 사유 기록)")

def run(quick, sp):
    sys.path.insert(0, str(P1)); import s5_lib as L5
    c0, c1, P = periods(); F, Mi, topics, venues = analysis_sets()
    cnt, vs, tp, fixed_v = L5.load_counts(); Y = np.asarray(L5.YEARS); wbar = cnt.sum((0, 2))/cnt.sum()
    if not np.array_equal(np.asarray(tp), topics) or set(vs) != set(venues): raise Halt("S5 토픽·저널 축이 S4 정렬 목록과 다름: topics_order.csv/venues_order.csv 확인 필요")
    obs = pd.crosstab(F.year, F.venue_short).reindex(index=Y, columns=vs, fill_value=0).values.astype(float)
    miss = Mi.groupby(["year", "venue_short"]).size().unstack(fill_value=0).reindex(index=Y, columns=vs, fill_value=0).values.astype(float)
    if not np.allclose(obs, cnt.sum(2)): raise Halt("셀 관측 카운트가 yearly_venue_topic_counts.npy와 다름")
    w = np.where(obs > 0, (obs + miss)/np.where(obs > 0, obs, 1), 1.0); cw = cnt*w[:, :, None]
    share = lambda c, lo, hi: (lambda a: a/a.sum())(c[(Y >= lo) & (Y <= hi)].sum((0, 1)))
    d_obs = share(cnt, *P[c1]) - share(cnt, *P[c0]); d_ipw = share(cw, *P[c1]) - share(cw, *P[c0])
    Q = pd.read_csv(S4/"topic_quadrants.csv", encoding="utf-8-sig").set_index("topic").loc[topics]
    if np.abs(d_obs - Q.delta.values).max() > 1e-9: raise Halt("관측 delta가 topic_quadrants.csv와 다름")
    qh = bl(Q.quality_high).values; D = pd.DataFrame(dict(topic=topics, delta=Q.delta.values, delta_ipw=d_ipw), index=topics)
    q0, b0, _ = label(D, "delta", qh)
    if not (q0.values == Q.quadrant.values).all(): raise Halt("관측 delta로 재계산한 라벨이 topic_quadrants.csv와 다름")
    s5 = json.loads((S5D/"S5_0_PREREG.json").read_text(encoding="utf-8")); Dd = s5["detection"]; PHI = {k: v["phi"] for k, v in Dd["phi"].items()}; C0, KMAX, MINLEN = Dd["c_primary"], Dd["k_max"], Dd["min_len"]
    K, T = len(topics), len(Y); SAM = s5["samples"]; ref = pd.read_csv(S5D/"regime_nulls.csv"); ref = ref[ref["null"] == "N2"].set_index("sample")
    def det(c, s): Pm, n = L5.sample_P(c, fixed_v, wbar, s); return L5.detect(Pm, n, C0*PHI[s]*(K - 1)*np.log(T), KMAX, MINLEN)
    for s in SAM:
        if abs(det(cnt, s)["R"] - float(ref.loc[s, "obs_R"])) > 1e-3: raise Halt(f"S5 관측 R 재현 실패({s})")
    print("[재현 OK] 셀 카운트, 관측 delta·라벨, S5 관측 R | 가중 w 범위", round(float(w[obs > 0].min()), 3), "~", round(float(w[obs > 0].max()), 3))
    if quick: print("[QUICK] 재현 점검만."); return
    q1, b1, cut1 = label(D, "delta_ipw", qh); ob = Q.big.pipe(bl).values
    kept_sign = np.sign(d_ipw) == np.sign(Q.delta.values); sg = float(kept_sign[ob].mean()); same = float((q1.values[ob] == Q.quadrant.values[ob]).mean()); newbig = int((b1.values & ~ob).sum())
    atten = float(np.median(np.abs(d_ipw[ob])/np.abs(Q.delta.values[ob])))
    out = pd.DataFrame([dict(n_big_orig=int(ob.sum()), n_big_ipw=int(b1.sum()), sign_kept_share=sg, label_same_share=same, n_newly_big=newbig, cut_orig=float(Q.delta.abs().quantile(2/3)), cut_ipw=cut1, atten_median=atten)])
    D.assign(big_orig=ob, big_ipw=b1.values, quad_orig=Q.quadrant.values, quad_ipw=q1.values, sign_kept=kept_sign).to_csv(PA/"PA_B7c_topics.csv", index=False, encoding="utf-8-sig"); out.to_csv(PA/"PA_B7c_summary.csv", index=False, encoding="utf-8-sig")
    meta = json.loads((S5D/"S5_meta.json").read_text(encoding="utf-8"))["obs_breaks"]; rows = []
    for s in SAM:
        a, b = det(cnt, s), det(cw, s); ya, yb = [int(Y[x]) for x in a["br"]], [int(Y[x]) for x in b["br"]]
        rows.append(dict(sample=s, breaks_base=str(ya), breaks_ipw=str(yb), s5_breaks=str(meta[s]), s5_kept_pm1=str([L5.near(y, yb, 1) for y in meta[s]]), R_base=a["R"], R_ipw=b["R"], k_base=a["k"], k_ipw=b["k"]))
    CP = pd.DataFrame(rows); CP.to_csv(PA/"PA_B7c_changepoints.csv", index=False, encoding="utf-8-sig")
    v1 = "유지" if sg >= 0.90 else ("부분" if sg >= 0.70 else "민감"); v2 = "둔감" if same >= 0.95 else "민감"
    print("\n[Post-hoc] PA-B7c 요약\n", out.round(4).T.to_string(header=False)); print(f"\n[동결 판독] 부호 {sg:.3f} → {v1} | 라벨 {same:.3f} → {v2}")
    print("\n[Post-hoc] 변화점(가중 전후, 판정 없음)\n", CP.round(4).to_string(index=False))
    print("[부호 유지 실패 big]\n", D[ob & ~kept_sign].round(4).to_string() if (ob & ~kept_sign).any() else "없음")
    print("※ 셀 사후층화(S4 IPW 모델과 다름). 가중으로 비용/벌점 비율이 달라짐. 세 판독을 합치지 않음. S0~S8 판정 불변.")

run_pa("B7c", PLAN, run, [S4/"topic_quadrants.csv", S4/"yearly_venue_topic_counts.npy", P1/"s5_lib.py", S5D/"S5_0_PREREG.json", S5D/"S5_meta.json", S5D/"regime_nulls.csv"], "저널x연도 상호작용 보정(셀 사후층화)으로 S4 라벨·S5 변화점 재점검(지침서 B7-3)")