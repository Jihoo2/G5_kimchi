# 교과 7 산출물 제출 안내 — G5 조각김치 이물검출

11개 공식 산출물이 **어디에 있고, 어떻게 만들고, 무엇을 제출하는지** 정리한 문서입니다.
라벨링 프로그램 완성 + 900장 작업·1차 검수·2차 검수 완료 상태를 기준으로 합니다.

---

## 0. 한 번에 만들기

### 팀원들이 각자 컴퓨터에서 검수한 경우 (먼저 합치기)

1. 프로젝트 안에 `수집/` 폴더를 만들고 팀원들의 결과를 넣습니다. 하위 폴더 구조는 자유입니다 (팀원별 폴더 권장).
   - 2차 검수를 마친 YOLO TXT (`2차검수자/pass·edited·reviewed/` 안의 `<이름>.txt`)
   - 각 팀원의 `label_status.csv` (작업자 / 검수자 / 2차검수자 폴더의 것, 한 파일로 합쳐 둔 CSV 도 가능)
   - 이미지는 넣지 않아도 됩니다 (원본 폴더에서 찾음). 이슈노트 TXT 는 넣어도 자동으로 제외됩니다.
2. 합치고 산출물을 만듭니다.

```bash
cd ~/kimchi_labeler
source .venv/bin/activate
python3 tools/merge_collected.py 수집     # → data/merged/ (합친 TXT·CSV) + merge_report.txt
python3 tools/make_all.py                 # data/merged/ 를 자동으로 사용
bash tools/export_git_history.sh
```

`merge_collected.py` 가 출력하는 보고서에서 **충돌(같은 이름인데 내용이 다른 TXT)**, **원본 이미지를 못 찾은 TXT**, **2차 CSV 기록 없는 TXT** 가 모두 0 인지 확인합니다.

### 한 컴퓨터에서 모두 작업한 경우

```bash
python3 tools/make_all.py            # 프로젝트의 작업자/ · 검수자/ · 2차검수자/ 를 그대로 읽음
bash tools/export_git_history.sh
```

| 순서 | 스크립트 | 만드는 것 | 산출물 |
|---:|---|---|---|
| 0 | `tools/merge_collected.py` | `data/merged/` (팀원 결과 합본) | — |
| 1 | `tools/build_final.py` | `data/final/images`, `data/final/labels`, `final_list.csv` | 3 |
| 2 | `tools/build_manifest.py` | `manifests/dataset_manifest.csv` | 7 |
| 3 | `tools/qa_summary.py` | `reports/qa_summary.md` | 8 |
| 4 | `tools/test_report.py` | `reports/test_report.md` | 9 |
| 5 | `tools/build_handoff.py` | `docs/subject08_handoff.md` | 11 |
| 6 | `tools/export_evidence.py` | `evidence/final_structure.txt`, `evidence/samples/` | 3 증빙 |
| — | `tools/export_git_history.sh` | `reports/git_commit_history.txt`, `git_change_history.txt` | 2 증빙 |

- 원본 이미지·받아온 TXT, `작업자/`·`검수자/`·`2차검수자/` 는 **읽기만** 합니다. 몇 번을 다시 실행해도 됩니다.
- 출력 마지막 줄이 **`QA 완료`** 여야 합니다. `QA 미완료` 면 `reports/qa_summary.md` 5장의 ❌ 항목과 제외 목록을 처리한 뒤 다시 실행합니다.
- 숫자(수량·오류·수정 건수·Class 분포)는 모두 실제 결과 폴더에서 계산되므로 손으로 고치지 않습니다.

---

## 1. 산출물별 제출 내용

### 🔴 P1 — 교과 8 직결 (60점)

| 번호 | 산출물 | 제출 | 만드는 방법 | 직접 할 일 |
|---:|---|---|---|---|
| 3 | FINAL YOLO 데이터 및 증빙 (25) | `final/` 구조·수량 캡처, 대표 이미지 3~5장, 대표 TXT 2~3개 | `make_all.py` → `evidence/` | `evidence/` 내용 확인·캡처 (아래 2장) |
| 5 | Class 기준서 (10) | `docs/class_guide.md` | 작성 완료 | 팀 기준과 다른 부분 수정 |
| 7 | Dataset Manifest (12) | `manifests/dataset_manifest.csv` | `make_all.py` | `original_split` 확인 (아래 3장) |
| 8 | QA Summary (13) | `reports/qa_summary.md` | `make_all.py` | 최종 판정 `QA 완료` 확인 |

### 🟠 P2 — 핵심·품질 보완 (25점)

| 번호 | 산출물 | 제출 | 만드는 방법 | 직접 할 일 |
|---:|---|---|---|---|
| 1 | 라벨링 프로그램 (12) | 프로그램 전체, 실행 화면 캡처 2~3장, 시연 영상 | 완성 | 캡처·영상 (아래 2장) |
| 6 | BBox 기준서 (7) | `docs/bbox_guide.md` | 작성 완료 | (선택) GOOD / BAD 예시 이미지 1~2장 추가 |
| 11 | 교과 8 Handoff (6) | `docs/subject08_handoff.md` | `make_all.py` | 데이터 전달 위치 기입 |

### 🟡 P3 — 문서·재현·증빙 (15점)

