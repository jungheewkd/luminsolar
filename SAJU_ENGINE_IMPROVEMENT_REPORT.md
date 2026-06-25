# 사주 엔진 종합 기술보고서 (개정판) — 아키텍처 진단·외부 벤치마크·명리 정합성·개선 로드맵

**문서 종류**: 적대적 기술심사 보고서 (Architecture Review, 개정 2판)
**작성일**: 2026-06-25
**작성자**: 수석 아키텍트
**대상 독자**: 엔진 개발팀 · 명리 자문 · 릴리스 관리자
**대상 릴리스**: `saju-runtime-8.1.0` (프롬프트 런타임 v8.1.0) / 엔진 빌드 `0.2.12` / 핸드오프 `saju.handoff.v3.8`
**호환 스키마 핀**: `tier1.v1.6` · `jieqi.v1.0` · `handoff.v3.8` (핸드셰이크 게이트) / 절기 커버리지 1951~2035
**범위**: (1) 현행 결정론 엔진(`bundle/saju_engine/**`)·KERNEL 거버넌스·ASK 파이프라인·검증체계의 코드 정밀진단, (2) 공개 사주/Bazi 엔진 및 타 도메인 의사결정엔진과의 비교(외부층 — 미검증 2차 주장으로 명시), (3) 명리학적 해석 프레임워크 정합성, (4) 개선 권고·로드맵·리스크. **본 개정은 1차 초안에 대한 적대적 심사(`needs_revision`)의 inaccuracies·gaps·must_add를 recovered 코드 재대조로 반영한 것이다.**

**검증 토대 표기 규약(본 보고서 전반 적용)**:
- `[V]` **검증됨(verified)** — recovered 코드/문서를 직접 열람해 행 단위로 확인. 내부 진단·권고는 원칙적으로 이 등급.
- `[S]` **2차 전문(secondhand)** — 외부 프로젝트·통계·논문에 대한 미검증 주장. 출처·접근일·버전 표기를 동반하되, **검증 불가**임을 명시한다. 외부 리서치층(§3 전체, §5의 외부 후크 인용)은 전부 이 등급이며, 본 보고서의 내부 권고(R-1·R-2·R-4·R-6 등)는 이 등급에 **의존하지 않는다**(§1.4 참조).

---

## 목차

- 1. Executive Summary
  - 1.1 핵심 진단
  - 1.2 핵심 미달 영역
  - 1.3 상위 권고 (우선순위)
  - 1.4 외부 리서치층의 인식론적 지위 — 핵심 논지의 인질화 방지
- 2. 현행 엔진 아키텍처 분석 (검증됨)
  - 2.1 사실/판정 경계의 코드 강제
  - 2.2 KERNEL 거버넌스
  - 2.3 ASK 파이프라인과 신(新)번호 직렬화
  - 2.4 검증체계
  - 2.5 강점 (공학적)
  - 2.6 한계 (공학적 + 명리학적)
- 3. 공개 사주 엔진 비교 분석 (외부 2차 주장 — 미검증)
- 4. 사주명리학적 해석 프레임워크 정합성
- 5. 타 도메인 엔진에서의 시사점과 현행 적용지점
- 6. 개선 권고안
- 7. 단계별 로드맵
- 8. 리스크·한계·미해결 논쟁·반증가능성
- 종합 결론

---

## 1. Executive Summary

### 1.1 핵심 진단

현행 엔진은 **"엔진=사실, LLM=판정"** 분업을 *프롬프트·스키마·엔진코드·테스트* 4개 층에서 동시에 강제하는, 내부 코드 기준으로 매우 성숙한 결정론 아키텍처다 `[V]`. tier1(결정론 사실) 영역의 사실관계 정확도·검증 인프라는 본 심사에서 행 단위로 재대조한 모든 항목이 코드와 일치했다.

이 철학이 "업계 best practice와 독립적으로 수렴한다"는 1차 초안의 논지는 **매력적이나 검증 불가능한 가설**이다 `[S]`. 그 근거(AI 점술 환각률 99.5%, `cantian-ai/bazi-mcp`·`FOR-BAZI`·`yhj1024/manseryeok`의 2층 분리, Swiss Ephemeris "Centaur" 등)는 recovered 코드로 확인할 수 없는 2차 주장이며, 본 보고서는 이를 **§1.4와 §3에서 미검증 가설로 강등하여** 다룬다. 따라서 본 Executive Summary의 검증 주장은 외부층이 아니라 내부 코드에만 기댄다.

내부 코드로 확인된 잘 구현된 항목 `[V]`:

- **결정론 사실 계산**: 4주(`day_pillar.py` 1900-01-31 甲辰 epoch / `constants.py` DAY_PILLAR_EPOCH_INDEX=40, `year_pillar.py` 입춘≥경계 → 1924 甲子 mod 60, `month_hour_pillar.py` 오호둔/오서둔), 진태양시 단방향 사슬(`timecontext.py`), 강약 정량화(`strength.py`), 합충(`relations.py`), 대운수(`daewoon_age.py`), 매화괘(`maehwa.py`), 일진/운(`daily.py`/`flow.py`)이 정수 인덱스 산술 + 동결 룩업 + `Decimal ROUND_HALF_UP`(`Q_STRENGTH=0.1`)로 byte-freeze 가능.
- **환각 봉쇄 규약**: KERNEL R1′(앵커=`tier1_facts` JSON 단일, L77), R2′(검산=전사, L78), R2″(금지연산 9종 명시 열거, L87), R6′ⓕ(OBSERVE_ONLY 외부 수치 역환산 금지, L94), 〔I8〕(운층 합충 *탐지*만 `flow_signals` JSON, L86).
- **검증 다중화**: `handoff_verify.verify_against_engine`의 no-new-values 대조, golden byte-freeze(`_golden` 20 + `_golden_handoff` 3 + `_golden_tier2` 4 = 골든 수 20+3+4), 640명식 invariants, characterization 박제, `gen_manifest`/`gen_handoff_static --check` 드리프트 게이트.
- **경계 처리**: `strength.py`의 A7 `boundary_hold` + `boundary_evidence`(I7, read-only echo) + ASK4 §4-1-B 이원용신 + ASK6 `activation_key`로 운-민감성 보존.

1차 초안의 최상급 표현(**"조사된 어떤 공개 엔진보다 정교"·"압도적"·"독보적"·"가장 엄격"·"best practice 독립 수렴"**)은 전수조사 불가능 명제이거나 직접 코드 비교 증거가 없는 과장이므로, 본 개정에서 **근거 강도에 맞는 서술로 완화**했다(§3.3·종합 결론). 강점 서술 분량은 줄이고 미달 영역·반증가능성 논의(§8)를 늘렸다.

### 1.2 핵심 미달 영역

문제는 **tier1(엔진 사실)이 아니라 tier2(LLM 판정: 강약 verdict 서사·격국·용신·청탁/진가)** 쪽에 집중된다. 환각 차단 강도가 파이프라인 후반(ASK4→5→대운)으로 갈수록 단조 감소한다 `[V]`.

