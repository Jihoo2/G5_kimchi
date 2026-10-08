"""팀원들이 각자 컴퓨터에서 만든 결과를 하나로 합치기 → data/merged/

사용법 (프로젝트 최상위에서)
    python tools/merge_collected.py <모은 폴더>
    예) python tools/merge_collected.py 수집
        python tools/merge_collected.py "/mnt/c/Users/user1/Desktop/수집"

<모은 폴더> 에 넣을 것 (하위 폴더 구조는 자유, 팀원별 폴더로 나눠도 됨)
    - 2차 검수를 마친 YOLO TXT        (<이미지이름>.txt)
    - 각 팀원의 label_status.csv       (작업자/ · 검수자/ · 2차검수자/ 의 CSV, 이름을 바꿔도 됨)
    이미지는 넣지 않아도 됨 → 프로젝트 안의 원본 이미지 폴더에서 찾음

결과
    data/merged/labels/<이름>.txt       FINAL 원천 TXT (같은 이름이 여러 개면 규칙에 따라 하나만)
    data/merged/worker.csv              작업자 기록 합본
    data/merged/reviewer.csv            1차 검수 기록 합본
    data/merged/reviewer2.csv           2차 검수 기록 합본
    data/merged/merge_report.txt        합친 결과·충돌·누락 보고
이후 python tools/make_all.py 를 실행하면 data/merged/ 를 자동으로 사용한다.

판단 규칙
    TXT 와 노트 구분   이슈노트/ 폴더, <이름>_리뷰노트.txt, '[작업 … 노트]' 로 시작하는 파일은 노트로 보고 제외
    같은 이름 TXT 여러 개   경로에 2차검수자 > reviewed > edited > pass 순으로 우선, 같으면 최근 수정 파일
                         내용이 서로 다르면 보고서에 '충돌'로 표시
    CSV 역할 판단     폴더·파일 이름에 2차검수자(2차) / 검수자(1차) / 작업자 가 있으면 그 역할,
                      없으면 행마다 판단 (reviewer2 칸이 있으면 2차, PASS·REVIEWED 또는 reviewer 칸이 있으면 1차, 그 외 작업자)
    같은 이미지 기록 여러 개   updated_at 이 가장 최근인 행
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
from collections import Counter, defaultdict

from common import C, MERGED_DIR, ROOT, RawIndex, rel, stem, write_text

FIELDS = ["filename", "status", "assignee", "reviewer", "reviewer2", "scene_type", "note", "num_boxes",
          "updated_at", "source"]
TXT_PRIORITY = [C.REVIEWER2_DIR, C.STATUS_DIRS["REVIEWED"], C.STATUS_DIRS["EDITED"], C.STATUS_DIRS["PASS"]]


def _parts(path):
    return [p for p in os.path.normpath(path).split(os.sep) if p]


def is_note(path: str) -> bool:
    """이슈노트·리뷰노트 TXT 인지 (YOLO 라벨과 이름이 같을 수 있어 내용까지 확인)"""
    if C.ISSUE_NOTE_DIR in _parts(os.path.dirname(path)) or path.endswith(C.REVIEW_NOTE_SUFFIX + ".txt"):
        return True
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            first = next((ln.strip() for ln in f if ln.strip()), "")
    except OSError:
        return True
    return first.startswith("[")


def read_csv_any(path: str):
    """utf-8 / Excel 저장(cp949) 모두 읽기"""
    for enc in ("utf-8-sig", "cp949"):
        try:
            with open(path, encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    return None


def csv_role(path: str, base: str = ""):
    """CSV 경로·파일 이름으로 역할 판단 (2차검수자 > 검수자 > 작업자 순서로 확인, '검수자' 가 '2차검수자' 에 포함되므로)
    예) 2차검수자/label_status.csv, 검수자_팀원A.csv, 1차검수_B.csv, 작업자 기록.csv"""
    text = (os.path.relpath(path, base) if base else path).replace("\\", "/")   # 모은 폴더 안쪽 경로만 봄
    keys = [("reviewer2", (C.REVIEWER2_DIR, "2차")), ("reviewer", (C.REVIEWER_DIR, "1차")), ("worker", (C.WORKER_DIR,))]
    for role, words in keys:
        if any(w in text for w in words):
            return role
    return None


def row_role(row: dict) -> str:
    if (row.get("reviewer2") or "").strip():
        return "reviewer2"
    if row.get("status") in ("PASS", "REVIEWED") or (row.get("reviewer") or "").strip():
        return "reviewer"
    return "worker"


def txt_rank(path: str):
    parts = _parts(path)
    return (min((i for i, k in enumerate(TXT_PRIORITY) if k in parts), default=len(TXT_PRIORITY)),
            -os.path.getmtime(path))


def merge(src: str):
    src = os.path.abspath(src)
    if not os.path.isdir(src):
        raise SystemExit(f"폴더가 없습니다: {src}")
    txts, notes, csvs = defaultdict(list), 0, []
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__", ".git")]
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            if fn.lower().endswith(".csv"):
                csvs.append(p)
            elif fn.lower().endswith(".txt") and fn != "classes.txt":
                if is_note(p):
                    notes += 1
                else:
                    txts[stem(fn)].append(p)

    # ---------------- TXT
    out_lbl = os.path.join(MERGED_DIR, "labels")
    shutil.rmtree(MERGED_DIR, ignore_errors=True)
    os.makedirs(out_lbl)
    conflicts, dup = [], 0
    for s, paths in sorted(txts.items()):
        paths.sort(key=txt_rank)
        if len(paths) > 1:
            dup += 1
            bodies = {open(p, encoding="utf-8", errors="replace").read().strip() for p in paths}
            if len(bodies) > 1:
                conflicts.append((s, [rel(p) if p.startswith(ROOT) else p for p in paths]))
        shutil.copy2(paths[0], os.path.join(out_lbl, s + ".txt"))

    # ---------------- CSV
    merged = {"worker": {}, "reviewer": {}, "reviewer2": {}}
    skipped_csv, rows_in, how = [], Counter(), []
    for p in csvs:
        rows = read_csv_any(p)
        if rows is None or not rows or "filename" not in rows[0] or "status" not in rows[0]:
            skipped_csv.append(p)
            continue
        fixed = csv_role(p, src)
        how.append((p, fixed or "행 내용으로 판단"))
        for r in rows:
            if not r.get("filename"):
                continue
            role = fixed or row_role(r)
            rows_in[role] += 1
            old = merged[role].get(r["filename"])
            if old is None or (r.get("updated_at") or "") >= (old.get("updated_at") or ""):
                merged[role][r["filename"]] = {k: (r.get(k) or "") for k in FIELDS}
    for role, table in merged.items():
        with open(os.path.join(MERGED_DIR, f"{role}.csv"), "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(table[k] for k in sorted(table))

    # ---------------- 점검
    raw = RawIndex()
    img_stems = {stem(n): n for n in raw.images}
    no_image = sorted(s for s in txts if s not in img_stems)
    r2_names = {stem(n) for n in merged["reviewer2"]}
    txt_no_r2 = sorted(s for s in txts if s not in r2_names)
    r2_no_txt = sorted(s for s in r2_names if s not in txts)

    L = ["팀원 결과 합치기 보고서", "=" * 40, f"모은 폴더: {src}", "",
         f"YOLO TXT (FINAL 원천)   : {len(txts)}개  (같은 이름 여러 개 {dup}개, 그중 내용이 다른 충돌 {len(conflicts)}개)",
         f"제외한 노트 TXT         : {notes}개",
         f"읽은 CSV                : {len(csvs) - len(skipped_csv)}개 (형식이 달라 건너뜀 {len(skipped_csv)}개)",
         f"  작업자 기록           : {len(merged['worker'])}장 (행 {rows_in['worker']})",
         f"  1차 검수 기록         : {len(merged['reviewer'])}장 (행 {rows_in['reviewer']})",
         f"  2차 검수 기록         : {len(merged['reviewer2'])}장 (행 {rows_in['reviewer2']})", "",
         f"원본 이미지를 못 찾은 TXT : {len(no_image)}",
         f"2차 CSV 기록 없는 TXT    : {len(txt_no_r2)}",
         f"2차 CSV 는 있는데 TXT 없음 : {len(r2_no_txt)}", ""]

    def section(title, items, fmt=str):
        if items:
            L.append(f"[{title}] {len(items)}건")
            L.extend("  - " + fmt(x) for x in items[:50])
            if len(items) > 50:
                L.append(f"  … 외 {len(items) - 50}건")
            L.append("")
    section("내용이 다른 같은 이름 TXT (우선순위가 높은 첫 번째를 사용)", conflicts,
            lambda c: f"{c[0]}: " + " | ".join(c[1]))
    section("원본 이미지를 못 찾은 TXT (원본 폴더를 프로젝트 안에 두세요)", no_image)
    section("2차 CSV 기록이 없는 TXT", txt_no_r2)
    section("2차 CSV 는 있는데 TXT 가 없음", r2_no_txt)
    section("건너뛴 CSV", skipped_csv)
    names = {"reviewer2": "2차 검수", "reviewer": "1차 검수", "worker": "작업자"}
    section("CSV 별 단계 판단 (파일·폴더 이름에 단계가 없으면 '행 내용으로 판단')", how,
            lambda h: f"{os.path.relpath(h[0], src)} → {names.get(h[1], h[1])}")
    report = "\n".join(L)
    write_text(os.path.join(MERGED_DIR, "merge_report.txt"), report + "\n")
    print(report)
    print(f"→ {rel(MERGED_DIR)}/ 생성. 이어서 python tools/make_all.py 를 실행하세요.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="팀원 결과(2차 검수 TXT + label_status.csv) 합치기")
    ap.add_argument("folder", help="모은 파일이 있는 폴더")
    merge(ap.parse_args().folder)
