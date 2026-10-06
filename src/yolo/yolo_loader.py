"""[카테고리] YOLO 읽기 — 이미지 목록, YOLO TXT 라벨 파싱

의사 코드
    list_images(폴더)        폴더 안의 이미지 파일 이름 목록 (하위 폴더 제외, 정렬)
    parse_yolo_line(줄)      "cls cx cy w h" → 값 5개, 형식이 틀리면 ValueError
    load_yolo(txt, W, H)     줄마다 파싱 → Box(픽셀 좌표) 목록
                             못 읽은 줄은 건너뛰고 errors 에 "N행 사유" 기록
"""
from __future__ import annotations

import os

from src.bbox.bbox_model import Box
from src.config import IMAGE_EXTS, NUM_CLASSES


def list_images(folder: str) -> list[str]:
    """폴더 안 이미지 파일 이름 목록 (정렬, 하위 폴더 제외)"""
    names = [n for n in os.listdir(folder)
             if n.lower().endswith(IMAGE_EXTS) and os.path.isfile(os.path.join(folder, n))]
    return sorted(names)


def parse_yolo_line(line: str):
    """'cls cx cy w h' 한 줄 파싱. 형식이 틀리면 ValueError."""
    parts = line.split()
    if len(parts) != 5:
        raise ValueError(f"값이 {len(parts)}개 (5개 필요)")
    try:
        cls_id = int(parts[0])
    except ValueError:
        raise ValueError(f"Class가 정수가 아님: {parts[0]}") from None
    try:
        cx, cy, w, h = (float(p) for p in parts[1:])
    except ValueError:
        raise ValueError("좌표가 숫자가 아님") from None
    return cls_id, cx, cy, w, h


def load_yolo(txt_path: str, W: int, H: int):
    """반환: (boxes, errors). 읽을 수 없는 줄은 건너뛰고 errors에 기록"""
    boxes: list[Box] = []
    errors: list[str] = []
    if not os.path.exists(txt_path):
        return boxes, errors
    try:
        with open(txt_path, encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        return boxes, ["TXT 인코딩이 UTF-8이 아님"]
    for lineno, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line:
            continue
        try:
            c, cx, cy, w, h = parse_yolo_line(line)
        except ValueError as e:
            errors.append(f"{lineno}행 {e}")
            continue
        if not 0 <= c < NUM_CLASSES:
            errors.append(f"{lineno}행 존재하지 않는 Class {c}")
            continue
        if w <= 0 or h <= 0:
            errors.append(f"{lineno}행 너비/높이가 0 이하")
            continue
        boxes.append(Box.from_yolo(c, cx, cy, w, h, W, H))
    return boxes, errors