1. **강약 verdict의 불확실성이 이산 플래그에 머문다.** `verdict_at`의 경성 임계(65/55/45/35)와 `boundary_hold` boolean에 의존하며(`strength.py:46-48,176`), "왜 이 verdict인가"를 항목별 기여도로 분해한 사유코드가 없다. 단 `boundary_evidence`(I7/D-067)가 `dist_to_strong`(pct−65)·`dist_to_weak`(pct−35)·`resource_ratio`·`ratio_to_d_gate` 등 **회귀/사유코드 입력 피처를 이미 read-only로 방출**한다(`strength.py:183-195`) — R-1·R-2 인프라의 절반은 완성돼 있다.
2. **임계·계수의 캘리브레이션 근거가 부재하다.** `DEUKRYEONG{50/35/15/5/0}`·`base{100/65/35/22.75}`·`GROUP_BONUS{±0.2/−0.3}`·`KHC{−0.30~−0.05}`·`SE_W{year60/month100/hour80}`·가중 `0.40/0.35/0.25`·임계 65/55/45/35가 전부 하드코딩이며, `constants.py:64`가 스스로 "**Step 14 캘리브레이션 대상**"이라 자인한다. 다행히 `STRENGTH_WEIGHTS`·`STRENGTH_THRESHOLDS`·`DEUK_RYEONG_RAW`가 `constants.py:65-67`에 이미 명명 분리되어 외부화 후크가 마련돼 있다.
3. **격국·종격·청탁/진가가 LLM 전적 위임.** `apply_a6`의 `neither∧strong` 분기는 도달 불가(`strength.py:57-64`, D-074, 실측 max pct 43.9, `test_neither_never_reaches_strong`)로 죽어 있고 `jonggyeok_review`는 emit 미직렬화. §⑦-5 청탁/진가는 '빈 슬롯'.
4. **tier2 판정에 검증 루프가 없고, Layer-2 골든이 사실상 비어 있다 — 단, "전부 None"은 부정확하다(C-002 정정).** `tier2_boundary_corpus.py`의 본 회귀대상 4건(`TIER2_BOUNDARY_CASES`: qi_only/with_longitude/samhap_pure/samhap_full)은 `captured_tier2=None`이다. 그러나 동일 파일의 `SYNTHETIC`·`SYNTHETIC_BOUNDARY` **2건은 `captured_tier2`가 채워져 있다**(`tier2_boundary_corpus.py:77-114`). 정확한 진술은 **"실제 LLM 봉인 산물 캡처가 0건이고, 채워진 2건은 명리 판정이 아니라 `provenance='SYNTHETIC — 하니스 검증 전용(명리 판정 아님)'`의 하니스 self-test 더미"**다. 이 2건이 `assembled()`→`assemble_handoff.assemble`→`handoff_verify` 경로(Layer-2 파이프라인)가 **이미 기계적으로 동작함**을 입증하므로, R-7은 "인프라 구축"이 아니라 "**기존에 동작하는 Layer-2 위에 실제 캡처 1건만 채우면 활성화되는 저비용 배선 작업**"이다.
5. **BLIND SPOT 필드의 값 검증 부재 — 단, branch_climate는 "없는 계산"이 아니라 "배선 갭"이다(C-003 정정).** `flow.current_*`·산문(`usage_hint`/`tldr`)은 엔진 raw에 없어 `handoff_verify`의 no-new-values 대조 밖이다. **그러나 `branch_climate`는 다르다**: `assets/lookup/climate.py`에 子→{寒/濕}, 午→{熱/燥} 등 **12지지 한난조습 결정론 lookup이 이미 존재**하며(`CLIMATE` 딕셔너리, 전 12지지 완비), `ask_modules.md`의 ASK2 STAGE CONTRACT는 ASK2(LLM)가 이 값을 `tier1_facts.chart.branch_climate` 컨테이너에 **"기록"하도록 설계**한다(`output`/`judgment_scope`에 명시: "branch_climate는 schema상 tier1_facts.chart 컨테이너지만 ASK 2가 결정"). 즉 R-8은 **없는 계산의 추가가 아니라, 이미 있는 lookup을 엔진 emit으로 배선해 no-new-values 대조 대상으로 끌어오는 순수 검증-배선 갭**이다.
6. **균시차 미적용 — SoT는 `timecontext.py`다(C-001 정정).** `timecontext.py:9-12`가 LMT(경도보정+DST)만 쓰고 균시차(연중 ±~15.5분)를 의도적 OFF한다. 시지 경계 ±60분 근접 출생에서 시주 1칸 오류 가능. **이 사안의 SoT는 `timecontext.py`이며 `solar_time.py`가 아니다**(`solar_time.py`는 1954 플래그용 `nearest_jieqi_for_flag` 헬퍼일 뿐 진태양시 산출 모듈이 아님 — D-027 통합기록 참조). 더 나아가 `timecontext.py:11-12`는 **`apparent_solar_dt`(기본 OFF) 필드를 이미 설계로 예약**한다.

### 1.3 상위 권고 (우선순위)

| # | 권고 | 적용지점 `[V]` | 외부 후크 `[S]` | 난이도 | 리스크(환경 제약 포함) |
|---|------|---------|----------|--------|----------|
| **P1** | verdict 기여도 분해 + 사유코드(`verdict_reason_codes[]`를 tier1 emit, LLM은 echo만) | `strength.py` `compute_strength_core` 말미 + R2′ echo 대상(L78) 확장 | MYCIN CF / 신용 Reason-Code·SHAP / GRADE | 중 | 낮음 — read-only echo, **코드 실행 불요(순수 엔진 emit)** |
| **P2** | tier2 용신 PoT화(자유서술→후보집합+엔진사실 인용+점수 구조화 JSON `tier2.v1`) | ASK4 §4-1 + `assemble_handoff` tool input schema | Program-of-Thoughts / 다후보 점수화 / constrained decoding | 중~상 | **중~높음 — constrained decoding은 코드 환경 전용. 주 배포(GPT Knowledge UI)에서는 강제 불가, 프롬프트 규약+`handoff_verify` 사후검증으로 대체** |
| **P3** | 균시차 옵트인(`apparent_solar_dt` 구현) + 절입 불확실성 노출 | `timecontext.py`(이미 예약된 필드 구현) + `solar_terms_ext.py` ±N분 플래그 | yhj1024 equation-of-time / sxtwl 定气 | 중 | 낮음 — 기본 OFF 유지 |
| **P4** | tier2 검증층(CoVe 엔진 역질의 + 3대 고전 LLM-as-jury + Layer-2 골든) | ASK4/5 후처리 + `_golden_tier2_verdict/` 신설 | CoVe / LLM-as-jury(CARE) / self-consistency | 상 | **높음 — self-consistency·jury는 코드 환경에서만 가용. GPT Knowledge UI 단독 배포 시 동작 불가, 코드 환경 가용성이 선행조건** |
| **P5** | 커버리지 확장(1951↓·2035↑) astropy/Swiss Ephemeris 定气로 절입 결정론 산출 후 byte-freeze | `solar_terms_ext.py` 파이프라인 + `day_pillar` 검증창 정렬 | sxtwl/lunar-python VSOP87 / Swiss Ephemeris DE431 | 상 | 중 — 절입 정밀도 검증 부담 |

### 1.4 외부 리서치층의 인식론적 지위 — 핵심 논지의 인질화 방지

1차 초안의 가장 큰 구조적 약점은, 보고서 전체 논지의 기둥(99.5% 환각률, `cantian-ai/bazi-mcp`·`FOR-BAZI`·`yhj1024`·`orrery`·`sxtwl`·Swiss Ephemeris "Centaur"·CARE/CoVe 등)이 **recovered 코드로 검증 불가능한 2차 주장인데도 출처·검증가능성 표기 없이 단정적으로 제시**되었다는 점이다. 외부층이 틀리면 "독립 수렴"이라는 핵심 검증 주장이 붕괴한다.

본 개정의 방어선:

1. **모든 외부 주장에 출처·접근일·신뢰도 등급을 부착**한다(§3 비교표·각주). 직접 코드 비교를 수행하지 않았으므로 전부 `[S]` secondhand이며, "독립 수렴"은 **검증된 사실이 아니라 미검증 가설**로 강등한다.
2. **내부 권고는 외부층에 의존하지 않는다.** R-1(verdict 사유코드)·R-2(캘리브레이션)·R-4(용신 PoT화)·R-6(tier2 검증층)의 정당성은 전적으로 내부 코드 사실(`constants.py:64` 자인, `apply_a6` dead-branch, `captured_tier2` 공백, `boundary_evidence` 기방출)에서 도출된다. **외부 프로젝트가 단 하나도 존재하지 않더라도 이 네 권고는 그대로 유효하다.** 외부 후크는 "구현 참고 패턴"일 뿐 "권고 근거"가 아니다.

