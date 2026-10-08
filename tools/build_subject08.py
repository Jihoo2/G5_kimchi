"""[교과 8 인계] 최종 제출 폴더 subject07_kimchi_labeling/ 만들기

사용법 (make_all.py 로 산출물을 만든 뒤, 프로젝트 최상위에서)
    python tools/build_subject08.py            # 폴더만 만듦
    python tools/build_subject08.py --zip      # 폴더 + subject07_kimchi_labeling.zip (이미지 포함이라 큼)

결과 (교과 8 제출 형식)
    subject07_kimchi_labeling/
    ├── 01_program/     src/, configs/, run.py, requirements.txt, README.md
    ├── 02_dataset/     dataset1/images·labels/train/
    │                   dataset2/images·labels/train/, validation/      (원본 데이터셋·Split 그대로)
    ├── 03_logs/        dataset_manifest.csv, work_history.csv
    ├── 04_reports/     validation_report.csv, qa_statistics.png
    └── 05_handover/    handover_guide.md, class_definition.json, final_checklist.md

읽는 것: data/final/ (FINAL 이미지·라벨), manifests/dataset_manifest.csv, 검수 기록 CSV, configs/
원본·결과 폴더는 읽기만 하며, subject07_kimchi_labeling/ 는 실행할 때마다 새로 만든다.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from collections import Counter, defaultdict
from datetime import datetime

from common import (C, DOCS_DIR, FINAL_DIR, MANIFEST_PATH, ROLE_LABELS, ROOT, class_name, is_image,
                    load_records, rel, stem, write_text)
from src.validation.validator import DUP_IOU, _check_line, _iou

OUT = os.path.join(ROOT, "subject07_kimchi_labeling")
P, D, L, R, H = (os.path.join(OUT, n) for n in ("01_program", "02_dataset", "03_logs", "04_reports", "05_handover"))
SPLIT_ORDER = ["train", "validation", "test", "unknown"]


# ---------------------------------------------------------------- 01 프로그램
def build_program():
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "*Zone.Identifier")
    for d in ("src", "configs"):                        # configs/ 가 없으면 프로그램이 실행되지 않음
        shutil.copytree(os.path.join(ROOT, d), os.path.join(P, d), ignore=ignore)
    shutil.copy2(os.path.join(ROOT, "main.py"), os.path.join(P, "run.py"))
    for f in ("requirements.txt", "README.md"):
        if os.path.isfile(os.path.join(ROOT, f)):
            shutil.copy2(os.path.join(ROOT, f), P)


# ---------------------------------------------------------------- 02 데이터셋
def read_manifest():
    if not os.path.isfile(MANIFEST_PATH):
        raise SystemExit("manifests/dataset_manifest.csv 가 없습니다. python tools/make_all.py 를 먼저 실행하세요.")
    with open(MANIFEST_PATH, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build_dataset(rows):
    """원본 데이터셋 이름 순서대로 dataset1, dataset2 … 로, Split 은 원본 그대로 나눠 복사"""
    img_dir, lbl_dir = os.path.join(FINAL_DIR, "images"), os.path.join(FINAL_DIR, "labels")
    if not os.path.isdir(img_dir):
        raise SystemExit("data/final/ 이 없습니다. python tools/make_all.py 를 먼저 실행하세요.")
    images = {stem(f): f for f in os.listdir(img_dir) if is_image(f)}
    names = sorted({r["source_dataset"] for r in rows if r.get("in_final") == "Y"})
    ds_map = {n: f"dataset{i}" for i, n in enumerate(names, 1)}
    placed, missing = [], []
    for r in rows:
        if r.get("in_final") != "Y":
            continue
        s = stem(r["file_name"])
        img = images.get(s)
        if not img:
            missing.append(r["file_name"])
            continue
        ds, split = ds_map[r["source_dataset"]], (r.get("original_split") or "unknown")
        for kind, src, name in (("images", os.path.join(img_dir, img), img),
                                ("labels", os.path.join(lbl_dir, s + ".txt"), s + ".txt")):
            dst = os.path.join(D, ds, kind, split)
            os.makedirs(dst, exist_ok=True)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(dst, name))
        placed.append((ds, split, img, r))
    return ds_map, placed, missing


# ---------------------------------------------------------------- 03 로그
def build_logs(rows):
    shutil.copy2(MANIFEST_PATH, os.path.join(L, "dataset_manifest.csv"))
    fields = ["file_name", "stage", "user", "status", "scene_type", "num_boxes", "note", "updated_at"]
    users = {"worker": "assignee", "reviewer": "reviewer", "reviewer2": "reviewer2"}
    out = []
    for name, rec in sorted(load_records().items()):
        for role in ("worker", "reviewer", "reviewer2"):
            row = rec.get(role)
            if not row or not row.get("status"):
                continue
            out.append({"file_name": name, "stage": ROLE_LABELS[role],
                        "user": row.get(users[role]) or row.get("assignee", ""),
                        "status": row.get("status", ""), "scene_type": row.get("scene_type", ""),
                        "num_boxes": row.get("num_boxes", ""), "note": " ".join((row.get("note") or "").split()),
                        "updated_at": row.get("updated_at", "")})
    out.sort(key=lambda x: (x["updated_at"], x["file_name"]))
    with open(os.path.join(L, "work_history.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out)
    return Counter(x["stage"] for x in out), len(out)


# ---------------------------------------------------------------- 04 리포트
def validate(ds_map):
    """02_dataset 의 이미지·라벨을 프로그램과 같은 규칙으로 검사 → 이미지마다 한 줄"""
    rows, issues_by_cat, cls_boxes, empty = [], Counter(), Counter(), 0
    for ds in sorted(set(ds_map.values())):
        for split in SPLIT_ORDER:
            idir, ldir = (os.path.join(D, ds, k, split) for k in ("images", "labels"))
            if not os.path.isdir(idir) and not os.path.isdir(ldir):
                continue
            imgs = {stem(f): f for f in (os.listdir(idir) if os.path.isdir(idir) else []) if is_image(f)}
            txts = {stem(f) for f in (os.listdir(ldir) if os.path.isdir(ldir) else []) if f.endswith(".txt")}
            for s in sorted(set(imgs) | txts):
                found, boxes, n = [], [], 0
                if s not in txts:
                    found.append(("ERROR", "JPG는 있는데 TXT 없음", "라벨 TXT 없음"))
                elif s not in imgs:
                    found.append(("ERROR", "TXT는 있는데 JPG 없음", "이미지 없음"))
                else:
                    with open(os.path.join(ldir, s + ".txt"), encoding="utf-8") as f:
                        for lineno, raw in enumerate(f, 1):
                            if not raw.strip():
                                continue
                            n += 1
                            line_issues, box = _check_line(raw.strip())
                            found += [(lv, cat, f"{lineno}행: {msg}") for lv, cat, msg in line_issues]
                            if box:
                                boxes.append((lineno, box))
                                cls_boxes[box[0]] += 1
                    for i in range(len(boxes)):
                        for j in range(i + 1, len(boxes)):
                            (li, a), (lj, b) = boxes[i], boxes[j]
                            if a[0] == b[0] and _iou(a[1:], b[1:]) >= DUP_IOU:
                                found.append(("WARN", "중복 의심 BBox", f"{li}행·{lj}행 겹침"))
                    if n == 0:
                        empty += 1
                        found.append(("INFO", "Empty Label", "박스 0개 (배경 이미지)"))
                levels = {lv for lv, _, _ in found}
                result = "ERROR" if "ERROR" in levels else "WARN" if "WARN" in levels else "PASS"
                issues_by_cat.update(cat for _, cat, _ in found)
                rows.append({"dataset": ds, "split": split, "file_name": imgs.get(s, s + ".txt"),
                             "num_boxes": n, "result": result, "issue_count": len(found),
                             "issues": " | ".join(f"[{lv}] {cat}: {msg}" for lv, cat, msg in found)})
    fields = ["dataset", "split", "file_name", "num_boxes", "result", "issue_count", "issues"]
    with open(os.path.join(R, "validation_report.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return rows, issues_by_cat, cls_boxes, empty


def draw_statistics(placed, val_rows, cls_boxes, path):
    """qa_statistics.png — 데이터셋·Split 수량 / Class 별 BBox 수 / 검수 결과 요약 (한 색 막대, 숫자 직접 표시)"""
    from PIL import Image, ImageDraw
    from export_evidence import _font

    INK, MUTED, GRID, BAR, BG = (31, 41, 55), (107, 114, 128), (229, 231, 235), (37, 99, 235), (255, 255, 255)
    split = Counter((ds, sp) for ds, sp, _, _ in placed)
    split_items = [(f"{ds} / {sp}", n) for (ds, sp), n in sorted(
        split.items(), key=lambda x: (x[0][0], SPLIT_ORDER.index(x[0][1]) if x[0][1] in SPLIT_ORDER else 9))]
    cls_items = [(f"{cid} {class_name(cid)}", cls_boxes.get(cid, 0)) for cid in sorted(C.CLASS_NAMES)
                 if cid in C.ENABLED_CLASSES or cls_boxes.get(cid)]
    W, Hh = 1600, 290 + 52 + 56 * max(len(split_items), len(cls_items)) + 90
    im = Image.new("RGB", (W, Hh), BG)
    d = ImageDraw.Draw(im)
    f = lambda s: _font(s)[0]                                   # noqa: E731
    d.text((48, 32), "G5 조각김치 이물검출 — FINAL 데이터 QA 통계", font=f(34), fill=INK)
    d.text((48, 82), f"생성 {datetime.now():%Y-%m-%d %H:%M} · 2차 검수 완료 데이터 기준", font=f(20), fill=MUTED)

    # 요약 숫자 4개
    res = Counter(r["result"] for r in val_rows)
    status = Counter(r["status"] for _, _, _, r in placed)
    tiles = [("FINAL 이미지", f"{len(placed):,}장"), ("전체 BBox", f"{sum(cls_boxes.values()):,}개"),
             ("Validation", f"PASS {res.get('PASS', 0)} · 오류 {res.get('ERROR', 0)}"),
             ("원본 대비", f"수정 {status.get('EDITED', 0)} · 유지 {status.get('DONE', 0)}")]
    tw = (W - 96 - 3 * 24) // 4
    for i, (k, v) in enumerate(tiles):
        x = 48 + i * (tw + 24)
        d.rounded_rectangle([x, 130, x + tw, 240], 12, outline=GRID, width=2)
        d.text((x + 20, 146), k, font=f(20), fill=MUTED)
        d.text((x + 20, 182), v, font=f(30), fill=INK)

    def hbars(x0, y0, w, title, items):
        d.text((x0, y0), title, font=f(24), fill=INK)
        top, row_h = y0 + 52, 56
        vmax = max([v for _, v in items] + [1])
        lab_w, num_w = 260, 90
        bw = w - lab_w - num_w
        for i, (lab, v) in enumerate(items):
            y = top + i * row_h
            d.text((x0, y + 8), lab, font=f(20), fill=INK)
            d.rectangle([x0 + lab_w, y + 4, x0 + lab_w + bw, y + 36], fill=(243, 244, 246))
            if v:
                d.rounded_rectangle([x0 + lab_w, y + 4, x0 + lab_w + max(6, int(bw * v / vmax)), y + 36], 4, fill=BAR)
            d.text((x0 + lab_w + bw + 14, y + 8), f"{v:,}", font=f(20), fill=INK)

    hbars(48, 290, 700, "데이터셋 · Split 별 이미지 수", split_items)
    hbars(820, 290, 732, "Class 별 BBox 수", cls_items)
    d.text((48, Hh - 50), "막대 끝 숫자 = 실제 개수 · 상세는 03_logs/dataset_manifest.csv, 04_reports/validation_report.csv",
           font=f(18), fill=MUTED)
    im.save(path)


# ---------------------------------------------------------------- 05 인계
def build_handover(ds_map, placed, val_rows, cls_boxes, empty, stage_count, n_hist):
    classes = [{"id": cid, "name": name, "color": color, "enabled": enabled}
               for cid, name, color, enabled in C.CLASSES]
    json.dump({"format": "YOLO (class_id x_center y_center width height, 0~1 정규화)",
               "num_classes": C.NUM_CLASSES, "enabled_ids": C.ENABLED_CLASSES,
               "unused_ids": C.UNUSED_CLASSES, "classes": classes},
              open(os.path.join(H, "class_definition.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    split = Counter((ds, sp) for ds, sp, _, _ in placed)
    inv = {v: k for k, v in ds_map.items()}
    ds_rows = "\n".join(f"| `{ds}/…/{sp}/` | {inv[ds]} | {sp} | {n} |" for (ds, sp), n in sorted(split.items()))
    cls_rows = "\n".join(f"| {cid} | {class_name(cid)} | {'사용' if cid in C.ENABLED_CLASSES else '사용 안 함'} | "
                         f"{cls_boxes.get(cid, 0)} |" for cid in sorted(C.CLASS_NAMES))
    detail = ""
    hp = os.path.join(DOCS_DIR, "subject08_handoff.md")
    if os.path.isfile(hp):
        detail = "\n---\n\n## 부록 — 교과 7 Handoff 상세\n\n" + open(hp, encoding="utf-8").read().replace("\n# ", "\n### ")
    write_text(os.path.join(H, "handover_guide.md"), f"""# 교과 8 인계 가이드 — G5 조각김치 이물검출

