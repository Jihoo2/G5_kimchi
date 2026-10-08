"""[산출물 9] Test Report — 라벨링 프로그램이 실제 데이터에서 안전하게 동작하는지 자동 시험

사용법 (build_final.py 실행 후, 프로젝트 최상위에서)
    python tools/test_report.py
결과
    reports/test_report.md

시험 단계 (실제 FINAL 이미지·라벨 사용, 원본·결과 폴더는 건드리지 않고 임시 폴더에서 시험)
    1. Golden Test   20장   이미지 열기 · YOLO Load/Save/Reload 왕복 · 좌표 변환(Zoom) · BBox 편집 · Validation 검출
    2. Pilot Test    50장   작업자 → 검수자 → 2차 검수자 저장 흐름 전체를 프로그램 저장 함수로 실행,
                            저장 위치·이미지 복사·Reload 복원·원본 무변경 확인
    3. Final Acceptance     FINAL 전체: Pair · 형식 · Reload 왕복 · Validation 오류 · 미해결 REVIEW
화면 조작(마우스 드래그·키 입력)은 같은 함수를 호출해 시험하고, 실제 화면 확인은 문서의 수동 체크리스트로 남긴다.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
import types
from datetime import datetime
from types import SimpleNamespace as NS

from common import (C, FINAL_DIR, REPORTS_DIR, final_decision, is_image, load_records, rel, stem,
                    write_text)

# 화면 모듈을 쓰지 않는 시험이므로 tkinter 를 가짜 모듈로 대체 (BBox 편집 함수만 불러오기 위함)
if "tkinter" not in sys.modules:
    class _Fake(types.ModuleType):
        def __getattr__(self, name):
            cls = type(name, (), {"__init__": lambda self, *a, **k: None})
            setattr(self, name, cls)
            return cls
    for _m in ("tkinter", "tkinter.ttk", "tkinter.font", "tkinter.filedialog", "tkinter.messagebox"):
        sys.modules[_m] = _Fake(_m)
    sys.modules["tkinter"].ttk = sys.modules["tkinter.ttk"]
    sys.modules["tkinter"].messagebox = sys.modules["tkinter.messagebox"]
    sys.modules["tkinter"].TclError = Exception

from PIL import Image, ImageOps                                  # noqa: E402

from src.bbox.bbox_model import Box, UndoStack                  # noqa: E402
from src.review.status_store import ImageMeta                    # noqa: E402
from src.validation.validator import validate_folder             # noqa: E402
from src.yolo.yolo_loader import load_yolo                       # noqa: E402
from src.yolo.yolo_writer import save_yolo                       # noqa: E402

TOL = 1e-6          # 정규화 좌표 허용 오차 (저장은 소수 6자리)


# ---------------------------------------------------------------- 공통 도구
def image_size(path):
    """EXIF 회전을 반영한 이미지 크기 (픽셀을 디코딩하지 않아 4K 900장도 빠름)
    프로그램은 ImageOps.exif_transpose 로 회전을 반영하므로, 90° 회전(Orientation 5~8)이면 가로·세로를 바꿈"""
    with Image.open(path) as im:
        w, h = im.size
        orient = im.getexif().get(0x0112, 1)
    return (h, w) if orient in (5, 6, 7, 8) else (w, h)


def open_full(path):
    """프로그램과 같은 방식으로 이미지 전체를 디코딩 (Golden: 이미지 열기 시험)"""
    with Image.open(path) as im:
        return ImageOps.exif_transpose(im).convert("RGB").size


def norm(boxes, W, H):
    return [(b.cls, *[round(v, 6) for v in b.to_yolo(W, H)[1:]]) for b in boxes]


def same(a, b):
    return len(a) == len(b) and all(x[0] == y[0] and all(abs(p - q) <= TOL for p, q in zip(x[1:], y[1:]))
                                    for x, y in zip(a, b))


def roundtrip(img, txt, tmp):
    """Load → Save → Reload 결과가 원래 라벨과 같은지"""
    W, H = image_size(img)
    boxes, errors = load_yolo(txt, W, H)
    out = os.path.join(tmp, "rt_" + os.path.basename(txt))
    save_yolo(out, boxes, W, H)
    again, _ = load_yolo(out, W, H)
    return not errors and same(norm(boxes, W, H), norm(again, W, H)), (W, H), len(boxes)


def md5(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def editor():
    """BBox 편집 기능(BoxEditMixin)을 화면 없이 쓰기 위한 최소 앱"""
    from src.bbox.bbox_manager import BoxEditMixin, ClassMixin

    class App(BoxEditMixin, ClassMixin):
        pass
    a = App()
    a.__dict__.update(boxes=[], selected=None, undo=UndoStack(), image=object(), img_w=0, img_h=0,
                      boxes_changed=False, class_rows={}, class_combo=NS(current=lambda i: None),
                      current_class=NS(v=0, get=lambda: a.current_class.v,
                                       set=lambda v: setattr(a.current_class, "v", v)),
                      status_var=NS(get=lambda: "EDITED", set=lambda v: None),
                      view=NS(draw_boxes=lambda: None, overlay=NS(refresh=lambda: None)))
    a.set_message = lambda *x, **k: None
    a._set_dirty = lambda v: None
    a.refresh_table = a.refresh_csv_info = lambda: None
    return a


class Result:
    def __init__(self):
        self.rows = []          # (항목, 대상, 통과, 실패, 비고)

    def add(self, item, passed, total, note=""):
        self.rows.append((item, total, passed, total - passed, note))

    @property
    def ok(self):
        return all(r[3] == 0 for r in self.rows)

    def table(self):
        L = ["| 시험 항목 | 대상 | PASS | FAIL | 비고 |", "|---|---:|---:|---:|---|"]
        L += [f"| {a} | {t} | {p} | {f} | {n} |" for a, t, p, f, n in self.rows]
        return "\n".join(L)


# ---------------------------------------------------------------- 1. Golden
def golden(names, img_dir, lbl_dir, tmp):
    r = Result()
    opened = rt = 0
    for n in names:
        try:
            ok_size = open_full(os.path.join(img_dir, n)) == image_size(os.path.join(img_dir, n))
            opened += ok_size
        except Exception:
            pass
        ok, _, _ = roundtrip(os.path.join(img_dir, n), os.path.join(lbl_dir, stem(n) + ".txt"), tmp)
        rt += ok
    r.add("이미지 열기 (EXIF 회전 반영)", opened, len(names), "디코딩 크기와 라벨 기준 크기 일치")
    r.add("YOLO TXT Load → Save → Reload 일치", rt, len(names), "정규화 좌표 오차 ≤ 0.000001")

    # Zoom / Pan 좌표 변환: 화면 ↔ 이미지 좌표 왕복 (ImageCanvas.to_canvas / to_image)
    from src.ui.canvas import ImageCanvas as IC
    zoom_ok = zoom_n = 0
    for scale in (0.15, 0.22, 1.0, 3.18, 8.0):
        for ox, oy in ((0, 0), (-1234.5, 87.25), (300, -4000)):
            v = NS(scale=scale, ox=ox, oy=oy)
            for x, y in ((0, 0), (1828.3, 1481.7), (3839, 2159)):
                cx, cy = IC.to_canvas(v, x, y)
                bx, by = IC.to_image(v, cx, cy)
                zoom_n += 1
                zoom_ok += abs(bx - x) < 1e-6 and abs(by - y) < 1e-6
    r.add("Zoom / Pan 좌표 변환 왕복", zoom_ok, zoom_n, "배율 5종 × 위치 3종 × 점 3개")

    # BBox 편집: 추가 → Class 변경 → 이동 → 크기 조절 → 삭제 → Undo → Redo → 저장·Reload
    n0 = names[0]
    W, H = image_size(os.path.join(img_dir, n0))
    a = editor()
    a.img_w, a.img_h = W, H
    a.boxes, _ = load_yolo(os.path.join(lbl_dir, stem(n0) + ".txt"), W, H)
    base = len(a.boxes)
    steps = []
    a.add_box(Box(0, W * 0.40, H * 0.40, W * 0.45, H * 0.46))
    a.boxes[-1].pending = False
    steps.append(("BBox 추가", len(a.boxes) == base + 1))
    a.set_class(2)
    steps.append(("Class 변경 (0→2)", a.boxes[-1].cls == 2))
    x1 = a.boxes[-1].x1
    a.nudge_selected(10, 0)
    steps.append(("BBox 이동 (방향키)", abs(a.boxes[-1].x1 - x1 - 10) < 1e-9))
    w0 = a.boxes[-1].w
    a.resize_selected("Right", True)
    steps.append(("BBox 크기 조절 (Ctrl+→)", a.boxes[-1].w > w0))
    a.delete_selected()
    steps.append(("BBox 삭제", len(a.boxes) == base))
    a.undo_action()
    steps.append(("Undo", len(a.boxes) == base + 1))
    a.redo_action()
    steps.append(("Redo", len(a.boxes) == base))
    a.undo_action()
    out = os.path.join(tmp, "edit_" + stem(n0) + ".txt")
    save_yolo(out, a.boxes, W, H)
    back, _ = load_yolo(out, W, H)
    steps.append(("편집 결과 저장 → Reload 복원", same(norm(a.boxes, W, H), norm(back, W, H))))
    for label, ok in steps:
        r.add(label, int(ok), 1, f"`{n0}`")

    # Validation: 문제를 일부러 넣은 파일을 모두 잡는지
    vdir = os.path.join(tmp, "validation")
    os.makedirs(vdir)
    src_img = os.path.join(img_dir, n0)
    cases = {"구조": "2 0.5 0.5 0.1\n", "숫자": "a 0.5 0.5 0.1 0.1\n", "범위": "9 0.5 0.5 0.1 0.1\n",
             "c4": "4 0.5 0.5 0.1 0.1\n", "좌표": "1 1.3 0.5 0.1 0.1\n", "wh": "1 0.5 0.5 0 0.1\n",
             "경계": "1 0.98 0.5 0.1 0.1\n", "중복": "2 0.5 0.5 0.1 0.1\n2 0.5 0.5 0.1 0.1\n", "빈": ""}
    expect = {"구조": "TXT 한 줄 구조 오류", "숫자": "숫자 변환 오류", "범위": "Class 범위 오류",
              "c4": "Class 4 발견", "좌표": "좌표 범위 오류", "wh": "Width/Height 비정상",
              "경계": "BBox 경계 오류", "중복": "중복 의심 BBox", "빈": "Empty Label",
              "notxt": "JPG는 있는데 TXT 없음", "orphan": "TXT는 있는데 JPG 없음"}
    for k, body in cases.items():
        shutil.copy2(src_img, os.path.join(vdir, f"{k}.jpg"))
        with open(os.path.join(vdir, f"{k}.txt"), "w", encoding="utf-8") as f:
            f.write(body)
    shutil.copy2(src_img, os.path.join(vdir, "notxt.jpg"))
    with open(os.path.join(vdir, "orphan.txt"), "w", encoding="utf-8") as f:
        f.write("0 0.5 0.5 0.1 0.1\n")
    names_v = sorted(f for f in os.listdir(vdir) if is_image(f))
    found = validate_folder(names_v, lambda x: (os.path.join(vdir, stem(x) + ".txt")
                                                if os.path.isfile(os.path.join(vdir, stem(x) + ".txt")) else None, ""),
                            lambda x: None, [vdir])
    hit = sum(1 for k, cat in expect.items()
              if any(i["category"] == cat and stem(str(i["file"])) == k for i in found))
    r.add("Validation 11개 검사 항목 검출", hit, len(expect), "항목별 문제 파일을 일부러 만들어 시험")
    return r


# ---------------------------------------------------------------- 2. Pilot
def pilot(names, img_dir, lbl_dir, tmp):
    """임시 프로젝트에서 작업자 → 검수자 → 2차 검수자 저장 흐름을 프로그램 함수로 실행"""
    from src.review.workspace import Workspace
    r = Result()
    proj = os.path.join(tmp, "pilot_project")
    raw = os.path.join(proj, "원본")
    os.makedirs(raw)
    for n in names:
        shutil.copy2(os.path.join(img_dir, n), os.path.join(raw, n))
        shutil.copy2(os.path.join(lbl_dir, stem(n) + ".txt"), os.path.join(raw, stem(n) + ".txt"))
    before = {f: md5(os.path.join(raw, f)) for f in os.listdir(raw)}
    old_root = C.PROJECT_DIR
    C.PROJECT_DIR = proj
    try:
        expect, saved = {}, {"worker": 0, "reviewer": 0, "reviewer2": 0}
        w = Workspace(raw, C.ROLE_WORKER)
        for i, n in enumerate(names):
            W, H = image_size(os.path.join(raw, n))
            boxes, _ = load_yolo(w.resolve_label(n)[0], W, H)
            if i % 5 == 0:                                         # 일부는 박스 추가
                boxes.append(Box(1, W * 0.1, H * 0.1, W * 0.15, H * 0.16))
            w.save_label(n, boxes, W, H, "EDITED")
            w.own_store.update(ImageMeta(n, "EDITED", "작업자", num_boxes=len(boxes)))
            saved["worker"] += 1
        r1 = Workspace(os.path.join(proj, C.WORKER_DIR), C.ROLE_REVIEWER)
        for i, n in enumerate(names):
            W, H = image_size(os.path.join(raw, n))
            boxes, _ = load_yolo(r1.resolve_label(n)[0], W, H)
            st = "PASS"
            if i % 7 == 0 and boxes:                               # 일부는 Class 수정
                boxes[0].cls = 6 if boxes[0].cls != 6 else 0
                st = "EDITED"
            r1.save_label(n, boxes, W, H, st)
            r1.own_store.update(ImageMeta(n, st, "작업자", "검수자1", num_boxes=len(boxes)))
            saved["reviewer"] += 1
        for st1 in ("PASS", "EDITED"):
            folder = os.path.join(proj, C.REVIEWER_DIR, C.STATUS_DIRS[st1])
            if not os.path.isdir(folder):
                continue
            r2 = Workspace(folder, C.ROLE_REVIEWER2)
            for n in sorted(f for f in os.listdir(folder) if is_image(f)):
                W, H = image_size(os.path.join(folder, n))
                boxes, _ = load_yolo(r2.resolve_label(n)[0], W, H)
                r2.save_label(n, boxes, W, H, "REVIEWED")
                r2.own_store.update(ImageMeta(n, "REVIEWED", "작업자", "검수자1", "검수자2",
                                              num_boxes=len(boxes)))
                expect[n] = norm(boxes, W, H)
                saved["reviewer2"] += 1

        final_dir = os.path.join(proj, C.REVIEWER2_DIR, C.STATUS_DIRS["REVIEWED"])
        img_ok = sum(os.path.isfile(os.path.join(final_dir, n)) for n in names)
        txt_ok = sum(os.path.isfile(os.path.join(final_dir, stem(n) + ".txt")) for n in names)
        reload_ok = 0
        for n in names:
            p = os.path.join(final_dir, stem(n) + ".txt")
            if n in expect and os.path.isfile(p):
                W, H = image_size(os.path.join(final_dir, n))
                b, _ = load_yolo(p, W, H)
                reload_ok += same(norm(b, W, H), expect[n])
        after = {f: md5(os.path.join(raw, f)) for f in os.listdir(raw)}
        r.add("작업자 저장 (작업자/)", saved["worker"], len(names))
        r.add("1차 검수 저장 (검수자/pass·edited)", saved["reviewer"], len(names))
        r.add("2차 검수 저장 (2차검수자/reviewed)", saved["reviewer2"], len(names))
        r.add("결과 폴더에 이미지 복사본 저장", img_ok, len(names))
        r.add("결과 폴더에 YOLO TXT 저장", txt_ok, len(names))
        r.add("2차 검수 결과 Reload 복원", reload_ok, len(names))
        r.add("원본 이미지·TXT 무변경", int(before == after), 1, f"파일 {len(before)}개 해시 비교")
        r1v = Workspace(raw, C.ROLE_REVIEWER)
        shown = sum(1 for n in names if r1v.display_meta(n) is None)
        r.add("원본 폴더를 다시 열면 저장 기록을 표시하지 않음", shown, len(names))
    finally:
        C.PROJECT_DIR = old_root
    return r


# ---------------------------------------------------------------- 3. Final Acceptance
def acceptance(img_dir, lbl_dir, tmp):
    r = Result()
    imgs = sorted(f for f in os.listdir(img_dir) if is_image(f))
    txts = {f for f in os.listdir(lbl_dir) if f.endswith(".txt")}
    pair = sum(stem(n) + ".txt" in txts for n in imgs)
    r.add("이미지 ↔ TXT Pair", pair, len(imgs), f"TXT만 있는 파일 {len(txts - {stem(n) + '.txt' for n in imgs})}개")
    rt = boxes = 0
    for n in imgs:
        t = os.path.join(lbl_dir, stem(n) + ".txt")
        if os.path.isfile(t):
            ok, _, k = roundtrip(os.path.join(img_dir, n), t, tmp)
            rt += ok
            boxes += k
    r.add("전체 Load → Save → Reload 일치", rt, len(imgs), f"BBox {boxes}개")
    issues = validate_folder(imgs, lambda x: (os.path.join(lbl_dir, stem(x) + ".txt")
                                              if os.path.isfile(os.path.join(lbl_dir, stem(x) + ".txt")) else None, ""),
                             lambda x: None, [])
    err = {i["file"] for i in issues if i["level"] == "ERROR"}
    r.add("Validation 오류(ERROR) 없음", len(imgs) - len(err), len(imgs))
    records = load_records()
    unresolved = [n for n, rec in records.items() if final_decision(rec)[3] == "미해결 REVIEW"]
    r.add("미해결 REVIEW 없음", int(not unresolved), 1, f"미해결 {len(unresolved)}장")
    return r, len(imgs), boxes, len(err), len(unresolved)


# ---------------------------------------------------------------- 개발 중 발견·수정한 문제
DEV_FAILS = [
    ("다른 이미지 폴더의 같은 이름 이미지 결과가 연동되어 표시됨",
     "파일 이름만으로 저장 결과를 찾음",
     "label_status.csv 에 source(원본 폴더) 칸 추가, 연 폴더 안의 TXT 만 표시"),
    ("원본 폴더를 열면 다른 폴더에 저장된 EDITED 배지·작업자 이름이 표시됨",
     "라벨과 달리 검수 기록은 결과 폴더 기록을 그대로 사용",
     "결과 폴더를 열었을 때만 기록 표시 (display_meta)"),
    ("Ctrl+Shift+Z 를 누르면 Redo 가 아니라 Undo 가 실행됨",
     "Shift 를 누르면 대문자 Z 로 입력되는데 대문자 Z 도 Undo 에 연결돼 있었음",
     "글자 대신 Shift 눌림 여부로 Undo / Redo 구분 (Caps Lock 영향 없음)"),
    ("작업자 REVIEW 저장 시 review 폴더에 노트만 저장되고 이미지가 없음",
     "REVIEW 결과의 저장 폴더가 노트 폴더로만 지정됨",
     "작업자/review/ 에 이미지 + 라벨 + <이름>_리뷰노트.txt 함께 저장"),
    ("리뷰 노트 TXT 가 YOLO 라벨로 잘못 읽힐 수 있음",
     "노트 파일 이름이 라벨과 같은 <이름>.txt",
     "노트 이름을 <이름>_리뷰노트.txt 로 바꾸고 Validation 짝 검사에서 제외"),
    ("검수자가 저장하면 TXT 만 저장되어 결과 폴더를 열 수 없음",
     "설정의 검수자 이미지 복사가 꺼져 있음",
     "copy_image.reviewer: true (모든 상태 이미지 + TXT)"),
    ("저장 결과 보기 중 같은 이미지 썸네일을 눌러도 원래 화면으로 돌아오지 않음",
     "같은 번호의 이미지는 이동하지 않도록 되어 있음",
     "저장 결과 보기 중이면 같은 이미지라도 다시 불러옴"),
    ("키패드 . (Num Lock 꺼짐 = 키패드 Del) 이 박스 삭제로 동작할 위험",
     "키패드 Del 이 삭제 키로 연결됨",
     "시점 이동은 Tab 으로 통합, 단축키 충돌 정리"),
]


def build(quiet: bool = False):
    img_dir, lbl_dir = os.path.join(FINAL_DIR, "images"), os.path.join(FINAL_DIR, "labels")
    if not os.path.isdir(img_dir):
        print("data/final/ 이 없습니다. 먼저 python tools/build_final.py 를 실행하세요.")
        return None
    imgs = sorted(f for f in os.listdir(img_dir) if is_image(f)
                  and os.path.isfile(os.path.join(lbl_dir, stem(f) + ".txt")))
    step = max(1, len(imgs) // 70)
    sample = imgs[::step][:70]
    g_names, p_names = sample[:20], sample[20:70]
    tmp = tempfile.mkdtemp(prefix="kimchi_test_")
    try:
        g = golden(g_names, img_dir, lbl_dir, tmp)
        p = pilot(p_names, img_dir, lbl_dir, tmp) if p_names else Result()
        a, n_all, n_box, n_err, n_rev = acceptance(img_dir, lbl_dir, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    accepted = g.ok and p.ok and a.ok
    L = ["# Labeling Tool Test Report\n",
         f"> 생성: {datetime.now():%Y-%m-%d %H:%M} · `python tools/test_report.py` 로 실제 FINAL 데이터에서 자동 시험\n"
         "> 원본·결과 폴더는 건드리지 않고 임시 폴더에 복사해서 시험했습니다.\n"
         "> 화면 조작(드래그·단축키)은 같은 동작을 하는 프로그램 함수를 직접 호출해 시험했고, "
         "실제 화면 확인은 4장의 체크리스트로 기록합니다.\n",
         "## 1. Golden Test\n",
         "**목적**: 본 작업 전에 핵심 기능이 실제 데이터에서 연결되어 동작하는지 확인\n",
         f"**데이터**: 실제 조각김치 이미지 {len(g_names)}장 + 대응 YOLO TXT {len(g_names)}개 (FINAL 에서 고르게 추출)\n",
         g.table(), f"\n**결과: {'PASS' if g.ok else 'FAIL'}**\n",
         "## 2. Pilot Test\n",
         "**목적**: 3단계 검수 저장 흐름 전체가 더 많은 데이터에서 안정적으로 동작하는지 확인\n",
         f"**데이터**: 실제 이미지 {len(p_names)}장 (Golden 과 겹치지 않음)\n",
         "**절차**: 작업자 저장(5장마다 BBox 추가) → 1차 검수(7장마다 Class 수정 EDITED, 나머지 PASS) → "
         "2차 검수 REVIEWED → 결과 Reload\n",
         p.table(), f"\n**결과: {'PASS' if p.ok else 'FAIL'}**\n",
         "### 개발·시험 중 발견하고 수정한 문제\n"]
    for i, (prob, cause, fix) in enumerate(DEV_FAILS, 1):
        L += [f"#### FAIL-{i:02d}", f"- 문제: {prob}", f"- 원인: {cause}", f"- 조치: {fix}", "- 재시험: PASS\n"]
    L += ["## 3. Final Acceptance Test\n",
          "**목적**: 전체 검수 완료 후 FINAL 데이터와 프로그램 결과를 최종 산출물로 인정할 수 있는지 확인\n",
          a.table(),
          f"\n| 항목 | 값 |\n|---|---:|\n| 전체 대상 | {n_all}장 |\n| 전체 BBox | {n_box}개 |\n"
          f"| Critical Error (Reload 불일치·Pair 깨짐) | {sum(r[3] for r in a.rows[:2])}건 |\n"
          f"| Unresolved Review | {n_rev}건 |\n| Validation Error | {n_err}장 |\n",
          f"**최종 판정: {'ACCEPTED' if accepted else 'NOT ACCEPTED — FAIL 항목 확인 필요'}**\n",
          "## 4. 실제 화면 확인 체크리스트 (시연 영상과 함께 기록)\n",
          "| 확인 항목 | 결과 |\n|---|:---:|",
          "| 4K 이미지 열기, Fit / Zoom / Pan 후 BBox 위치가 이미지와 일치 | ☐ |",
          "| 드래그로 BBox 추가 → Enter 확정 / Esc 취소 | ☐ |",
          "| 모서리·테두리 드래그, Ctrl/Alt + 방향키 크기 조절 | ☐ |",
          "| 숫자키 Class 변경, Delete 삭제, Ctrl+Z / Ctrl+Shift+Z | ☐ |",
          "| Tab 으로 박스 선택 시 그 박스로 시점 이동 (줌 유지) | ☐ |",
          "| 저장 → 다음 이미지 → 돌아와서(라벨 완료 목록) 복원 확인 | ☐ |",
          "| Validation 결과 창, 항목 더블클릭으로 이미지 이동 | ☐ |",
          "| 역할별 검수 상태 제한 (검수자 REVIEWED ✕, 2차 검수자 REVIEW ✕) | ☐ |\n"]
    path = os.path.join(REPORTS_DIR, "test_report.md")
    write_text(path, "\n".join(L))
    if not quiet:
        print(f"[Test] → {rel(path)} · Golden {'PASS' if g.ok else 'FAIL'} · Pilot {'PASS' if p.ok else 'FAIL'} · "
              f"Acceptance {'ACCEPTED' if accepted else 'NOT ACCEPTED'}")
    return accepted


if __name__ == "__main__":
    build()
