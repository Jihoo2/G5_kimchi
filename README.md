# AI Campus 교과 7 — 조각김치 이물검출 YOLO 라벨링 도구 (tkinter)

## 1. 프로젝트 소개
조각김치 이물검출용 이미지 900장과 기존 YOLO TXT 를 불러와 BBox·Class 를 확인·수정하고,
작업자 → 검수자 → 2차 검수자 3단계 검수를 거쳐 **교과 8 객체검출 학습용 FINAL 데이터**를 만드는 프로젝트입니다.

## 2. 주요 기능
- 이미지 폴더 열기, 같은 이름의 기존 YOLO TXT 자동 Load, Class 별 색상 표시
- BBox 추가(드래그 → Enter 확정) · 이동 · 모서리/테두리 크기 조절 · 삭제, Ctrl/Alt + 방향키 미세 조절
- Class 변경(숫자키 0~6), Undo / Redo (Ctrl+Z / Ctrl+Shift+Z)
- 4K 이미지 Zoom / Pan / Fit, Tab 으로 박스 순서 선택 + 시점 이동
- 역할 3개(작업자 / 검수자 / 2차 검수자)와 상태(PASS / EDITED / REVIEW / REVIEWED) 관리, 검수 규칙 자동 확인
- YOLO TXT 저장 및 Reload, 라벨 완료 목록에서 저장 결과 보기
- Validation 11개 항목 (Pair·형식·Class·좌표·크기·경계·중복·Empty Label)
- 산출물 자동 생성 스크립트 (`tools/`): FINAL 데이터, Manifest, QA Summary, Test Report, Handoff

## 3. 문서와 산출물 위치
| 산출물 | 위치 |
|---|---|
| 1. 라벨링 프로그램 | `main.py`, `src/`, `configs/` |
| 2. 소스코드 / Git 이력 | 이 저장소, `reports/git_commit_history.txt` |
| 3. FINAL YOLO 데이터 | `data/final/images`, `data/final/labels` (Git 제외), 증빙 `evidence/` |
| 4. Project Baseline | `docs/project_baseline.md` |
| 5. Class 기준서 | `docs/class_guide.md` |
| 6. BBox 기준서 | `docs/bbox_guide.md` |
| 7. Dataset Manifest | `manifests/dataset_manifest.csv` |
| 8. QA Summary | `reports/qa_summary.md` |
| 9. Test Report | `reports/test_report.md` |
| 10. README | `README.md` |
| 11. 교과 8 Handoff | `docs/subject08_handoff.md` |
| 산출물 제출 안내 | `docs/deliverables_guide.md` |
| 기능별 의사 코드 | `docs/의사코드.md` |

## 설치 (WSL Ubuntu)
```bash
sudo apt update
sudo apt install -y python3-tk python3-venv fonts-nanum
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 실행
```bash
source .venv/bin/activate
python3 main.py
```

## 설정 (코드 수정 없이 변경)
- `configs/classes.yaml` — 클래스 번호·이름·색상·사용 여부
- `configs/settings.yaml` — 저장 위치, 폴더 이름, 이미지 복사 여부, 썸네일·줌·Undo, 폰트

## 라벨 표시 규칙
**연 폴더 안의 이미지와, 그 폴더 안에 있는 같은 이름의 txt만 보여줍니다.** (작업자·검수자 공통)

| 연 폴더 | 보이는 라벨 |
|---|---|
| 원본 폴더 | 원본 폴더의 txt (받아온 라벨) |
| `작업자/` | 작업자가 저장한 라벨 |
| `작업자/review/` | 작업자가 REVIEW로 저장한 라벨 |

- 원본에서 작업하고 저장해도 원본 폴더는 원래 모습 그대로 보이고, 결과는 `작업자/` 폴더를 열면 보입니다.
- 원본 폴더에서는 저장된 작업 기록(상태 배지, 작업자 이름, Scene, Note)도 표시하지 않습니다. 검수자는 `작업자/` 폴더를 열어 검수합니다.
- 오른쪽 **라벨 완료 이미지** 목록을 클릭하면, 연 폴더를 바꾸지 않고 내가 저장한 결과(예: `검수자/pass/` 의 이미지 + txt)를 바로 볼 수 있습니다.
- 이미 저장한 이미지를 원본 폴더에서 다시 저장하려 하면 덮어쓰기 확인 창이 뜹니다. 이전 작업을 고칠 때는 `작업자/` 폴더를 여세요.

## 저장 위치 (원본 이미지는 수정하지 않음)
`작업자/`, `검수자/`는 **프로젝트 최상위 폴더(main.py 위치)**에 하나씩 만들고, 결과를 그 안에 바로 저장합니다.
```
kimchi_labeler/                  ← 최상위 (main.py 위치)
  ├─ 이물검출_학습데이터1/         이미지 (+ 받아온 *.txt) — 수정하지 않음
  ├─ 작업자/                       이미지 복사본 + TXT + label_status.csv
  │    ├─ 이슈노트/                작업자 Issue/Note 메모 (<이미지이름>.txt)
  │    └─ review/                  작업자 REVIEW: 이미지 복사본 + TXT + <이미지이름>_리뷰노트.txt
  ├─ 검수자/                       label_status.csv
  │    ├─ pass/  edited/  review/          이미지 복사본 + TXT (1차 검수)
  └─ 2차검수자/                    label_status.csv
       ├─ pass/  edited/  reviewed/        이미지 복사본 + TXT (2차 검수 = FINAL 원천)
