"""교과 7 산출물 자동 생성 — 한 번에 실행

사용법 (프로젝트 최상위에서, 가상환경 켠 상태)
    (팀원별 컴퓨터에서 검수했다면 먼저) python tools/merge_collected.py <모은 폴더>
    python tools/make_all.py                # 기대 수량 900장
    python tools/make_all.py --expected 900

실행 순서와 결과
    1. build_final.py     → data/final/images, data/final/labels, data/final/final_list.csv   (산출물 3)
    2. build_manifest.py  → manifests/dataset_manifest.csv                                    (산출물 7)
    3. qa_summary.py      → reports/qa_summary.md                                             (산출물 8)
    4. test_report.py     → reports/test_report.md                                            (산출물 9)
    5. build_handoff.py   → docs/subject08_handoff.md                                         (산출물 11)
    6. export_evidence.py → evidence/ (FINAL 구조·수량, 대표 이미지·TXT)  — LMS 제출용, Git 제외   (산출물 3 증빙)
원본 이미지·TXT 와 작업자/·검수자/·2차검수자/ 결과 폴더는 읽기만 하고 수정하지 않는다.
data/merged/ 가 있으면 그 합본을, 없으면 프로젝트 결과 폴더를 읽는다 (tools/common.py results_mode).
"""
import argparse
import os

import build_final
import build_handoff
import build_manifest
import export_evidence
import qa_summary
import test_report
from common import ROOT

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="교과 7 산출물 자동 생성")
    ap.add_argument("--expected", type=int, default=900, help="기대 이미지 수 (기본 900)")
    args = ap.parse_args()
    os.chdir(ROOT)
    print("=" * 60)
    build_final.build()
    build_manifest.build()
    qa = qa_summary.build(args.expected)
    test_report.build()
    build_handoff.build()
    export_evidence.build()
    print("=" * 60)
    print("완료. 최종 판정:", "QA 완료" if qa and qa["done"] else "QA 미완료 — reports/qa_summary.md 확인")
