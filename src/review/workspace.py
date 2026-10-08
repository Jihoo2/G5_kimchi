"""[카테고리] 저장 위치 규칙 — 역할·상태에 따라 어디서 읽고 어디에 저장할지 결정

폴더 구조 (configs/settings.yaml 의 output 기본값)
    <이미지 폴더>/                 *.jpg (+ 받아온 *.txt) — 절대 수정하지 않음 (어디에 있든 상관없음)
    <main.py 가 있는 최상위 폴더>/
      ├─ 작업자/                   이미지 복사본 + *.txt + label_status.csv
      │    ├─ 이슈노트/            작업자 Issue/Note 메모 (<이미지이름>.txt, 메모장으로 열림)
      │    └─ review/              작업자 REVIEW: 이미지 복사본 + *.txt + <이미지이름>_리뷰노트.txt
      ├─ 검수자/                   label_status.csv  (1차 검수자)
      │    ├─ pass/  edited/  review/      이미지 복사본 + *.txt (상태별)
      └─ 2차검수자/                label_status.csv  (2차 검수자)
           ├─ pass/  edited/  reviewed/    이미지 복사본 + *.txt (상태별)

폴더끼리 섞이지 않게 하는 방법
    결과는 작업자/ 에 바로 저장하고, label_status.csv 의 source 칸에 '어느 이미지 폴더의 결과인지' 기록
    SourceView 가 지금 연 이미지 폴더의 기록만 보여줌
    → 다른 폴더에 같은 이름의 이미지가 있어도 그 결과를 불러오지 않음
    → 같은 이름으로 저장하려 하면 덮어쓰기 전에 확인 창 (overwrite_conflict)

의사 코드
    resolve_label(이미지):        지금 연 폴더 안의 같은 이름 TXT 만 불러옴 (작업자·검수자 공통)
        원본 폴더 → 원본 TXT / 작업자/ → 작업자 TXT / 작업자/review/ → 리뷰 TXT
        (저장 결과는 그 결과 폴더를 열어야 보임)
    save_label(이미지, 박스, 상태):
        저장 폴더 = 작업자/ (REVIEW 는 작업자/review/)  또는  검수자/<상태>/   (없으면 생성, 있으면 그대로 사용)
        원본 이미지 복사본 저장 (작업자·검수자, configs 의 copy_image) — 원본은 그대로
        TXT 저장
        다른 상태 폴더에 남아 있던 같은 이미지 결과 삭제 → 한 곳에만 존재
    save_issue_note(기록):        Note 내용 → 작업자/이슈노트/<이미지이름>.txt (비우면 파일 삭제)
                                  REVIEW 체크 시 → 작업자/review/<이미지이름>_리뷰노트.txt
    cross_review_reasons(이미지):  6.3 100% Cross Review 대상인지
        검수 기록이 EDITED / REVIEW, 또는 Class 4 발견, 또는 Empty Label → 사유 목록
"""
from __future__ import annotations

import os
import shutil
import tempfile

from src import config as C
from src.common.fileio import atomic_write
from src.review.status_store import StatusStore
from src.yolo.yolo_loader import parse_yolo_line
from src.yolo.yolo_writer import save_yolo


def dataset_folder(folder: str) -> str:
    """연 폴더가 결과 폴더(작업자/…, 검수자/…)이면 원래 이미지 폴더 경로로 되돌림. 아니면 그대로.
        <상위>/작업자/<데이터셋>                → <상위>/<데이터셋>
        <상위>/검수자/<데이터셋>[/<상태>]       → <상위>/<데이터셋>
        <이미지폴더>/작업자 · 검수자[/<상태>]    → <이미지폴더>   (image_folder 방식 / 예전 구조)"""
    f = os.path.normpath(os.path.abspath(folder))
    name = os.path.basename(f)
    parent = os.path.dirname(f)
    grand = os.path.dirname(parent)
    roles = (C.WORKER_DIR, C.REVIEWER_DIR, C.REVIEWER2_DIR)
    statuses = set(C.STATUS_DIRS.values())
    if name == C.WORKER_REVIEW_DIR and os.path.basename(parent) == C.WORKER_DIR:  # …/작업자/review
        return dataset_folder(parent)
    if name in statuses and os.path.basename(parent) in (C.REVIEWER_DIR, C.REVIEWER2_DIR):          # 이미지폴더/검수자/<상태>
        return grand
    if name in statuses and os.path.basename(grand) in (C.REVIEWER_DIR, C.REVIEWER2_DIR):           # 상위/검수자/<데이터셋>/<상태>
        return os.path.join(os.path.dirname(grand), os.path.basename(parent))
    if os.path.basename(parent) in roles:                                         # 상위/작업자/<데이터셋>
        return os.path.join(grand, name)
    if name in roles:                                                             # 이미지폴더/작업자
        return parent
    return f


