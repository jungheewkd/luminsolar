# 사주명리 AI — GPT 배포 패키지

> **런타임 v8.1.0 · handoff schema v3.8 · engine v0.2.12**
> 결정론 Python 엔진(saju-engine)이 원국·대운·강약·합충·일진·매화괘를 `tier1_facts` JSON으로 산출하고,
> 프롬프트 3파일이 이를 **전사(echo)·해석**만 한다 ("엔진=사실, LLM=판정" · 환각 ZERO).

---

## 📦 패키지 구성 (GPT Knowledge 업로드용)

| 파일 | 역할 | 적재 |
|:--|:--|:--|
| `core_kernel.md` | 글로벌 KERNEL [1]~[9]·실행 흐름·거버넌스 | 상시 |
| `ask_modules.md` | ASK 1~13 실행 모듈 | `<ASK N>` 요청 시 |
| `reference_tables.md` | cold 참조 데이터 (§②~⑪·월간지) | 해당 § 필요 시 |
| `saju-engine-gpt-bundle-v0_2_12-rt8_1_0.zip` | 결정론 엔진 + handoff 도구체인 | Code Interpreter |

## 🔧 GPT 빌더 설정 (3단계)
1. GPT 빌더에서 **Code Interpreter** 활성화
2. 위 **zip + 프롬프트 3 .md**를 Knowledge에 함께 업로드 (별도 절기 xlsx 불요)
3. 사용자가 생년월일 입력 → GPT가 zip을 풀어 `run_emit.py` 실행 → `tier1_facts` 산출
   ```
   python3 run_emit.py <ISO출생> <F|M> [경도 또는 --region "지역명"] [--no-time] [--divination <ISO>]
   python3 run_emit.py --jieqi <YYYY>
   ```

## 🔑 호환 핀 (핸드셰이크 게이트)
- `tier1.v1.6` · `jieqi.v1.0` · **`saju.handoff.v3.8`**
- `meta.engine_version = 0.2.12` · `prompt_pin` = provenance(거동 무관)
- 커버리지: 출생 1951-01-06(소한)~2035 · 범위 밖 fail-loud(간지 추정 금지)

---

## 📝 이번 릴리스 변경 요약 (handoff v3.7 → v3.8 가산·상위호환)

**ASK 5 재범위화 + 개운·건강 직렬화(D3)**
- ASK 5의 **건강(오행-장부)·개운(색·방위·시진·직업)**을 ASK 8 §6(현실 실행 가이드)로 **이관**.
  ASK 5는 **용신 작용·質(yong_mechanism)** 분석에 집중.
- `reference_tables.md §⑪`(개운·건강 오행 상관표) **SoT 신설**.
- handoff `derived_lookup.remedy_map`/`health_map` **직렬화** → 하류(ASK 9·10·11·13)가
  재산출 없이 **lookup** (환각 표면 차단). ASK 9·10·11·13 소비 와이어링 완료.

**ASK 1~6 핸드오프 최적화 (5렌즈·19발견 적대 검증)**
- **P1**: boundary 소유권 자가점검(C1) · 강약 echo SoT 단일고정(C2) ·
  경계보류 부분봉인 fail-loud(C5) · ASK 6 contract 고아 채널 제거(D2).
- **P2**: inherits_kernel 봉인(E2) · branch_climate 정직화(E1/B1) ·
  stale-operative 재봉인 가드(D4) · 실효 강약 괴리 직렬화(C3).

**handoff v3.8 동기화**
- 엔진: `assemble_handoff`(remedy/health 빌더 + 5오행 폐쇄 validate) · `handoff_static`
  STATIC_VERSION · `_golden_handoff` 재생성(roundtrip 일치).
- **불변**: emit 거동 · `engine_version` 0.2.12 · `tier1.v1.6` · `jieqi.v1.0`
  (가산 schema라 핸드셰이크 게이트만 v3.8).

> 상세 이력: zip 내부 `docs/CHANGELOG.md` 참조. (정본 git: `Before/`, 커밋 `79883c9`)

---

## ⚠️ 주의
- 이 폴더는 **배포 스냅샷**입니다. 수정은 정본(git `Before/`)에서 하고 재배포하세요.
- `module_manifest.json`은 개발/CI 산출물(stage-contract 미러)이라 GPT 업로드 대상 아님.
