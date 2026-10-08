"""[산출물 스크립트 공통] 검수 기록(CSV) 읽기, 원본 위치 찾기, 라벨 비교

산출물 스크립트는 화면(tkinter) 없이 실행되며, 라벨링 프로그램과 같은 설정(configs/)을 읽는다.

    ROOT                      프로젝트 최상위 (main.py 위치)
    results_mode()            결과를 data/merged/ (팀원 결과 합본) 또는 프로젝트 결과 폴더에서 읽을지
    load_records()            작업자 / 검수자 / 2차검수자 label_status.csv → {파일명: {역할: 행}}
    label_path()              역할·상태별 결과 TXT 경로
    final_decision(rec)       이 이미지가 FINAL 인지, 어느 폴더의 결과를 쓰는지
    RawIndex                  원본 이미지·원본(받아온) TXT 위치 찾기
    read_boxes(txt)           YOLO TXT → [(cls, cx, cy, w, h)]
    compare_boxes(a, b)       원본 vs FINAL 비교 → 추가 / 삭제 / Class 변경 / 위치 수정 / 그대로
"""
from __future__ import annotations

import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import config as C                       # noqa: E402  (프로그램과 같은 설정 사용)

ROLES = ("worker", "reviewer", "reviewer2")
ROLE_DIRS = {"worker": C.WORKER_DIR, "reviewer": C.REVIEWER_DIR, "reviewer2": C.REVIEWER2_DIR}
ROLE_LABELS = {"worker": "작업자", "reviewer": "검수자(1차)", "reviewer2": "2차 검수자"}

FINAL_DIR = os.path.join(ROOT, "data", "final")
MERGED_DIR = os.path.join(ROOT, "data", "merged")        # tools/merge_collected.py 결과 (팀원 결과를 합친 것)


def results_mode() -> str:
    """검수 결과를 어디서 읽을지
        merged  : data/merged/ (팀원별 컴퓨터 결과를 merge_collected.py 로 합친 경우) — 있으면 우선
        project : 이 프로젝트의 작업자/ · 검수자/ · 2차검수자/ (한 컴퓨터에서 작업한 경우)
    환경 변수 KIMCHI_RESULTS=project 로 강제 지정 가능"""
    forced = os.environ.get("KIMCHI_RESULTS", "")
    if forced in ("merged", "project"):
        return forced
    return "merged" if os.path.isdir(os.path.join(MERGED_DIR, "labels")) else "project"
MANIFEST_PATH = os.path.join(ROOT, "manifests", "dataset_manifest.csv")
REPORTS_DIR = os.path.join(ROOT, "reports")
DOCS_DIR = os.path.join(ROOT, "docs")

# 원본을 찾을 때 건너뛰는 폴더 (결과·코드·환경)
SKIP_DIRS = {C.WORKER_DIR, C.REVIEWER_DIR, C.REVIEWER2_DIR, "data", "manifests", "reports", "docs",
             "src", "tools", "configs", ".venv", "venv", ".git", "__pycache__", "node_modules"}

SPLIT_WORDS = {"train": "train", "training": "train",
               "val": "validation", "valid": "validation", "validation": "validation",
               "test": "test", "testing": "test"}


def rel(path: str) -> str:
    """프로젝트 기준 상대 경로 (화면·문서 표시용)"""
    try:
        return os.path.relpath(path, ROOT)
    except ValueError:
        return path


def is_image(name: str) -> bool:
    return name.lower().endswith(C.IMAGE_EXTS)


def stem(name: str) -> str:
    return os.path.splitext(name)[0]


# ---------------------------------------------------------------- 검수 기록
def read_status_csv(folder: str) -> dict:
    """<folder>/label_status.csv → {파일명: 행(dict)} (없으면 빈 dict)"""
    path = os.path.join(folder, C.STATUS_CSV_NAME)
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["filename"]: r for r in csv.DictReader(f) if r.get("filename")}


def _read_csv(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["filename"]: r for r in csv.DictReader(f) if r.get("filename")}


def merged_label(name: str) -> str:
    return os.path.join(MERGED_DIR, "labels", stem(name) + ".txt")


