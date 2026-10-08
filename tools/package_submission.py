"""11개 산출물을 제출·발표용 폴더 하나로 정리 → submission/

사용법 (make_all.py 실행 후, 프로젝트 최상위에서)
    python tools/package_submission.py
결과
    submission/
    ├── 00_제출목록.md                       11개 산출물 목록·상태·파일 위치
    ├── 01_라벨링프로그램/   01_labeling_program.md, labeling_program.zip, captures/
    ├── 02_소스코드/         02_source_code.md, git_commit_history.txt, requirements.txt, classes.yaml
    ├── 03_FINAL_YOLO데이터/ 03_final_dataset.md, samples/ (대표 이미지·TXT), final_structure.txt
    ├── 04_Project_Baseline/ project_baseline.md
    ├── 05_Class_기준서/     class_guide.md
    ├── 06_BBox_기준서/      bbox_guide.md
    ├── 07_Dataset_Manifest/ 07_dataset_manifest.md, dataset_manifest.csv
    ├── 08_QA_Summary/       qa_summary.md
    ├── 09_Test_Report/      test_report.md
    ├── 10_README/           README.md
    └── 11_교과8_Handoff/    subject08_handoff.md
    submission.zip                          위 폴더 압축 (LMS 업로드용)

md 가 아닌 산출물(1 프로그램, 2 소스코드, 3 FINAL 데이터, 7 Manifest CSV)은 실제 데이터로 채운 설명 md 를 함께 만든다.
FINAL 이미지 900장 자체는 넣지 않는다 (산출물 예시: 구조·수량·대표 결과만 증빙). 필요하면 --with-final 로 포함.
md 를 직접 고친 뒤에는 이 스크립트만 다시 실행하면 된다 (make_all.py 를 다시 돌리면 생성 문서가 새로 덮어써짐).
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import zipfile
from collections import Counter
from datetime import datetime

from common import C, DOCS_DIR, FINAL_DIR, MANIFEST_PATH, REPORTS_DIR, ROOT, class_name, is_image, read_boxes, \
    rel, stem, write_text

OUT = os.path.join(ROOT, "submission")
EVIDENCE = os.path.join(ROOT, "evidence")
SKIP = {"__pycache__", ".git", ".venv"}

ITEMS = [  # (번호, 폴더, 산출물, 우선순위, 배점, 대표 파일)
    (1, "01_라벨링프로그램", "라벨링 프로그램", "🟠 P2", 12, "01_labeling_program.md"),
    (2, "02_소스코드", "소스코드", "🟡 P3", 7, "02_source_code.md"),
    (3, "03_FINAL_YOLO데이터", "FINAL YOLO 라벨 데이터 및 증빙", "🔴 P1", 25, "03_final_dataset.md"),
    (4, "04_Project_Baseline", "Project Baseline", "🟡 P3", 2, "project_baseline.md"),
    (5, "05_Class_기준서", "Class 기준서", "🔴 P1", 10, "class_guide.md"),
    (6, "06_BBox_기준서", "BBox 기준서", "🟠 P2", 7, "bbox_guide.md"),
    (7, "07_Dataset_Manifest", "Dataset Manifest", "🔴 P1", 12, "07_dataset_manifest.md"),
    (8, "08_QA_Summary", "QA Summary", "🔴 P1", 13, "qa_summary.md"),
    (9, "09_Test_Report", "Test Report", "🟡 P3", 4, "test_report.md"),
    (10, "10_README", "README", "🟡 P3", 2, "README.md"),
    (11, "11_교과8_Handoff", "교과 8 Handoff", "🟠 P2", 6, "subject08_handoff.md"),
]


def d(num):
    return os.path.join(OUT, next(f for n, f, *_ in ITEMS if n == num))


def copy(src, dst_dir, name=None):
    if os.path.isfile(src):
        os.makedirs(dst_dir, exist_ok=True)
        shutil.copy2(src, os.path.join(dst_dir, name or os.path.basename(src)))
        return True
    return False


def copy_md(src, dst_dir):
    """md 복사 + md 안에서 쓰는 로컬 이미지도 같이 복사 (Obsidian ![[이미지]] 는 ![](이미지) 로 바꿔 어디서나 보이게)"""
    import re
    if not copy(src, dst_dir):
        return False
    base = os.path.dirname(src)
    text = open(src, encoding="utf-8").read()
    search = [base, DOCS_DIR, REPORTS_DIR, os.path.join(ROOT, "captures"), ROOT]

    def find(name):
        p = os.path.normpath(os.path.join(base, name))
        if os.path.isfile(p):
            return p
        for top in search:                       # Obsidian 은 파일 이름만으로도 찾으므로 하위 폴더까지 검색
            for dp, dn, fn in os.walk(top):
                dn[:] = [x for x in dn if x not in (".git", ".venv", "submission", "data", "__pycache__")]
                if os.path.basename(name) in fn:
                    return os.path.join(dp, os.path.basename(name))
        return None

    def put(name):
        f = find(name)
        if not f:
            return None
        rel_name = os.path.relpath(f, base) if f.startswith(base + os.sep) else os.path.basename(f)
        copy(f, os.path.join(dst_dir, os.path.dirname(rel_name)))
        return rel_name.replace(os.sep, "/")

    def wiki(m):
        name = m.group(1).split("|")[0].strip()
        r = put(name)
        return f"![{os.path.basename(name)}](<{r}>)" if r else m.group(0)

    def mdimg(m):
        target = m.group(2).strip().strip("<>")
        if not target.startswith(("http://", "https://", "data:")):
            put(target.split("#")[0])
        return m.group(0)

    text = re.sub(r"!\[\[([^\]]+)\]\]", wiki, text)
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", mdimg, text)
    with open(os.path.join(dst_dir, os.path.basename(src)), "w", encoding="utf-8") as f:
        f.write(text)
    return True


def zip_dir(zip_path, paths, base):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in paths:
            full = os.path.join(base, p)
            if os.path.isfile(full):
                z.write(full, p)
                continue
            for dp, dn, fn in os.walk(full):
                dn[:] = [x for x in dn if x not in SKIP]
                for f in fn:
                    if f.endswith(".pyc") or "Zone.Identifier" in f:
                        continue
                    fp = os.path.join(dp, f)
                    z.write(fp, os.path.relpath(fp, base))


def tree(path, prefix="", depth=0, max_depth=2):
    lines = []
    entries = sorted(e for e in os.listdir(path) if e not in SKIP and not e.endswith(".pyc")
                     and "Zone.Identifier" not in e)
    for i, e in enumerate(entries):
        last = i == len(entries) - 1
        full = os.path.join(path, e)
        lines.append(f"{prefix}{'└── ' if last else '├── '}{e}{'/' if os.path.isdir(full) else ''}")
        if os.path.isdir(full) and depth < max_depth:
            lines += tree(full, prefix + ("    " if last else "│   "), depth + 1, max_depth)
    return lines


def git(*args):
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


# ---------------------------------------------------------------- 01 라벨링 프로그램
def item01():
    out = d(1)
    os.makedirs(os.path.join(out, "captures"), exist_ok=True)
    zip_dir(os.path.join(out, "labeling_program.zip"),
            ["main.py", "requirements.txt", "README.md", "configs", "src"], ROOT)
    n_py = sum(1 for dp, dn, fn in os.walk(os.path.join(ROOT, "src")) for f in fn if f.endswith(".py"))
    caps = sorted(f for f in os.listdir(os.path.join(out, "captures"))
                  if f.lower().endswith((".png", ".jpg", ".gif")) and "final" not in f.lower())
    cap_md = "\n".join(f"![{c}](captures/{c})" for c in caps) if caps else \
        "> `captures/` 폴더에 아래 3장을 넣고 이 스크립트를 다시 실행하면 여기에 자동으로 표시됩니다.\n" \
        "> `01_load.png`, `02_edit.png`, `03_validation.png`"
    vids = sorted(f for f in os.listdir(os.path.join(out, "captures")) if f.lower().endswith((".mp4", ".webm")))
    vid_md = "\n\n".join(f"## 시연 영상\n\n![{v}](captures/{v})\n\n재생이 안 되면 [{v} 열기](captures/{v})" for v in vids)
    md = f"""# 1. 라벨링 프로그램

