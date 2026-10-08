"""[산출물 8] QA Summary — 자동 Validation + Human QA 결과를 실제 데이터로 집계

사용법 (build_final.py 실행 후)
    python tools/qa_summary.py               # 기대 수량 900장 기준
    python tools/qa_summary.py --expected 900
결과
    reports/qa_summary.md

집계 내용
    1. 전체 데이터       검수 기록 수, FINAL 이미지·TXT 수, Pair 일치
    2. 자동 Validation   원본(받아온) 라벨 검사 결과 → FINAL 라벨 검사 결과 (전 / 후)
    3. Human QA          1차·2차 검수 판정 분포, 원본 대비 수정 내용, Class 변경 표
    4. FINAL 데이터 구성 Class 별 박스 수, Empty Label(배경) 이미지
    5. 최종 결과         PASS / FAIL / REVIEW, 최종 판정
"""
from __future__ import annotations

import argparse
import os
from collections import Counter
from datetime import datetime

from common import (C, FINAL_DIR, REPORTS_DIR, RawIndex, class_name, compare_boxes, final_decision,
                    is_image, iou, label_path, load_records, read_boxes, rel, results_mode, source_of, status_of, stem,
                    write_text)
from src.validation.validator import CATEGORIES, validate_folder

LEVEL_KO = {"ERROR": "오류", "WARN": "경고", "INFO": "참고"}


def _validate(names, label_of):
    issues = validate_folder(names, lambda n: (label_of(n), ""), lambda n: None, [])
    by_cat = Counter(i["category"] for i in issues)
    by_level = Counter(i["level"] for i in issues)
    fail_files = {i["file"] for i in issues if i["level"] == "ERROR"}
    return issues, by_cat, by_level, fail_files


DEFAULT_LEVEL = {"JPG는 있는데 TXT 없음": "경고", "TXT는 있는데 JPG 없음": "경고", "TXT 한 줄 구조 오류": "오류",
                 "숫자 변환 오류": "오류", "Class 범위 오류": "오류", "Class 4 발견": "오류", "좌표 범위 오류": "오류",
                 "Width/Height 비정상": "오류 / 경고", "BBox 경계 오류": "경고", "중복 의심 BBox": "경고",
                 "Empty Label": "참고"}


def _cat_table(by_cat_before, by_cat_after, issues_b, issues_a):
    level = {}
    lines = ["| 검사 항목 | 수준 | 원본 라벨 | FINAL 라벨 |", "|---|:---:|---:|---:|"]
    for c in CATEGORIES:
        if c == "기록 불일치":
            continue
        lv = DEFAULT_LEVEL.get(c, "-")
        lines.append(f"| {c} | {lv} | {by_cat_before.get(c, 0)} | {by_cat_after.get(c, 0)} |")
    return "\n".join(lines)


def _class_matrix(raw_all, fin_all):
    """원본 Class → FINAL Class (IoU 0.5 이상으로 짝지은 박스만)"""
    m = Counter()
    for raw, fin in zip(raw_all, fin_all):
        pairs = sorted(((iou(r, f), i, j) for i, r in enumerate(raw) for j, f in enumerate(fin)), reverse=True)
        ur, uf = set(), set()
        for v, i, j in pairs:
            if v < 0.5:
                break
            if i in ur or j in uf:
                continue
            ur.add(i)
            uf.add(j)
            if raw[i][0] != fin[j][0]:
                m[(raw[i][0], fin[j][0])] += 1
    return m


