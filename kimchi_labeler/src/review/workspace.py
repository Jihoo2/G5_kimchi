"""[카테고리] 저장 위치 규칙 — 역할·상태에 따라 어느 폴더에서 읽고 어디에 저장할지 결정

폴더 구조
    <원본 이미지 폴더>/          *.jpg (+ 받아온 *.txt) — 절대 수정하지 않음
    <main.py 폴더 = configs/settings.yaml 의 output_root>/
      ├─ 작업자/                 이미지 복사본 + *.txt + label_status.csv
      └─ 검수자/                 label_status.csv
           ├─ pass/  edited/  review/  reviewed/      *.txt (상태별)

의사 코드
    resolve_label(이미지):        화면에 불러올 TXT 찾기
        작업자: 작업자/ → 원본 폴더
        검수자: 검수자/<상태>/ → 작업자/ → 원본 폴더
    save_label(이미지, 박스, 상태):
        저장 폴더 = 작업자/  또는  검수자/<상태>/   (없으면 생성, 있으면 그대로 사용)
        (작업자) 원본 이미지를 복사본으로 저장 — 원본은 그대로
        TXT 저장
        (검수자) 다른 상태 폴더에 남아 있던 같은 이미지 결과 삭제 → 한 곳에만 존재
    cross_review_reasons(이미지):  6.3 100% Cross Review 대상인지
        검수 기록이 EDITED / REVIEW, 또는 Class 4 발견, 또는 Empty Label → 사유 목록
        검수 기록 없음(2단계 전) 또는 REVIEWED → []
"""
from __future__ import annotations

import os
import shutil
import tempfile

from src import config as C
from src.review.status_store import StatusStore
from src.yolo.yolo_loader import parse_yolo_line
from src.yolo.yolo_writer import save_yolo


class Workspace:
    """역할별 저장 위치 규칙 (열린 이미지 폴더 + 로그인 역할 기준)"""
    def __init__(self, image_folder: str, role: str):
        """원본 폴더·저장 루트·상태별 폴더 경로 준비, 두 역할의 CSV 읽기 (폴더는 저장할 때 생성)"""
        self.src = os.path.normpath(os.path.abspath(image_folder))   # 이미지를 읽는 폴더
        self.root = os.path.normpath(os.path.abspath(C.OUTPUT_ROOT))  # 작업자/·검수자/ 가 놓일 위치
        self.role = role
        self.worker_dir = os.path.join(self.root, C.WORKER_DIR)
        self.reviewer_dir = os.path.join(self.root, C.REVIEWER_DIR)
        self.status_dirs = {st: os.path.join(self.reviewer_dir, d) for st, d in C.STATUS_DIRS.items()}
        self.pass_dir = self.status_dirs["PASS"]
        self.review_dir = self.status_dirs["REVIEW"]
        # CSV는 있으면 읽기만 함. 폴더는 실제 저장할 때 생성
        self.worker_store = StatusStore(self.worker_dir)
        self.reviewer_store = StatusStore(self.reviewer_dir)

    @property
    def is_reviewer(self) -> bool:
        """검수자로 로그인했는지"""
        return self.role == C.ROLE_REVIEWER

    @property
    def own_store(self) -> StatusStore:
        """내 역할의 CSV (작업자/ 또는 검수자/)"""
        return self.reviewer_store if self.is_reviewer else self.worker_store

    @property
    def own_dir_label(self) -> str:
        """내 역할 폴더 이름 (화면 표시용)"""
        return C.REVIEWER_DIR if self.is_reviewer else C.WORKER_DIR

    @staticmethod
    def _txt(name: str) -> str:
        """이미지 이름 → 같은 이름의 .txt"""
        return os.path.splitext(name)[0] + ".txt"

    def reviewer_dirs(self) -> list[str]:
        # 마지막 reviewer_dir 은 이전 버전(검수자/ 바로 아래 저장) 호환용
        """검수자 상태별 폴더 목록 (마지막은 이전 버전 호환용 검수자/ 바로 아래)"""
        return list(self.status_dirs.values()) + [self.reviewer_dir]

    def output_dirs(self) -> list[str]:
        """내 역할이 저장하는 폴더들 (Validation 짝 없는 TXT 검사용)"""
        return self.reviewer_dirs() if self.is_reviewer else [self.worker_dir]

    # ------------------------------------------------------------ 불러오기
    def resolve_label(self, name: str):
        """(txt 경로 또는 None, 출처 설명)"""
        txt = self._txt(name)
        candidates = []
        if self.is_reviewer:
            for d in self.reviewer_dirs():
                candidates.append((os.path.join(d, txt), self.rel(d)))
        candidates += [(os.path.join(self.worker_dir, txt), C.WORKER_DIR),
                       (os.path.join(self.src, txt), "원본")]
        for path, label in candidates:
            if os.path.exists(path):
                return path, label
        return None, "없음"

    def own_meta(self, name: str):
        """내 역할 CSV의 이 이미지 기록"""
        return self.own_store.get(name)

    def effective_meta(self, name: str):
        """화면 표시·필터용: 검수자는 검수 기록이 없으면 작업자 기록"""
        if self.is_reviewer:
            return self.reviewer_store.get(name) or self.worker_store.get(name)
        return self.worker_store.get(name)

    # ------------------------------------------------------------ 저장
    def target_dir(self, status: str) -> str:
        """저장 폴더 결정: 작업자 → 작업자/, 검수자 → 검수자/<상태>/"""
        if not self.is_reviewer:
            return self.worker_dir
        return self.status_dirs.get(status, self.reviewer_dir)

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
        if self.is_reviewer:
            # 상태가 바뀌었을 때(예: review → pass) 다른 폴더의 이전 결과(TXT·이미지) 제거 → 한 곳에만 존재
            for d in self.reviewer_dirs():
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
