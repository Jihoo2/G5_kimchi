"""[카테고리] 설정 — configs/*.yaml 을 읽어서 프로그램 전체가 쓰는 상수로 제공

    configs/classes.yaml    클래스 번호·이름·색상·사용 여부        ← 팀원이 수정하는 곳
    configs/settings.yaml   저장 폴더, 이미지 복사, 화면 옵션, 폰트  ← 팀원이 수정하는 곳
    이 파일                  YAML 값 → 상수 변환 + 코드와 묶인 고정값(상태, 역할, 색상)

다른 파일에서는 `from src import config as C` 후 `C.CLASS_NAMES` 처럼 사용한다.

의사 코드
    classes.yaml 읽기 → id 가 0부터 빈 번호 없이 이어지는지 확인 (아니면 바로 오류)
    settings.yaml 읽기 → 저장 위치·폴더 이름·복사 옵션·화면 옵션 상수 생성
    output_root 가 상대 경로면 프로젝트 폴더(main.py 위치) 기준으로 변환
"""
import os

import yaml

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # main.py 가 있는 폴더
CONFIG_DIR = os.path.join(PROJECT_DIR, "configs")
APP_DIR = PROJECT_DIR


def _load_yaml(name: str) -> dict:
    """configs/<name> 읽기. 파일이 없거나 문법이 틀리면 원인을 알려주는 오류"""
    path = os.path.join(CONFIG_DIR, name)
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        raise SystemExit(f"[설정 오류] {path} 파일이 없습니다.") from None
    except yaml.YAMLError as e:
        raise SystemExit(f"[설정 오류] {path} 형식이 잘못됐습니다.\n{e}") from None


_classes_cfg = _load_yaml("classes.yaml")
_settings = _load_yaml("settings.yaml")
_view = _settings.get("view", {})
_folders = _settings.get("folders", {})
_copy = _settings.get("copy_image", {})

# ================================================================ 기본
APP_TITLE = _settings.get("app_title", "조각김치 이물검출 라벨링 도구")
IMAGE_EXTS = tuple(e.lower() for e in _settings.get("image_exts", [".jpg", ".jpeg", ".png", ".bmp"]))
STATUS_CSV_NAME = _settings.get("status_csv", "label_status.csv")
ISSUE_NOTE_DIR = _settings.get("issue_note_dir", "이슈노트")    # 작업자/<이 폴더>/<이미지이름>.txt
WORKER_REVIEW_DIR = _settings.get("worker_review_dir", _settings.get("review_note_dir", "review"))
#   작업자 REVIEW → 작업자/review/ 에 이미지 + 라벨 TXT + <이미지이름>_리뷰노트.txt
REVIEW_NOTE_SUFFIX = _settings.get("review_note_suffix", "_리뷰노트")

# ================================================================ 저장 위치 (원본 폴더는 수정하지 않음)
#   <저장 루트>/작업자/            작업자: 이미지 복사본 + TXT + label_status.csv
#   <저장 루트>/검수자/            label_status.csv
#   <저장 루트>/검수자/<상태>/     pass / edited / review / reviewed  (이미지 복사본 + TXT)
# 저장 루트 = OUTPUT_BASE 기준 폴더 + OUTPUT_PATH (상대 경로) → 실제 계산은 src/review/workspace.py
_output = _settings.get("output", {})
if "output_root" in _settings and not _output:          # 예전 설정 파일 호환 (main.py 폴더 기준)
    _output = {"base": "project", "path": _settings["output_root"]}
OUTPUT_BASE = _output.get("base", "project")            # "project" | "parent" | "image_folder"
OUTPUT_PATH = str(_output.get("path", "."))
OUTPUT_PER_DATASET = bool(_output.get("per_dataset", False)) and OUTPUT_BASE != "image_folder"
if OUTPUT_BASE not in ("parent", "image_folder", "project"):
    raise SystemExit("[설정 오류] configs/settings.yaml 의 output.base 는 parent / image_folder / project "
                     f"중 하나여야 합니다. 현재: {OUTPUT_BASE}")

WORKER_DIR = _folders.get("worker", "작업자")
REVIEWER_DIR = _folders.get("reviewer", "검수자")
REVIEWER2_DIR = _folders.get("reviewer2", "2차검수자")       # 2차 검수자 → 2차검수자/<상태>/
STATUS_DIRS = {"PASS": "pass", "EDITED": "edited", "REVIEW": "review", "REVIEWED": "reviewed"}
STATUS_DIRS.update(_folders.get("status", {}))
PASS_DIR, EDITED_DIR = STATUS_DIRS["PASS"], STATUS_DIRS["EDITED"]
REVIEW_DIR, REVIEWED_DIR = STATUS_DIRS["REVIEW"], STATUS_DIRS["REVIEWED"]

COPY_IMAGE_WORKER = bool(_copy.get("worker", True))
COPY_IMAGE_REVIEWER = bool(_copy.get("reviewer", True))                       # 검수자 결과 폴더에 이미지 복사
REVIEWER_NO_IMAGE_STATUSES = tuple(_copy.get("reviewer_no_image_statuses", []))  # 이 상태는 TXT만

# ================================================================ 클래스 (configs/classes.yaml)
CLASSES = [(int(c["id"]), str(c["name"]), str(c["color"]), bool(c.get("enabled", True)))
           for c in _classes_cfg.get("classes", [])]
