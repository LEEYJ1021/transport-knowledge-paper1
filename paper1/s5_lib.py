# -*- coding: utf-8 -*-
# s5_lib.py: S5 공용 함수. 입력은 4.6 산출물(yearly_venue_topic_counts.npy 등)뿐. OpenAlex 호출 없음.
# 비용: x_t = sqrt(토픽 비중), 가중 w_t = 4*n_t. 구간 비용 = 구간 내 가중 제곱편차. 벌점 = c*phi*(K-1)*log(T) * (구간 수)
import json, hashlib
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path.home() / "Research/Minnesota_Transport"
S0, S3, S4, S5 = ROOT / "paper1/00_S0", ROOT / "paper1/03_S3", ROOT / "paper1/04_S4", ROOT / "paper1/05_S5"
YEARS = np.arange(2000, 2026)
SAMPLES = ["all", "fixed14", "within"]
now = lambda: pd.Timestamp.now().isoformat(timespec="seconds")
sha_b = lambda b: hashlib.sha256(b).hexdigest()
sha_f = lambda p: sha_b(Path(p).read_bytes())
tf = lambda s: s.astype(str).str.strip().str.lower().isin(["1", "1.0", "true", "t", "yes"])

def find_key(o, key):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key: return v
            r = find_key(v, key)
            if r is not None: return r

def load_counts():
    cnt = np.rint(np.load(S4 / "yearly_venue_topic_counts.npy")).astype(np.int64)      # (년, 저널, 토픽)
    venues = pd.read_csv(S4 / "venues_order.csv").venue.astype(str).values
    topics = pd.read_csv(S4 / "topics_order.csv").topic.astype(int).values
    PRE = json.loads((S0 / "PREREG.json").read_text(encoding="utf-8"))
    fixed = set(find_key(PRE, "fixed_venues")); fixed_v = np.array([v in fixed for v in venues])
    assert cnt.shape == (len(YEARS), len(venues), len(topics)), cnt.shape
    assert int(fixed_v.sum()) == 14, int(fixed_v.sum())
    assert int(cnt.sum()) == 76984, int(cnt.sum())
    return cnt, venues, topics, fixed_v

# ---------------- 표본별 연 벡터 ----------------
def sample_P(cnt, fixed_v, wbar, kind, tmask=None):
    c = cnt if tmask is None else cnt[:, :, tmask]
    if kind == "within":
        nj = c.sum(2); ok = nj > 0
        sj = np.divide(c, nj[:, :, None], out=np.zeros(c.shape), where=ok[:, :, None])
        v = (np.where(ok, wbar[None, :], 0.0)[:, :, None] * sj).sum(1); tot = v.sum(1, keepdims=True)
        return np.divide(v, tot, out=np.zeros_like(v), where=tot > 0), c.sum((1, 2))
    cy = c.sum(1) if kind == "all" else c[:, fixed_v, :].sum(1)
    n = cy.sum(1)
    return np.divide(cy, n[:, None], out=np.zeros(cy.shape), where=n[:, None] > 0), n

def detrend_P(P, n):
    w = n.astype(float); x = YEARS - np.average(YEARS, weights=w)
    pbar = (w[:, None] * P).sum(0) / w.sum()
    sl = ((w * x)[:, None] * (P - pbar)).sum(0) / (w * x * x).sum()
    Q = np.clip(P - np.outer(x, sl), 0, None); s = Q.sum(1, keepdims=True)
    return np.divide(Q, s, out=np.zeros_like(Q), where=s > 0)

# ---------------- 제약 군집화(동적계획) ----------------
def seg_costs(X, w):
    T = len(w); S0_ = np.concatenate([[0], np.cumsum(w)])
    S1 = np.vstack([np.zeros(X.shape[1]), np.cumsum(w[:, None] * X, 0)])
    S2 = np.concatenate([[0], np.cumsum(w * (X ** 2).sum(1))])
    C = np.full((T + 1, T + 1), np.inf)
    for a in range(T):
        b = np.arange(a + 1, T + 1); s0 = S0_[b] - S0_[a]; s1 = S1[b] - S1[a]; s2 = S2[b] - S2[a]
        with np.errstate(divide="ignore", invalid="ignore"): c = s2 - (s1 ** 2).sum(1) / s0
        C[a, b] = np.maximum(np.where(s0 > 0, c, 0.0), 0.0)
    return C

def segment(X, w, kmax=6, minlen=3):
    T = len(w); C = seg_costs(X, w)
    best = np.full((kmax + 1, T + 1), np.inf); arg = np.zeros((kmax + 1, T + 1), int)
    for b in range(minlen, T + 1): best[1, b] = C[0, b]
    for k in range(2, kmax + 1):
        for b in range(k * minlen, T + 1):
            a = np.arange((k - 1) * minlen, b - minlen + 1); v = best[k - 1, a] + C[a, b]
            i = int(np.argmin(v)); best[k, b] = v[i]; arg[k, b] = a[i]
    res = {}
    for k in range(1, kmax + 1):
        if not np.isfinite(best[k, T]): continue
        br, b = [], T
        for kk in range(k, 1, -1): a = arg[kk, b]; br.append(int(a)); b = a
        res[k] = (float(best[k, T]), sorted(br))
    return res

def seg_means(X, w, br):
    e = [0] + list(br) + [len(w)]
    return [np.average(X[a:b], axis=0, weights=w[a:b]) if w[a:b].sum() > 0 else X[a:b].mean(0) for a, b in zip(e[:-1], e[1:])]