조각김치 이물검출 이미지 900장과 기존 YOLO TXT 를 불러와 BBox·Class 를 확인·수정하고,
작업자 → 1차 검수자 → 2차 검수자 3단계 검수로 FINAL 데이터를 만든 tkinter 프로그램입니다.

## 제출물

| 항목 | 파일 |
|---|---|
| 실행 가능한 프로그램 전체 | `labeling_program.zip` (main.py, src/ {n_py}개 모듈, configs/, requirements.txt) |
| 실행 화면 캡처 | `captures/` |
| 시연 영상 | `captures/demo.mp4` (아래 '시연 영상'에서 바로 재생) |

## 실행 방법 (WSL Ubuntu)

```bash
sudo apt install -y python3-tk python3-venv fonts-nanum
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

## 필수 흐름 동작

| 단계 | 동작 | 사용 방법 |
|---|:---:|---|
| 이미지 폴더 열기 · JPG 표시 | ✅ | `폴더 열기` (Ctrl+O), EXIF 회전 반영 |
| 같은 이름의 기존 YOLO TXT 불러오기 | ✅ | 폴더를 열면 자동, Class 별 색상 표시 |
| BBox 추가 · 수정 · 삭제 | ✅ | 드래그 → Enter 확정, 모서리·테두리 드래그, Delete |
| Class 변경 | ✅ | 숫자키 0~6, Class 목록 클릭 (Class 4 는 사용 불가) |
| 이전 / 다음 이미지 이동 | ✅ | A / D, 썸네일 클릭 |
| 4K 이미지 Zoom / Pan | ✅ | 휠, Fit(F), 휠 클릭·우클릭 드래그 |
| 검수 상태 기록 | ✅ | PASS / EDITED / REVIEW / REVIEWED, 역할별 선택 제한 |
| YOLO TXT 저장 | ✅ | Ctrl+S, Ctrl+Enter (저장 후 다음) |
| 다시 열어 복원 확인 | ✅ | 라벨 완료 목록 클릭 → 저장 결과 보기 |
| Validation | ✅ | 툴바 `✓ Validation` — 11개 검사 항목 |

## 추가 기능

- 역할 3개 로그인 (작업자 / 검수자 / 2차 검수자), 단계별 저장 폴더와 `label_status.csv` 기록
- Undo / Redo (Ctrl+Z / Ctrl+Shift+Z), Ctrl/Alt + 방향키 0.0005 단위 크기 조절
- Tab 으로 박스 순서 선택 + 해당 박스로 시점 이동 (줌 유지)
- 검수 편의: 이전 선택(상태·노트·Scene Type) 유지, 이미지 화면·패널 크기 조절
- 원본 이미지·TXT 는 수정하지 않고 결과는 별도 폴더에만 저장

## 실행 화면

{cap_md}

{vid_md}

## 시연 순서 (1~2분)

```
로그인 → 폴더 열기 → 기존 BBox 확인 → BBox 추가·수정 → 저장
→ 다음 이미지 → 라벨 완료 목록에서 돌아와 복원 확인 → Validation
```
"""
    write_text(os.path.join(out, "01_labeling_program.md"), md)


# ---------------------------------------------------------------- 02 소스코드
def item02():
    out = d(2)
    copy(os.path.join(ROOT, "requirements.txt"), out)
    copy(os.path.join(ROOT, "configs", "classes.yaml"), out)
    for f in ("git_commit_history.txt", "git_change_history.txt"):
        copy(os.path.join(REPORTS_DIR, f), out)
    remote = git("remote", "get-url", "origin") or "(Git 저장소 주소)"
    log = git("log", "--oneline", "--all", "-n", "40")
    n_commit = git("rev-list", "--all", "--count") or "-"
    branches = git("branch", "-a", "--format=%(refname:short)")
    keep = ("main.py", "requirements.txt", "README.md", "configs", "src", "tools", "docs", "manifests", "reports")
    top = [e for e in sorted(os.listdir(ROOT)) if e in keep]
    t = "\n".join(["kimchi_labeler/"] + [f"{'└── ' if i == len(top) - 1 else '├── '}{e}{'/' if os.path.isdir(os.path.join(ROOT, e)) else ''}"
                                          for i, e in enumerate(top)])
    src_tree = "\n".join(["src/"] + tree(os.path.join(ROOT, "src"), max_depth=1))
    md = f"""# 2. 소스코드

## Git 저장소

| 항목 | 내용 |
|---|---|
| 저장소 | {remote} |
| 전체 커밋 | {n_commit}개 |
| 브랜치 | {', '.join(b for b in branches.splitlines() if b) or '-'} |
| 커밋 이력 파일 | `git_commit_history.txt`, `git_change_history.txt` (파일별 변경) |

> 실제 이미지·라벨 데이터는 저장소에 포함하지 않았습니다 (`.gitignore`).

## 프로젝트 구조

```
{t}
```

```
{src_tree}
```

| 폴더 | 역할 |
|---|---|
| `main.py` | 프로그램 시작 (창 생성 → 로그인 → 메인 화면) |
| `src/ui/` | 화면 구성, 캔버스(Zoom/Pan/BBox 그리기), 패널, 단축키, 파일 열기·저장 |
| `src/bbox/` | BBox 모델, 추가·수정·삭제·Undo/Redo, Class 지정 |
| `src/yolo/` | YOLO TXT Load / Save |
| `src/review/` | 저장 위치 규칙, 검수 기록(CSV), 검수 규칙, 필터 |
| `src/validation/` | Validation 11개 검사, 결과 창 |
| `src/auth/` | 로그인 / 로그아웃 (역할 3개) |
| `configs/` | `classes.yaml` (Class 0~6), `settings.yaml` (저장 위치·화면 설정) |
| `tools/` | 산출물 자동 생성 (합본·FINAL·Manifest·QA·Test·Handoff) |

## 실행 환경

`requirements.txt`

```
{open(os.path.join(ROOT, 'requirements.txt'), encoding='utf-8').read().strip() if os.path.isfile(os.path.join(ROOT, 'requirements.txt')) else ''}
```

## Class 설정 파일

`classes.yaml` — 프로그램이 읽어서 Class 목록·색상·사용 여부를 구성합니다.

## 최근 커밋 (최대 40개)

```
{log or '(git log 를 읽을 수 없음 — git_commit_history.txt 참고)'}
```
"""
    write_text(os.path.join(out, "02_source_code.md"), md)


# ---------------------------------------------------------------- 03 FINAL 데이터
def item03(with_final: bool):
    out = d(3)
    img_dir, lbl_dir = os.path.join(FINAL_DIR, "images"), os.path.join(FINAL_DIR, "labels")
    imgs = sorted(f for f in os.listdir(img_dir) if is_image(f)) if os.path.isdir(img_dir) else []
    txts = sorted(f for f in os.listdir(lbl_dir) if f.endswith(".txt")) if os.path.isdir(lbl_dir) else []
    pairs = len({stem(f) for f in imgs} & {stem(f) for f in txts})
    cls_boxes, cls_imgs, empty = Counter(), Counter(), 0
    for t in txts:
        b = read_boxes(os.path.join(lbl_dir, t))
        empty += not b
        cls_boxes.update(x[0] for x in b)
        cls_imgs.update({x[0] for x in b})
    copy(os.path.join(EVIDENCE, "final_structure.txt"), out)
    cap_src = os.path.join(ROOT, "captures")
    fcaps = sorted(f for f in os.listdir(cap_src) if "final" in f.lower()
                   and f.lower().endswith((".png", ".jpg"))) if os.path.isdir(cap_src) else []
    for f in fcaps:
        copy(os.path.join(cap_src, f), os.path.join(out, "captures"))
    fcap_md = "\n\n".join(f"![{c}](captures/{c})" for c in fcaps) or \
        "> 프로젝트 `captures/` 에 이름에 final 이 들어간 캡처(예: `04_final_images.png`)를 넣으면 여기에 표시됩니다."
    samples_src = os.path.join(EVIDENCE, "samples")
    samples = []
    if os.path.isdir(samples_src):
        shutil.copytree(samples_src, os.path.join(out, "samples"), dirs_exist_ok=True)
        samples = sorted(f[:-9] for f in os.listdir(samples_src) if f.endswith("_bbox.jpg"))
    if with_final and imgs:
        zip_dir(os.path.join(out, "final_dataset.zip"), ["data/final/images", "data/final/labels"], ROOT)
    rows = "\n".join(f"| {cid} | {class_name(cid)} | {cls_boxes.get(cid, 0)} | {cls_imgs.get(cid, 0)} |"
                     for cid in sorted(C.CLASS_NAMES))
    sample_md = []
    for s in samples:
        body = open(os.path.join(samples_src, s + ".txt"), encoding="utf-8").read().strip()
        sample_md.append(f"### {s}\n\n![{s}](samples/{s}_bbox.jpg)\n\n```\n{body or '(빈 TXT — 배경 이미지)'}\n```\n")
    md = f"""# 3. FINAL YOLO 라벨 데이터 및 증빙

900장을 1차 검수(수정) → 2차 교차 검수로 확인한 뒤, **2차 검수가 끝난 데이터만** `data/final/` 에 정리했습니다.

## 폴더 구조와 수량

```
data/final/
├── images/   {len(imgs)}장
├── labels/   {len(txts)}개
└── final_list.csv
```

| 항목 | 값 |
|---|---:|
| FINAL 이미지 | {len(imgs)}장 |
| FINAL YOLO TXT | {len(txts)}개 |
| 이미지 ↔ TXT Pair 일치 | {pairs}쌍 |
| 전체 BBox | {sum(cls_boxes.values())}개 |
| Empty Label (배경 이미지) | {empty}장 |

상세: `final_structure.txt` · 품질 결과: `08_QA_Summary/qa_summary.md`

## YOLO 형식

```
class_id x_center y_center width height   (이미지 크기 대비 0~1 비율)
```

## Class 별 수량

| Class | 이름 | BBox 수 | 포함 이미지 수 |
|---:|---|---:|---:|
{rows}

## 대표 검수 완료 이미지와 TXT

{chr(10).join(sample_md) if sample_md else '(evidence/samples 가 없습니다 — python tools/export_evidence.py 실행)'}

## 탐색기 캡처

{fcap_md}

Windows 탐색기 `\\\\wsl$\\Ubuntu\\home\\user1\\kimchi_labeler\\data\\final` 에서
`images/` "항목 {len(imgs)}개", `labels/` "항목 {len(txts)}개" 가 보이는 화면입니다.
"""
    write_text(os.path.join(out, "03_final_dataset.md"), md)


# ---------------------------------------------------------------- 07 Manifest
def item07():
    out = d(7)
    copy(MANIFEST_PATH, out)
    rows = []
    if os.path.isfile(MANIFEST_PATH):
        with open(MANIFEST_PATH, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    cnt = lambda k: ", ".join(f"{v} {n}" for v, n in sorted(Counter(r[k] or "-" for r in rows).items()))  # noqa: E731
    by_ds = Counter((r["source_dataset"], r["original_split"]) for r in rows)
    ds = "\n".join(f"| {a} | {b} | {n} |" for (a, b), n in sorted(by_ds.items()))
    head_cols = ["file_name", "source_dataset", "original_split", "scene_type", "worker", "status", "qa_status",
                 "review_reason"]
    preview = "\n".join("| " + " | ".join((r.get(c, "") or "")[:30] for c in head_cols) + " |" for r in rows[:10])
    md = f"""# 7. Dataset Manifest

이미지 {len(rows)}장의 출처·작업자·작업 상태·QA 상태를 한 줄씩 기록한 작업대장입니다.
파일: `dataset_manifest.csv` (Excel 에서 바로 열림, 이미지 없이 파일명과 상태만 기록)

## 요약

| 항목 | 분포 |
|---|---|
| status | {cnt('status')} |
| qa_status | {cnt('qa_status')} |
| scene_type | {cnt('scene_type')} |

| source_dataset | original_split | 이미지 수 |
|---|---|---:|
{ds}

## 칸 설명

| 칸 | 의미 |
|---|---|
| `file_name` | 이미지 파일명 |
| `source_dataset` / `original_split` | 원본 데이터셋 / 기존 train·validation 위치 |
| `scene_type` | kimchi_with_target / normal_kimchi / object_only / need_check |
| `worker` | 작업자 |
| `status` | DONE = 원본 라벨 그대로 / EDITED = 원본 대비 추가·삭제·Class 변경·위치 수정 / REVIEW = 미해결 |
| `qa_status` | PASS = 2차 검수 완료(FINAL) / WAIT = 미완료 |
| `review_reason` | REVIEW 로 올렸던 이유 (검수자 노트) |
| `reviewer1`, `reviewer2` | 1차·2차 검수자 |
| `*_status` | 단계별 저장 상태 |
| `raw_boxes`, `final_boxes`, `added`, `removed`, `class_changed`, `moved` | 원본 대비 박스 변경 내용 (IoU 비교) |
| `in_final` | FINAL 포함 여부 |

## 미리보기 (처음 10행)

| {' | '.join(head_cols)} |
|{'---|' * len(head_cols)}
{preview}
"""
    write_text(os.path.join(out, "07_dataset_manifest.md"), md)


# ---------------------------------------------------------------- 목록
def index(status):
    lines = [f"# 교과 7 산출물 제출 — G5 조각김치 이물검출\n",
             f"> 정리: {datetime.now():%Y-%m-%d %H:%M} · `python tools/package_submission.py`\n",
             "| 번호 | 산출물 | 우선순위 | 배점 | 대표 파일 | 상태 |", "|---:|---|:---:|---:|---|---|"]
    for n, folder, name, pri, pt, main in ITEMS:
        lines.append(f"| {n} | {name} | {pri} | {pt} | [`{folder}/{main}`]({folder}/{main}) | {status.get(n, '✅')} |")
    lines += ["", "**합계 100점** — 🔴 P1 60점 · 🟠 P2 25점 · 🟡 P3 15점", "",
              "## 직접 확인·보완할 것", ""]
    todo = [f"- {n}. {msg}" for n, msg in status.items() if msg.startswith("⬜")]
    lines += todo or ["- 없음"]
    lines += ["", "## 참고", "",
              "- FINAL 이미지 900장 원본은 데이터 보안상 이 폴더에 넣지 않았습니다. 교과 8 전달용은 `data/final/` 을 따로 압축합니다.",
              "- 문서를 직접 고친 뒤에는 `python tools/package_submission.py` 만 다시 실행하면 이 폴더가 갱신됩니다."]
    write_text(os.path.join(OUT, "00_제출목록.md"), "\n".join(lines) + "\n")


def build(with_final: bool = False, quiet: bool = False):
    shutil.rmtree(OUT, ignore_errors=True)
    for _, folder, *_ in ITEMS:
        os.makedirs(os.path.join(OUT, folder), exist_ok=True)
    # 01 의 캡처는 지우지 않도록 별도 보관 위치에서 복원
    keep = os.path.join(ROOT, "captures")
    item01()
    if os.path.isdir(keep):
        shutil.copytree(keep, os.path.join(d(1), "captures"), dirs_exist_ok=True)
        for f in os.listdir(os.path.join(d(1), "captures")):
            if "final" in f.lower():
                os.remove(os.path.join(d(1), "captures", f))
        item01()
    item02()
    item03(with_final)
    copy_md(os.path.join(DOCS_DIR, "project_baseline.md"), d(4))
    copy_md(os.path.join(DOCS_DIR, "class_guide.md"), d(5))
    copy_md(os.path.join(DOCS_DIR, "bbox_guide.md"), d(6))
    item07()
    copy_md(os.path.join(REPORTS_DIR, "qa_summary.md"), d(8))
    copy_md(os.path.join(REPORTS_DIR, "test_report.md"), d(9))
    copy_md(os.path.join(ROOT, "README.md"), d(10))
    copy_md(os.path.join(DOCS_DIR, "subject08_handoff.md"), d(11))

    status = {}
    caps = os.listdir(os.path.join(d(1), "captures"))
    if not any(c.lower().endswith((".png", ".jpg", ".gif")) for c in caps):
        status[1] = "⬜ 실행 화면 캡처 2~3장을 프로젝트의 `captures/` 폴더에 넣고 다시 실행, 시연 영상 준비"
    if not os.path.isfile(os.path.join(d(2), "git_commit_history.txt")):
        status[2] = "⬜ `bash tools/export_git_history.sh` 실행 후 다시 정리"
    bl = os.path.join(d(4), "project_baseline.md")
    if os.path.isfile(bl) and "[이름]" in open(bl, encoding="utf-8").read():
        status[4] = "⬜ `docs/project_baseline.md` 의 `[이름]` 칸 채우기"
    tr = os.path.join(d(9), "test_report.md")
    if os.path.isfile(tr) and "☐" in open(tr, encoding="utf-8").read():
        status[9] = "⬜ `reports/test_report.md` 4장 화면 체크리스트 ☐ → ☑"
    for n, folder, _, _, _, main in ITEMS:
        if not os.path.isfile(os.path.join(OUT, folder, main)):
            status[n] = f"⬜ `{main}` 없음 — python tools/make_all.py 먼저 실행"
    index(status)

    zpath = os.path.join(ROOT, "submission.zip")
    zip_dir(zpath, ["submission"], ROOT)
    if not quiet:
        print(f"[제출] → {rel(OUT)}/ (11개 폴더 + 00_제출목록.md), {rel(zpath)} "
              f"({os.path.getsize(zpath) / 1024 / 1024:.1f}MB)")
        for n, msg in status.items():
            print(f"   {n:>2}. {msg}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="11개 산출물을 submission/ 으로 정리")
    ap.add_argument("--with-final", action="store_true", help="FINAL 이미지·라벨 전체도 zip 으로 포함")
    build(ap.parse_args().with_final)