def output_root(image_folder: str) -> str:
    """작업자/·검수자/ 를 만들 위치 = 기준 폴더 + 상대 경로 (configs/settings.yaml 의 output)
        project      : <main.py 가 있는 최상위 폴더>/<path>   (기본)
        parent       : <이미지 폴더의 바로 위 폴더>/<path>
        image_folder : <이미지 폴더>/<path>
        path 가 절대 경로면 그 경로를 그대로 사용"""
    if os.path.isabs(C.OUTPUT_PATH):
        return os.path.normpath(C.OUTPUT_PATH)
    if C.OUTPUT_BASE == "project":
        base = C.PROJECT_DIR
    else:
        data = dataset_folder(image_folder)
        base = os.path.dirname(data) if C.OUTPUT_BASE == "parent" else data
    return os.path.normpath(os.path.join(base, C.OUTPUT_PATH))


def _inside(path: str, parent: str) -> bool:
    return os.path.commonpath([path, parent]) == parent and path != parent


def dataset_key(image_folder: str, root: str):
    """이미지 폴더를 구분하는 이름 (CSV 의 source 칸, per_dataset 일 때는 하위 폴더 이름)
        1) 결과 폴더(<root>/작업자, <root>/검수자 …)를 직접 열었으면
           - per_dataset 이면 그 안의 경로, 아니면 None (각 기록에 적힌 source 를 그대로 따름)
        2) 이미지 폴더가 최상위(main.py 폴더) 안에 있으면 최상위 기준 상대 경로 (예: data/임시데이터)
        3) 그 밖이면 절대 경로"""
    f = os.path.normpath(os.path.abspath(image_folder))
    statuses = set(C.STATUS_DIRS.values())
    for role in (C.WORKER_DIR, C.REVIEWER_DIR, C.REVIEWER2_DIR):
        role_dir = os.path.join(root, role)
        if f == role_dir or _inside(f, role_dir):
            if not C.OUTPUT_PER_DATASET or f == role_dir:
                return None
            parts = os.path.relpath(f, role_dir).split(os.sep)
            if role != C.WORKER_DIR and len(parts) > 1 and parts[-1] in statuses:
                parts = parts[:-1]
            if role != C.WORKER_DIR and parts == [p for p in parts if p in statuses]:
                return None
            return os.path.join(*parts)
    data = dataset_folder(f)
    if _inside(data, C.PROJECT_DIR):
        return os.path.relpath(data, C.PROJECT_DIR)
    return data if not C.OUTPUT_PER_DATASET else os.path.basename(data)


class SourceView:
    """StatusStore 를 '지금 연 이미지 폴더의 기록'만 보이게 감싼 것.
    같은 파일 이름이라도 다른 이미지 폴더(source)의 기록은 없는 것처럼 처리한다.
    source 가 None 이면(결과 폴더를 직접 연 경우) 모든 기록을 그대로 보여준다."""

    def __init__(self, store, source, source_of):
        self.store = store
        self.source = source
        self._source_of = source_of          # 결과 폴더를 직접 열었을 때 저장할 source 를 찾는 함수
        self.path = store.path

    def matches(self, meta) -> bool:
        """이 기록이 지금 연 이미지 폴더의 것인지 (예전 기록처럼 source 가 비어 있으면 인정)"""
        return self.source is None or not meta.source or meta.source == self.source

    def get(self, name):
        m = self.store.get(name)
        return m if m and self.matches(m) else None

    def raw(self, name):
        """source 와 상관없이 기록 그대로 (덮어쓰기 확인용)"""
        return self.store.get(name)

    def update(self, meta) -> None:
        meta.source = self.source if self.source is not None else self._source_of(meta.filename)
        self.store.update(meta)

    def completed(self, valid_names=None):
        return [m for m in self.store.completed(valid_names) if self.matches(m)]


