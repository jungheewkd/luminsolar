# 사주명리 AI — 배포 스냅샷 (연계성 정합 수정본)

> **릴리스 표시명**: `saju-runtime-8.1.0` (+ ASK1 출생지 정합 + ASK1~6 연계성 7건 + §⑪ 슬라이스 정합)
> **빌드 id**: engine `0.2.12` (handoff_verify 증분3 패치 — emit 거동 불변) · **handoff** `saju.handoff.v3.8` · schema 핀 `tier1.v1.6` / `jieqi.v1.0`
> **스냅샷 일자**: 2026-06-19
> **상태**: 전체 게이트 실측 통과 ✅ (배포 zip 추출본 193 passed / 1 skipped / 0 fail)

---

## 📦 구성 (GPT Knowledge 업로드 세트)

| 파일 | 역할 | 변경 |
|:--|:--|:--|
| `core_kernel.md` | 글로벌 KERNEL·실행 거버넌스·REDIRECT MAP | ✏️ IDREF-3·IDREF-5 |
| `ask_modules.md` | ASK 1~13 실행 모듈 | ✏️ 출생지 + COUP-3·R1·IDREF-6 |
| `reference_tables.md` | cold 참조 데이터 §②~⑪·월간지 | ✏️ IDREF-4·IDREF-3·IDREF-5 |
| `saju-engine-…-rt8_1_0.zip` | 결정론 엔진 + handoff 도구체인 | ✏️ COUP-1/H4 + §⑪ 슬라이스 |
| `README.md` | 패키지 개요 | (무변경) |

업로드: 위 **3 .md + 엔진 zip**을 GPT Knowledge에 함께 올리고 Code Interpreter 활성화.

---

## 📝 본 릴리스 변경

### A. ASK1 출생지 입력 지원 (선행 정합)
ASK 1 입력 패턴에 출생지(시/군/구) 선택 추가 — 엔진 `--region`·handoff `birth_place`와 ASK 1 로컬 패턴 정합(6곳).

### B. ASK1~6 연계성 권장 7건 (연계성 검토 보고서 🟡 worthwhile)
원국→강약→십성→격국/용신→병약→대운 파이프라인의 모듈 간·Core/Ref 수직 연계 정합. **고위험 잔재 아님 — 정본 일관성·추적성·verify 정합 위생.**

| ID | 이음매 | 수정 | 파일 |
|---|---|---|---|
| **IDREF-4** | §④ 헤더 소비자 self-inconsistency | `ASK 2·ASK 4` → `ASK 2·4·12` | reference_tables.md |
| **IDREF-3** | 월간지표 소비자 두 정본 드리프트 | core·ref 모두 `ASK 6 주·10·11·12 보조`로 통일(ASK9 비소비 제거) | core_kernel.md · reference_tables.md |
| **IDREF-5** | §⑪만 REF 앵커 부재 | `<!--REF:§⑪-->` 앵커 + 표기규약 `§②~⑩`→`§②~⑪` | reference_tables.md · core_kernel.md |
| **COUP-3** | [강약 민감도] 라벨 오기(소비처) | `← ASK 6 핸드오프` → `← ASK 4 §2-3 핸드오프(boundary.activation_key 경유)` | ask_modules.md |
| **R1** | ASK6 신살 inline表 ↔ §⑩ needs_curation 충돌 | 신살 산출셀을 §⑩ lookup으로 위임 + confidence 상속 가드(단독 verified 발현 금지) | ask_modules.md |
| **IDREF-6** | stage-contract 헤더 과소선언 | ASK1 reads_reference +§②·§③-2 / ASK4 inputs.prior +twelve_stages(본문 실소비 정합) | ask_modules.md |
| **COUP-1/H4** | boundary verify BLIND | `validate_boundary_consistency()` 추가 — operative_branch 멤버십 + clarity.by_branch cross-key 검사(+테스트 4종) | handoff_verify.py · assemble_handoff.py · test_handoff_verify.py |

