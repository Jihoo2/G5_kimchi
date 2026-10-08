# G5 Project Baseline — 조각김치 이물검출 라벨링

이 문서는 **우리 팀이 교과 7 프로젝트를 어떤 기준으로 진행했는지** 정한 공통 규칙입니다.

> `[이름]` 칸은 팀원 이름으로 채워 주세요.

---

## 1. 공통 데이터 기준

| 항목 | 기준 |
|---|---|
| 전체 이미지 | 900장 (`이물검출_학습데이터1`, `이물검출_학습데이터2`) |
| Label Format | YOLO TXT — `class_id x_center y_center width height`, 0~1 정규화, 소수 6자리 |
| Class | 0~6 (`configs/classes.yaml`), **Class 4 고무장갑은 사용하지 않음** |
| 빈 TXT | 검출 대상이 없는 이미지 = 빈 TXT (배경 이미지로 학습, 삭제하지 않음) |
| RAW 데이터 | **수정 금지** — 원본 이미지·받아온 TXT 는 읽기만 하고, 결과는 별도 폴더에 저장 |
| 판단 기준 | Class: `docs/class_guide.md` · BBox: `docs/bbox_guide.md` |

---

## 2. 역할과 검수 절차

| 단계 | 역할 | 선택 가능한 상태 | 하는 일 |
|---|---|---|---|
| 1차 작업 | 작업자 | EDITED, REVIEW | 원본 라벨 확인·수정, 애매하면 REVIEW + 이슈 노트 |
| 2단계 검수 | 검수자 (1차) | PASS, EDITED, REVIEW | 전수 검수 — 정상 PASS / 수정 EDITED / 애매 REVIEW |
| 3단계 교차검수 | 2차 검수자 | PASS, EDITED, REVIEWED | 1차 결과 최종 확인 — 정상 REVIEWED / 수정 EDITED |

- 2차 검수자는 **1차 검수자와 다른 사람**이어야 REVIEWED 를 줄 수 있습니다 (프로그램이 막음).
- REVIEW 는 추측하지 않고 다음 단계에서 판단합니다. **REVIEW 최종 판단은 2차 검수자**가 합니다.
- 수정(EDITED) 때 이슈 노트는 선택, REVIEW 때는 필수입니다.

### 팀 구성

| 담당 | 이름 | 개발 파트 (Git 브랜치) |
|---|---|---|
| 팀장 (PM) | Jihoo2 | ① 기반·설정·로그인·문서 (`feature/base`) |
| 팀원 | [이름] | ② 메인 화면 (`feature/ui-layout`) |
| 팀원 | [이름] | ③ 캔버스·HUD (`feature/canvas`) |
| 팀원 | [이름] | ④ BBox·파일 입출력 (`feature/bbox-io`) |
| 팀원 | [이름] | ⑤ 검수·Validation (`feature/review-validation`) |

| 검수 역할 | 이름 |
|---|---|
| 작업자 | [이름], [이름] |
| 검수자 (1차) | [이름], [이름] |
| 2차 검수자 | [이름] |

---

## 3. 저장 위치

| 구분 | 위치 | 내용 |
|---|---|---|
| RAW | `이물검출_학습데이터1/`, `이물검출_학습데이터2/` | 원본 이미지 + 받아온 TXT (수정 금지) |
| WORK | `작업자/`, `작업자/review/` | 작업자 결과 (이미지 복사본 + TXT + `label_status.csv`) |
| WORK | `검수자/pass·edited·review/` | 1차 검수 결과 |
| WORK | `2차검수자/pass·edited·reviewed/` | 2차 검수 결과 |
| FINAL | `data/final/images/`, `data/final/labels/` | QA 완료 데이터 (`tools/build_final.py` 로 2차 검수 결과에서 생성) |

- 각 단계 폴더의 `label_status.csv` 에 이미지별 상태·작업자·검수자·노트·원본 폴더(`source`)가 기록됩니다.
- **FINAL 기준**: 2차 검수 PASS / EDITED / REVIEWED → FINAL. 미해결 REVIEW·검수 대기는 제외.

---

## 4. Git 작업 기준

```text
기능 하나 구현 → 직접 실행 → 정상 동작 확인 → Commit → 다음 기능
```

| 규칙 | 내용 |
|---|---|
| 브랜치 | 파트별 `feature/*` 브랜치에서 작업, Pull Request 후 `main` 에 merge (Create a merge commit) |
| 커밋 메시지 | `feat` 기능 · `fix` 버그 · `docs` 문서 · `chore` 설정 · `refactor` 구조 + `(영역)` |
| 예시 | `feat(canvas): 박스 테두리를 잡아 한 방향 크기 조절` / `fix(io): 저장 결과 보기 중 썸네일 복귀` |
| 금지 | `update`, `수정`, `최종` 처럼 무엇을 바꿨는지 알 수 없는 메시지 |
| 올리지 않는 것 | 이미지·라벨 데이터(RAW·WORK·FINAL), `.venv/`, `__pycache__/`, `*Zone.Identifier` |
| merge 순서 | 다른 파트 함수를 쓰는 변경은 **쓰이는 쪽을 먼저** merge (예: ① 설정 → ⑤ 검수 → ④ 입출력 → ② 화면) |

---

## 5. 프로젝트 완료 기준

다음을 모두 만족하면 교과 7 작업이 완료된 것으로 봅니다. (`reports/qa_summary.md` 5장에서 자동 확인)

```text
900장 전체 검수 완료 (2차 검수까지)
미처리 REVIEW: 0건
Validation 오류: 0건
이미지와 TXT Pair 확인 완료
FINAL 데이터 정리 완료 (data/final/ 900장)
```
