"""[카테고리] 공통 파일 도구

    atomic_write(경로, write_fn):
        같은 폴더에 임시 파일 생성 → write_fn 으로 내용 쓰기 → 원래 파일과 교체
        → 쓰는 도중 프로그램이 꺼져도 기존 파일은 온전함 (TXT, CSV 저장에 사용)
"""
from __future__ import annotations

import os
import tempfile


def atomic_write(path: str, write_fn, encoding="utf-8", newline=None) -> None:
    """임시 파일에 쓴 뒤 교체 → 저장 중 강제 종료돼도 기존 파일이 깨지지 않음"""
    folder = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".tmp_", suffix=".part")
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline=newline) as f:
            write_fn(f)
        try:
            os.chmod(tmp, 0o644)
        except OSError:
            pass
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
