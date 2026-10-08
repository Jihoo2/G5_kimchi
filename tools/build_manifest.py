"""[산출물 7] Dataset Manifest — 이미지별 출처·작업 상태·QA 상태 작업대장

사용법
    python tools/build_manifest.py
결과
    manifests/dataset_manifest.csv   (Excel 에서 한글이 깨지지 않게 utf-8-sig)

칸 설명
    file_name         이미지 파일명
    source_dataset    원본 데이터셋 (원본 경로의 첫 폴더, 예: 이물검출_학습데이터1)
    original_split    원본 경로의 train / validation / test (없으면 unknown)
    scene_type        kimchi_with_target / normal_kimchi / object_only / need_check
    worker            작업자 이름
    status            DONE   = 원본 라벨과 FINAL 라벨이 같음 (수정 없이 검수 완료)
                      EDITED = 원본 대비 박스 추가·삭제·Class 변경·위치 수정이 있음
                      REVIEW = 아직 판단이 끝나지 않음
    qa_status         PASS = FINAL 확정 (2차 검수 완료) / WAIT = 아직 아님
    review_reason     REVIEW 였던 이유 (작업자·검수자가 Issue/Note 에 적은 내용)
    -- 추가 정보 --
    reviewer1, reviewer2              1차·2차 검수자
    worker_status, reviewer1_status, reviewer2_status   단계별 저장 상태
    raw_boxes, final_boxes            원본 / FINAL 박스 수
    added, removed, class_changed, moved   원본 대비 변경 내용 (IoU 비교)
    in_final                          data/final 에 포함됐는지 (Y/N)
"""
from __future__ import annotations

import csv
import os

from common import (MANIFEST_PATH, RawIndex, compare_boxes, final_decision, load_records, read_boxes,
                    label_path, rel, source_of, split_dataset, status_of, stem)

FIELDS = ["file_name", "source_dataset", "original_split", "scene_type", "worker", "status", "qa_status",
          "review_reason", "reviewer1", "reviewer2", "worker_status", "reviewer1_status", "reviewer2_status",
          "raw_boxes", "final_boxes", "added", "removed", "class_changed", "moved", "in_final"]


def _one_line(s: str) -> str:
    return " ".join((s or "").split())


def build(quiet: bool = False):
    records = load_records()
    raw = RawIndex()
    rows = []
    for name, rec in records.items():
        ok, role, status, reason = final_decision(rec)
        src = source_of(rec)
        img = raw.image(name, src)
        dataset, split = split_dataset("", img) if img else split_dataset(src)

        # 비교 대상: FINAL 이면 FINAL 라벨, 아니면 가장 마지막 단계의 결과
        if ok:
            final_txt = label_path(name, role, status)
        else:
            last = next((r for r in ("reviewer2", "reviewer", "worker") if status_of(rec, r)), "")
            final_txt = label_path(name, last, status_of(rec, last)) if last else None
        raw_txt = RawIndex.raw_label(img)
        raw_b, fin_b = read_boxes(raw_txt), read_boxes(final_txt)
        diff = compare_boxes(raw_b, fin_b)
        changed = diff["added"] + diff["removed"] + diff["class_changed"] + diff["moved"] > 0

        if not ok and reason == "미해결 REVIEW":
            st = "REVIEW"
        elif raw_txt is None:            # 원본 TXT 가 없으면 검수 상태로 판단
            st = "EDITED" if "EDITED" in (status_of(rec, "reviewer"), status_of(rec, "reviewer2")) else "DONE"
        else:
            st = "EDITED" if changed else "DONE"

        notes = [(r, (rec.get(r) or {}).get("note", "")) for r in ("reviewer2", "reviewer", "worker")]
        review_note = next((n for r, n in notes if status_of(rec, r) == "REVIEW" and n), "")
        if not review_note and not rec.get("worker") and not rec.get("reviewer"):
            review_note = (rec.get("reviewer2") or {}).get("note", "")   # 2차 기록만 있을 때는 2차 노트
        scene = next(((rec.get(r) or {}).get("scene_type", "") for r in ("reviewer2", "reviewer", "worker")
                      if (rec.get(r) or {}).get("scene_type")), "")
        get = lambda r, k: (rec.get(r) or {}).get(k, "")          # noqa: E731
        rows.append({
            "file_name": name, "source_dataset": dataset, "original_split": split, "scene_type": scene,
            "worker": get("worker", "assignee") or get("reviewer", "assignee") or get("reviewer2", "assignee"),
            "status": st, "qa_status": "PASS" if ok else "WAIT",
            "review_reason": _one_line(review_note),
            "reviewer1": get("reviewer", "reviewer") or get("reviewer2", "reviewer"),
            "reviewer2": get("reviewer2", "reviewer2"),
            "worker_status": status_of(rec, "worker"), "reviewer1_status": status_of(rec, "reviewer"),
            "reviewer2_status": status_of(rec, "reviewer2"),
            "raw_boxes": len(raw_b) if raw_txt else "", "final_boxes": len(fin_b),
            "added": diff["added"], "removed": diff["removed"], "class_changed": diff["class_changed"],
            "moved": diff["moved"], "in_final": "Y" if ok else "N",
        })

    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    if not quiet:
        from collections import Counter
        print(f"[Manifest] {len(rows)}행 → {rel(MANIFEST_PATH)}")
        print("   status   ", dict(Counter(r["status"] for r in rows)))
        print("   qa_status", dict(Counter(r["qa_status"] for r in rows)))
        print("   dataset  ", dict(Counter((r["source_dataset"], r["original_split"]) for r in rows)))
    return rows


if __name__ == "__main__":
    build()