def jump(X, w, br):
    if not br: return 0.0
    m = seg_means(X, w, br); return float(max(np.linalg.norm(m[i] - m[i + 1]) / np.sqrt(2) for i in range(len(m) - 1)))

def cost_given(X, w, br):
    e = [0] + list(br) + [len(w)]; tot = 0.0
    for a, b in zip(e[:-1], e[1:]):
        if w[a:b].sum() == 0: continue
        m = np.average(X[a:b], axis=0, weights=w[a:b]); tot += float((w[a:b] * ((X[a:b] - m) ** 2).sum(1)).sum())
    return tot

def detect(P, n, pen, kmax=6, minlen=3, keep=None):
    X, w = np.sqrt(P), 4.0 * n
    if keep is not None: X, w = X[keep], w[keep]
    res = segment(X, w, kmax, minlen); k = min(res, key=lambda kk: res[kk][0] + pen * kk)
    c1, ck = res[1][0], res[k][0]; br = res[k][1]
    return dict(k=k, br=br, cost1=c1, costk=ck, R=(1 - ck / c1) if c1 > 0 else 0.0, jump=jump(X, w, br),
                curve={kk: res[kk][0] for kk in res}, X=X, w=w)

def uni_bic(v, kmax=6, minlen=3):
    v = np.asarray(v, float); T = len(v); X = ((v - v.mean()) / v.std())[:, None]
    res = segment(X, np.ones(T), kmax, minlen)
    bic = {k: T * np.log(max(res[k][0], 1e-9) / T) + 2 * k * np.log(T) for k in res}
    return res[min(bic, key=bic.get)][1]

def near(y, ys, tol=1): return any(abs(int(y) - int(z)) <= tol for z in ys)

# ---------------- 귀무/부트스트랩 생성기 (모두 (년, 저널, 토픽) 개수 배열을 돌려줌) ----------------
def gen_boot(cnt, rng):
    out = np.zeros(cnt.shape, dtype=np.int64); n = cnt.sum(2)
    for y, v in zip(*np.nonzero(n)): out[y, v] = rng.multinomial(int(n[y, v]), cnt[y, v] / n[y, v])
    return out

def gen_N0(cnt, rng):   # 구조 전무: 모든 논문을 풀에 넣고 셀 크기만 유지해 무작위 배분
    pool = cnt.sum((0, 1)).astype(np.int64); n = cnt.sum(2); out = np.zeros(cnt.shape, dtype=np.int64)
    cells = list(zip(*np.nonzero(n)))
    for i in rng.permutation(len(cells)):
        y, v = cells[i]; d = rng.multivariate_hypergeometric(pool, int(n[y, v])); out[y, v] = d; pool = pool - d
    return out

def gen_N1(cnt, rng):   # 저널 안에서 연도 라벨만 섞기: 저널 구성(규모)은 유지, 저널 내 시간 구조는 제거
    T, V, K = cnt.shape; out = np.zeros(cnt.shape, dtype=np.int64)
    for v in range(V):
        pool = cnt[:, v, :].sum(0).astype(np.int64)
        for y in rng.permutation(T):
            m = int(cnt[y, v].sum())
            if m == 0: continue
            d = rng.multivariate_hypergeometric(pool, m); out[y, v] = d; pool = pool - d
    return out

def trend_probs(cnt):   # 저널x토픽별 연도 선형 추세(가중 OLS) 적합 확률. 0 미만 절단 후 재정규화
    T, V, K = cnt.shape; n = cnt.sum(2).astype(float); P2 = np.zeros((T, V, K)); x = YEARS - YEARS.mean()
    for v in range(V):
        ok = n[:, v] > 0
        if ok.sum() == 0: continue
        s = cnt[ok, v] / n[ok, v][:, None]
        if ok.sum() < 3: P2[ok, v] = s; continue
        X = np.c_[np.ones(ok.sum()), x[ok]]; W = n[ok, v]
        beta = np.linalg.solve(X.T @ (W[:, None] * X) + 1e-9 * np.eye(2), X.T @ (W[:, None] * s))
        f = np.clip(X @ beta, 0, None); fs = f.sum(1, keepdims=True)
        P2[ok, v] = np.where(fs > 0, f / np.where(fs > 0, fs, 1), s)
    return P2

def gen_N2(cnt, P2, rng):
    out = np.zeros(cnt.shape, dtype=np.int64); n = cnt.sum(2)
    for y, v in zip(*np.nonzero(n)):
        p = P2[y, v]; out[y, v] = rng.multinomial(int(n[y, v]), p / p.sum())
    return out

# ---------------- 저널 내/간 정확 분해 (인접 두 구간) ----------------
def decomp_break(cnt, a0, a1, b1):
    def mats(lo, hi):
        c = cnt[lo:hi].sum(0).astype(float); nj = c.sum(1); w = nj / nj.sum()
        return w, np.divide(c, nj[:, None], out=np.zeros(c.shape), where=nj[:, None] > 0)
    w0, s0 = mats(a0, a1); w1, s1 = mats(a1, b1)
    within = (((w0 + w1) / 2)[:, None] * (s1 - s0)).sum(0); between = (((s0 + s1) / 2) * (w1 - w0)[:, None]).sum(0)
    tot = w1 @ s1 - w0 @ s0
    assert abs(within + between - tot).max() < 1e-9, "불변식 실패: 내+간 != 총변화"
    return within, between, tot
