"""[산출물 11] 교과 8 Handoff — FINAL 데이터를 바로 찾아 쓸 수 있도록 한곳에 정리

사용법 (build_final · build_manifest · qa_summary 실행 후)
    python tools/build_handoff.py
결과
    docs/subject08_handoff.md
"""
from __future__ import annotations

import csv
import os
from collections import Counter
from datetime import datetime

from common import C, DOCS_DIR, FINAL_DIR, MANIFEST_PATH, REPORTS_DIR, class_name, is_image, read_boxes, rel, write_text


def build(quiet: bool = False):
    img_dir, lbl_dir = os.path.join(FINAL_DIR, "images"), os.path.join(FINAL_DIR, "labels")
    imgs = sorted(f for f in os.listdir(img_dir) if is_image(f)) if os.path.isdir(img_dir) else []
    txts = sorted(f for f in os.listdir(lbl_dir) if f.endswith(".txt")) if os.path.isdir(lbl_dir) else []
    cls_boxes, empty = Counter(), 0
    for t in txts:
        b = read_boxes(os.path.join(lbl_dir, t))
        empty += not b
        cls_boxes.update(x[0] for x in b)
    split = Counter()
    if os.path.isfile(MANIFEST_PATH):
        with open(MANIFEST_PATH, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if r.get("in_final") == "Y":
                    split[(r["source_dataset"], r["original_split"])] += 1
    qa_text = ""
    qp = os.path.join(REPORTS_DIR, "qa_summary.md")
    if os.path.isfile(qp):
        with open(qp, encoding="utf-8") as f:
            qa_text = next((ln.strip("* \n") for ln in f if ln.startswith("**최종 판정")), "")

    names_yaml = "\n".join(f"  {cid}: {class_name(cid)}" for cid in sorted(C.CLASS_NAMES))
    L = ["# 교과 8 Handoff — 조각김치 이물검출 FINAL Dataset\n",
         f"> 생성: {datetime.now():%Y-%m-%d %H:%M} · `python tools/build_handoff.py`\n",
         "## 1. 한눈에 보기\n",
         "| 항목 | 내용 |\n|---|---|",
         f"| FINAL 이미지 | {len(imgs)}장 (`data/final/images/`) |",
         f"| FINAL YOLO TXT | {len(txts)}개 (`data/final/labels/`) |",
         f"| 전체 BBox | {sum(cls_boxes.values())}개 |",
         f"| Empty Label (배경 이미지) | {empty}장 — 빈 TXT, 이물 없음으로 학습 |",
         f"| 최종 QA | {qa_text or '`reports/qa_summary.md` 참고'} |",
         "| 이미지 원본 | 저장소에 올리지 않음 (데이터 보안) — 팀 공유 위치에서 전달 |\n",
         "## 2. 폴더 구조\n",
         "```\ndata/final/\n├── images/      <이름>.jpg\n├── labels/      <이름>.txt   (이미지와 이름 1:1)\n"
         "└── final_list.csv   각 파일을 어느 검수 결과에서 가져왔는지\n```\n",
         "## 3. YOLO Label 형식\n",
         "```\nclass_id x_center y_center width height\n```\n",
         "- 한 줄 = 객체 1개, 좌표는 이미지 크기 대비 0~1 비율 (소수 6자리)",
         "- 박스가 없는 이미지는 **빈 TXT** (삭제하지 말 것 — 오검출을 줄이는 배경 데이터)",
         "- 이미지 EXIF 회전이 반영된 방향 기준 좌표\n",
         "## 4. Class 정보\n",
         "| ID | 이름 | 사용 | FINAL BBox 수 |\n|---:|---|:---:|---:|"]
    for cid in sorted(C.CLASS_NAMES):
        L.append(f"| {cid} | {class_name(cid)} | {'✕' if cid in C.UNUSED_CLASSES else '○'} | {cls_boxes.get(cid, 0)} |")
    L += ["\n- Class 4(고무장갑)는 사용하지 않지만 **ID 순서를 유지하기 위해 번호는 비워 둠** → 학습 설정에서도 nc=7 로 두는 것을 권장",
          "  (ID 를 당겨서 바꾸면 기존 TXT 와 번호가 어긋남)",
          "- 판단 기준: `docs/class_guide.md` · BBox 기준: `docs/bbox_guide.md` · 프로그램 설정: `configs/classes.yaml`\n",
          "## 5. 원본 출처 / 기존 Split\n",
          "| source_dataset | original_split | FINAL 이미지 |\n|---|---|---:|"]
    for (d, s), v in sorted(split.items()):
        L.append(f"| {d} | {s} | {v} |")
    if not split:
        L.append("| (Manifest 없음) | - | - |")
    L += ["\n- 이미지별 출처·Split·작업 이력: `manifests/dataset_manifest.csv`",
          "- Train / Validation / Test 를 다시 나눌 때는 **같은 촬영 묶음(파일명 날짜·시각이 연속된 이미지)이 "
          "양쪽에 섞이지 않게** 나누는 것을 권장 (비슷한 장면이 섞이면 검증 점수가 부풀려짐)\n",
          "## 6. 학습 설정 예시 (dataset.yaml)\n",
          "```yaml\npath: data/final_split      # Train/Val 로 나눈 뒤의 위치\ntrain: images/train\nval: images/val\n"
          f"nc: {len(C.CLASS_NAMES)}\nnames:\n{names_yaml}\n```\n",
          "## 7. 관련 문서\n",
          "| 문서 | 위치 |\n|---|---|",
          "| QA 결과 | `reports/qa_summary.md` |",
          "| 프로그램 시험 결과 | `reports/test_report.md` |",
          "| Dataset Manifest | `manifests/dataset_manifest.csv` |",
          "| Class 기준서 | `docs/class_guide.md` |",
          "| BBox 기준서 | `docs/bbox_guide.md` |",
          "| 팀 작업 기준 | `docs/project_baseline.md` |\n"]
    path = os.path.join(DOCS_DIR, "subject08_handoff.md")
    write_text(path, "\n".join(L))
    if not quiet:
        print(f"[Handoff] → {rel(path)}")


if __name__ == "__main__":
    build()
