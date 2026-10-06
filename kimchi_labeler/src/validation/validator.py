"""[카테고리] Validation 검사 로직 — 라벨 TXT가 규칙에 맞는지 자동 검사
(결과 창은 src/validation/validation_dialog.py)

의사 코드
    validate_folder(이미지 목록, resolve, meta_of, 저장 폴더들):
        이미지마다:
            지금 역할이 불러올 TXT 경로 찾기 (resolve)
            TXT 없음  → CSV에 박스가 있다고 돼 있으면 오류
            줄마다:
                형식 (값 5개, 정수 Class, 숫자 좌표)            → 오류
                없는 Class / 사용 안 함 Class(4)                → 오류
                좌표 0~1 밖, 너비·높이 ≤ 0                     → 오류
                이미지 경계 넘음, 너무 작은 박스, 중복 박스     → 경고
            CSV 박스 수 ≠ TXT 박스 수, Scene Type 모순         → 경고
        저장 폴더 안에 짝 이미지가 없는 TXT                     → 경고
        반환: [{file, line, level(ERROR/WARN), msg}, ...]
"""
from __future__ import annotations

import os

from src.config import CLASS_NAMES, ENABLED_CLASSES, NUM_CLASSES
from src.yolo.yolo_loader import parse_yolo_line


EPS = 1e-6


TINY = 0.002   # 정규화 기준 이보다 작으면 실수로 찍힌 박스일 가능성


def validate_folder(image_names: list[str], resolve, meta_of, scan_dirs: list[str]) -> list[dict]:
    """
    resolve(name)  -> (txt 경로 또는 None, 출처)   현재 역할 기준으로 읽게 될 라벨
    meta_of(name)  -> ImageMeta 또는 None
    scan_dirs      -> 짝 없는 TXT를 찾을 저장 폴더들
    반환: [{file, line, level(ERROR/WARN), msg}, ...]
    """
    issues: list[dict] = []

    def add(file, line, level, msg):
        """검사 결과 한 건 추가"""
        issues.append({"file": file, "line": line, "level": level, "msg": msg})

    for name in image_names:
        txt, _src = resolve(name)
        meta = meta_of(name)

        if txt is None:
            if meta and meta.num_boxes > 0:
                add(name, "-", "ERROR", f"CSV에는 BBox {meta.num_boxes}개로 기록됐지만 TXT 파일이 없음")
            continue

        try:
            with open(txt, encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            add(name, "-", "ERROR", "TXT 인코딩이 UTF-8이 아님")
            continue

        seen = set()
        count = 0
        for lineno, raw in enumerate(lines, 1):
            line = raw.strip()
            if not line:
                continue
            try:
                c, cx, cy, w, h = parse_yolo_line(line)
            except ValueError as e:
                add(name, lineno, "ERROR", f"형식 오류: {e}")
                continue
            count += 1

            if not 0 <= c < NUM_CLASSES:
                add(name, lineno, "ERROR", f"존재하지 않는 Class: {c}")
            elif c not in ENABLED_CLASSES:
                add(name, lineno, "ERROR", f"사용 안 함 Class 사용: {c} {CLASS_NAMES[c]}")

            if any(not 0 <= v <= 1 for v in (cx, cy, w, h)):
                add(name, lineno, "ERROR", "좌표가 0~1 범위를 벗어남")
            elif w <= 0 or h <= 0:
                add(name, lineno, "ERROR", "너비/높이가 0 이하")
            elif (cx - w / 2 < -EPS or cx + w / 2 > 1 + EPS
                  or cy - h / 2 < -EPS or cy + h / 2 > 1 + EPS):
                add(name, lineno, "WARN", "BBox가 이미지 경계를 벗어남")
            elif w < TINY or h < TINY:
                add(name, lineno, "WARN", "BBox가 매우 작음 (실수로 찍힌 박스인지 확인)")

            key = (c, round(cx, 4), round(cy, 4), round(w, 4), round(h, 4))
            if key in seen:
                add(name, lineno, "WARN", "중복 BBox")
            seen.add(key)

        if meta:
            if meta.num_boxes != count:
                add(name, "-", "WARN", f"CSV BBox 수({meta.num_boxes})와 TXT({count}) 불일치")
            if meta.scene_type == "normal_kimchi" and count > 0:
                add(name, "-", "WARN", "Scene Type이 '정상 김치'인데 BBox가 있음")
            if meta.scene_type in ("kimchi_with_target", "object_only") and count == 0:
                add(name, "-", "WARN", "Scene Type은 대상 포함인데 BBox가 없음")

    stems = {os.path.splitext(n)[0] for n in image_names}
    for d in scan_dirs:
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if (fn.lower().endswith(".txt") and fn != "classes.txt"
                    and os.path.splitext(fn)[0] not in stems):
                add(os.path.join(os.path.basename(d), fn), "-", "WARN", "짝이 되는 이미지가 없는 TXT")

    return issues
