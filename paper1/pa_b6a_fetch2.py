import os
# -*- coding: utf-8 -*-
# PA-B6a 수집 재개(429 대응). 동결된 pa_b6a.py·계획은 수정하지 않음. 캐시 CSV에 이어 쓰기만 함.
import json, time, urllib.request, urllib.parse, urllib.error, sys
from pathlib import Path
import pandas as pd
ROOT = Path.home()/"Research/Minnesota_Transport"; PA = ROOT/"paper1/09_PA"; DATA = ROOT/"analysis_data/final"
CACHE = PA/"PA_B6a_orcid_cache.csv"
MAILTO = sys.argv[1] if len(sys.argv) > 1 else ""     # 사용: python3 pa_b6a_fetch2.py you@example.com
if not MAILTO: sys.exit("⛔ 이메일 인자 필요 (OpenAlex polite pool)")
f7 = pd.read_csv(DATA/"F7_oa_author_ids.csv", encoding="utf-8-sig", low_memory=False)
ids = sorted(set(f7.oa_id.dropna().astype(str).str.replace("https://openalex.org/", "", regex=False)))
done = set(pd.read_csv(CACHE).oa_id) if CACHE.exists() else set()
todo = [i for i in ids if i not in done]; print(f"고유 {len(ids):,} | 캐시 {len(done):,} | 남음 {len(todo):,}", flush=True)
wait = 1.0
for k in range(0, len(todo), 50):
    b = todo[k:k+50]
    url = "https://api.openalex.org/authors?" + urllib.parse.urlencode({"filter": "openalex:" + "|".join(b), "select": "id,orcid", "per-page": 50, "mailto": MAILTO})
    res = None
    for att in range(8):
        try:
            req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + os.environ['OPENALEX_KEY']})
            res = json.load(urllib.request.urlopen(req, timeout=60)); wait = max(1.0, wait*0.9); break
        except urllib.error.HTTPError as e:
            if e.code == 429: wait = min(wait*2, 120); print(f"429, {wait:.0f}s 대기", flush=True); time.sleep(wait)
            else: print("HTTP", e.code, flush=True); time.sleep(5)
        except Exception as e: print("오류", str(e)[:60], flush=True); time.sleep(5)
    if res is None: sys.exit("⛔ 연속 실패: 캐시 보존, 잠시 후 재실행하면 이어서 진행")
    got = {r["id"].replace("https://openalex.org/", ""): (r.get("orcid") or "") for r in res.get("results", [])}
    pd.DataFrame([dict(oa_id=i, orcid=got.get(i, ""), found=i in got) for i in b]).to_csv(CACHE, mode="a", header=not CACHE.exists(), index=False, encoding="utf-8-sig")
    if (k//50) % 20 == 0: print(f"  {k+len(b):,}/{len(todo):,}", flush=True)
    time.sleep(wait)
c = pd.read_csv(CACHE); print("완료", len(c), "행 | ORCID 보유", int((c.orcid.fillna('') != '').sum()))