if [c[0] for c in CLASSES] != list(range(len(CLASSES))):
    raise SystemExit("[설정 오류] configs/classes.yaml 의 id 는 0부터 빈 번호 없이 순서대로 적어야 합니다. "
                     f"현재: {[c[0] for c in CLASSES]}")
CLASS_NAMES = {cid: name for cid, name, _, _ in CLASSES}
CLASS_COLORS = {cid: color for cid, _, color, _ in CLASSES}
ENABLED_CLASSES = [cid for cid, _, _, enabled in CLASSES if enabled]
UNUSED_CLASSES = [cid for cid, _, _, enabled in CLASSES if not enabled]   # Class 4 등
NUM_CLASSES = len(CLASSES)

# ================================================================ 검수 상태 (코드 규칙과 묶여 있어 여기서 관리)
STATUSES = ["PASS", "EDITED", "REVIEW", "REVIEWED"]
STATUS_DESC = {     # 검수 상태 라디오 버튼 툴팁
    "PASS": "[검수자 · 2차 검수자] 기존 BBox·Class 확인, 누락 없음\n"
            "수정했거나 Class 4가 있으면 선택 불가",
    "EDITED": "[작업자 · 검수자 · 2차 검수자] BBox/Class 를 수정·추가·삭제함\n"
              "(박스를 고치면 자동 지정, 이슈 노트 없이 저장 가능)",
    "REVIEW": "[작업자 · 검수자] 애매함 → 추측하지 않음, 애매한 점을 Issue/Note 에 기록\n"
              "(2차 검수자는 선택 불가)",
    "REVIEWED": "[2차 검수자 전용] 1차 검수 결과가 정상임을 확인\n"
                "1차 검수 기록이 있는 이미지만, 1차 검수자와 다른 사람만 가능",
}
# 역할별로 선택할 수 있는 검수 상태 (나머지는 화면에서 비활성화, 저장 시에도 막음)
ROLE_STATUSES = {
    "worker":    ("EDITED", "REVIEW"),             # 작업자
    "reviewer":  ("PASS", "EDITED", "REVIEW"),     # 1차 검수자 — REVIEWED 불가
    "reviewer2": ("PASS", "EDITED", "REVIEWED"),   # 2차 검수자 — REVIEW 불가
}
WORKER_STATUSES = ROLE_STATUSES["worker"]
REVIEWER_ONLY_STATUSES = ("PASS", "REVIEWED")   # (이전 버전 호환) 작업자가 선택할 수 없는 상태
STATUS_COLORS = {"PASS": "#22A33A", "EDITED": "#FB8C00", "REVIEW": "#D93025", "REVIEWED": "#1E6FE8"}

SCENE_TYPES = [     # (CSV 저장 코드, 화면 표시 이름)
    ("kimchi_with_target", "김치+대상"),
    ("normal_kimchi", "정상 김치"),
    ("object_only", "객체 단독"),
    ("need_check", "기타 확인 필요"),
]

# ================================================================ 로그인 역할
ROLE_WORKER = "worker"
ROLE_REVIEWER = "reviewer"          # 1차 검수자
ROLE_REVIEWER2 = "reviewer2"        # 2차 검수자
REVIEW_ROLES = (ROLE_REVIEWER, ROLE_REVIEWER2)    # 검수 화면·규칙을 쓰는 역할
ROLE_LABELS = {ROLE_WORKER: "작업자", ROLE_REVIEWER: "검수자", ROLE_REVIEWER2: "2차 검수자"}

# ================================================================ 화면 · 편집 옵션 (configs/settings.yaml 의 view)
THUMB_W = int(_view.get("thumb_width", 150))
THUMB_H = int(_view.get("thumb_height", 100))
THUMB_CACHE_MAX = int(_view.get("thumb_cache_max", 300))
ZOOM_STEP = float(_view.get("zoom_step", 1.25))
ZOOM_MIN = float(_view.get("zoom_min", 0.05))
ZOOM_MAX = float(_view.get("zoom_max", 30.0))
MIN_BOX_PX = float(_view.get("min_box_px", 3))
UNDO_LIMIT = int(_view.get("undo_limit", 100))
RESIZE_STEP = float(_view.get("resize_step", 0.0005))   # Ctrl/Alt + 방향키 크기 조절 단위 (정규화)

# ================================================================ 화면 색상
COLOR_BG = "#EEF1F6"
COLOR_PANEL = "#FFFFFF"
COLOR_BORDER = "#D8DEE8"
COLOR_ACCENT = "#1E6FE8"
COLOR_ACCENT_DARK = "#1757BD"
COLOR_TEXT = "#1F2937"
COLOR_MUTED = "#6B7280"
COLOR_CANVAS = "#2B2F36"
COLOR_DANGER = "#D93025"
COLOR_SUCCESS = "#22A33A"

# ================================================================ 폰트 (configs/settings.yaml 의 fonts)
_fonts = _settings.get("fonts", {})
FONT_CANDIDATES = list(_fonts.get("ui", ["NanumGothic", "Noto Sans CJK KR", "Malgun Gothic", "DejaVu Sans"]))
MONO_CANDIDATES = list(_fonts.get("mono", ["D2Coding", "DejaVu Sans Mono", "Monospace"]))
