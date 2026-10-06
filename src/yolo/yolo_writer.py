"""[카테고리] YOLO 저장 — Box 목록 → YOLO TXT

의사 코드
    save_yolo(txt, 박스들, W, H):
        박스마다 "cls cx cy w h" 한 줄 (0~1 정규화, 소수 6자리)
        박스가 없으면 빈 파일 (YOLO 학습 시 '이물 없음' 배경 이미지)
        atomic_write 로 저장 → 저장 중 꺼져도 기존 파일이 깨지지 않음
"""
from __future__ import annotations

from src.bbox.bbox_model import Box
from src.common.fileio import atomic_write


def save_yolo(txt_path: str, boxes: list[Box], W: int, H: int) -> None:
    """BBox가 없으면 빈 TXT를 저장 (YOLO에서 '이물 없음' 배경 이미지로 학습됨)"""
    def write(f):
        """박스마다 'cls cx cy w h' 한 줄 (소수 6자리)"""
        for b in boxes:
            c, cx, cy, w, h = b.to_yolo(W, H)
            f.write(f"{c} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")
    atomic_write(txt_path, write)
