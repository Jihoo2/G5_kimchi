"""[산출물 3] FINAL YOLO 데이터 만들기 — 2차 검수 결과를 data/final/ 로 모음

사용법 (프로젝트 최상위에서, 가상환경 켠 상태)
    python tools/build_final.py            # data/final/ 을 새로 만듦
    python tools/build_final.py --dry-run  # 복사하지 않고 결과만 확인

결과
    data/final/images/<이름>.jpg      FINAL 이미지
    data/final/labels/<이름>.txt      FINAL YOLO TXT (박스 없으면 빈 파일 = 배경 이미지)
    data/final/final_list.csv         어떤 결과 폴더에서 가져왔는지 기록

FINAL 기준 (tools/common.py final_decision)
    2차 검수 PASS / EDITED / REVIEWED → FINAL
    (2차 기록이 없고 1차 검수가 REVIEWED 인 예전 방식 결과도 FINAL)
    그 외(미해결 REVIEW, 검수 대기)는 제외하고 사유를 출력
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
from collections import Counter

from common import (FINAL_DIR, ROOT, RawIndex, final_decision, label_path, load_records, rel, result_dir,
                    results_mode, source_of, stem)


def build(dry_run: bool = False, quiet: bool = False):
    records = load_records()
    raw = RawIndex()
    img_dir, lbl_dir = os.path.join(FINAL_DIR, "images"), os.path.join(FINAL_DIR, "labels")
    if not dry_run:
        for d in (img_dir, lbl_dir):
            shutil.rmtree(d, ignore_errors=True)
            os.makedirs(d)

    rows, excluded, problems = [], Counter(), []
    for name, rec in records.items():
        ok, role, status, reason = final_decision(rec)
        if not ok:
            excluded[reason] += 1
            problems.append((name, reason))
            continue
        txt = label_path(name, role, status)
        img = os.path.join(result_dir(role, status), name) if role != "merged" else ""
        if not img or not os.path.isfile(img):          # 결과 폴더에 이미지가 없으면 원본에서 가져옴
            img = raw.image(name, source_of(rec))
        if not os.path.isfile(txt):
            excluded["결과 TXT 없음"] += 1
            problems.append((name, f"결과 TXT 없음: {rel(txt)}"))
            continue
        if not img or not os.path.isfile(img):
            excluded["이미지 없음"] += 1
            problems.append((name, "이미지를 찾을 수 없음"))
            continue
        if not dry_run:
            shutil.copy2(img, os.path.join(img_dir, name))
            shutil.copy2(txt, os.path.join(lbl_dir, stem(name) + ".txt"))
        rows.append({"file_name": name, "from_role": role, "from_status": status,
                     "label_from": rel(txt), "image_from": rel(img)})

    if not dry_run:
        with open(os.path.join(FINAL_DIR, "final_list.csv"), "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else
                               ["file_name", "from_role", "from_status", "label_from", "image_from"])
            w.writeheader()
            w.writerows(rows)

    if not quiet:
        print(f"[FINAL] 결과 위치: {'data/merged (팀원 결과 합본)' if results_mode() == 'merged' else '프로젝트 결과 폴더'}")
        print(f"[FINAL] 검수 기록 {len(records)}장 → FINAL {len(rows)}장"
              + (" (dry-run, 복사 안 함)" if dry_run else f" → {rel(FINAL_DIR)}/"))
        by = Counter(f"{r['from_role']}:{r['from_status']}" for r in rows)
        for k, v in sorted(by.items()):
            print(f"   {k:<22} {v}")
        if excluded:
            print("[제외]", dict(excluded))
            for name, why in problems[:20]:
                print(f"   - {name}: {why}")
            if len(problems) > 20:
                print(f"   … 외 {len(problems) - 20}건")
    return {"total_records": len(records), "final": rows, "excluded": excluded, "problems": problems}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="2차 검수 결과 → data/final/")
    ap.add_argument("--dry-run", action="store_true", help="복사하지 않고 결과만 출력")
    args = ap.parse_args()
    os.chdir(ROOT)
    build(args.dry_run)
