"""[카테고리] Validation 검사 로직 — 라벨 TXT가 규칙에 맞는지 자동 검사
(결과 창은 src/validation/validation_dialog.py)

검사 항목 (CATEGORIES 순서 = 결과 창 표시 순서)
    파일 짝
        JPG는 있는데 TXT 없음      경고   라벨링이 안 된 이미지
        TXT는 있는데 JPG 없음      경고   이미지가 지워졌거나 이름이 다른 TXT
    한 줄 형식
        TXT 한 줄 구조 오류        오류   값이 5개가 아님 (cls cx cy w h)
        숫자 변환 오류             오류   Class 가 정수가 아님 / 좌표가 숫자가 아님
    Class
        Class 범위 오류            오류   0 ~ (클래스 수-1) 밖의 번호
        Class 4 발견               오류   사용 안 함 Class (configs/classes.yaml 의 enabled: false)
    좌표
        좌표 범위 오류             오류   cx, cy, w, h 중 0~1 밖의 값
        Width/Height 비정상        오류   너비·높이 0 이하
                                   경고   너무 작음 (실수로 찍힌 점) / 이미지 거의 전체를 덮음
        BBox 경계 오류             경고   중심 ± 너비/2 가 이미지 밖으로 나감
        중복 의심 BBox             경고   같은 Class 박스끼리 IoU 0.9 이상 (완전히 같은 좌표 포함)
    내용
        Empty Label                참고   TXT 는 있는데 박스가 0개 (정상 김치라면 문제 없음, Cross Review 대상)
    기록
        기록 불일치                경고   (결과 폴더) CSV 박스 수 ≠ TXT, Scene Type 과 박스 유무 모순

의사 코드
    validate_folder(이미지 목록, resolve, meta_of, 검사 폴더들):
        이미지마다:
            txt = resolve(이미지)                 # 지금 연 폴더의 같은 이름 TXT
            없으면 → 'JPG는 있는데 TXT 없음'
            줄마다: 구조 → 숫자 → Class → 좌표 → W/H → 경계 순서로 검사
            정상 박스끼리 같은 Class IoU 계산 → 중복 의심
            박스 0개 → Empty Label
            CSV 기록이 있으면 박스 수 · Scene Type 비교
        검사 폴더의 TXT 중 짝 이미지가 없는 것 → 'TXT는 있는데 JPG 없음'
        반환: [{file, line, level(ERROR/WARN/INFO), category, msg}, ...]
"""
from __future__ import annotations

import os

from src.config import CLASS_NAMES, IMAGE_EXTS, NUM_CLASSES, REVIEW_NOTE_SUFFIX, UNUSED_CLASSES

# 결과 창에 이 순서로 표시
CATEGORIES = [
    "JPG는 있는데 TXT 없음", "TXT는 있는데 JPG 없음",
    "TXT 한 줄 구조 오류", "숫자 변환 오류",
    "Class 범위 오류", "Class 4 발견",
    "좌표 범위 오류", "Width/Height 비정상", "BBox 경계 오류", "중복 의심 BBox",
    "Empty Label", "기록 불일치",
]

EPS = 1e-6
TINY = 0.002          # 정규화 너비·높이가 이보다 작으면 실수로 찍힌 박스일 가능성
HUGE = 0.95           # 너비·높이 모두 이보다 크면 이미지 전체를 덮은 박스일 가능성
DUP_IOU = 0.9         # 같은 Class 박스끼리 IoU 가 이 이상이면 중복 의심


def _iou(a, b) -> float:
    """정규화 (cx, cy, w, h) 두 박스의 IoU"""
    ax1, ay1, ax2, ay2 = a[0] - a[2] / 2, a[1] - a[3] / 2, a[0] + a[2] / 2, a[1] + a[3] / 2
    bx1, by1, bx2, by2 = b[0] - b[2] / 2, b[1] - b[3] / 2, b[0] + b[2] / 2, b[1] + b[3] / 2
    iw = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    ih = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