def build(expected: int = 900, quiet: bool = False):
    records = load_records()
    raw_index = RawIndex()
    img_dir, lbl_dir = os.path.join(FINAL_DIR, "images"), os.path.join(FINAL_DIR, "labels")
    final_imgs = sorted(f for f in os.listdir(img_dir) if is_image(f)) if os.path.isdir(img_dir) else []
    final_txts = sorted(f for f in os.listdir(lbl_dir) if f.endswith(".txt")) if os.path.isdir(lbl_dir) else []
    img_stems, txt_stems = {stem(f) for f in final_imgs}, {stem(f) for f in final_txts}
    only_img, only_txt = sorted(img_stems - txt_stems), sorted(txt_stems - img_stems)

    # ------------------------------------------------ 2. 자동 Validation (원본 → FINAL)
    raw_label = {}
    for n, rec in records.items():
        raw_label[n] = RawIndex.raw_label(raw_index.image(n, source_of(rec)))
    issues_b, cat_b, lvl_b, fail_b = _validate(list(records), lambda n: raw_label.get(n))
    issues_a, cat_a, lvl_a, fail_a = _validate(
        final_imgs, lambda n: (os.path.join(lbl_dir, stem(n) + ".txt")
                               if os.path.isfile(os.path.join(lbl_dir, stem(n) + ".txt")) else None))
    raw_missing = sum(1 for v in raw_label.values() if v is None)

    # ------------------------------------------------ 3. Human QA
    s1 = Counter(status_of(r, "reviewer") or "(기록 없음)" for r in records.values())
    s2 = Counter(status_of(r, "reviewer2") or "(기록 없음)" for r in records.values())
    sw = Counter(status_of(r, "worker") or "(기록 없음)" for r in records.values())
    review_hist = [n for n, r in records.items()
                   if "REVIEW" in (status_of(r, "worker"), status_of(r, "reviewer"))]
    decisions = {n: final_decision(r) for n, r in records.items()}
    unresolved = [n for n, d in decisions.items() if not d[0] and d[3] == "미해결 REVIEW"]
    waiting = [n for n, d in decisions.items() if not d[0] and d[3] != "미해결 REVIEW"]
    review_resolved = [n for n in review_hist if decisions[n][0]]

    diff_total, changed_imgs, raw_all, fin_all = Counter(), 0, [], []
    for n, (ok, role, st, _) in decisions.items():
        if not ok or raw_label.get(n) is None:
            continue
        rb = read_boxes(raw_label[n])
        fb = read_boxes(label_path(n, role, st))
        d = compare_boxes(rb, fb)
        diff_total.update(d)
        if d["added"] + d["removed"] + d["class_changed"] + d["moved"]:
            changed_imgs += 1
        raw_all.append(rb)
        fin_all.append(fb)
    matrix = _class_matrix(raw_all, fin_all)
    raw_err_fixed = [f for f in fail_b if decisions.get(f, (False,))[0] and f not in fail_a]

    # ------------------------------------------------ 4. FINAL 구성
    cls_boxes, cls_imgs, empty, box_total = Counter(), Counter(), 0, 0
    for t in final_txts:
        b = read_boxes(os.path.join(lbl_dir, t))
        box_total += len(b)
        if not b:
            empty += 1
        cls_boxes.update(x[0] for x in b)
        cls_imgs.update({x[0] for x in b})

    # ------------------------------------------------ 5. 최종 판정
    fail_final = len(fail_a) + len(only_img) + len(only_txt)
    checks = [
        ("FINAL 이미지 수 = 기대 수량", len(final_imgs) == expected, f"{len(final_imgs)} / {expected}"),
        ("이미지 ↔ TXT Pair 일치", not only_img and not only_txt and len(final_imgs) == len(final_txts),
         f"이미지만 {len(only_img)} · TXT만 {len(only_txt)}"),
        ("FINAL Validation 오류 0", not fail_a, f"오류 이미지 {len(fail_a)}"),
        ("미해결 REVIEW 0", not unresolved, f"{len(unresolved)}"),
        ("검수 대기 0", not waiting, f"{len(waiting)}"),
    ]
    done = all(ok for _, ok, _ in checks)

    pct = lambda a, b: f"{a / b * 100:.1f}%" if b else "-"      # noqa: E731
    L = []
    L.append("# QA Summary — 조각김치 이물검출 FINAL 데이터\n")
    L.append(f"> 생성: {datetime.now():%Y-%m-%d %H:%M} · `python tools/qa_summary.py` 로 실제 결과 폴더에서 자동 집계\n"
             "> 자동 Validation 은 라벨링 프로그램의 Validation 기능(`src/validation/validator.py`)과 같은 검사입니다.\n")
    L.append("## 1. 전체 데이터\n")
    L.append("| 항목 | 값 |\n|---|---:|")
    L.append(f"| 기대 수량 | {expected}장 |")
    L.append(f"| 검수 기록이 있는 이미지 | {len(records)}장 |")
    L.append(f"| FINAL 이미지 (`data/final/images`) | {len(final_imgs)}장 |")
    L.append(f"| FINAL TXT (`data/final/labels`) | {len(final_txts)}개 |")
    L.append(f"| 이미지만 있음 / TXT만 있음 | {len(only_img)} / {len(only_txt)} |")
    no_r2 = sum(1 for d in decisions.values() if d[0] and d[2] == "기록 없음")
    L.append(f"| FINAL 전체 BBox | {box_total}개 |")
    L.append(f"| 결과 위치 | {'팀원별 결과 합본 (`data/merged/`)' if results_mode() == 'merged' else '프로젝트 결과 폴더'} |")
    if no_r2:
        L.append(f"| ⚠ 2차 검수 CSV 기록 없이 TXT 만 있는 FINAL | {no_r2}장 |")
    L.append("")

    L.append("## 2. 자동 Validation 결과\n")
    L.append("받아온 **원본 라벨**과 검수를 마친 **FINAL 라벨**을 같은 기준으로 검사했습니다.\n")
    L.append("| 구분 | 검사 이미지 | 오류(FAIL) 이미지 | 오류 | 경고 | 참고 |\n|---|---:|---:|---:|---:|---:|")
    L.append(f"| 원본 라벨 | {len(records)} | {len(fail_b)} | {lvl_b.get('ERROR', 0)} | {lvl_b.get('WARN', 0)} | "
             f"{lvl_b.get('INFO', 0)} |")
    L.append(f"| FINAL 라벨 | {len(final_imgs)} | {len(fail_a)} | {lvl_a.get('ERROR', 0)} | {lvl_a.get('WARN', 0)} | "
             f"{lvl_a.get('INFO', 0)} |\n")
    if raw_missing:
        L.append(f"> 원본 TXT 를 찾지 못한 이미지 {raw_missing}장은 원본 검사에서 'JPG는 있는데 TXT 없음'으로 집계됩니다.\n")
    L.append("### 항목별 건수\n")
    L.append(_cat_table(cat_b, cat_a, issues_b, issues_a) + "\n")
    L.append("- **Empty Label(참고)** 은 정상 김치처럼 대상이 없는 이미지에서는 정상입니다. "
             "Human QA 에서 이미지를 직접 보고 누락 여부를 확인했습니다.")
    L.append("- **경고** 는 형식 오류가 아니라 사람이 확인할 대상(작은 박스·중복 의심·경계)입니다.\n")
    L.append(f"원본에서 오류가 있던 이미지 {len(fail_b)}장 중 **{len(raw_err_fixed)}장**이 검수 후 FINAL 에서 오류 없이 정리되었습니다.\n")

    L.append("## 3. Human QA 결과\n")
    L.append("작업자 → 1차 검수자 → 2차 검수자 순서로 전체 이미지를 사람이 직접 확인했습니다.\n")
    L.append("### 단계별 판정\n")
    L.append("| 단계 | 판정 분포 |\n|---|---|")
    L.append(f"| 작업자 | {', '.join(f'{k} {v}' for k, v in sorted(sw.items()))} |")
    L.append(f"| 1차 검수자 | {', '.join(f'{k} {v}' for k, v in sorted(s1.items()))} |")
    L.append(f"| 2차 검수자 | {', '.join(f'{k} {v}' for k, v in sorted(s2.items()))} |\n")
    L.append("### 원본 라벨 대비 수정 내용 (FINAL 기준, IoU 0.5 로 박스 짝짓기)\n")
    L.append("| 항목 | 건수 |\n|---|---:|")
    L.append(f"| 수정이 있었던 이미지 | {changed_imgs}장 |")
    L.append(f"| 누락 객체 추가 (BBox 추가) | {diff_total['added']} |")
    L.append(f"| 잘못된 BBox 삭제 | {diff_total['removed']} |")
    L.append(f"| Class 변경 | {diff_total['class_changed']} |")
    L.append(f"| 위치·크기 수정 (IoU 0.5~0.95) | {diff_total['moved']} |")
    L.append(f"| 그대로 유지 | {diff_total['kept']} |\n")
    if matrix:
        L.append("### Class 변경 내역 (원본 → FINAL)\n")
        L.append("| 원본 Class | FINAL Class | 건수 |\n|---|---|---:|")
        for (a, b), v in matrix.most_common():
            L.append(f"| {a} {class_name(a)} | {b} {class_name(b)} | {v} |")
        L.append("")
    L.append("### REVIEW 처리\n")
    L.append("| 항목 | 건수 |\n|---|---:|")
    L.append(f"| 작업 중 REVIEW 로 올라온 이미지 | {len(review_hist)} |")
    L.append(f"| 2차 검수에서 판단 완료 | {len(review_resolved)} |")
    L.append(f"| 미해결 REVIEW | {len(unresolved)} |\n")

    L.append("## 4. FINAL 데이터 구성\n")
    L.append("| Class | 이름 | BBox 수 | 포함 이미지 수 |\n|---:|---|---:|---:|")
    for cid in sorted(set(C.CLASS_NAMES) | set(cls_boxes)):
        note = " (사용 안 함)" if cid in C.UNUSED_CLASSES else ""
        L.append(f"| {cid} | {class_name(cid)}{'' if '사용 안 함' in class_name(cid) else note} | "
                 f"{cls_boxes.get(cid, 0)} | {cls_imgs.get(cid, 0)} |")
    L.append(f"\n- Empty Label(검출 대상이 없는 배경 이미지): **{empty}장** ({pct(empty, len(final_txts))})")
    rare = [cid for cid in C.ENABLED_CLASSES if cls_boxes.get(cid, 0) < 50]
    if rare:
        L.append(f"- BBox 50개 미만 Class: {', '.join(f'{c} {class_name(c)}({cls_boxes.get(c, 0)})' for c in rare)}"
                 " → 교과 8 학습 시 Class 불균형 주의 (증강·가중치 검토)")
    L.append("")

    L.append("## 5. 최종 결과\n")
    L.append("| 항목 | 결과 |\n|---|---:|")
    L.append(f"| PASS (FINAL 포함, Validation 오류 없음) | {len(final_imgs) - len(fail_a)}장 |")
    L.append(f"| FAIL (FINAL Validation 오류·Pair 불일치) | {fail_final}건 |")
    L.append(f"| REVIEW (미해결) | {len(unresolved)}장 |")
    L.append(f"| 검수 대기 (FINAL 제외) | {len(waiting)}장 |\n")
    L.append("| 완료 조건 | 충족 | 값 |\n|---|:---:|---|")
    for label, ok, val in checks:
        L.append(f"| {label} | {'✅' if ok else '❌'} | {val} |")
    L.append(f"\n**최종 판정: {'QA 완료 — 교과 8 학습 데이터로 사용 가능' if done else 'QA 미완료 — 위 ❌ 항목 처리 필요'}**\n")
    if fail_a:
        L.append("### 남은 FINAL 오류 (최대 20건)\n")
        for i in [x for x in issues_a if x["level"] == "ERROR"][:20]:
            L.append(f"- `{i['file']}` {i['line']}행 · {i['category']} · {i['msg']}")
        L.append("")
    if unresolved or waiting:
        L.append("### FINAL 에서 제외된 이미지 (최대 20건)\n")
        for n in (unresolved + waiting)[:20]:
            L.append(f"- `{n}` · {decisions[n][3]}")
        L.append("")

    path = os.path.join(REPORTS_DIR, "qa_summary.md")
    write_text(path, "\n".join(L))
    if not quiet:
        print(f"[QA] → {rel(path)} · FINAL {len(final_imgs)} · FAIL {fail_final} · REVIEW {len(unresolved)} · "
              f"{'QA 완료' if done else 'QA 미완료'}")
    return {"done": done, "final": len(final_imgs), "fail": fail_final, "review": len(unresolved),
            "waiting": len(waiting), "boxes": box_total, "empty": empty, "cls_boxes": cls_boxes,
            "cls_imgs": cls_imgs}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="QA Summary 자동 생성")
    ap.add_argument("--expected", type=int, default=900, help="기대 이미지 수 (기본 900)")
    build(ap.parse_args().expected)
