"""[카테고리] BBox 데이터 모델 — 박스 1개(Box)와 Undo 스택

    Box        좌표는 항상 '원본 이미지 픽셀' 기준 (x1, y1 좌상단 / x2, y2 우하단)
               to_yolo()   → (class, cx, cy, w, h) 0~1 정규화   ← TXT 저장용
               from_yolo() → YOLO 값을 픽셀 좌표 Box로           ← TXT 읽기용
               state       "" 저장됨 / "new" 신규 / "modified" 수정
               pending     True = 그린 직후 Enter 확정 전
    UndoStack  BBox 목록 스냅샷을 쌓아 두고 Ctrl+Z 때 꺼냄 (이미지를 바꾸면 비움)
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Box:
    """BBox. 좌표는 항상 '원본 이미지 픽셀' 기준(x1,y1 좌상단 / x2,y2 우하단)으로 보관한다.
    화면 좌표 변환은 ImageCanvas에서만 한다."""
    cls: int
    x1: float
    y1: float
    x2: float
    y2: float
    state: str = ""   # "" = 저장됨, "new" = 신규, "modified" = 수정
    pending: bool = False   # True = 그린 직후 Enter로 확정 전

    @property
    def w(self) -> float:
        """너비(px)"""
        return self.x2 - self.x1

    @property
    def h(self) -> float:
        """높이(px)"""
        return self.y2 - self.y1

    def area(self) -> float:
        """넓이(px²) — 겹친 박스 중 작은 것 우선 선택에 사용"""
        return max(0.0, self.w) * max(0.0, self.h)

    def normalize(self) -> "Box":
        """x1>x2, y1>y2 이면 서로 바꿔서 항상 좌상단/우하단 순서로"""
        if self.x1 > self.x2:
            self.x1, self.x2 = self.x2, self.x1
        if self.y1 > self.y2:
            self.y1, self.y2 = self.y2, self.y1
        return self

    def clamp(self, W: float, H: float) -> "Box":
        """좌표를 이미지 범위(0~W, 0~H) 안으로 자르기"""
        self.x1 = min(max(self.x1, 0.0), W)
        self.x2 = min(max(self.x2, 0.0), W)
        self.y1 = min(max(self.y1, 0.0), H)
        self.y2 = min(max(self.y2, 0.0), H)
        return self.normalize()

    def copy(self) -> "Box":
        """복사본 (Undo 스냅샷용)"""
        return Box(self.cls, self.x1, self.y1, self.x2, self.y2, self.state, self.pending)

    def to_yolo(self, W: int, H: int):
        """(cls, cx, cy, w, h) — 0~1 정규화"""
        cx = (self.x1 + self.x2) / 2 / W
        cy = (self.y1 + self.y2) / 2 / H
        return self.cls, cx, cy, self.w / W, self.h / H

    @staticmethod
    def from_yolo(cls_id, cx, cy, w, h, W, H, state="") -> "Box":
        """YOLO (cls, cx, cy, w, h) 정규화 값 → 픽셀 좌표 Box"""
        bw, bh = w * W, h * H
        x1 = cx * W - bw / 2
        y1 = cy * H - bh / 2
        return Box(int(cls_id), x1, y1, x1 + bw, y1 + bh, state).clamp(W, H)


class UndoStack:
    """BBox 리스트 스냅샷 기반 Undo (이미지별로 비움)"""

    def __init__(self, limit: int = 100):
        """limit 개까지만 보관"""
        self.limit = limit
        self._stack: list[list[Box]] = []

    def push(self, boxes: list[Box]) -> None:
        """박스 목록 전체를 복사해서 저장"""
        self._stack.append([b.copy() for b in boxes])
        if len(self._stack) > self.limit:
            self._stack.pop(0)

    def pop(self):
        """가장 최근 스냅샷 꺼내기 (없으면 None)"""
        return self._stack.pop() if self._stack else None

    def clear(self) -> None:
        """전체 비우기 (이미지 바꿀 때)"""
        self._stack.clear()

    def __len__(self) -> int:
        """남은 Undo 개수"""
        return len(self._stack)
