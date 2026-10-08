"""[카테고리] BBox 데이터 모델 — 박스 1개(Box)와 Undo 스택

    Box        좌표는 항상 '원본 이미지 픽셀' 기준 (x1, y1 좌상단 / x2, y2 우하단)
               to_yolo()   → (class, cx, cy, w, h) 0~1 정규화   ← TXT 저장용
               from_yolo() → YOLO 값을 픽셀 좌표 Box로           ← TXT 읽기용
               state       "" 저장됨 / "new" 신규 / "modified" 수정
               pending     True = 그린 직후 Enter 확정 전
    UndoStack  BBox 목록 스냅샷을 쌓아 두고 Ctrl+Z(Undo) / Ctrl+Shift+Z·Ctrl+Y(Redo) 때 꺼냄 (이미지를 바꾸면 비움)
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
    """BBox 리스트 스냅샷 기반 Undo / Redo (이미지별로 비움)

        push(박스들)      박스를 바꾸기 직전 상태 저장 → 새 작업이 생겼으니 Redo 기록은 비움
        undo(현재 박스)   직전 상태 꺼내기 (현재 상태는 Redo 쪽으로)          Ctrl+Z
        redo(현재 박스)   Undo 했던 상태 다시 꺼내기 (현재 상태는 Undo 쪽으로)  Ctrl+Shift+Z / Ctrl+Y
        pop()            Redo 기록 없이 직전 상태만 꺼내기 (자동 되돌리기용)
    """

    def __init__(self, limit: int = 100):
        """limit 개까지만 보관"""
        self.limit = limit
        self._stack: list[list[Box]] = []
        self._redo: list[list[Box]] = []

    @staticmethod
    def _copy(boxes):
        return [b.copy() for b in boxes]

    def _push_undo(self, boxes) -> None:
        self._stack.append(self._copy(boxes))
        if len(self._stack) > self.limit:
            self._stack.pop(0)

    def push(self, boxes: list[Box]) -> None:
        """박스 목록 전체를 복사해서 저장 (새 작업 → Redo 기록 삭제)"""
        self._push_undo(boxes)
        self._redo.clear()

    def undo(self, current: list[Box]):
        """직전 스냅샷 꺼내기, 현재 상태는 Redo 로 보관 (없으면 None)"""
        if not self._stack:
            return None
        self._redo.append(self._copy(current))
        return self._stack.pop()

    def redo(self, current: list[Box]):
        """Undo 했던 스냅샷 다시 꺼내기, 현재 상태는 Undo 로 보관 (없으면 None)"""
        if not self._redo:
            return None
        self._push_undo(current)
        return self._redo.pop()

    def pop(self):
        """가장 최근 스냅샷 꺼내기 — Redo 기록을 남기지 않음 (없으면 None)"""
        return self._stack.pop() if self._stack else None

    def clear(self) -> None:
        """전체 비우기 (이미지 바꿀 때)"""
        self._stack.clear()
        self._redo.clear()

    @property
    def redo_count(self) -> int:
        """남은 Redo 개수"""
        return len(self._redo)

    def __len__(self) -> int:
        """남은 Undo 개수"""
        return len(self._stack)