교과 7 에서 라벨링 프로그램으로 900장을 1차 검수(수정) → 2차 교차 검수해 확정한 FINAL 데이터입니다.

## 폴더 구성

| 폴더 | 내용 |
|---|---|
| `01_program/` | 라벨링 프로그램 (`run.py` 실행, `src/`, `configs/`, `requirements.txt`, `README.md`) |
| `02_dataset/` | FINAL 이미지·YOLO 라벨 (원본 데이터셋·Split 그대로) |
| `03_logs/` | `dataset_manifest.csv` (이미지별 출처·상태), `work_history.csv` (검수 이력 {n_hist}행) |
| `04_reports/` | `validation_report.csv` (이미지별 검사 결과), `qa_statistics.png` (수량·Class 통계) |
| `05_handover/` | 이 문서, `class_definition.json`, `final_checklist.md` |

## 데이터셋

| 폴더 | 원본 데이터셋 | Split | 이미지 수 |
|---|---|---|---:|
{ds_rows}

- 같은 이름의 이미지(`images/`)와 라벨(`labels/`)이 한 쌍입니다. Empty Label(박스 0개) {empty}장.
- 라벨 형식: `class_id x_center y_center width height` (이미지 크기 대비 0~1, 소수 6자리)

## Class

| ID | 이름 | 사용 | BBox 수 |
|---:|---|---|---:|
{cls_rows}

