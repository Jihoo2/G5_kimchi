"""[카테고리] 검수 기록 — label_status.csv 의 한 행(ImageMeta)과 CSV 파일 관리(StatusStore)

    ImageMeta     filename, status, assignee(작업자), reviewer(검수자), scene_type, note,
                  num_boxes, updated_at, source(어느 이미지 폴더의 결과인지)
    StatusStore   폴더 하나의 label_status.csv
        load()       CSV → {파일명: ImageMeta}
        update()     저장 시각 기록 → CSV 전체 다시 쓰기 (Excel 한글 호환 utf-8-sig)
        completed()  상태가 기록된 이미지를 저장 순서대로 (라벨 완료 목록용)
"""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import datetime

from src.common.fileio import atomic_write
from src.config import STATUS_CSV_NAME


@dataclass
class ImageMeta:
    """label_status.csv 의 한 행"""
    filename: str
    status: str = ""
    assignee: str = ""
    reviewer: str = ""
    reviewer2: str = ""     # 2차 검수자
    scene_type: str = ""
    note: str = ""
    num_boxes: int = 0
    updated_at: str = ""
    source: str = ""        # 어느 이미지 폴더의 결과인지 (최상위 기준 경로). 비어 있으면 예전 기록


CSV_FIELDS = ["filename", "status", "assignee", "reviewer", "reviewer2",
              "scene_type", "note", "num_boxes", "updated_at", "source"]


class StatusStore:
    """폴더 단위 label_status.csv 관리 (Excel 한글 호환을 위해 utf-8-sig)"""

    def __init__(self, folder: str):
        """<폴더>/label_status.csv 를 대상으로, 있으면 바로 읽음"""
        self.path = os.path.join(folder, STATUS_CSV_NAME)
        self.records: dict[str, ImageMeta] = {}
        self.load()

    def load(self) -> None:
        """CSV → {파일명: ImageMeta}"""
        self.records.clear()
        if not os.path.exists(self.path):
            return
        with open(self.path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                name = (row.get("filename") or "").strip()
                if not name:
                    continue
                try:
                    n = int(row.get("num_boxes") or 0)
                except ValueError:
                    n = 0
                self.records[name] = ImageMeta(
                    filename=name,
                    status=(row.get("status") or "").strip(),
                    assignee=row.get("assignee") or "",
                    reviewer=row.get("reviewer") or "",
                    reviewer2=row.get("reviewer2") or "",
                    scene_type=(row.get("scene_type") or "").strip(),
                    note=row.get("note") or "",
                    num_boxes=n,
                    updated_at=row.get("updated_at") or "",
                    source=row.get("source") or "",
                )

    def get(self, filename: str):
        """파일명의 기록 (없으면 None)"""
        return self.records.get(filename)

    def update(self, meta: ImageMeta) -> None:
        """저장 시각을 넣어 기록 갱신 후 CSV 저장"""
        meta.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.records[meta.filename] = meta
        self.save()

    def save(self) -> None:
        """기록 전체를 CSV로 다시 쓰기 (폴더 없으면 생성)"""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

        def write(f):
            """헤더 + 파일명 순서로 한 행씩"""
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for name in sorted(self.records):
                m = self.records[name]
                writer.writerow({
                    "filename": m.filename, "status": m.status,
                    "assignee": m.assignee, "reviewer": m.reviewer, "reviewer2": m.reviewer2,
                    "scene_type": m.scene_type, "note": m.note,
                    "num_boxes": m.num_boxes, "updated_at": m.updated_at,
                    "source": m.source,
                })
        atomic_write(self.path, write, encoding="utf-8-sig", newline="")

    def completed(self, valid_names=None) -> list[ImageMeta]:
        """저장 완료된 이미지(상태가 기록된 것)를 저장 시각 순으로"""
        metas = [m for m in self.records.values()
                 if m.status and (valid_names is None or m.filename in valid_names)]
        return sorted(metas, key=lambda m: (m.updated_at, m.filename))