def load_records() -> dict:
    """{파일명: {"worker": 행 | None, "reviewer": 행 | None, "reviewer2": 행 | None, "_name": 파일명}}
    merged 모드: data/merged/{worker,reviewer,reviewer2}.csv + data/merged/labels/ 의 TXT 이름(이미지 이름은 원본에서 찾음)"""
    if results_mode() == "merged":
        tables = {role: _read_csv(os.path.join(MERGED_DIR, f"{role}.csv")) for role in ROLES}
        names = set().union(*[t.keys() for t in tables.values()])
        known = {stem(n) for n in names}
        idx = None
        for t in os.listdir(os.path.join(MERGED_DIR, "labels")):
            if t.endswith(".txt") and stem(t) not in known:          # CSV 기록 없이 TXT 만 있는 이미지
                idx = idx or RawIndex()
                img = next((n for n in idx.images if stem(n) == stem(t)), stem(t) + ".jpg")
                names.add(img)
    else:
        tables = {role: read_status_csv(os.path.join(ROOT, d)) for role, d in ROLE_DIRS.items()}
        names = set().union(*[t.keys() for t in tables.values()])
    out = {}
    for n in sorted(names):
        rec = {role: tables[role].get(n) for role in ROLES}
        rec["_name"] = n
        out[n] = rec
    return out


def status_of(rec: dict, role: str) -> str:
    row = rec.get(role)
    return (row or {}).get("status", "") or ""


def result_dir(role: str, status: str) -> str:
    """그 역할·상태로 저장된 결과 폴더"""
    base = os.path.join(ROOT, ROLE_DIRS[role])
    if role == "worker":
        return os.path.join(base, C.WORKER_REVIEW_DIR) if status == "REVIEW" else base
    return os.path.join(base, C.STATUS_DIRS.get(status, ""))


def label_path(name: str, role: str, status: str):
    """그 역할·상태 결과의 TXT 경로 (merged 모드면 모은 TXT)"""
    if role == "merged" or (results_mode() == "merged" and role):
        return merged_label(name)
    return os.path.join(result_dir(role, status), stem(name) + ".txt") if role else None


def final_decision(rec: dict):
    """(FINAL 여부, 사용할 역할, 상태, 제외 사유)
    FINAL 기준 (docs/project_baseline.md 와 같음)
        1) 2차 검수 기록이 있으면 → 2차 검수 결과 (PASS / EDITED / REVIEWED 모두 확정본)
        2) 2차 기록이 없고, 1차 검수가 REVIEWED (예전 방식의 교차검수 완료) → 1차 결과
        3) 그 외 → FINAL 아님 (WAIT)"""
    s2 = status_of(rec, "reviewer2")
    if results_mode() == "merged":
        # 합친 결과: 모은 2차 검수 TXT 가 있으면 FINAL (상태는 2차 CSV 기록, 없으면 '기록 없음')
        if os.path.isfile(merged_label(rec.get("_name", ""))):
            return True, "merged", s2 or "기록 없음", ""
        if status_of(rec, "reviewer") == "REVIEW" or (status_of(rec, "worker") == "REVIEW"
                                                       and not status_of(rec, "reviewer")):
            return False, "", "", "미해결 REVIEW"
        return False, "", "", "2차 검수 TXT 없음"
    if s2 in ("PASS", "EDITED", "REVIEWED"):
        return True, "reviewer2", s2, ""
    s1 = status_of(rec, "reviewer")
    if s1 == "REVIEWED":
        return True, "reviewer", s1, ""
    if s1 == "REVIEW" or status_of(rec, "worker") == "REVIEW" and not s1:
        return False, "", "", "미해결 REVIEW"
    if s1:
        return False, "", "", "2차 검수 대기"
    if status_of(rec, "worker"):
        return False, "", "", "1차 검수 대기"
    return False, "", "", "작업 기록 없음"


def source_of(rec: dict) -> str:
    """이 이미지가 어느 원본 폴더에서 왔는지 (가장 먼저 기록한 단계의 source)"""
    for role in ROLES:
        s = (rec.get(role) or {}).get("source", "")
        if s:
            return s
    return ""


def split_dataset(source: str, image_path: str = ""):
    """(source_dataset, original_split)
    source_dataset = 원본 경로의 첫 폴더 (예: 이물검출_학습데이터1)
    original_split = 경로 안의 train / val(idation) / test 폴더 이름, 없으면 unknown"""
    path = source or (rel(os.path.dirname(image_path)) if image_path else "")
    parts = [p for p in path.replace("\\", "/").split("/") if p and p != "."]
    dataset = parts[0] if parts else "unknown"
    split = "unknown"
    for p in reversed(parts):
        if p.lower() in SPLIT_WORDS:
            split = SPLIT_WORDS[p.lower()]
            break
    return dataset, split


