# -*- coding: utf-8 -*-
# =====================================================================================
# S4 본 계산: 양 x 질 4분면, 저널 내/간 정확 분해, 신생 정의 4종, 결측 보정 민감도.
# 규칙은 동결된 S4_0_PREREG.json에서 읽는다. OpenAlex 호출 없음.
# 구현 선택(CHANGELOG 기록): has_topic 기준 비중, 부재 저널 w=0·s=0, 안정성은 저널 내 성분으로
#   상위 3분위 규칙 재적용, 질 부트스트랩은 토픽 내 논문 복원추출, D1=F6.emerging
# =====================================================================================
import json, hashlib, warnings
from pathlib import Path
import numpy as np, pandas as pd
import scipy.sparse as sp
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import OneHotEncoder
warnings.filterwarnings("ignore"); pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)

ROOT = Path.home() / "Research/Minnesota_Transport"
DATA, S0, S3, S4 = ROOT / "analysis_data/final", ROOT / "paper1/00_S0", ROOT / "paper1/03_S3", ROOT / "paper1/04_S4"
SPEC_FILE = S4 / "S4_0_PREREG.json"
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds")
sha_f = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
sha_b = lambda b: hashlib.sha256(b).hexdigest()
tf = lambda s: s.astype(str).str.strip().str.lower().isin(["1", "1.0", "true", "t", "yes"])
class Halt(Exception): pass

def changelog_once(key, line):
    cl = S4 / "CHANGELOG_S4.md"
    if key in cl.read_text(encoding="utf-8"): return
    with cl.open("a", encoding="utf-8") as f: f.write(line + "\n")