| 외부 주장 | 본 보고서 신뢰도 | 검증가능성 비고 |
|-----------|------------------|------------------|
| AI 점술 LLM 직접 위임 시 환각률 ~99.5% | `[S]` | 단일 통계·출처 미상. **본 보고서 권고는 이 수치에 의존하지 않음** |
| `cantian-ai/bazi-mcp`·`FOR-BAZI`·`yhj1024`의 2층 분리 "독립 수렴" | `[S] 가설` | 외부 저장소 직접 코드 비교 미수행. 수렴은 단정이 아닌 가설 |
| `sxtwl`/`lunar-python` VSOP87·1913~3000 커버리지 | `[S]` | P5 구현 참고용. 실제 채택 전 라이선스·정밀도 직접 검증 필요 |
| Swiss Ephemeris DE431·"Centaur" 분리 철학 | `[S]` | 철학적 유비. 채택 시 별도 검증 |
| MYCIN CF · CoVe · LLM-as-jury(CARE) · PoT 패턴 | `[S]` | 학술 패턴. 적용은 내부 후크(§5)에 한해 유효, 효과는 미검증 |

---

## 2. 현행 엔진 아키텍처 분석 (검증됨 `[V]`)

### 2.1 사실/판정 경계가 코드 구조로 못박혀 있다

이 시스템의 본질적 설계는 사실/판정 경계가 **선언이 아니라 함수 시그니처·주석·emit 정책으로 강제**된다는 점이다.

**(a) 단방향 시각 파생 사슬이 인자명으로 못박혀 있다.** `timecontext.build_time_context`가 `clock_dt → boundary_dt(DST −1h) → solar_dt(경도보정)`를 단방향 파생하고(`timecontext.py:3-7`), 각 명리 요소가 받을 시각이 인자에 고정된다:

- 일주: `clock` 날짜만 (`day_pillar.py`에 `solar_dt` 인자 자체가 없음)
- 년·월주: `boundary` (`year_pillar.py` effective year = boundary ≥ 당해 입춘)
- 시주: `solar_dt` (`month_hour_pillar.py` 조립자가 세 시각 분배)

**핵심 정정 — 진태양시 SoT는 `timecontext.py`다.** `solar_dt = 지방평균태양시(LMT)`이며 균시차 미적용임이 `timecontext.py:9-12` docstring에 명시되고, 동일 docstring이 균시차 옵트인을 `apparent_solar_dt`(기본 OFF) 별도 필드로 **이미 예약**한다. `solar_time.py`는 1954 플래그용 `nearest_jieqi_for_flag` 헬퍼이며 진태양시 산출과 무관하다(D-027 통합기록: 과거 시지 2종 중복 보유 사고의 잔재이며 시지 정본은 `hour_branch.py`). 따라서 균시차 OFF·LMT 근거를 인용할 때는 **항상 `timecontext.py:9-12`로 귀속**해야 하며, `solar_time.py`로 매다는 것은 오귀속이다.

**(b) 강약 정량화 사슬** (`strength.compute_strength_core`, `strength.py:99-208`):

```
pct = quantize( 0.40 × (ryeong × 2)  +  0.35 × ji  +  0.25 × (se + 100)/2,  0.1, ROUND_HALF_UP )
verdict_at(pct): ≥65 strong / ≥55 quasi_strong / ≥45 balanced / ≥35 quasi_weak / <35 weak
```