def _check_line(line: str):
    """한 줄 검사 → (문제 목록[(level, category, msg)], 정상 박스 (cls, cx, cy, w, h) 또는 None)"""
    parts = line.split()
    if len(parts) != 5:
        return [("ERROR", "TXT 한 줄 구조 오류", f"값이 {len(parts)}개 (cls cx cy w h, 5개 필요)")], None
    try:
        cls_id = int(parts[0])
    except ValueError:
        return [("ERROR", "숫자 변환 오류", f"Class 가 정수가 아님: '{parts[0]}'")], None
    try:
        cx, cy, w, h = (float(p) for p in parts[1:])
    except ValueError:
        bad = next(p for p in parts[1:] if not _is_float(p))
        return [("ERROR", "숫자 변환 오류", f"좌표가 숫자가 아님: '{bad}'")], None

    issues = []
    if not 0 <= cls_id < NUM_CLASSES:
        issues.append(("ERROR", "Class 범위 오류", f"Class {cls_id} (0~{NUM_CLASSES - 1} 만 사용)"))
    elif cls_id in UNUSED_CLASSES:
        issues.append(("ERROR", "Class 4 발견", f"사용 안 함 Class: {cls_id} {CLASS_NAMES[cls_id]}"))

    values = {"cx": cx, "cy": cy, "w": w, "h": h}
    out = [f"{k}={v:g}" for k, v in values.items() if not 0 <= v <= 1]   # nan 도 여기서 걸림
    if out:
        issues.append(("ERROR", "좌표 범위 오류", f"0~1 밖의 값: {', '.join(out)}"))
        return issues, None

    if w <= 0 or h <= 0:
        issues.append(("ERROR", "Width/Height 비정상", f"너비·높이가 0 이하 (w={w:g}, h={h:g})"))
        return issues, None
    if w < TINY or h < TINY:
        issues.append(("WARN", "Width/Height 비정상", f"너무 작음 (w={w:.4f}, h={h:.4f}) — 실수로 찍힌 박스인지 확인"))
    elif w > HUGE and h > HUGE:
        issues.append(("WARN", "Width/Height 비정상", f"이미지 거의 전체를 덮음 (w={w:.3f}, h={h:.3f})"))

    if cx - w / 2 < -EPS or cx + w / 2 > 1 + EPS or cy - h / 2 < -EPS or cy + h / 2 > 1 + EPS:
        issues.append(("WARN", "BBox 경계 오류", "박스가 이미지 밖으로 나감 (중심 ± 크기/2 가 0~1 밖)"))

    return issues, (cls_id, cx, cy, w, h)


def _is_float(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def validate_folder(image_names: list[str], resolve, meta_of, scan_dirs: list[str]) -> list[dict]:
    """
    resolve(name)  -> (txt 경로 또는 None, 출처)   지금 연 폴더 기준으로 불러올 라벨
    meta_of(name)  -> ImageMeta 또는 None          (결과 폴더를 열었을 때만 기록 비교)
    scan_dirs      -> 'TXT는 있는데 JPG 없음' 을 찾을 폴더들
    반환: [{file, line, level, category, msg}, ...]
    """
    issues: list[dict] = []

    def add(file, line, level, category, msg):
        issues.append({"file": file, "line": line, "level": level, "category": category, "msg": msg})

    for name in image_names:
        txt, _src = resolve(name)
        meta = meta_of(name)

        if txt is None:
            add(name, "-", "WARN", "JPG는 있는데 TXT 없음", "라벨 TXT 가 없음 (라벨링 안 된 이미지)")
            continue

        try:
            with open(txt, encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            add(name, "-", "ERROR", "숫자 변환 오류", "TXT 인코딩이 UTF-8 이 아님 (읽을 수 없음)")
            continue

        boxes = []                 # (줄 번호, (cls, cx, cy, w, h))
        n_lines = 0
        for lineno, raw in enumerate(lines, 1):
            line = raw.strip()
            if not line:
                continue
            n_lines += 1
            line_issues, box = _check_line(line)
            for level, cat, msg in line_issues:
                add(name, lineno, level, cat, msg)
            if box:
                boxes.append((lineno, box))

        # 중복 의심: 같은 Class 끼리 많이 겹침
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                (li, a), (lj, b) = boxes[i], boxes[j]
                if a[0] != b[0]:
                    continue
                iou = _iou(a[1:], b[1:])
                if iou >= DUP_IOU:
                    kind = "완전히 같은 좌표" if iou > 0.9999 else f"IoU {iou:.2f}"
                    add(name, lj, "WARN", "중복 의심 BBox", f"{li}행과 같은 Class 박스가 겹침 ({kind})")

        if n_lines == 0:
            add(name, "-", "INFO", "Empty Label",
                "TXT 는 있는데 박스가 0개 (정상 김치라면 문제 없음, Cross Review 대상)")

        if meta:
            if meta.num_boxes != n_lines:
                add(name, "-", "WARN", "기록 불일치", f"CSV BBox 수({meta.num_boxes})와 TXT({n_lines}) 다름")
            if meta.scene_type == "normal_kimchi" and n_lines > 0:
                add(name, "-", "WARN", "기록 불일치", "Scene Type 이 '정상 김치'인데 BBox 가 있음")
            if meta.scene_type in ("kimchi_with_target", "object_only") and n_lines == 0:
                add(name, "-", "WARN", "기록 불일치", "Scene Type 은 대상 포함인데 BBox 가 없음")

    # TXT는 있는데 JPG 없음
    for d in scan_dirs:
        if not os.path.isdir(d):
            continue
        stems = {os.path.splitext(f)[0] for f in os.listdir(d) if f.lower().endswith(IMAGE_EXTS)}
        for fn in sorted(os.listdir(d)):
            if (fn.lower().endswith(".txt") and fn != "classes.txt"
                    and not fn.endswith(REVIEW_NOTE_SUFFIX + ".txt")
                    and os.path.splitext(fn)[0] not in stems):
                add(fn, "-", "WARN", "TXT는 있는데 JPG 없음", "같은 이름의 이미지가 폴더에 없음")

    order = {c: i for i, c in enumerate(CATEGORIES)}
    issues.sort(key=lambda it: (order.get(it["category"], 99), str(it["file"])))
    return issues
