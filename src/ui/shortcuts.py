"""[카테고리] 단축키 — 키보드 입력을 기능에 연결한다.

의사 코드
    _bind_shortcuts():
        Ctrl+O 폴더 열기 / Ctrl+S 저장 / Ctrl+Z Undo / Ctrl+T HUD / Ctrl+Enter 저장 후 다음
        나머지 키 → _on_key
    _on_key(키):
        글자 입력칸(이름, Note, HUD 편집기)에서 누른 키면 무시
        숫자 0~6      → Class 지정 (선택 BBox가 있으면 Class 변경)
        Enter         → 미확정 BBox 확정
        방향키         → 선택 BBox 1px 이동 (Shift 10px) / 선택 없으면 ←→ 이미지 이동
        A / D         → 이전 / 다음 이미지
        W / E / H     → 그리기 / 선택·이동 / Pan 모드
        F, + / -      → Fit, 확대 / 축소
        I             → HUD 편집기 열기
        Delete        → 선택 BBox 삭제
        Esc           → 미확정 BBox 취소, 없으면 선택 해제
"""
import tkinter as tk
from tkinter import messagebox, ttk

from src import config as C


# 글자 입력칸: 이 위젯에 포커스가 있을 때는 단축키를 처리하지 않음 (ttk.Combobox ⊂ ttk.Entry)
TEXT_INPUTS = (tk.Entry, ttk.Entry, tk.Text, tk.Spinbox)


# 단축키 도움말 창에 표시할 목록 (키, 설명)
SHORTCUTS = [
    ("Ctrl+O", "폴더 열기"), ("Ctrl+S", "저장"), ("Ctrl+Enter", "저장 후 다음"),
    ("Enter", "그린 BBox 확정"), ("Esc", "미확정 BBox 취소 / 선택 해제"),
    ("방향키", "선택한 BBox 1px 이동 (Shift: 10px)"),
    ("A / D", "이전 / 다음 이미지 (선택 없을 땐 ← / →도 가능)"),
    ("W", "새 BBox 그리기 모드"), ("E", "선택·이동 모드"),
    ("H", "Pan 모드 (휠 클릭·우클릭 드래그는 항상 Pan)"),
    ("0 ~ 6", "선택한 BBox Class 변경 / 그릴 Class 선택"),
    ("Delete", "선택한 BBox 삭제"), ("Ctrl+Z", "Undo"),
    ("F", "Fit to Window"), ("+ / -", "Zoom In / Out (마우스 휠도 가능)"),
    ("I", "선택한 BBox 정보 수정 (HUD 더블클릭도 가능)"),
    ("Ctrl+T", "BBox 정보 HUD 표시/숨김"),
]


class ShortcutMixin:
    """단축키 기능 (LabelingApp에 섞여 들어감 — self는 LabelingApp)"""

    def _bind_shortcuts(self):
        """Ctrl 조합 단축키 + 일반 키 처리기를 root 창에 연결 (로그아웃 시 해제하려고 목록 보관)"""
        def bind(seq, fn):
            self.root.bind(seq, fn)
            self._bound.append(seq)

        for keys, fn in ((("o", "O"), self.open_folder), (("s", "S"), self.save),
                         (("z", "Z"), self.undo_action), (("t", "T"), self.toggle_overlay)):
            for k in keys:
                bind(f"<Control-{k}>", lambda e, f=fn: (f(), "break")[1])
        bind("<Control-Return>", lambda e: (self.save_and_next(), "break")[1])
        bind("<Control-KP_Enter>", lambda e: (self.save_and_next(), "break")[1])
        bind("<Key>", self._on_key)

    def _on_key(self, e):
        """일반 키 처리: 숫자=Class, Enter=확정, Esc=취소/해제, 방향키=박스 이동 또는 이미지 이동 등
        (글자 입력칸에 포커스가 있으면 무시)
        """
        if isinstance(e.widget, TEXT_INPUTS) or e.state & 0x4:   # 입력칸 / Ctrl 조합 제외
            return None
        k = e.keysym
        digit = k[3:] if k.startswith("KP_") else k
        if len(digit) == 1 and digit.isdigit():
            cid = int(digit)
            if cid < C.NUM_CLASSES:
                self._on_class_click(cid)
            return "break"
        low = k.lower()
        if k in ("Return", "KP_Enter"):
            self.confirm_pending()
        elif k in ("Left", "Right", "Up", "Down") and self.selected is not None:
            step = 10 if e.state & 0x1 else 1          # Shift = 10px
            dx = {"Left": -step, "Right": step}.get(k, 0)
            dy = {"Up": -step, "Down": step}.get(k, 0)
            self.nudge_selected(dx, dy)
        elif k == "Left" or low == "a":
            self.go_prev()
        elif k == "Right" or low == "d":
            self.go_next()
        elif low == "w":
            self.set_mode("draw")
        elif low == "e":
            self.set_mode("select")
        elif low == "h":
            self.set_mode("pan")
        elif low == "f":
            self.view.fit()
        elif low == "i":
            self.view.open_editor()
        elif k in ("plus", "equal", "KP_Add"):
            self.view.zoom(C.ZOOM_STEP)
        elif k in ("minus", "KP_Subtract"):
            self.view.zoom(1 / C.ZOOM_STEP)
        elif k in ("Delete", "BackSpace", "KP_Delete"):
            self.delete_selected()
        elif k == "Escape":
            if self.pending_index() is not None:
                self.cancel_pending()
            else:
                self.select_box(None)
        else:
            return None
        return "break"

    def show_shortcuts(self):
        """단축키 목록 안내 창 (상태바 '단축키 ?' 버튼)"""
        text = "\n".join(f"{k:<12} {d}" for k, d in SHORTCUTS)
        messagebox.showinfo("단축키", text, parent=self.root)
