# 조각김치 이물검출 라벨링 도구 (tkinter)

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
- 이미 저장한 이미지를 원본 폴더에서 다시 저장하려 하면 덮어쓰기 확인 창이 뜹니다. 이전 작업을 고칠 때는 `작업자/` 폴더를 여세요.

## 저장 위치 (원본 이미지는 수정하지 않음)
`작업자/`, `검수자/`는 **프로젝트 최상위 폴더(main.py 위치)**에 하나씩 만들고, 결과를 그 안에 바로 저장합니다.
```
kimchi_labeler/                  ← 최상위 (main.py 위치)
  ├─ 이물검출_학습데이터1/         이미지 (+ 받아온 *.txt) — 수정하지 않음
  ├─ 작업자/                       이미지 복사본 + TXT + label_status.csv
  │    ├─ 이슈노트/                작업자 Issue/Note 메모 (<이미지이름>.txt)
  │    └─ review/                  작업자 REVIEW: 이미지 복사본 + TXT + <이미지이름>_리뷰노트.txt
  └─ 검수자/                       label_status.csv
       ├─ pass/  edited/  review/  reviewed/      TXT
```
- 어느 이미지 폴더의 결과인지 `label_status.csv` 의 `source` 칸에 기록 → 다른 폴더에 같은 이름의 이미지가 있어도 결과가 섞이지 않음
- 같은 이름의 다른 폴더 결과를 덮어쓰게 되면 저장 전에 확인 창이 뜸
- 작업자가 Issue/Note 에 적은 내용은 `작업자/이슈노트/<이미지이름>.txt` 로도 저장 (메모장으로 열림, Note 를 비우고 저장하면 삭제)
- 작업자가 REVIEW 로 저장하면 `작업자/review/` 에 이미지 + 라벨 + `<이미지이름>_리뷰노트.txt` 저장 (다시 EDITED 로 저장하면 `작업자/` 로 이동)
- 작업자로 폴더를 열면 **미완료 이미지만** 목록에 표시 (이미 저장한 이미지는 '라벨 완료 이미지' 목록에서 열거나 '미완료만 보기' 버튼을 눌러 전체 보기)
- 위치 변경: `configs/settings.yaml` 의 `output`, 이슈노트 폴더 이름은 `issue_note_dir`
- 이미지 폴더를 프로젝트 안에 둘 경우 `.gitignore` 에 추가해 GitHub에 올라가지 않게 할 것

## 검수 절차
- 작업자: EDITED (기본) / REVIEW (판단이 어렵거나 이슈가 있을 때, Issue/Note 기록 필수 → 검수자 확인 요청)
- 2단계 전수 검수: 정상 → PASS / 오류 → 수정 + 이유 기록 → EDITED / 애매함 → 이유 기록 → REVIEW
- 3단계 100% Cross Review 대상: EDITED, REVIEW였던 이미지, Class 4 발견, Empty Label
  - 정상 → REVIEWED (직전 처리자와 다른 검수자만)
  - 오류 → 수정 후 EDITED(재수정) → 다시 Review

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
```