`class_definition.json` 에 같은 내용이 있습니다. 사용 안 함 Class 는 학습에서 제외합니다 (데이터에 0개).

## 프로그램 실행 (WSL Ubuntu)

```bash
cd 01_program
sudo apt install -y python3-tk python3-venv fonts-nanum
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 run.py
```

## 검수 이력 요약

{chr(10).join(f"- {k}: {v}건" for k, v in stage_count.items()) or "- (기록 없음)"}
{detail}""")

    res = Counter(r["result"] for r in val_rows)
    n_img = sum(len([f for f in os.listdir(dp) if is_image(f)]) for dp, _, _ in os.walk(D) if os.sep + "images" in dp)
    n_txt = sum(len([f for f in fn if f.endswith(".txt")]) for dp, _, fn in os.walk(D) if os.sep + "labels" in dp)
    checks = [
        ("02_dataset 이미지 수 = Manifest FINAL 수", n_img == len(placed), f"{n_img} / {len(placed)}"),
        ("이미지 ↔ 라벨 수 일치", n_img == n_txt, f"이미지 {n_img} · 라벨 {n_txt}"),
        ("Validation 오류 0건", res.get("ERROR", 0) == 0, f"ERROR {res.get('ERROR', 0)} · WARN {res.get('WARN', 0)}"),
        ("사용 안 함 Class 0개", all(cls_boxes.get(c, 0) == 0 for c in C.UNUSED_CLASSES),
         ", ".join(f"Class {c}: {cls_boxes.get(c, 0)}" for c in C.UNUSED_CLASSES) or "-"),
        ("원본 Split 유지 (unknown 없음)", all(sp != "unknown" for _, sp, _, _ in placed),
         ", ".join(sorted({sp for _, sp, _, _ in placed}))),
        ("Manifest · 검수 이력 포함", os.path.isfile(os.path.join(L, "dataset_manifest.csv")) and n_hist > 0,
         f"work_history {n_hist}행"),
        ("Class 정의 파일", os.path.isfile(os.path.join(H, "class_definition.json")), "class_definition.json"),
        ("프로그램 실행 파일", all(os.path.exists(os.path.join(P, x)) for x in ("run.py", "src", "configs", "requirements.txt")),
         "run.py · src · configs · requirements.txt"),
        ("통계 이미지", os.path.isfile(os.path.join(R, "qa_statistics.png")), "qa_statistics.png"),
    ]
    ok = all(c[1] for c in checks)
    write_text(os.path.join(H, "final_checklist.md"),
               "# 최종 제출 체크리스트\n\n"
               f"생성: {datetime.now():%Y-%m-%d %H:%M} · 판정: **{'제출 가능' if ok else '확인 필요'}**\n\n"
               "| 확인 항목 | 결과 | 값 |\n|---|:---:|---|\n"
               + "\n".join(f"| {k} | {'☑' if v else '☐'} | {val} |" for k, v, val in checks)
               + "\n\n## 사람이 확인할 것\n\n| 항목 | 확인 |\n|---|:---:|\n"
               "| `01_program` 에서 `python3 run.py` 로 프로그램이 열림 | ☐ |\n"
               "| `qa_statistics.png` 를 열어 숫자가 QA Summary 와 같음 | ☐ |\n"
               "| 이미지 몇 장을 열어 라벨 위치가 맞음 | ☐ |\n")
    return ok, checks


def build(make_zip: bool = False):
    shutil.rmtree(OUT, ignore_errors=True)
    for d in (P, D, L, R, H):
        os.makedirs(d)
    build_program()
    rows = read_manifest()
    ds_map, placed, missing = build_dataset(rows)
    stage_count, n_hist = build_logs(rows)
    val_rows, issues, cls_boxes, empty = validate(ds_map)
    draw_statistics(placed, val_rows, cls_boxes, os.path.join(R, "qa_statistics.png"))
    ok, checks = build_handover(ds_map, placed, val_rows, cls_boxes, empty, stage_count, n_hist)

    print(f"[교과8] → {rel(OUT)}/")
    for name, ds in ds_map.items():
        sp = Counter(s for d_, s, _, _ in placed if d_ == ds)
        print(f"   {ds} ({name}): " + ", ".join(f"{k} {v}" for k, v in sorted(sp.items())))
    if missing:
        print(f"   ⚠ data/final 에 없는 Manifest FINAL 이미지 {len(missing)}장 (예: {missing[:3]})")
    res = Counter(r["result"] for r in val_rows)
    print(f"   Validation: " + ", ".join(f"{k} {v}" for k, v in sorted(res.items())))
    for k, v, val in checks:
        if not v:
            print(f"   ☐ {k}: {val}")
    print(f"   최종: {'제출 가능' if ok else '확인 필요 — 05_handover/final_checklist.md 참고'}")
    if make_zip:
        z = shutil.make_archive(OUT, "zip", ROOT, os.path.basename(OUT))
        print(f"   zip → {rel(z)} ({os.path.getsize(z) / 1024 / 1024:.1f}MB)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="교과 8 제출 형식 폴더 만들기")
    ap.add_argument("--zip", action="store_true", help="subject07_kimchi_labeling.zip 도 만듦 (이미지 포함, 큼)")
    build(ap.parse_args().zip)