```
- 어느 이미지 폴더의 결과인지 `label_status.csv` 의 `source` 칸에 기록 → 다른 폴더에 같은 이름의 이미지가 있어도 결과가 섞이지 않음
- 같은 이름의 다른 폴더 결과를 덮어쓰게 되면 저장 전에 확인 창이 뜸
- 작업자가 Issue/Note 에 적은 내용은 `작업자/이슈노트/<이미지이름>.txt` 로도 저장 (메모장으로 열림, Note 를 비우고 저장하면 삭제)
- 작업자가 REVIEW 로 저장하면 `작업자/review/` 에 이미지 + 라벨 + `<이미지이름>_리뷰노트.txt` 저장 (다시 EDITED 로 저장하면 `작업자/` 로 이동)
- 작업자로 폴더를 열면 **미완료 이미지만** 목록에 표시 (이미 저장한 이미지는 '라벨 완료 이미지' 목록에서 열거나 '미완료만 보기' 버튼을 눌러 전체 보기)
- 위치 변경: `configs/settings.yaml` 의 `output`, 이슈노트 폴더 이름은 `issue_note_dir`
- 이미지 폴더를 프로젝트 안에 둘 경우 `.gitignore` 에 추가해 GitHub에 올라가지 않게 할 것

## 검수 절차 (역할 3개)
| 역할 | 선택 가능 | 저장 위치 |
|---|---|---|
| 작업자 | EDITED, REVIEW (REVIEW 는 이슈 노트 필수) | `작업자/`, `작업자/review/` |
| 검수자 (1차) | PASS, EDITED, REVIEW | `검수자/<상태>/` |
| 2차 검수자 | PASS, EDITED, REVIEWED | `2차검수자/<상태>/` |

- EDITED 는 검수자·2차 검수자 모두 이슈 노트 없이 저장 가능
- REVIEWED 는 2차 검수자만, 1차 검수 기록이 있는 이미지에 대해 1차 검수자와 다른 사람이 선택
- `label_status.csv` 에 assignee(작업자) / reviewer(1차) / reviewer2(2차) 이름이 남음

## 구조
기능별 의사 코드와 "어디를 고치면 되는지"는 **docs/의사코드.md** 참고.
```
main.py              실행만
configs/             classes.yaml, settings.yaml
src/
  config.py          YAML → 상수
  auth/              login.py, logout.py
  ui/                main_window.py, layout.py, canvas.py, thumbnails.py, panels.py,
                     file_actions.py, navigation.py, shortcuts.py, theme.py, widgets.py
  bbox/              bbox_model.py, bbox_manager.py, bbox_editor.py
  yolo/              yolo_loader.py, yolo_writer.py
  review/            workspace.py, status_store.py, review_rules.py, review_filters.py
  validation/        validator.py, validation_dialog.py
  common/            fileio.py
tools/               산출물 생성 스크립트 (merge_collected, make_all, build_final, build_manifest, qa_summary,
                     test_report, build_handoff, export_evidence, export_git_history.sh)
docs/                project_baseline, class_guide, bbox_guide, subject08_handoff, deliverables_guide, 의사코드
manifests/           dataset_manifest.csv
reports/             qa_summary.md, test_report.md, git_commit_history.txt
data/final/          FINAL 이미지·라벨 (Git 제외)
```

## 산출물 자동 생성 (검수 완료 후)
```bash
source .venv/bin/activate
python3 tools/merge_collected.py 수집 # (팀원별 컴퓨터에서 검수했을 때) 결과 합치기 → data/merged/
python3 tools/make_all.py            # FINAL → Manifest → QA → Test → Handoff → 증빙
bash tools/export_git_history.sh     # Git 커밋 이력 TXT
```
원본·결과 폴더는 읽기만 하고 수정하지 않습니다. 자세한 내용은 `docs/deliverables_guide.md`.

## YOLO Label 형식
```
class_id x_center y_center width height     (이미지 크기 대비 0~1 비율, 소수 6자리)
```
박스가 없는 이미지는 빈 TXT (배경 이미지). Class 정보는 `configs/classes.yaml`, 판단 기준은 `docs/class_guide.md`.

## 데이터 보안 · 주의사항
- 이미지·라벨 데이터(원본, `작업자/`, `검수자/`, `2차검수자/`, `data/`, `evidence/`)는 **Git 에 올리지 않습니다** (`.gitignore`).
- 원본 이미지·받아온 TXT 는 수정하지 않습니다. 모든 결과는 역할별 결과 폴더와 `data/final/` 에만 저장됩니다.
- Windows 에서 복사한 파일의 `*Zone.Identifier` 는 커밋 전에 삭제합니다: `find . -name "*Zone.Identifier" -delete`
- 새 터미널마다 `source .venv/bin/activate` 를 먼저 실행합니다 (`No module named 'PIL'` 오류 방지).