# ---------------------------------------------------------------- 원본 위치
class RawIndex:
    """프로젝트 안의 원본 이미지 위치 색인 (결과 폴더·코드 폴더는 제외)"""

    def __init__(self):
        self.images: dict[str, list[str]] = {}
        for dirpath, dirnames, filenames in os.walk(ROOT):
            if dirpath == ROOT:
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            for fn in filenames:
                if is_image(fn):
                    self.images.setdefault(fn, []).append(os.path.join(dirpath, fn))

    def image(self, name: str, source: str = ""):
        """원본 이미지 경로 (source 가 있으면 그 폴더를 우선)"""
        if source:
            p = os.path.join(ROOT, source, name) if not os.path.isabs(source) else os.path.join(source, name)
            if os.path.isfile(p):
                return p
        cands = self.images.get(name, [])
        return cands[0] if cands else None

    @staticmethod
    def raw_label(image_path: str):
        """받아온 원본 TXT: 이미지와 같은 폴더 → YOLO 구조(images/… → labels/…) 순서로 찾음"""
        if not image_path:
            return None
        txt = stem(os.path.basename(image_path)) + ".txt"
        folder = os.path.dirname(image_path)
        cands = [os.path.join(folder, txt)]
        parts = folder.split(os.sep)
        for i in range(len(parts) - 1, -1, -1):
            if parts[i].lower() == "images":
                p2 = parts[:]
                p2[i] = "Labels" if parts[i] == "Images" else "labels"
                cands.append(os.path.join(os.sep.join(p2) or os.sep, txt))
                break
        return next((c for c in cands if os.path.isfile(c)), None)


# ---------------------------------------------------------------- 라벨 비교
def read_boxes(txt: str | None):
    """YOLO TXT → [(cls, cx, cy, w, h)], 읽을 수 없는 줄은 건너뜀"""
    out = []
    if not txt or not os.path.isfile(txt):
        return out
    with open(txt, encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.split()
            if len(p) != 5:
                continue
            try:
                out.append((int(p[0]), *map(float, p[1:])))
            except ValueError:
                pass
    return out


def iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a[1] - a[3] / 2, a[2] - a[4] / 2, a[1] + a[3] / 2, a[2] + a[4] / 2
    bx1, by1, bx2, by2 = b[1] - b[3] / 2, b[2] - b[4] / 2, b[1] + b[3] / 2, b[2] + b[4] / 2
    iw, ih = max(0.0, min(ax2, bx2) - max(ax1, bx1)), max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    union = a[3] * a[4] + b[3] * b[4] - inter
    return inter / union if union > 0 else 0.0


def compare_boxes(raw, final, match_iou: float = 0.5, same_iou: float = 0.95):
    """원본 박스와 FINAL 박스를 IoU 로 짝지어 변경 내용 집계
    반환: {"kept", "moved", "class_changed", "added", "removed"} 개수
        kept          같은 Class, IoU ≥ 0.95 (사실상 그대로)
        moved         같은 Class, 0.5 ≤ IoU < 0.95 (위치·크기 수정)
        class_changed IoU ≥ 0.5 인데 Class 가 다름
        added         FINAL 에만 있음 (누락 객체 추가)
        removed       원본에만 있음 (잘못된 박스 삭제)"""
    pairs = sorted(((iou(r, f), i, j) for i, r in enumerate(raw) for j, f in enumerate(final)),
                   reverse=True)
    used_r, used_f = set(), set()
    res = {"kept": 0, "moved": 0, "class_changed": 0, "added": 0, "removed": 0}
    for v, i, j in pairs:
        if v < match_iou:
            break
        if i in used_r or j in used_f:
            continue
        used_r.add(i)
        used_f.add(j)
        if raw[i][0] != final[j][0]:
            res["class_changed"] += 1
        elif v >= same_iou:
            res["kept"] += 1
        else:
            res["moved"] += 1
    res["removed"] = len(raw) - len(used_r)
    res["added"] = len(final) - len(used_f)
    return res


def class_name(cid: int) -> str:
    return C.CLASS_NAMES.get(cid, f"알 수 없음({cid})")


def write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
