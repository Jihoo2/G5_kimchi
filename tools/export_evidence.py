"""[산출물 3 증빙] FINAL 데이터 증빙 자료 만들기 (LMS 제출용, Git 에는 올리지 않음)

사용법 (build_final.py 실행 후)
    python tools/export_evidence.py            # 대표 이미지 5장
    python tools/export_evidence.py --n 3
결과 (evidence/ 폴더)
    final_structure.txt              data/final 폴더 구조 + 이미지·TXT 수량 + Pair 확인
    samples/<이름>_bbox.jpg          대표 검수 완료 이미지 (BBox·Class 표시)
    samples/<이름>.txt               같은 이름의 FINAL YOLO TXT
대표 이미지는 여러 Class 가 함께 있는 이미지를 우선해서 고르고, Class 가 고르게 보이도록 선택한다.
"""
from __future__ import annotations

import argparse
import os
import shutil

from PIL import Image, ImageDraw, ImageFont, ImageOps

from common import C, FINAL_DIR, ROOT, class_name, is_image, read_boxes, rel, stem, write_text

EVIDENCE = os.path.join(ROOT, "evidence")
FONT_CANDIDATES = ["/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
                   "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
                   "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
                   "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                   "C:/Windows/Fonts/malgunbd.ttf", "C:/Windows/Fonts/malgun.ttf"]


def _font(size):
    for p in FONT_CANDIDATES:
        if os.path.isfile(p):
            return ImageFont.truetype(p, size), True
    return ImageFont.load_default(), False          # 한글 글꼴이 없으면 Class 번호만 표시


def pick(imgs, lbl_dir, n):
    """Class 종류가 많은 이미지 우선, 이미 고른 Class 와 겹치지 않는 이미지를 골라 Class 가 고르게 보이게"""
    info = []
    for f in imgs:
        b = read_boxes(os.path.join(lbl_dir, stem(f) + ".txt"))
        if b:
            info.append((f, {x[0] for x in b}, len(b)))
    chosen, seen = [], set()
    while info and len(chosen) < n:
        info.sort(key=lambda x: (len(x[1] - seen), len(x[1]), -abs(x[2] - 4)), reverse=True)
        f, cls, _ = info.pop(0)
        chosen.append(f)
        seen |= cls
    return chosen


def draw(img_path, txt_path, out_path):
    with Image.open(img_path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
    W, H = im.size
    d = ImageDraw.Draw(im)
    lw = max(2, W // 640)
    font, korean = _font(max(14, W // 90))
    for c, cx, cy, w, h in read_boxes(txt_path):
        x1, y1, x2, y2 = (cx - w / 2) * W, (cy - h / 2) * H, (cx + w / 2) * W, (cy + h / 2) * H
        color = C.CLASS_COLORS.get(c, "#FFFFFF")
        d.rectangle([x1, y1, x2, y2], outline=color, width=lw)
        label = f"{c} {class_name(c)}" if korean else str(c)
        tb = d.textbbox((0, 0), label, font=font)
        tw, th = tb[2] - tb[0] + 8, tb[3] - tb[1] + 6
        ty = y1 - th if y1 > th else y1
        tx = min(x1, W - tw)                    # 이미지 오른쪽 끝에서 글자가 잘리지 않게
        d.rectangle([tx, ty, tx + tw, ty + th], fill=color)
        d.text((tx + 4, ty + 1 - tb[1]), label, fill="white", font=font)
    im.save(out_path, quality=90)


def build(n: int = 5, quiet: bool = False):
    img_dir, lbl_dir = os.path.join(FINAL_DIR, "images"), os.path.join(FINAL_DIR, "labels")
    if not os.path.isdir(img_dir):
        print("data/final/ 이 없습니다. 먼저 python tools/build_final.py 를 실행하세요.")
        return
    imgs = sorted(f for f in os.listdir(img_dir) if is_image(f))
    txts = sorted(f for f in os.listdir(lbl_dir) if f.endswith(".txt"))
    istems, tstems = {stem(f) for f in imgs}, {stem(f) for f in txts}
    shutil.rmtree(os.path.join(EVIDENCE, "samples"), ignore_errors=True)
    os.makedirs(os.path.join(EVIDENCE, "samples"))

    def tree(files):
        if not files:
            return []
        head = [f"    │   ├── {x}" for x in files[:3]]
        return head + (["    │   ├── …"] if len(files) > 4 else []) + [f"    │   └── {files[-1]}"]

    lines = (["data/final/ 폴더 구조", "", "data/", "└── final/", f"    ├── images/   ({len(imgs)}장)"] + tree(imgs)
             + [f"    ├── labels/   ({len(txts)}개)"] + tree(txts) + ["    └── final_list.csv", "",
                f"이미지 수         : {len(imgs)}", f"TXT 수            : {len(txts)}",
                f"Pair 일치         : {len(istems & tstems)}", f"이미지만 있음     : {len(istems - tstems)}",
                f"TXT만 있음        : {len(tstems - istems)}", "", "확인 명령 (WSL):",
                "  ls data/final/images | wc -l", "  ls data/final/labels | wc -l"])
    write_text(os.path.join(EVIDENCE, "final_structure.txt"), "\n".join(lines) + "\n")

    chosen = pick(imgs, lbl_dir, n)
    for f in chosen:
        t = os.path.join(lbl_dir, stem(f) + ".txt")
        draw(os.path.join(img_dir, f), t, os.path.join(EVIDENCE, "samples", stem(f) + "_bbox.jpg"))
        shutil.copy2(t, os.path.join(EVIDENCE, "samples", stem(f) + ".txt"))
    if not quiet:
        print(f"[증빙] → {rel(EVIDENCE)}/ · 구조·수량 final_structure.txt · 대표 이미지 {len(chosen)}장 (samples/)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="FINAL 데이터 증빙 자료")
    ap.add_argument("--n", type=int, default=5, help="대표 이미지 수 (기본 5)")
    build(ap.parse_args().n)