class Workspace:
    """역할별 저장 위치 규칙 (열린 이미지 폴더 + 로그인 역할 기준)"""
    def __init__(self, image_folder: str, role: str):
        """원본 폴더·저장 루트·상태별 폴더 경로 준비, 두 역할의 CSV 읽기 (폴더는 저장할 때 생성)"""
        self.src = os.path.normpath(os.path.abspath(image_folder))   # 이미지를 읽는 폴더
        self.root = output_root(image_folder)                         # 작업자/·검수자/ 가 놓일 위치
        self.dataset = dataset_key(image_folder, self.root)            # 이미지 폴더 구분 (CSV 의 source)
        self.role = role
        sub = tuple(self.dataset.split(os.sep)) if (C.OUTPUT_PER_DATASET and self.dataset) else ()
        self.worker_dir = os.path.join(self.root, C.WORKER_DIR, *sub)       # 작업자/<데이터셋>/
        self.reviewer_dir = os.path.join(self.root, C.REVIEWER_DIR, *sub)   # 검수자/<데이터셋>/
        self.worker_review_dir = os.path.join(self.worker_dir, C.WORKER_REVIEW_DIR)   # 작업자/review/
        self.status_dirs = {st: os.path.join(self.reviewer_dir, d) for st, d in C.STATUS_DIRS.items()}
        self.reviewer2_dir = os.path.join(self.root, C.REVIEWER2_DIR, *sub)  # 2차검수자/<데이터셋>/
        self.status_dirs2 = {st: os.path.join(self.reviewer2_dir, C.STATUS_DIRS[st])
                             for st in C.ROLE_STATUSES[C.ROLE_REVIEWER2]}  # pass / edited / reviewed
        self.pass_dir = self.status_dirs["PASS"]
        self.review_dir = self.status_dirs["REVIEW"]
        # CSV는 있으면 읽기만 함. 폴더는 실제 저장할 때 생성
        # SourceView: 지금 연 이미지 폴더의 기록만 보이게 → 다른 폴더의 같은 이름 결과와 섞이지 않음
        worker_raw, reviewer_raw = StatusStore(self.worker_dir), StatusStore(self.reviewer_dir)
        reviewer2_raw = StatusStore(self.reviewer2_dir)
        def source_of(name):
            for store in (reviewer2_raw, reviewer_raw, worker_raw):
                m = store.get(name)
                if m and m.source:
                    return m.source
            return ""
        self.worker_store = SourceView(worker_raw, self.dataset, source_of)
        self.reviewer_store = SourceView(reviewer_raw, self.dataset, source_of)
        self.reviewer2_store = SourceView(reviewer2_raw, self.dataset, source_of)

    @property
    def is_reviewer(self) -> bool:
        """검수자(1차 또는 2차)로 로그인했는지 — 검수 화면·규칙을 쓰는 역할"""
        return self.role in C.REVIEW_ROLES

    @property
    def is_reviewer2(self) -> bool:
        """2차 검수자로 로그인했는지"""
        return self.role == C.ROLE_REVIEWER2

    @property
    def own_store(self) -> "SourceView":
        """내 역할의 CSV (작업자/ · 검수자/ · 2차검수자/)"""
        return {C.ROLE_REVIEWER: self.reviewer_store,
                C.ROLE_REVIEWER2: self.reviewer2_store}.get(self.role, self.worker_store)

    @property
    def own_dir_label(self) -> str:
        """내 역할 저장 폴더 (저장 루트 기준 상대 경로, 화면 표시용) 예) 작업자/임시데이터"""
        return self.rel({C.ROLE_REVIEWER: self.reviewer_dir,
                         C.ROLE_REVIEWER2: self.reviewer2_dir}.get(self.role, self.worker_dir))

    @staticmethod
    def _txt(name: str) -> str:
        """이미지 이름 → 같은 이름의 .txt"""
        return os.path.splitext(name)[0] + ".txt"

    def reviewer_dirs(self) -> list[str]:
        # 마지막 reviewer_dir 은 이전 버전(검수자/ 바로 아래 저장) 호환용
        """검수자 상태별 폴더 목록 (마지막은 이전 버전 호환용 검수자/ 바로 아래)"""
        return list(self.status_dirs.values()) + [self.reviewer_dir]

    def reviewer2_dirs(self) -> list[str]:
        """2차 검수자 상태별 폴더 목록 (pass / edited / reviewed)"""
        return list(self.status_dirs2.values())

    def own_result_dirs(self) -> list[str]:
        """내 역할이 저장하는 결과 폴더들"""
        if self.role == C.ROLE_REVIEWER2:
            return self.reviewer2_dirs()
        if self.role == C.ROLE_REVIEWER:
            return self.reviewer_dirs()
        return self.worker_dirs()

    def worker_dirs(self) -> list[str]:
        """작업자 저장 폴더: 작업자/review/ (REVIEW), 작업자/ (EDITED)"""
        return [self.worker_review_dir, self.worker_dir]

    def output_dirs(self) -> list[str]:
        """내 역할이 저장하는 폴더들 (Validation 짝 없는 TXT 검사용)"""
        return self.own_result_dirs()

    # ------------------------------------------------------------ 불러오기
    @property
    def is_result_folder(self) -> bool:
        """지금 연 폴더가 저장 결과 폴더(작업자/, 작업자/review/, 검수자/<상태>/, 2차검수자/<상태>/)인지"""
        dirs = self.worker_dirs() + self.reviewer_dirs() + self.reviewer2_dirs()
        return self.src in {os.path.normpath(d) for d in dirs}

    def folder_label(self) -> str:
        """화면 표시용 '연 폴더' 이름: 결과 폴더면 작업자/review 처럼, 아니면 '원본'"""
        return self.rel(self.src) if self.is_result_folder else "원본"

    def resolve_label(self, name: str):
        """(txt 경로 또는 None, 출처 설명)
        지금 연 폴더 안의 같은 이름 TXT 만 사용한다. 다른 폴더(작업자/·검수자/·원본)의 라벨은 불러오지 않음
            원본 폴더를 열면        → 원본 폴더의 TXT
            작업자/ 를 열면         → 작업자/ 의 TXT
            작업자/review/ 를 열면  → 작업자/review/ 의 TXT (리뷰노트는 이름이 달라 섞이지 않음)"""
        path = os.path.join(self.src, self._txt(name))
        if os.path.exists(path):
            return path, self.folder_label()
        return None, "없음"

    def saved_result(self, name: str):
        """내 역할로 저장한 결과(이미지 복사본 + TXT)의 위치. 기록이 없으면 None
        라벨 완료 목록에서 이미지를 고르면, 연 폴더 대신 이 결과를 화면에 보여줌"""
        m = self.own_store.get(name)
        if not (m and m.status):
            return None
        d = self.target_dir(m.status)
        img, txt = os.path.join(d, name), os.path.join(d, self._txt(name))
        return {"dir": d, "rel": self.rel(d), "meta": m,
                "image": img if os.path.exists(img) else None,
                "txt": txt if os.path.exists(txt) else None}

    def saved_elsewhere(self, name: str):
        """원본 등 결과 폴더가 아닌 곳을 열었는데, 이 이미지가 이미 내 역할 폴더에 저장돼 있으면 그 폴더(상대 경로)
        → 원본 모습만 보이는 상태에서 저장하면 이전 작업을 덮어쓰게 되므로 확인용"""
        if self.is_result_folder:
            return None
        m = self.own_store.get(name)
        if not (m and m.status):
            return None
        return self.rel(self.target_dir(m.status))

    def display_meta(self, name: str):
        """화면 표시용 기록 (상태 배지, 검수 상태, 작업자/검수자 이름, Scene, Note, 필터, Validation)
        결과 폴더를 열었을 때만 돌려주고, 원본 폴더에서는 None → 다른 폴더의 저장 결과를 표시하지 않음"""
        return self.effective_meta(name) if self.is_result_folder else None

    def display_own_meta(self, name: str):
        """display_meta 와 같은 규칙으로 '내 역할' 기록만"""
        return self.own_meta(name) if self.is_result_folder else None

    folder_meta = display_meta      # Validation 에서 쓰던 이름 (호환)

    def overwrite_conflict(self, name: str):
        """내 역할 폴더에 '다른 이미지 폴더'의 같은 이름 결과가 있으면 그 source, 없으면 None"""
        raw = self.own_store.raw(name)
        if raw and not self.own_store.matches(raw):
            return raw.source
        return None

    # ------------------------------------------------------------ 작업자 이슈 노트 (메모장)
    def issue_note_path(self, name: str, status: str = "") -> str:
        """작업자 노트 위치
            REVIEW 체크 → 작업자/review/<이미지이름>_리뷰노트.txt  (이미지·라벨과 같은 폴더)
            그 외      → 작업자/이슈노트/<이미지이름>.txt"""
        stem = os.path.splitext(name)[0]
        if status == "REVIEW":
            return os.path.join(self.worker_review_dir, stem + C.REVIEW_NOTE_SUFFIX + ".txt")
        return os.path.join(self.worker_dir, C.ISSUE_NOTE_DIR, stem + ".txt")

    def save_issue_note(self, meta) -> str | None:
        """Issue/Note 내용을 메모장 파일로 저장. 내용이 비었으면 기존 파일 삭제. 저장 경로 반환"""
        path = self.issue_note_path(meta.filename, meta.status)
        note = (meta.note or "").strip()
        # REVIEW ↔ EDITED 로 바뀌었으면 다른 폴더의 이전 노트 삭제 (항상 한 곳에만 존재)
        for st in ("REVIEW", ""):
            other = self.issue_note_path(meta.filename, st)
            if other != path and os.path.exists(other):
                os.remove(other)
        if not note:
            if os.path.exists(path):
                os.remove(path)
            return None
        os.makedirs(os.path.dirname(path), exist_ok=True)
        title = "[작업 리뷰 노트]" if meta.status == "REVIEW" else "[작업 이슈 노트]"
        text = (f"{title}\n"
                f"이미지      : {meta.filename}\n"
                f"이미지 폴더 : {meta.source or self.src}\n"
                f"작업자      : {meta.assignee}\n"
                f"상태        : {meta.status}\n"
                f"저장 시각   : {meta.updated_at}\n"
                + "-" * 40 + "\n" + note + "\n")
        atomic_write(path, lambda f: f.write(text), encoding="utf-8-sig")   # Windows 메모장 한글 호환
        return path

    def own_meta(self, name: str):
        """내 역할 CSV의 이 이미지 기록"""
        return self.own_store.get(name)

    def effective_meta(self, name: str):
        """화면 표시·필터용: 내 기록이 없으면 앞 단계 기록 (2차 검수자 → 1차 검수자 → 작업자)"""
        if self.role == C.ROLE_REVIEWER2:
            return (self.reviewer2_store.get(name) or self.reviewer_store.get(name)
                    or self.worker_store.get(name))
        if self.role == C.ROLE_REVIEWER:
            return self.reviewer_store.get(name) or self.worker_store.get(name)
        return self.worker_store.get(name)

    # ------------------------------------------------------------ 저장
    def target_dir(self, status: str) -> str:
        """저장 폴더 결정
            작업자     → 작업자/ (REVIEW 는 작업자/review/)
            검수자     → 검수자/<상태>/
            2차 검수자 → 2차검수자/<상태>/"""
        if self.role == C.ROLE_REVIEWER2:
            return self.status_dirs2.get(status, self.reviewer2_dir)
        if self.role == C.ROLE_REVIEWER:
            return self.status_dirs.get(status, self.reviewer_dir)
        return self.worker_review_dir if status == "REVIEW" else self.worker_dir

    # ------------------------------------------------------------ 3단계 Cross Review
    def label_classes(self, name: str) -> list[int]:
        """현재 불러올 TXT 안의 Class 번호 목록 (Class 4·Empty Label 판정용)"""
        txt, _ = self.resolve_label(name)
        classes = []
        if txt:
            try:
                with open(txt, encoding="utf-8") as f:
                    for line in f:
                        try:
                            classes.append(parse_yolo_line(line.strip())[0])
                        except ValueError:
                            pass
            except (OSError, UnicodeDecodeError):
                pass
        return classes

    def cross_review_reasons(self, name: str) -> list[str]:
        """100% Cross Review 대상이면 사유 목록. 2단계 검수 전이거나 REVIEWED면 []
        대상: 새 BBox·수정·Class 변경·추가삭제(=EDITED), REVIEW였던 이미지, Class 4 발견, Empty Label"""
        m = self.reviewer_store.get(name)
        if not m or m.status == "REVIEWED":
            return []
        if self.reviewer2_store.get(name):           # 2차 검수자가 이미 처리한 이미지
            return []
        reasons = []
        if m.status == "EDITED":
            reasons.append("수정·신규 라벨")
        if m.status == "REVIEW":
            reasons.append("REVIEW였던 이미지")
        classes = self.label_classes(name)
        if any(c in C.UNUSED_CLASSES for c in classes):
            reasons.append("Class 4 발견")
        if not classes:
            reasons.append("Empty Label")
        return reasons

    def _copy_flag(self, status: str) -> bool:
        """이번 저장에서 이미지 복사본을 만들지 (config 설정 + 상태)"""
        if not self.is_reviewer:
            return C.COPY_IMAGE_WORKER
        return C.COPY_IMAGE_REVIEWER and status not in C.REVIEWER_NO_IMAGE_STATUSES

    def _copy_image(self, name: str, target: str) -> None:
        """원본 이미지를 target 폴더로 복사. 이미 같은 파일이 있으면 건너뜀"""
        src = os.path.join(self.src, name)
        dst = os.path.join(target, name)
        if os.path.normpath(dst) == os.path.normpath(src) or (
                os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src)):
            return
        fd, tmp = tempfile.mkstemp(dir=target, prefix=".tmp_", suffix=".part")
        os.close(fd)
        try:
            shutil.copy2(src, tmp)          # 복사 중 중단돼도 반쪽 파일이 남지 않도록 임시 파일 → 교체
            os.replace(tmp, dst)
        except Exception:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    def save_label(self, name: str, boxes, W: int, H: int, status: str) -> str:
        """역할·상태에 맞는 폴더에 이미지 복사본 + TXT 저장 (폴더는 없으면 생성, 있으면 그대로 사용).
        원본 폴더는 건드리지 않음. 저장된 TXT 경로 반환"""
        target = self.target_dir(status)
        os.makedirs(target, exist_ok=True)
        if self._copy_flag(status):
            self._copy_image(name, target)
        path = os.path.join(target, self._txt(name))
        save_yolo(path, boxes, W, H)
        # 상태가 바뀌었을 때(예: 작업자 REVIEW → EDITED, 검수자 review → pass)
        # 다른 폴더의 이전 결과(TXT·이미지 복사본) 제거 → 항상 한 곳에만 존재
        for d in self.own_result_dirs():
            if d == target:
                continue
            old_txt = os.path.join(d, self._txt(name))
            if os.path.isfile(old_txt):
                os.remove(old_txt)
            self._remove_copy(d, name)
        return path

    def _remove_copy(self, folder: str, name: str) -> None:
        """저장 폴더의 이미지 복사본 삭제. 지금 이미지를 읽고 있는 폴더면 절대 지우지 않음"""
        if os.path.normpath(folder) == self.src:
            return
        p = os.path.join(folder, name)
        if os.path.isfile(p):
            os.remove(p)

    def rel(self, path: str) -> str:
        """저장 루트 기준 상대 경로 (화면 표시용)"""
        return os.path.relpath(path, self.root)
