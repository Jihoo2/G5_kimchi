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

## 저장 위치 (원본 이미지 폴더는 수정하지 않음)
```
kimchi_labeler/            ← main.py 가 있는 폴더 (settings.yaml 의 output_root 로 변경 가능)
  ├─ 작업자/               이미지 복사본 + TXT + label_status.csv
  └─ 검수자/               label_status.csv
       ├─ pass/  edited/  review/  reviewed/      TXT
```

## 검수 절차
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
