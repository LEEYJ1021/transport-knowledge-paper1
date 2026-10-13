# 영토·구 국가 표기 규칙 (S1)
- 작성: 2026-10-13T11:48:55  (S7 결과 열람 전)

## 규칙
1. 국가는 OpenAlex가 부여한 `country_code`를 그대로 쓴다. 영토(HK, TW, PR 등)는 모국과 합치지 않고 별도 국가로 둔다.
2. 영토 코드에는 `is_territory=True` 열을 붙여 민감도 분석에서 분리할 수 있게 한다.
3. 구 국가 코드(SU, YU, CS, DD, AN)는 `ZZ_former`로 묶고 승계국에 배분하지 않는다.
4. 다중 소속 저자는 소속 국가에 균등 분할한다. 소속이 없는 몫은 `UNK`로 유지한다.
5. 소속 국가는 국적이 아니다.
6. 국가 미상 복구(recovery) 규칙에서도 영토 코드가 잡히면 모국 코드는 제외한다(예: 'Hong Kong, China' -> HK). 복구는 민감도 분석에서만 쓰고 주 분석 테이블은 바꾸지 않는다.
7. 소득군은 OGHIST 산정 달력연도 기준(income_tv)을 주로 쓰고, 회계연도 기준은 wb_income_history_long.csv로 민감도. 결측은 채우지 않는다(ET 2024 원본 빈칸, RE는 OGHIST에 없음).

## 영토 코드 목록
AS, AW, BM, CW, EH, FO, GF, GI, GL, GP, GU, HK, KY, MO, MP, MQ, NC, PF, PR, PS, RE, SX, TW, VI, XK, YT

## 구 국가 코드 목록
AN, CS, DD, SU, YU

## 현재 자료의 규모 (기술 통계, 가설 검정 아님)
- 영토 합계 몫: 0.0332
- 구 국가(ZZ_former) 몫: 0.00000
- 영토별 몫: HK 0.0203, TW 0.0113, MO 0.0013, PR 0.0002, PS 0.0001, PF 0.0000, XK 0.0000, RE 0.0000