def main():
    # ---------- 0. 동결 검증 ----------
    if not SPEC_FILE.exists(): raise Halt("S4_0_PREREG.json 없음")
    spec = json.loads(SPEC_FILE.read_text(encoding="utf-8"))
    core = {k: v for k, v in spec.items() if k not in ("created", "sha256", "reference_hashes_at_freeze")}
    if sha_b(json.dumps(core, sort_keys=True, ensure_ascii=False).encode()) != spec["sha256"]: raise Halt("동결 해시 불일치: SPEC이 변경됨")
    for f, h in spec["reference_hashes_at_freeze"].items():
        if sha_f(S3 / f) != h: raise Halt(f"참조 파일 {f} 해시가 동결 시점과 다름")
    print(f"동결 검증 통과 (해시 {spec['sha256'][:12]})")
    P = {k: tuple(v) for k, v in spec["periods"].items()}; Q = spec["quality"]; seed = int(spec["seed"]); B = int(Q["bootstrap_B"])
    rng = np.random.default_rng(seed); main0, main1 = spec["main_contrast"]; sens0, sens1 = spec["sens_contrast"]

    # ---------- 1. 데이터 ----------
    W = pd.read_csv(DATA / "F1_papers.csv", low_memory=False); W["pid"] = W.pid.astype(str)
    EXC = set(pd.read_csv(S0 / "EXCLUDE_PIDS_FROZEN.csv", dtype=str, encoding="utf-8-sig").pid)
    W = W[~W.pid.isin(EXC) & tf(W.in_sample) & W.year.between(2000, 2025)].copy().reset_index(drop=True)
    W["ht"] = tf(W.has_topic) & W.topic150.notna()
    F = W[W.ht].copy().reset_index(drop=True)
    print(f"창 내 {len(W):,}편 | 분석 집합(has_topic) {len(F):,}편")
    if len(F) != 76984: raise Halt("분석 집합이 76,984편이 아닙니다")
    F["topic"] = F.topic150.astype(int); F["cited_by_count"] = pd.to_numeric(F.cited_by_count, errors="coerce")
    g = F.groupby(["year", "venue_short"]).cited_by_count
    F["cit_pct"] = (g.rank(method="average") - 0.5) / g.transform("count")
    G = pd.read_csv(S3 / "L7_topic_grade.csv"); grade = dict(zip(G.topic.astype(int), G.grade))
    topics = np.array(sorted(grade)); venues = np.array(sorted(F.venue_short.unique()))
    if set(F.topic) != set(topics): raise Halt("토픽 집합이 L7과 다릅니다")

    # ---------- 2. 양 + 정확 분해 ----------
    def mats(lo, hi):
        d = F[F.year.between(lo, hi)]
        ct = pd.crosstab(d.venue_short, d.topic).reindex(index=venues, columns=topics, fill_value=0)
        nj = ct.sum(1).values.astype(float); w = nj / nj.sum()
        s = np.divide(ct.values, nj[:, None], out=np.zeros(ct.shape), where=nj[:, None] > 0)
        return w, s, ct.values.sum(0) / ct.values.sum(), int(nj.sum())
    def decomp(a, b):
        w0, s0, S0_, N0 = mats(*P[a]); w1, s1, S1_, N1 = mats(*P[b])
        if abs(w0 @ s0 - S0_).max() > 1e-9 or abs(w1 @ s1 - S1_).max() > 1e-9: raise Halt("불변식 실패: 질량 보존")
        within = (((w0 + w1) / 2)[:, None] * (s1 - s0)).sum(0)
        between = (((s0 + s1) / 2) * (w1 - w0)[:, None]).sum(0); tot = S1_ - S0_
        if abs(within + between - tot).max() > 1e-9: raise Halt("불변식 실패: 내+간 != 총변화")
        lr = np.log((S1_ + 0.5 / N1) / (S0_ + 0.5 / N0))
        return pd.DataFrame(dict(topic=topics, s0=S0_, s1=S1_, delta=tot, within=within, between=between, log_ratio=lr)), (N0, N1)
    M, (n0, n1) = decomp(main0, main1); Ms, _ = decomp(sens0, sens1)
    print(f"불변식 통과(질량 보존, 내+간=총변화) | 주 대비 {main0}->{main1}: N={n0:,}/{n1:,}")
    M["between_share"] = M.between.abs() / (M.within.abs() + M.between.abs()).replace(0, np.nan)

    # ---------- 3. 질 ----------
    Fq = F[F.year <= int(Q["max_year"])]; rows = []
    for t in topics:
        x = Fq.loc[Fq.topic == t, "cit_pct"].values; n = len(x)
        if n == 0: rows.append(dict(topic=t, q_n=0)); continue
        bm = x[rng.integers(0, n, (B, n))].mean(1)
        rows.append(dict(topic=t, q_n=n, q_mean=x.mean(), q_lo=np.percentile(bm, 2.5), q_hi=np.percentile(bm, 97.5), q_top10=(x >= Q["top_decile_cut"]).mean()))
    M = M.merge(pd.DataFrame(rows), on="topic"); M["quality_high"] = (M.q_mean > 0.5) & (M.q_lo > 0.5)

    # ---------- 4. 4분면 ----------
    def label(df, col, quality_high):
        cut = df[col].abs().quantile(2 / 3); big = df[col].abs() >= cut
        lab = ["small_change" if not b else ("growth" if d > 0 else "decline") + ("_highQ" if q else "_notHighQ")
               for b, d, q in zip(big, df[col], quality_high)]
        return pd.Series(lab, index=df.index), big, cut
    M["quadrant"], M["big"], cut_tot = label(M, "delta", M.quality_high)
    M["quadrant_within"], M["big_within"], cut_w = label(M, "within", M.quality_high)
    M["grade"] = M.topic.map(grade)
    stab = lambda d: float((d[d.big].quadrant == d[d.big].quadrant_within).mean()) if d.big.any() else np.nan
    s_all, s_A = stab(M), stab(M[M.grade == "A"]); thr = spec["stability"]["quadrant_within_component_min"]
    print(f"\n[4분면 분포 전체]\n{M.quadrant.value_counts().to_string()}")
    print(f"\n[A등급만]\n{M[M.grade == 'A'].quadrant.value_counts().to_string()}")
    print(f"\n|Delta| 상위 3분위 경계 {cut_tot:.5f} | 저널 내 성분 경계 {cut_w:.5f}")
    print(f"4분면 안정성(저널 내 성분으로 재분류 시 big_change 라벨 유지): 전체 {s_all:.3f} | A등급만 {s_A:.3f} | 기준 {thr} -> {'통과' if s_all >= thr else '미달'}")
    bg = M[M.big]; print("big_change 토픽의 부호 유지율(저널 내 부호 = 총변화 부호):", round(float((np.sign(bg.within) == np.sign(bg.delta)).mean()), 3))
    dec, gro = M[M.big & (M.delta < 0)], M[M.big & (M.delta > 0)]
    print(f"\n[저널 구성 분해] 쇠퇴 big {len(dec)}개: 저널 간 성분 비중 중앙값 {dec.between_share.median():.2f} (A등급만 {dec[dec.grade=='A'].between_share.median():.2f})"
          f" | 성장 big {len(gro)}개: {gro.between_share.median():.2f} (A등급만 {gro[gro.grade=='A'].between_share.median():.2f})")
    print(f"저널 간 성분이 총변화와 반대 부호인 토픽: {int((np.sign(M.between) != np.sign(M.delta)).sum())}개")
    cols = ["topic", "grade", "delta", "within", "between", "between_share", "q_mean", "quadrant"]
    print("\n쇠퇴 상위 8:\n", M.sort_values("delta").head(8)[cols].round(4).to_string(index=False))
    print("\n성장 상위 8:\n", M.sort_values("delta", ascending=False).head(8)[cols].round(4).to_string(index=False))
    print("\n[토픽 0, 38, 49, 147, 88, 69]\n", M[M.topic.isin([0, 38, 49, 147, 88, 69])][["topic", "grade", "delta", "within", "between", "q_mean", "q_lo", "q_hi", "quadrant", "quadrant_within"]].round(4).to_string(index=False))

    # ---------- 5. 신생 정의 4종 ----------
    E = {}
    try:
        F6 = pd.read_csv(DATA / "F6_topics.csv"); E["D1"] = set(F6.loc[tf(F6.emerging), "topic150"].astype(int)) & set(topics)
    except Exception as e: print("※ D1 생략:", e); E["D1"] = set()
    E["D2"] = set(M.sort_values("log_ratio", ascending=False).head(14).topic); E["D3"] = set(M.sort_values("delta", ascending=False).head(14).topic)
    E["D4"] = set(Ms.sort_values("delta", ascending=False).head(14).topic)
    ks = list(E); J = pd.DataFrame([[len(E[a] & E[b]) / len(E[a] | E[b]) if E[a] | E[b] else np.nan for b in ks] for a in ks], index=ks, columns=ks).round(2)
    print("\n[신생 정의별 토픽 수와 Jaccard]", {k: len(v) for k, v in E.items()}); print(J.to_string())
    DS = pd.DataFrame([dict(topic=t, grade=grade[t], **{k: t in E[k] for k in ks}, n_defs=sum(t in E[k] for k in ks))
                       for t in sorted(set().union(*E.values()))]).sort_values("n_defs", ascending=False)
    print("신생 후보 중 4종 모두:", int((DS.n_defs == 4).sum()), "| 1종만:", int((DS.n_defs == 1).sum()), "| C등급 포함:", DS[DS.grade == "C"].topic.tolist())

    # ---------- 6. 저장(본 계산) ----------
    M.to_csv(S4 / "topic_quadrants.csv", index=False, encoding="utf-8-sig")
    M[["topic", "grade", "s0", "s1", "delta", "within", "between", "between_share", "log_ratio"]].to_csv(S4 / "journal_decomposition.csv", index=False, encoding="utf-8-sig")
    Ms.assign(grade=Ms.topic.map(grade)).to_csv(S4 / "journal_decomposition_sens_1519_2024.csv", index=False, encoding="utf-8-sig")
    DS.to_csv(S4 / "definition_sensitivity.csv", index=False, encoding="utf-8-sig")

    # ---------- 7. 결측 보정 민감도 ----------
    print("\n=== 결측 보정 민감도 (역확률 가중) ===")
    W["n_authors"] = pd.to_numeric(W.n_authors, errors="coerce").fillna(1)
    W["solo"] = tf(W.is_solo).astype(float); W["lna"] = np.log(W.n_authors.clip(lower=1))
    W["per"] = pd.cut(W.year, [1999, 2004, 2009, 2014, 2019, 2025], labels=False).astype(str)
    enc = OneHotEncoder(handle_unknown="ignore", min_frequency=5)
    C = enc.fit_transform(pd.DataFrame({"y": W.year.astype(str), "v": W.venue_short, "pv": W.per + "_" + W.venue_short}))
    X = sp.hstack([C, sp.csr_matrix(W[["lna", "solo"]].values)]).tocsr()
    m = LogisticRegression(C=1.0, max_iter=2000, random_state=seed).fit(X, W.ht.astype(int))
    p = m.predict_proba(X)[:, 1]; auc = roc_auc_score(W.ht, p); W["p"] = p
    w = W.ht.mean() / p; lo, hi = np.percentile(w[W.ht], [1, 99]); W["w"] = np.clip(w, lo, hi)
    T = W[W.ht].copy(); T["topic"] = T.topic150.astype(int); ess = T.w.sum() ** 2 / (T.w ** 2).sum()
    print(f"AUC {auc:.3f} (S2: 0.73) | 유효 표본 {ess:,.0f}/{len(T):,} | p_hat<0.05 비중 {(T.p < 0.05).mean():.3%} | 가중치 범위 {lo:.2f}~{hi:.2f}")
    def shares(lo_, hi_, weighted):
        d = T[T.year.between(lo_, hi_)]; wt = d.w if weighted else pd.Series(1.0, index=d.index)
        return wt.groupby(d.topic).sum().reindex(topics, fill_value=0).values / wt.sum()
    d_u = shares(*P[main1], False) - shares(*P[main0], False); d_w = shares(*P[main1], True) - shares(*P[main0], True)
    if abs(d_u - M.delta.values).max() > 1e-9: raise Halt("가중 없는 Delta가 본 계산과 다릅니다")
    print("원 Delta와 보정 Delta 상관:", round(float(np.corrcoef(d_u, d_w)[0, 1]), 3), "| 부호 일치율:", round(float((np.sign(d_u) == np.sign(d_w)).mean()), 3))
    Mw = M[["topic", "grade", "delta", "big", "quadrant", "quality_high"]].copy(); Mw["delta_w"] = d_w
    Mw["quad_w"], Mw["big_w"], _ = label(Mw, "delta_w", Mw.quality_high)
    for name, sub in {"전체": Mw, "A등급": Mw[Mw.grade == "A"]}.items():
        s = sub[sub.big]; print(f"[{name}] 원 big {len(s)}개 중 보정 후 같은 라벨 유지: {(s.quadrant == s.quad_w).mean():.3f} | big 유지(라벨 무관): {s.big_w.mean():.3f}")
    keep_all = float((Mw[Mw.big].quadrant == Mw[Mw.big].quad_w).mean()); keep_A = float((Mw[Mw.big & (Mw.grade == "A")].quadrant == Mw[Mw.big & (Mw.grade == "A")].quad_w).mean())
    print("보정 후 라벨이 바뀐 big 토픽:\n", Mw[Mw.big & (Mw.quadrant != Mw.quad_w)][["topic", "grade", "delta", "delta_w", "quadrant", "quad_w"]].round(4).to_string(index=False))
    Mw.to_csv(S4 / "missingness_sensitivity.csv", index=False, encoding="utf-8-sig")

    # ---------- 8. 메타·기록 ----------
    outs = ["topic_quadrants.csv", "journal_decomposition.csv", "journal_decomposition_sens_1519_2024.csv", "definition_sensitivity.csv", "missingness_sensitivity.csv"]
    meta = dict(spec_sha256=spec["sha256"], at=now(), n_docs=len(F), stability_all=round(s_all, 3), stability_A=round(s_A, 3), passed=bool(s_all >= thr),
                miss_auc=round(float(auc), 3), miss_ess=round(float(ess)), miss_keep_all=round(keep_all, 3), miss_keep_A=round(keep_A, 3), outputs={f: sha_f(S4 / f) for f in outs})
    (S4 / "S4_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    changelog_once("S4 실행", f"- {now()} | S4 실행(규칙 해시 {spec['sha256'][:12]}): 구현 선택(규칙이 정의하지 않음) has_topic 기준 비중, 부재 저널 w=0·s=0, 안정성은 저널 내 성분으로 상위 3분위 규칙 재적용, D1=F6.emerging. "
                   f"안정성 전체 {s_all:.3f}, A등급 {s_A:.3f}(기준 {thr}). 결측 보정: AUC {auc:.3f}, 유효 표본 {ess:,.0f}, 라벨 유지 전체 {keep_all:.3f}, A등급 {keep_A:.3f} | S4 | 4분면·분해·결측 민감도")
    print("\n저장:", outs, "+ S4_meta.json, CHANGELOG 기록")

try: main()
except Halt as e: print(f"⛔ 중단: {e}")