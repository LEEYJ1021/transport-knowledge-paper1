# -*- coding: utf-8 -*-
# s4_1_keywords.py: 4.1 기간별 키워드 Jaccard, 탄생·소멸 단어. 규칙값은 S3_0_PREREG에서 읽음. OpenAlex 호출 없음.
import json, warnings
from pathlib import Path
import numpy as np, pandas as pd, scipy.sparse as sp
from sklearn.feature_extraction.text import CountVectorizer
warnings.filterwarnings("ignore"); pd.set_option("display.width", 200)
ROOT = Path.home() / "Research/Minnesota_Transport"
DATA, S0, S3, S4 = ROOT / "analysis_data/final", ROOT / "paper1/00_S0", ROOT / "paper1/03_S3", ROOT / "paper1/04_S4"
tf = lambda s: s.astype(str).str.strip().str.lower().isin(["1", "1.0", "true", "t", "yes"])
spec = json.loads((S3 / "S3_0_PREREG.json").read_text(encoding="utf-8")); L1, txt = spec["L1"], spec["text"]
periods = [tuple(p) for p in spec["periods"]]; a0 = float(L1["alpha0"]); min_c, min_p = L1["min_word_count_in_topic_period"], L1["min_topic_papers_in_period"]
F = pd.read_csv(DATA / "F1_papers.csv", low_memory=False); F["pid"] = F.pid.astype(str)
EXC = set(pd.read_csv(S0 / "EXCLUDE_PIDS_FROZEN.csv", dtype=str, encoding="utf-8-sig").pid)
F = F[~F.pid.isin(EXC) & tf(F.in_sample) & tf(F.has_topic) & F.topic150.notna() & F.year.between(periods[0][0], periods[-1][1])].copy().reset_index(drop=True)
assert len(F) == 76984, len(F)
F["topic"] = F.topic150.astype(int); F["title"] = F.title.fillna("").astype(str)
cv = CountVectorizer(lowercase=txt["lowercase"], ngram_range=tuple(txt["ngram"]), stop_words="english", min_df=txt["min_df_corpus"])
X = cv.fit_transform(F.title).tocsr(); vocab = np.array(cv.get_feature_names_out())
freq = np.asarray(X.sum(0)).ravel().astype(float); a_w = a0 * freq / freq.sum()
topics = np.sort(F.topic.unique()); ti = F.topic.map({t: i for i, t in enumerate(topics)}).values; yr = F.year.values
G7 = pd.read_csv(S3 / "L7_topic_grade.csv"); grade = {int(t): g for t, g in zip(G7.topic, G7.grade)}

def tops(lo, hi):
    m = (yr >= lo) & (yr <= hi); Xp = X[m]; tp = ti[m]
    Y = sp.csr_matrix((np.ones(len(tp)), (tp, np.arange(len(tp)))), shape=(len(topics), len(tp))) @ Xp
    tot = np.asarray(Xp.sum(0)).ravel().astype(float); cnt = np.bincount(tp, minlength=len(topics)); out = {}
    for k, t in enumerate(topics):
        if cnt[k] < min_p: continue
        Yk = Y[k].toarray().ravel(); Yr = tot - Yk
        d = np.log((Yk + a_w) / (Yk.sum() + a0 - Yk - a_w)) - np.log((Yr + a_w) / (Yr.sum() + a0 - Yr - a_w))
        z = d / np.sqrt(1 / (Yk + a_w) + 1 / (Yr + a_w)); idx = np.where((Yk >= min_c) & (d > 0))[0]
        out[int(t)] = list(vocab[idx[np.argsort(-z[idx])][:50]])
    return out
T = {f"{a}-{b}": tops(a, b) for a, b in periods}; ks = list(T); rows = []
for p0, p1 in zip(ks[:-1], ks[1:]):
    for t in T[p0].keys() & T[p1].keys():
        a10, b10 = T[p0][t][:10], T[p1][t][:10]; sa, sb = set(a10), set(b10)
        if not sa or not sb: continue
        born = [w for w in b10 if w not in set(T[p0][t])]; died = [w for w in a10 if w not in set(T[p1][t])]
        rows.append(dict(topic=t, grade=grade.get(t), pair=f"{p0}->{p1}", jaccard_top10=len(sa & sb) / len(sa | sb),
                         n_born=len(born), n_died=len(died), born=", ".join(born), died=", ".join(died)))
R = pd.DataFrame(rows); R.to_csv(S4 / "keyword_turnover.csv", index=False, encoding="utf-8-sig")
print("[인접 기간 top-10 Jaccard: 쌍별 중앙값 (전체 / A등급)]")
print(pd.DataFrame({"n": R.groupby("pair").size(), "all": R.groupby("pair").jaccard_top10.median().round(3),
                    "A": R[R.grade == "A"].groupby("pair").jaccard_top10.median().round(3)}).to_string())
print("\n탄생 단어 수 중앙값(쌍별):\n", R.groupby("pair").n_born.median().to_string())
print("\n토픽별 평균 Jaccard 최저 10:\n", R.groupby("topic").jaccard_top10.mean().sort_values().head(10).round(3).to_string())
print("※ unigram과 bigram이 섞여 Jaccard가 부풀거나 줄 수 있습니다.")
with (S4 / "CHANGELOG_S4.md").open("a", encoding="utf-8") as f:
    f.write(f"- {pd.Timestamp.now().isoformat(timespec='seconds')} | 4.1 실행(이월 항목): L1과 같은 점수로 기간별 top-50 재산출, 인접 기간 top-10 Jaccard, 탄생=후 기간 top-10 중 전 기간 top-50에 없는 단어 | S4 4.1 | 키워드 변화\n")
print("저장: keyword_turnover.csv")