- **득령**(`_ryeong_state` → `DEUKRYEONG{旺50/相35/休15/囚5/死0}`, 정규화 ×2; 旺=50→100 만점, 死=0→0). **중요(부호 규약, C-006 정정 — §6 R-1 참조)**: 死는 *감점이 아니라 0점*이며 ×2 후에도 0이다. "死=−50 기여"는 절대기여가 아니라 旺(만점) 대비 **기회손실(opportunity loss)**이다. 산식상 득령은 [0, 100] 범위의 비음수 가산항이다.
- **득지**(`strength.py:121-136`): 뿌리별 `base × (1+k12) × (1+kc)`. base = 비겁본기 100 / 인성본기 65 / 비겁여중 35 / 인성여중 22.75(=35×0.65, D-034). k12 = 12운성 `GROUP_BONUS{生旺祿+0.2/中立0/衰絶期−0.3}` (일지 full·타지 ×0.5). kc = `KHC` 육합/육충 지지별 max-single. 년지 뿌리 40캡(C-005: 타지=년지 해석), 전체 100캡.
- **득세**(`strength.py:138-145`): 일간 외 천간 비겁·인성(+)/식재관(−) × `SE_W{year60/month100/hour80}` ±100캡. **일지는 득세에 미산입**(천간만 셈) — 일지 통근은 득지로 흡수(8.2 #3 논쟁).

**(c) A6 기형 중재 + A7 경계 보류** (`strength.py:51-65,158-178`):

```
apply_a6:
  qi_only ∧ strong              → quasi_strong (강등)
  xing_only ∧ (weak|quasi_weak) → balanced     (상향, D-035 보수측 中和)
  neither ∧ (strong|quasi_strong) → balanced + jonggyeok_review=True   # ⚠️ 도달 불가(D-074)
```

A7 `boundary_hold` 트리거 5종: (a) 수치밴드 `30≤pct≤40 또는 60≤pct≤70`, (b) `qi_only/xing_only`, (c) 일지 충, (d) 인성과다 게이트(`bi_p==0 ∧ in_p≥65` 또는 `in_p/bi_p≥2.5`; `d_fuzzy`는 ≥40/≥1.5로 LLM 위임), (e) 조습 무력화(`e_metal` 조토불생금 / `e_fire` 회화). hold면 `cands = SCALE 인접 ±1칸`.

**(d) boundary_evidence(I7/D-067) read-only echo** (`strength.py:180-195`). `raw_pct`·`raw_verdict`·`a6_shift_levels`·`dist_to_strong`(pct−65)·`dist_to_weak`(pct−35)·`nearer_boundary`·`resource_ratio`(인성/비겁)·`ratio_to_d_gate`(/2.5)·`ratio_to_dfuzzy_gate`(/1.5)를 **신규 산술 0**으로 산출. "회귀/사유코드 입력 피처가 이미 방출돼 있다"는 결정적 사실이며 R-1·R-2의 직접 근거다.

**(e) 합충·일진·운의 부호(吉凶) 일관 위임 — relations 결정론 범위는 '삼합 등급만'이 아니다(C-005 정정).** `relations.detect_relations`(`relations.py:61-184`)가 결정론으로 소유하는 것은 1차 초안이 적은 삼합 등급에 국한되지 않는다. 실제 코드 소유 범위:

- **삼합 등급**: 3자 투출 1.0(극강)/미투출 0.8(강), 반합(왕지 포함) 투출 0.5(중)/미투출 0.3(약). 코드 주석·basis는 `100/80/50/30`(계수 표기 `1.0/0.8/0.5/0.3`)의 **이원 표기**다(`relations.py:1,12,121-128`).
- **방국**: 3자 0.8(투출 불필요, `relations.py:130-134`).
- **암합(지장간 천간합)**: 계수 `(0.3, 0.5)` (`relations.py:89-91`).
- **쟁합 화기 억제(D-031)**: 같은 type 합 hit이 위치 공유 시 `status=contended` + 화기 억제 — 육합·천간합 공통(`relations.py:100-109,174-178`).
- **천간합 화기 3요건(§④-4)**: 월령 비극제(c1)·투출(c2)·통근(c3 보조) (`relations.py:157-173`).
- **형/파/해/원진**: 탐지·status까지(형 삼형/반형/상형/자형 `relations.py:136-155`).

세력 비교·파합·해소(§④-6)·형파해 잔여 색채 적용만 LLM(tier2)·Step10에 위임된다(D-030). `daily.py`/`flow.py`는 `target_element`만 방출하고 부호는 미산출하며, `flow.py` 헤더가 旺衰·STAGE1 해소·부호 비방출을 "의도적 SoT 이원화 방지"로 못박는다.

### 2.2 KERNEL 거버넌스 (`[1′]`~`[9]`)

확인된 `core_kernel.md` §2 (행번호 재확인):

- **R1′** (L77): 허용 앵커 = `tier1_facts` JSON 단일. 앵커 없는 기억·추측 간지 생성 절대 금지.
- **R2′** (L78): 검산 = 전사. `derivation.*`·`strength.deuk_*_raw`·`daewoon.reference_jieqi(_dt)`·`maehwa` 산출 필드만 옮겨적기. **재계산은 위반.** "JSON에 없는 중간 산술값이 응답에 새로 등장하면 위반."
- **R2″** (L87): 금지연산 9종 — JDN/60갑자 산술 · 절기 대조 · 월두/시두 · 진태양시/DST 가감 · 음력 변환 · 합충 스캔/성립 판정 · 십성/12운성 재lookup(원국) · Strength 산식 · 대운 수 계산 · 기괘 산술.
- **R6′ⓕ** (L94): OBSERVE_ONLY — 외부 수치를 엔진 SCALE으로 역환산 금지.
- **〔I8〕** (L86): 대운·세운 간지 × 원국 합충 *탐지*는 `flow_signals`로 JSON 산출, 그 외 탐지·우세·해소·부호·旺衰는 LLM.

이것은 환각 차단의 핵심 — **'검산'을 전통적 self-check(재계산 후 대조)에서 'tier1_facts echo 전사'로 재정의**해, LLM이 검증을 빌미로 재산출하는 경로 자체를 닫았다(MODULE CONTRACT 3·6). 전체 파일이 적재되는 GPT Knowledge 환경에서도 최소-컨텍스트 API와 동일 거동을 강제하는 READ-ONLY-DECLARED-INPUTS 봉인은 독창적 거버넌스다.

### 2.3 ASK 파이프라인과 신(新)번호 직렬화 (gap #2 교차검증 반영)

**1차 초안의 ASK 번호 매핑을 `core_kernel.md` 실행흐름(L11-13)과 교차검증했다.** 코드의 권위 서술은 다음과 같다:

> Step 0 초기화 → 입력 대기 → **ASK 1: tier1_facts 산출** → **ASK 2~6 추론**(세션 tier1_facts 토대) → **신(新)7 직렬화**(tier1 필드 = 세션 tier1_facts 전사, tier2 = ASK 2~6 결과) → **신8 종합 보고서** → ASK 9~13.

즉 SILENT_BUILD는 1차 초안 서술대로 "ASK1~6 무출력 다단계"이되, **직렬화/종합은 '신(新)번호 체계'(신7·신8)로 재배열**된다. 본 개정은 이 신번호를 명시한다: **신7 = handoff 직렬화(D-077로 LLM 수동 직렬화 SPOF 제거, 결정론 파이프라인+게이트화), 신8 = 종합 보고서, ASK9~13 = 통변(상대 원국·일진 등)**. 1차 초안의 "ASK7 handoff·ASK8 종합·ASK10~12 통변" 매핑은 이 신번호 재배열과 정합하나, 본문 전반에서 직렬화 단계를 가리킬 때는 **"신7(handoff 직렬화)"**로 표기해 구(舊)순번과의 혼동을 차단한다.

- 명리 추론 흐름: 강약(ASK2) → 격국(ASK4 §1) → 용신(ASK4 §4-1) → 청탁/진가(ASK5 §5) → 대운/세운 통변(ASK10~12) → handoff(신7).
- ASK4 §4-1 용신 계층: **특수격(전왕/종/화) → 극단조후(생존) → 정격(격국) → 억부(통관/병약)**, 억부 진입 시 상전이면 §4-1-A-ter 통관 우선(적천수 流通). 中和 명식은 계층1·2 먼저 검사 후 §4-1-B 이원용신.

### 2.4 검증체계

| 레이어 | 도구 | 무엇을 잠그나 |
|--------|------|--------------|
| no-new-values | `handoff_verify.verify_against_engine` | 봉인 handoff를 `project_tier1_verifiable(raw)`와 값 대조(pillars·five_elements·ten_gods·지장간·gong_mang·relations·strength canonical) |
| canonical 폐쇄 | `validate_static_blocks`/`validate_legend_codes` | LEGEND·SPEC·CONSUMER_SCOPE를 `handoff_static`과 == 비교 |
| boundary 정합 | `validate_boundary_consistency`(COUP-1/H4) | `operative_branch` ∈ {strong/weak_branch} 멤버십 + clarity.by_branch cross-key |
| 소유권/순서 | `gen_manifest.validate` | output 단일소유·의존순서·judgment_scope |
| byte-freeze | `test_golden`(20+3+4)·`test_invariants`(640명식)·`test_characterization` | 엔진 산출 동결, I7 echo 항등식, A6 승격·dead-branch 박제 |
| 문서 드리프트 | `test_doc_version_coherence` | STALE_TIER1(v1.3~v1.5) 잔존 금지 |

**`rehome_strength`**(`assemble_handoff.py:104-132`)가 R2′ 권위의 핵심 구현 — `tier1.strength`를 tier2_interpretation으로 재배치하면서 boundary를 엔진 권위로 덮고 `source='derived'`로 LLM source를 무력화(`assemble_handoff.py:131`). **단 boundary_hold=true 명식의 Layer-2 골든은 이 canonical 재배치(strength top-key 충돌 해소)가 선결조건**이며(`tier2_boundary_corpus.py:15-19`), `SYNTHETIC_BOUNDARY`가 그 경로를 self-test로 이미 통과시킨다.

### 2.5 강점 (공학적 — 분량 축소)

1. **다층 방어**: 동일 불변식(재계산 금지)이 프롬프트(R2″)·스키마(handoff 검증)·엔진코드(flow.py 부호 비산출, strength.py echo)·테스트(골든 byte-freeze) 4층 중복 강제.
2. **fail-loud 통일**: 커버리지 밖 `LookupError`, 해외 경도 `ValueError`(D-025), 어디서도 간지 추정 안 함.
3. **round-trip 정합**: `build_handoff_tier1`(생성기)과 `project_tier1_verifiable`(검증기)이 동일 헬퍼 공유 → 그림자 스펙 이중화 해소.
4. **SoT 단일화**: 진본 ↔ 파생을 `gen_*.py --check`로 드리프트만 exit 1.
5. **D-077(8.1.0)**: 신7 LLM 수동 직렬화 SPOF 제거 — 결정론 파이프라인+게이트로 대체.

### 2.6 한계 (공학적 + 명리학적)

| # | 한계 | 근거 `[V]` |
|---|------|------|
| L1 | 강약 임계·계수 캘리브레이션 미검증 | `constants.py:64` "Step 14 캘리브레이션 대상" 자인 |
| L2 | 균시차 미적용(LMT만) | `timecontext.py:9-12` 의도적 OFF; 시지 ±60분 윈도 |
| L3 | 절입 ±수분 스냅샷, 1967 망종 +10분 오기 의심(C-006), 불확실성 미노출 | `solar_terms_ext.py:4` |
| L4 | 합충 계수가 '존재' 기준(세력 무관) | `strength.py:9-10`; 먼 충·약한 합도 동일 KHC |
| L5 | 종격·화격(외격) 엔진 미산출 | `apply_a6` neither∧strong 도달 불가(D-074), jonggyeok_review 미직렬화 |
| L6 | 커버리지 1951-01-06~2035 + 한반도(경도 124-132) 전용 | solar_terms 강결합; 2036+ 절벽 |
| L7 | tier2 검증 부재(통관·상전·청탁·진가가 결정론 안전망 밖) | §⑦-5 빈 슬롯; Layer-2 실캡처 0건 |
| L8 | BLIND SPOT 값 미검증 (단 branch_climate는 lookup 존재·배선 갭) | `flow.current_*`·산문은 raw 없음 / `branch_climate`는 `climate.py` lookup 존재(C-003) |
| L9 | 코드실행 불가 환경(GPT Knowledge UI) 취약 | `--verify` 부재 시 정적블록 오전사 리스크(신7 P1 자인). **R-4·R-6의 constrained decoding/jury 의존 권고가 이 환경에서 동작 불가** |
| L10 | 핀 미범프 역인센티브 | `doc_coherence` 게이트가 정당한 0.2.13 범프 억제(DEPLOY_MANIFEST 자인) |

---

## 3. 공개 사주 엔진 비교 분석 (외부 2차 주장 — 전 항목 `[S]`, 미검증)

> **인식론 경고**: 본 절의 모든 외부 프로젝트·통계·커버리지·"수렴" 주장은 recovered 코드로 검증 불가능한 secondhand이다. 직접 코드 비교를 수행하지 않았다. 출처·접근일은 일반 공개 저장소(GitHub) 기준이며, **채택 전 반드시 직접 검증**해야 한다. 본 절이 통째로 틀려도 §6 내부 권고는 유효하다(§1.4).

### 3.1 만세력 계산의 두 계보

| 계보 | 대표(접근: GitHub 공개 저장소, 2026-06 기준 `[S]`) | 절기 산출 | 커버리지 | 현행 대비 |
|------|------|---------------|---------|-----------|
| 룩업/사전계산표 | orrery, sajupy, bazica | 기준점+분오프셋 룩업·보간 | 테이블 종속 | **현행과 동일 전략**(KASI assets 1951~2035 룩업) |
| 천문계산 定气/定朔 | sxtwl, lunar-python | VSOP87/ELP2000 실제 황경 | (저장소 주장) 광범위 | 현행에 없는 광범위·고정밀(주장) |
| 절충형 | yhj1024/manseryeok | KASI 임베드표 + 분단위 교차검증 + **균시차 적용** | (저장소 주장) 광범위 | **가장 유사한 한국 사례**(주장) |

핵심 후크(가설): (a) sxtwl식 定气 천문계산을 fallback/검증 레이어로 두면 fail-loud를 깨지 않고 커버리지 확장 가능(P5), (b) yhj1024가 적용한다고 알려진 균시차가 현행 미적용 차이(P3).

**1차 초안 정정(C-001)**: 1차 초안 3.1 비교표는 균시차 차이를 "현행 `solar_time.py`에 없는"으로 귀속했으나 이는 오귀속이다. **진태양시 SoT는 `timecontext.py`이며 `solar_dt`가 LMT 파생 필드다**(`solar_time.py`는 1954 플래그 헬퍼). 따라서 비교표의 해당 셀은 **"`timecontext.py`(solar_dt 파생; 균시차 OFF·`apparent_solar_dt` 예약). solar_time.py는 1954 플래그 헬퍼"**로 정정한다.

### 3.2 계산 vs 해석 분리 수준 `[S]`

- 사실만(해석 없음): orrery·sajupy·bazica·yhj1024 — 현행 tier1과 동급(주장).
- 엔진=사실 + LLM=판정: `cantian-ai/bazi-mcp`·`FOR-BAZI` — 현행 R2″·tier1 read-only와 **유사하다고 알려짐**. "독립 수렴"은 **가설**이며 직접 코드 대조 미수행.
- 룰기반 해석 자동화: `bazi-calculator-by-alvamind`(통근 2점/1점), `bazi-sdk`, scentedpotions — **confidence·경계보류 부재로 단정적**(저장소 표면 관찰).

### 3.3 현행 차별점 (최상급 표현 완화 — C-004)

1. **강약 정량화 성숙도**: 통근 2점/1점식 단순 점수 대비, 현행은 득령+득지(base×k12×kHC)+득세(위치가중)+정규화+임계+A6+A7+confidence_asymmetry로 **구조가 더 정교하다**(내부 코드 `[V]`). 단 "조사된 어느 공개 엔진도 경계보류·비대칭 신뢰도가 없다"는 **전수조사 불가능 명제이므로 단정하지 않는다** — "본 심사가 표면 관찰한 공개 표본 내에서는 경계보류·비대칭 신뢰도를 갖춘 사례를 확인하지 못했다" `[S]`로 한정한다.
2. **schema 버전관리 + golden byte-freeze + handoff_verify**: 내부 코드 기준 성숙(`[V]`). 외부 비교는 `[S]` 표본 한정.
3. **fail-loud 간지 추정 금지**: 내부 코드 기준 일관 적용(`[V]`).

### 3.4 차용 우선순위(외부 — 채택 전 직접 검증 전제 `[S]`)

(a) `FOR-BAZI`식 古典 RAG로 tier2 해석 출처 인용 + 자가검증 → P4. (b) `yhj1024`식 균시차 보정 → P3. (c) `sxtwl`식 定气를 범위밖 검증·확장 fallback → P5. (d) `bazi-mcp`식 MCP 인터페이스 → 장기.

---

## 4. 사주명리학적 해석 프레임워크 정합성

### 4.1 단일 '정통'은 없다 — 세 고전은 서로 다른 축

| 고전 | 축 | 현행 구현 `[V]` | 정합도 |
|------|----|-----------|--------|
| 자평진전 | 격국(사회적 성취) | ASK4 §1-2 정격 월령 투출법 | 충실(단 validity 3분류 단순화) |
| 적천수 | 억부·체용·통관 | `strength.py` + ASK4 계층4·§4-1-A-ter 통관·§5 청탁 | 핵심 구현(단 §⑦-5 빈 슬롯) |
| 궁통보감 | 조후(한난조습) | `climate.py` lookup + ASK2 §2 + ASK4 계층2 극단조후 | 충실(이중계산 차단은 정통 이상) |
| 물상론 | 통변 보조 | ASK9 격리("판정 미사용") | 모범적 격리 |
| 신살론 | 보조 tier | ref §⑩ 별도 tier | 정통적(보조로만) |

**"최적"은 단일 학파가 아니라 위계적 결합**(특수격→극단조후→정격→억부/통관/병약)이며, 현행 ASK4 §4-1이 이를 IF-ELSE 강제 계층으로 코드화한다 `[V]`.

### 4.2 명리의 최대 약점 = 재현성·해석자간 신뢰도

| 요건 | 현행 충족 `[V]` |
|------|-----------|
| (a) 사실/판정층 분리 | 충족 — KERNEL R2′/R2″ |
| (b) 계산가능 부분 byte-freeze | 충족 — golden test |
| (c) 정성 판정 명시적 위계 + 재계산 금지 | 충족 — ASK4 §4-1 ladder |
| (d) 경계사례 다중후보 + 근거추적 | 부분 — boundary_hold/이원용신 있으나 **확률·신뢰도 점수 부재**, 근거추적은 평면 echo |

### 4.3 미달 영역 (명리학적)

1. **용신 후보의 명시적 확률/신뢰도 점수 부재.** 이진 ladder + 정성 hedge 의존. 용신 후보를 점수화 분포로 산출하는 확장이 다음 단계(P2/R-4).
2. **격국·종격 진가, 청탁(§⑦-5)의 결정론 보조지표 미시드.** 빈 슬롯·LLM 전적 위임.
3. **해석자간 신뢰도 직접 측정 회귀 부재.** golden은 엔진 산출만 동결(P4/R-6).

### 4.4 명리학적으로 잘한 것 (보존 대상)

- **이중계산 차단**: 온도극단=계층2 / 조습무력=계층2-bis / 상전정체=통관 / 형파해=강약 미반영(`strength.py` KHC 육합·육충만 1회, 형파해 0). 점수 인플레이션 방지의 모범.
- **전거 부착형 거버넌스**: 고전 인용이 확정 판정을 바꾸지 못하고 '부착'만(§⑦-00).
- **주역(매화역수)의 인식론적 종속**(§3-3-B): enriching 레이어 한정, 혼조에서만 tiebreak.

---

## 5. 타 도메인 엔진에서의 시사점과 현행 적용지점

> 패턴 자체는 `[S]`(학술), 그러나 각 적용지점(후크)은 내부 코드 사실 `[V]`에 못박는다. **코드 실행 불가 환경 제약은 5.6·5.7에 명시**한다.

### 5.1 MYCIN CF → 강약 기여도 분해
`strength.py`의 `0.40/0.35/0.25` 가중합 + 경성 임계는 CF 결합과 구조가 유사하다. 각 뿌리·득세 위치의 **부호 있는 기여도**를 분해 산출하고, `boundary_hold`를 임계 ±ε 저확신 구간으로 정량화 → `confidence_asymmetry` 베이스화. 적용지점: `compute_strength_core` 말미(R-1).

### 5.2 신용 Reason-Code/WoE/SHAP → verdict_reason_codes
ECOA Reg B식 "구체·정확한 주요 사유" 통지를 모델로, 득령·득지·득세 항목별 사유코드를 결정론 산출. **부호 규약 필수**(R-1 상세 참조). 적용지점: `boundary_evidence` 인프라 재사용 + R2′ echo 확장(L78).

### 5.3 GRADE → verdict와 분리된 확실성 축
권고 강도 ≠ 근거 강도 분리. 근거 확실성(뿌리 투출·합충 충돌·경계 근접도)을 verdict와 분리 산출. Condition B(시각 미상)를 indirectness 감점으로 형식화. 적용지점: ASK2/4.

### 5.4 JTMS/ATMS → R2′ echo를 의존성 그래프로 승격
가장 직접적 차용. verdict별 의존성 그래프를 봉인하고 `handoff_verify`를 의존성 정합 대조로 확장. ATMS 다중컨텍스트가 boundary_hold 이원용신과 동형 — 강/약 가지를 가정집합으로 태깅(ASK6 activation_key). 적용지점: `assemble_handoff`·`handoff_verify`(R-5).

### 5.5 Drools/RETE salience → 합충·용신 위계 외화
§④ 합충 우선순위와 §⑤ 용신 계층을 선언적 룰셋으로 외화하면 `why_skipped`("억부 스킵: 극단조후 성립") 추적 가능. 적용지점: `relations.py` 위계.

### 5.6 CoVe + LLM-as-jury + self-consistency → tier2 검증층 (⚠️ 코드 환경 전용)
CoVe 엔진 역질의·3대 고전 이질 jury·self-consistency N회 다수결. **결정론 게이트는 LLM judge가 아니라 `handoff_verify` 유지**(self-preference 편향 회피). **환경 제약**: self-consistency 다중 샘플·jury 다중 호출은 **코드 실행 환경에서만 가용**하며, 주 배포인 GPT Knowledge UI 단독에서는 동작 불가다 — **코드 환경 가용성이 R-6의 선행조건**(L9·P4 리스크 반영). 적용지점: ASK4/5 후처리(R-6).

### 5.7 RAG citation faithfulness + constrained decoding (⚠️ constrained decoding 코드 환경 전용)
ASK2~6 해석 문장을 atomic claim으로 보고 tier1 필드ID/§참조에 grounding 의무화. **`element_favorability` 등 범주값의 JSON grammar/legend constrained decoding 강제는 코드/구조화출력 API 환경 전용**이다 — GPT Knowledge UI에서는 프롬프트 규약 + `handoff_verify` 사후검증으로 **대체**해야 한다(R-4 리스크 반영). 적용지점: ASK 해석 산문(R-4·R-6).

### 5.8 Swiss Ephemeris(Centaur + DE431) → 커버리지 결정론 확장 `[S]`
JPL DE류로 절입시각을 결정론 산출 후 byte-freeze하면 fail-loud를 깨지 않고 커버리지 확장(P5). 적용지점: `solar_terms_ext.py`.

### 5.9 Arden Syntax MLM 슬롯 → 모듈 거버넌스
각 CONTRACT에 maintenance(릴리스 핀·D-코드·골든 ID)·library(§⑦ 출처)·knowledge(로직) 슬롯 정형화. `d_fuzzy`(D-037)를 연속 멤버십 점수로 표현하는 선례.

---

## 6. 개선 권고안

### 6.1 우선순위 테이블

| ID | 권고 | 우선 | 난이도 | 리스크(환경 제약 직접 반영) | 외부 후크 `[S]` |
|----|------|------|--------|--------|-----------|
| **R-1** | verdict 기여도 분해 + `verdict_reason_codes[]` | ★★★ | 중 | 낮음 — read-only echo, **코드 실행 불요** | MYCIN CF / 신용 Reason-Code / GRADE |
| **R-2** | 강약 캘리브레이션 후크 외부화 + 튜닝 | ★★★ | 중~상 | 중 — golden 전면 갱신. **ground-truth 부재(8.1 #1·라벨-free 대안 §6.2)** | 로지스틱/순서회귀 + boundary_evidence 피처 |
| **R-3** | 균시차 옵트인(`apparent_solar_dt` **구현**) + 절입 ±N분 | ★★★ | 중 | 낮음 — 기본 OFF | yhj1024 equation-of-time |
| **R-4** | tier2 용신 PoT화(`tier2.v1`) | ★★★ | 중~상 | **중~높음 — constrained decoding은 코드 환경 전용. GPT Knowledge UI에선 사후검증 대체. 코드 환경 가용성 선행조건** | PoT / constrained decoding |
| **R-5** | R2′ echo → JTMS 의존성 그래프 | ★★ | 상 | 중 | JTMS/ATMS |
| **R-6** | tier2 검증층(CoVe + jury + self-consistency) | ★★ | 상 | **높음 — 코드 환경 전용(jury·self-consistency). GPT Knowledge UI 단독 동작 불가. 코드 환경 가용성 선행조건** | CoVe / LLM-as-jury / self-consistency |
| **R-7** | Layer-2 assembled 골든 활성화(실캡처 1건) | ★★ | 중→**낮음** | 낮음 — **인프라 기동작(SYNTHETIC self-test 통과). 캡처 1건만 충원** | LLM eval harness |
| **R-8** | branch_climate **배선/이관**(lookup→엔진 emit) | ★★ | 중→**낮음** | 낮음 — **계산 추가 아님. `climate.py` lookup 존재, no-new-values 대상화** | claim-level grounding |
| **R-9** | 합충 강도 모델링(KHC × 거리 가중) | ★ | 중 | 중 — golden 변경 | Drools salience |
| **R-10** | 커버리지 확장(定气 → byte-freeze) | ★ | 상 | 중 | sxtwl / DE431 |
| **R-11** | 외격 결정론 부분회복(종격 predicate) | ★ | 중 | 중 — 유파 논쟁 | 다후보 점수화 |
| **R-12** | MCP 인터페이스로 tier1_facts 노출 | ☆ | 중 | 낮음 | bazi-mcp |

### 6.2 항목별 상세

#### R-1. verdict 기여도 분해 + 사유코드 [★★★, 중] — 부호 규약 명시
- **문제**: `verdict_at`이 가중합 pct를 경성 임계로 5단계 판정만 하고 항목별 분해가 없다. LLM이 강약 설명 시 임의 서사 주입 표면이 남는다.
- **권고**: `compute_strength_core` 말미에 결정론 기여도 분해를 추가해 `verdict_reason_codes[]`를 tier1 emit. LLM은 echo만.
- **부호 규약(C-006 — R-1 구현 전 반드시 못박을 것)**: 산식은 `pct = 0.40×(ryeong×2) + 0.35×ji + 0.25×(se+100)/2`로, **득령·득지는 비음수 가산항, 득세만 부호를 가진다**. 따라서:
  - **절대기여(absolute contribution) 규약**을 기본으로 한다: 死=0(만점 旺 대비 손실이 아니라 *절대 0점 기여*), 무근=0, 식상과다 득세=음수. 이때 **항등식 `Σ(기여) = pct`가 성립**하도록 정의해야 한다(`test_invariants` echo 항등식의 신규 안전망).
  - **기회손실(opportunity-loss) 규약**(死는 旺 대비 −50 등)은 *별도 보조 필드*로만 제공하고 절대기여와 명확히 분리한다. **두 규약을 혼용하면 부호 혼란·항등식 깨짐**이 발생한다(1차 초안 P1 예시의 "득령 死=−50 기여"가 바로 이 혼동 — 死의 절대기여는 0이며, −50은 旺 대비 기회손실이지 실제 −50 감점이 아니다).
  - reason-code 스키마: `{factor, state, absolute_contribution, opportunity_loss_vs_max}`로 두 축을 분리 표기.
- **적용지점**: `strength.py` + R2′ echo 대상(`core_kernel.md` L78)에 `verdict_reason_codes` 추가 + `test_invariants`에 `Σ(absolute_contribution)=pct` 항등식.
- **난이도/리스크**: 중. read-only echo + 신규 산술 0이면 verdict 불변. `boundary_evidence`가 이미 거리·비율 방출이라 인프라 절반 완성. **코드 실행 불요(순수 엔진 emit)이므로 GPT Knowledge UI 환경에도 안전**.

#### R-2. 강약 캘리브레이션 후크 [★★★, 중~상] — 라벨-free 검증 경로 포함
- **문제**: 임계·계수 전부 매직넘버. `constants.py:64` 미검증 자인. **ground-truth(전문가 라벨) 부재**가 근본 병목으로, 데이터 없이는 무기한 보류 위험.
- **권고(인프라)**: `STRENGTH_WEIGHTS`·`STRENGTH_THRESHOLDS`·`DEUK_RYEONG_RAW`(이미 `constants.py:65-67` 분리)를 외부 설정으로 승격, `boundary_evidence` 피처로 로지스틱/순서회귀 튜닝.
- **라벨-free 검증 경로(8.1 #1 대안 — 데이터 병목 우회)**: 전문가 라벨 없이도 가능한 **내적 일관성 검증**을 R-2 선행 단계로 둔다:
  - (a) **인접 분(分) 연속성**: 동일 명식의 출생시각을 ±1분 단위로 스윕해 verdict·pct가 경계 외에서 급변하지 않는지(단조성·연속성) 검증.
  - (b) **경계 ±ε 안정성**: 임계(65/55/45/35) ±ε 섭동에서 verdict 분포의 안정성·`boundary_hold` 발화 일관성 측정.
  - (c) **계수 섭동 민감도**: 가중·base를 소폭 섭동해 verdict 뒤집힘 비율(flip rate)로 계수 견고성 정량화.
  이들은 라벨 0건으로 즉시 실행 가능하며, 전문가 라벨 확보 전에도 R-2를 "데이터 대기"에서 "**진행 가능**"으로 전환한다.
- **적용지점**: `constants.py` 외부화 + 라벨-free 검증 스위트 + golden 재생성 절차.
- **난이도/리스크**: 인프라 중, 전문가 라벨 확보 상. 매직넘버 변경 = golden 전면 갱신 → ruleset_version 범프 + D-코드 필수.

#### R-3. 균시차 옵트인 + 절입 불확실성 [★★★, 중] — 신규 아님, 기예약 필드 구현(C-003)
- **문제**: `timecontext.py:9-12` LMT만, 균시차 OFF. 시지 ±60분 윈도. 절입 ±수분 스냅샷, 1967 망종 +10분(C-006).
- **권고**: (a) **`apparent_solar_dt` 필드를 구현**한다. **이는 신규 설계가 아니라 `timecontext.py:11-12` docstring이 이미 예약한 필드의 구현**이다("균시차 옵트인 보정은 별도 필드(apparent_solar_dt, 기본 OFF)로 분리한다"). 권고 신규성을 과대평가하지 말 것. (b) 절입 경계 ±N분 출생에 '월주 경계 근접' 플래그 emit. (c) 1967 망종을 ephemeris 재산출로 교정하고 |Δ|≤1분 회귀 자동화(`solar_terms_ext.py:4` 수용기준과 정렬).
- **적용지점**: `timecontext.py`(예약 필드 구현)·`solar_terms_ext.py`·신규 invariant.
- **난이도/리스크**: 중. 기본 OFF 유지로 기존 golden 호환.

#### R-4. tier2 용신 PoT화 [★★★, 중~상] — 환경 제약 명시
- **문제**: ASK4 용신이 LLM 자유서술. 다후보(扶抑/調候/通關/病藥) 문제에 단일 자유서술 부적합. 인용 환각·재현성 약점.
- **권고**: `tier2.v1` JSON Schema 신설(`{yongshin_candidates:[{element, method, cited_facts:[tier1 경로], score, rationale}], chosen, runner_up, boundary_note}`). `cited_facts`의 tier1 실재성을 `handoff_verify`가 검증.
- **환경 제약(must_add 반영)**: constrained decoding/structured output 강제는 **코드/API 환경 전용**이다. 주 배포 GPT Knowledge UI에서는 강제 불가하므로, 그 환경에서는 **프롬프트 스키마 규약 + `handoff_verify` 사후 cited_facts 실재성 검사**로 대체한다. **코드 환경 가용성이 강제(constrained) 경로의 선행조건**이며, 우선순위 ★★★는 "사후검증 대체 경로가 GPT Knowledge UI에서도 부분 동작함"을 전제로 한다.
- **적용지점**: ASK4 §4-1 + `assemble_handoff.py` + `handoff_verify` cited_facts 검사.

#### R-5. JTMS 의존성 그래프 [★★, 상]
verdict별 의존성 그래프를 handoff에 `justification[]`로 봉인, ATMS label로 boundary_hold 강/약 가지 태깅, `handoff_verify`를 의존성 정합 대조로 확장. 적용지점: `assemble_handoff`·`handoff_verify`·ASK6.

#### R-6. tier2 검증층 [★★, 상] — 코드 환경 전용
CoVe 역질의·3대 고전 이질 jury·self-consistency. **최종 봉인 게이트는 결정론 `handoff_verify` 유지.** **환경 제약**: jury 다중호출·self-consistency 다중샘플은 **코드 실행 환경 전용**으로 GPT Knowledge UI 단독 배포에서 동작 불가 — **코드 환경 가용성이 선행조건**. 고부담 질문(채무·투자·건강)에만 선택 적용. 적용지점: ASK4/5 후처리.

#### R-7~R-12 (요약)
- **R-7**: `TIER2_BOUNDARY_CASES`의 `captured_tier2`(현재 4건 None)에 **실제 LLM 봉인 산물 1건 캡처**. **인프라는 이미 동작**한다(SYNTHETIC·SYNTHETIC_BOUNDARY가 `assembled()`→`assemble_handoff`→`handoff_verify` self-test 통과). 따라서 **저비용**. `_golden_tier2_verdict/` 전문가 라벨 케이스 + LLM-judge 게이트는 후속. (단 boundary_hold=true 캡처는 canonical strength 재배치 선결 — 이미 `SYNTHETIC_BOUNDARY`로 경로 검증됨.)
- **R-8**: **계산 추가가 아니라 배선/이관**(C-003). `climate.py`의 12지지 한난조습 lookup을 엔진 emit으로 배선해 `branch_climate`를 no-new-values 대조 대상으로 승격. 현재는 ASK2(LLM)가 chart 컨테이너에 기록하는 설계라 대조 밖.
- **R-9**: KHC 계수에 거리 가중 또는 `strength_hint` 방출 — L4 교정. golden 변경.
- **R-10**: `build_ephemeris_terms.py` 1900-2100 확장 + `day_pillar` 검증창 정렬 + byte-freeze.
- **R-11**: 종격 트리거(極弱∧無根∧無生扶)를 결정론 predicate로 산출해 LLM에 후보+근거. `apply_a6` dead-branch(D-074) 정리. **유파 논쟁(진종<5%·假從 다수) 주의**.
- **R-12**: tier1_facts를 MCP 서버로 노출. 역방향 조회는 신규 기능.

---

## 7. 단계별 로드맵

### Phase 1 — Quick Win (1~2 스프린트, 거동 영향 최소, 전부 코드 환경 불요)

| 작업 | 근거 `[V]` | 위험 |
|------|------|------|
| **R-1** verdict_reason_codes (read-only echo, 부호규약 명시) | boundary_evidence 인프라 재사용 | 거의 0 |
| **R-3a** 균시차 옵트인 = `apparent_solar_dt` 구현 (기예약 필드) | `timecontext.py:11-12` 예약 | 낮음 |
| **R-3c** 1967 망종 +10분 교정 + |Δ|≤1분 회귀 | C-006 (`solar_terms_ext.py:4`) | 낮음 |
| **R-7** Layer-2 assembled 골든 실캡처 1건 | 인프라 기동작(SYNTHETIC self-test) | 낮음 |
| **R-8** branch_climate 배선/이관 | `climate.py` lookup 존재 | 낮음 |
| **R-2 라벨-free 검증** (인접 분 연속성·경계 ±ε 안정성) | 라벨 0건 즉시 실행 | 낮음 |

### Phase 2 — 중기 (캘리브레이션·tier2 구조화 / 일부 코드 환경 선행)

| 작업 | 선행 | 비고 |
|------|------|------|
| **R-2** 캘리브레이션 + 데이터셋 | R-1, R-2 라벨-free | ruleset_version 범프, golden 전면 갱신 |
| **R-4** tier2 용신 PoT화 | R-7 | **코드 환경: constrained decoding / GPT UI: 사후검증 대체** |
| **R-9** 합충 강도 모델링 | — | L4 교정 |
| **R-3b** 절입 ±N분 플래그 | R-3a | 월주 불확실성 노출 |

### Phase 3 — 장기 (검증층·커버리지·생태계 / 코드 환경 선행)

| 작업 | 선행 | 비고 |
|------|------|------|
| **R-5** JTMS 의존성 그래프 | R-4 | 감사성 |
| **R-6** tier2 검증층 | R-4, R-7, **코드 환경 가용성** | 결정론 게이트 최종 |
| **R-10** 커버리지 확장 | — | 1951↓·2035↑ |
| **R-11** 외격 결정론 부분회복 | 명리 자문 합의 | 유파 논쟁 |
| **R-12** MCP 인터페이스 | — | 생태계 |

---

## 8. 리스크·한계·미해결 논쟁·반증가능성 (분량 강화)

### 8.1 공학적 리스크
1. **캘리브레이션 ground-truth 부재(R-2 근본 병목).** 전문가 라벨 부재 시 R-2가 무기한 보류될 위험. **완화책은 §6.2 R-2의 라벨-free 내적 일관성 검증**(인접 분 연속성·경계 ±ε 안정성·계수 섭동 flip rate)으로, 데이터 없이 진행 가능한 경로를 확보했다. R-6 jury를 라벨 생성기로 부트스트랩하는 접근은 순환 위험이 있어 라벨-free 경로를 우선한다.
2. **매직넘버 변경 = golden 전면 갱신.** byte-freeze가 강점이자 변경 비용. R-2/R-9는 대규모 재생성 동반.
3. **코드 실행 불가 환경(L9).** GPT Knowledge UI에서 `--verify` 부재 → 정적블록 오전사 검출이 RoE 준수 의존. **R-4의 constrained decoding·R-6의 jury/self-consistency는 코드 환경 전용**이라 환경별 fidelity 분기가 생긴다. R-1·R-3·R-7·R-8은 코드 실행 불요로 전 환경 안전.
4. **tier2 검증층 비용·지연(R-6).** self-consistency N회 + jury 3 + CoVe는 토큰·지연 수배 증가. 고부담 질문 게이트 필요.

### 8.2 명리학적 미해결 논쟁
1. **외격(종격·화격) 결정론화 가부(R-11).** 진종<5%·假從 다수라 LLM 위임이 발산 방지에 안전하다는 D-074 vs 결정론 predicate로 일관성을 높이자는 R-11 충돌. 명리 자문 합의 선행.
2. **음간 12운성 역행 — 강약 pct 정량 영향 분석(must_add 반영).** `STAGE_MATRIX`(`twelve_stages.py`)는 **양생음사 역행을 반영한 표**다: 乙(음목)이 午=장생, 亥=사로 甲과 반대 방향을 돈다(코드 확인 `[V]`). 이 표값이 `STAGE_MATRIX[day_s][b] → STAGE_GROUP → GROUP_BONUS{+0.2/0/−0.3}`로 흐르고, `GROUP_BONUS`가 득지 산식 `base × (1+k12) × (1+kc)`의 **k12로 직접 곱**해진다(`strength.py:123-132`). **정량 영향 추정**: 만약 유파 학설대로 음간을 양간과 동일시(양생음사 폐기)하면, 음일간 명식에서 동일 지지의 stage가 체계적으로 바뀐다 — 예컨대 乙 일간이 午를 만날 때 현행 표는 장생(生旺祿군, +0.2)으로 보아 득지를 **+20% 가산**하지만, 양간동일설에서는 午가 乙에게 장생이 아니므로 그 가산이 사라진다. 반대 지지에서는 부호가 뒤집힌다. 즉 **양생음사 단일표는 음일간 명식의 득지 pct를 지지 분포에 따라 ±20%까지 체계적으로 편향**시킬 수 있고, 이는 0.35 가중을 통해 verdict 임계(45/55 등)를 넘나드는 경계 명식에서 verdict를 1칸 이동시킬 수 있다. **편향 방향은 명식의 음일간×지지 조합에 따라 부호가 갈리므로 단일 방향 단정은 불가**하나, 그 크기(±20% 득지)는 verdict-flipping 규모다. 이 분석은 **R-2 캘리브레이션 시 음일간 부분표본을 분리 검증**하거나, **유파 옵션 플래그(GROUP_BONUS 분기)** 도입을 결정하기 위한 선행 정량 근거다 — 단 byte-freeze 단일 결정론과 긴장하므로 옵션화 시 ruleset_version 분리 필수.
3. **득세에서 일지 누락.** `SE_W{년60/월100/시80}`이 천간만 세고 일지 통근은 득지로만 흡수. 일지 위치가중 반영(이중계산 위험) vs 현행 분리 유지 논쟁.
4. **년지 뿌리 ≤40 캡의 '타지=년지'(C-005)·인성 ×0.65(D-034).** 원문 모호점 단일 선택. R-2 캘리브레이션이 데이터로 결정 가능하나 명리적 정당성 vs 통계적 적합 충돌 시 우선순위 정책 부재.
5. **균시차 적용의 만세력 관행 충돌(R-3).** 전통 만세력은 LMT 기준이라 균시차 적용 시 기존 역서와 시주 상이 가능. 기본 OFF + 옵트인이 타협안이나 "어느 시주가 맞나"는 명리계 미합의.

### 8.3 반증가능성 (본 보고서가 틀릴 수 있는 지점)
- **외부 "독립 수렴" 가설(§1.4·§3)**: 외부 저장소를 직접 코드 비교하면 수렴이 표면적이거나 거짓일 수 있다. 이 경우에도 §6 내부 권고는 무영향(설계상 격리).
- **음간 12운성 영향 추정(8.2 #2)**: ±20% 추정은 단일 지지 가산 기준 상한이며, 실제 명식 표본 분포에서의 verdict-flip 비율은 측정 전 미확정 — R-2 음일간 분리표본으로 반증/확증 가능.
- **R-7 "저비용" 판단**: SYNTHETIC self-test가 비-boundary·boundary 경로를 통과하나, 실제 LLM 캡처가 스키마 외 출력을 내면 비용이 증가할 수 있다(반증 가능).

### 8.4 보존해야 할 불변 (개선이 침범 금지)
- **"봉인은 결정론, 판정만 LLM"**: R-6 추가 시에도 최종 게이트는 `handoff_verify`. LLM judge를 봉인 게이트로 쓰면 self-preference 편향.
- **fail-loud 간지 추정 금지**: R-10도 ephemeris 결정론 산출 + byte-freeze로만.
- **이중계산 차단**: R-9가 KHC를 득지·형파해 양쪽에 중복 계상 금지.
- **boundary_evidence read-only echo 불변(I7)**: R-1 기여도 분해도 신규 산술 0·verdict 불변·항등식(`Σ기여=pct`) 유지.

---

### 종합 결론

현행 엔진은 **내부 코드 기준으로 결정론 사실 계산(tier1)과 환각 차단 거버넌스가 매우 성숙한** 아키텍처다 `[V]`. 명리학적으로도 3대 고전의 위계적 결합·이중계산 차단·전거 부착·주역 종속 등 최적 프레임워크의 골격을 충실히 구현했다. **"타 도메인 best practice와 독립 수렴"은 매력적이나 검증되지 않은 가설**이며(`[S]`), 본 보고서의 권고는 그 가설에 의존하지 않는다(§1.4). 1차 초안의 최상급 비교우위 단정(압도적·독보적·전수조사형 부재 주장)은 근거 강도에 맞게 완화했다.

남은 과제는 일관되게 **tier2(LLM 판정)에 tier1 수준의 verifiability를 부여하는 것**이며, 내부 코드 사실만으로 정당화되는 네 권고가 그 핵심이다: verdict 사유코드화(R-1, **부호 규약 명시 전제**), 캘리브레이션(R-2, **라벨-free 검증으로 데이터 병목 우회**), 용신 PoT 구조화(R-4, **코드 환경 의존 명시**), tier2 검증층(R-6, **코드 환경 선행조건**). 더불어 즉시 착수 가능한 저비용 정정·배선 — `apparent_solar_dt` 구현(R-3a, 기예약), Layer-2 실캡처 1건(R-7, 인프라 기동작), branch_climate 배선(R-8, lookup 기존재) — 이 Phase 1의 빠른 성과다. 이 묶음이 "환각 ZERO 지향"을 강약 raw에서 격국·용신 판정까지 끝까지 관철시키는 다음 단계다.