| 번호 | 산출물 | 제출 | 만드는 방법 | 직접 할 일 |
|---:|---|---|---|---|
| 2 | 소스코드 (7) | Git 저장소 (`main.py`, `src/`, `configs/classes.yaml`, `requirements.txt`), 커밋 이력 | `export_git_history.sh` | 팀원 브랜치 `main` merge 후 이력 추출, (선택) VS Code 구조 캡처 |
| 9 | Test Report (4) | `reports/test_report.md` | `make_all.py` | 4장 화면 체크리스트 ☐ → ☑ (시연하면서) |
| 10 | README (2) | `README.md` | 작성 완료 | — |
| 4 | Project Baseline (2) | `docs/project_baseline.md` | 작성 완료 | `[이름]` 칸 채우기 |

---

## 2. 캡처·시연 가이드

### 1번 — 실행 화면 캡처 (2~3장)

| 캡처 | 화면 | 만드는 방법 |
|---|---|---|
| 캡처 1 | 기존 YOLO BBox 가 Load 된 화면 | 원본 폴더 열기 → 박스가 여러 개 있는 이미지 → 하단 `BBox n개 불러옴 (출처: 원본)` 이 보이게 |
| 캡처 2 | BBox·Class 를 수정한 화면 | 박스 선택 → 숫자키로 Class 변경 또는 테두리 드래그 → 상태 EDITED, HUD 가 보이게 |
| 캡처 3 | 저장 + Validation 결과 | 저장 후 툴바 `✓ Validation` → 결과 창(항목별 건수) |

### 1번 — 시연 영상 (1~2분)

```
① 로그인 (역할 선택)
② 폴더 열기 → 기존 BBox 확인
③ BBox 하나 추가 (드래그 → Enter → 숫자키 Class)
④ 기존 BBox 하나 수정 (테두리 드래그 또는 Ctrl/Alt + 방향키)
⑤ Ctrl+S 저장 → 다음 이미지 이동
⑥ 라벨 완료 목록에서 방금 이미지 클릭 → 수정한 BBox 복원 확인
⑦ Validation 실행 → 결과 창 확인
```
WSL 화면 녹화는 Windows `Win + Alt + R` (Xbox Game Bar) 또는 `Win + Shift + S` → 녹화를 사용하면 됩니다.

### 3번 — FINAL 증빙

| 증빙 | 파일 |
|---|---|
| `final/` 폴더 구조 | `evidence/final_structure.txt` 내용 또는 Windows 탐색기 `\\wsl$\Ubuntu\home\user1\kimchi_labeler\data\final` 캡처 |
| 이미지 900장 | 탐색기에서 `data/final/images` 열고 하단 "항목 900개" 가 보이게 캡처 |
| TXT 900개 | `data/final/labels` 같은 방식 |
| 대표 이미지 3~5장 | `evidence/samples/*_bbox.jpg` (BBox·Class 표시됨) |
| 대표 TXT 2~3개 | `evidence/samples/*.txt` (위 이미지와 같은 이름) |

---

## 3. 확인이 필요한 부분

| 항목 | 내용 |
|---|---|
| `original_split` | 원본 경로에 `train` / `val` / `test` 폴더가 있으면 자동으로 채워집니다. 폴더 구분 없이 이미지만 있는 데이터셋은 `unknown` 으로 남습니다. 원래 Split 정보가 따로 있다면 알려주세요. 그 기준으로 채우도록 바꿀 수 있습니다. |
| `status` 판정 | DONE / EDITED 는 **원본 TXT 와 FINAL TXT 를 직접 비교**해서 정합니다 (박스 추가·삭제·Class 변경·위치 변경이 있으면 EDITED). 단계별 저장 상태는 `worker_status`, `reviewer1_status`, `reviewer2_status` 칸에 따로 남습니다. |
| FINAL 기준 | 2차 검수 PASS / EDITED / REVIEWED 를 FINAL 로 봅니다. 2차 검수자의 EDITED 는 2차 검수자가 직접 확정한 수정본으로 봅니다 (`docs/project_baseline.md`). |
| 같은 이름 이미지 | 서로 다른 원본 폴더에 같은 파일명이 있으면 결과 폴더에서 한쪽이 덮어써졌을 수 있습니다. 이때 `data/final` 수량이 900 보다 적게 나오므로 QA Summary 에서 바로 드러납니다. |

---

## 4. Git 에 올리는 것 / 올리지 않는 것

| 올림 | 올리지 않음 |
|---|---|
| `main.py`, `src/`, `configs/`, `tools/`, `requirements.txt` | 원본 이미지 폴더, `작업자/`, `검수자/`, `2차검수자/`, `수집/` |
| `docs/*.md`, `README.md` | `data/` (FINAL 이미지·라벨) |
| `manifests/dataset_manifest.csv` (파일명·상태만, 이미지 없음) | `evidence/` (대표 이미지 → LMS 로 제출) |
| `reports/*.md`, `reports/git_*.txt` | `.venv/`, `__pycache__/`, `*Zone.Identifier` |

`.gitignore` 에 아래 줄이 있는지 확인합니다.

```gitignore
.venv/
__pycache__/
*Zone.Identifier
작업자/
검수자/
2차검수자/
수집/
이물검출_학습데이터*/
data/
evidence/
```