### C. §⑪ 슬라이스 정합 (B의 부수 — 선재결함 완결)
IDREF-5의 §⑪ 앵커를 전제로, `assemble_slice.py`의 `_REF_SERIES`·`normalize_ref` 정규식에 §⑪ 추가 — ASK7 슬라이스의 §⑪ 미해소(이미 RED였던 선재결함) 해소. `test_assemble_slice` 복구.

### 버전 미범프 사유
모든 변경이 ```stage-contract``` 헤더 dependency-valid·schema 핀 불변·emit 결정론 불변(추가된 `validate_boundary_consistency`는 `--verify`/`--assemble` 봉인 시 handoff-only 검사로, tier1 emit 산출 무영향). 런타임/엔진 표시명 범프는 PIN과 어긋나 `test_doc_version_coherence`를 깨므로 **8.1.0 / 0.2.12 유지**(provenance상 패치만 부기). engine `0.2.12`는 동일 emit 거동의 도구체인 패치 빌드.

---

## ✅ 게이트 실측 검증 (2026-06-19 · pytest 9.1.0 · Python 3.13.7 · PYTHONUTF8=1)

배포 zip 추출본 + 편집 .md(REPO_ROOT 배치) 기준:

- **전체 스위트**: `193 passed · 1 skipped · 0 failed` (skip=tier2 Layer-2 캡처 공백, 기존·의도)
- **계약(IDREF-6)**: `gen_manifest.py --check` → `7 스테이지 · 위반 0 · 드리프트 없음` (twelve_stages dependency validation 통과)
- **버전 핀**: `test_doc_version_coherence` 5 passed (핀 불변 확인)
- **stage_contract_manifest**: 6 passed (헤더↔manifest 동기)
- **slice(§⑪)**: `test_assemble_slice` 복구 통과
- **boundary verify(COUP-1/H4)**: 신규 4종 passed (clean·skip-absent·illegal-value·cross-key-mismatch)
- **tier2 boundary 골든**: ASK4 계약 변경분 `gen_tier2_boundary.py` 재생성(4 manifest, 일치 4·변경 0)
- **엔진 결정론**: `test_golden` 통과(원국 산출 byte-freeze 불변) · `run_emit` 스모크 `tier1.v1.6` 정상 방출

---

## 🔐 무결성 (SHA256)

| 파일 | 크기(B) | SHA256 |
|:--|--:|:--|
| `README.md` | 3,236 | `3C4FD73D063E948EBA47FA8AC312167042B2E2A4C0D7A4263A02331CC83B4B40` |
| `core_kernel.md` | 55,292 | `D91E8AB2D81A1704C14B466440BC1EDC06C347D9A4D993387F2107F063620D34` |
| `ask_modules.md` | 323,956 | `70416F036DC70778B2EF94BF9239AF505DBFD2E7A5BC77C677D7CF72F87E0A99` |
| `reference_tables.md` | 182,127 | `B04640AA9F9644F1BAB1AE76B64C05D54930DA58106694F15A39D78DCF8DD346` |
| `saju-engine-…-rt8_1_0.zip` | 247,892 | `176516523E636D9D64FE2D391C17B61C421F96027D8467D2B2EDBE79E8BD2F4F` |

> 엔진 zip은 transient(`__pycache__`·`.pytest_cache`) 제거 후 재빌드(102 파일). 원 엔진 zip(SHA256 `D8B205D9…`)은 `D:/AI_SAJU/_backup/saju-engine-v0_2_12-PRISTINE-D8B205.zip`에 보존(정본 git `Before/`에서도 재구성 가능).

---

## ⚠️ 정본 반영 (필수 후속)
배포 스냅샷이다. 동일 변경을 **정본 git `Before/`**에 반영해야 재배포 시 덮어쓰이지 않는다. 정본에서는 engine 도구체인 패치이므로 **engine_version 범프(0.2.12→0.2.13)** + CHANGELOG 항목을 정식 절차로 부여하는 것을 권장한다(본 스냅샷은 게이트 호환 위해 핀 유지).
변경 .py: `tools/handoff_verify.py` · `tools/assemble_handoff.py` · `tools/assemble_slice.py` · `tests/test_handoff_verify.py` · `tests/_golden_tier2/*_ask_4.manifest.json`(재생성).
