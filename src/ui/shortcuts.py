"""[카테고리] 단축키 — 키보드 입력을 기능에 연결한다.

의사 코드
    _bind_shortcuts():
        Ctrl+O 폴더 열기 / Ctrl+S 저장 / Ctrl+Z Undo / Ctrl+Shift+Z·Ctrl+Y Redo / Ctrl+T HUD / Ctrl+Enter 저장 후 다음
        나머지 키 → _on_key
    _on_key(키):
        글자 입력칸(이름, Note, HUD 편집기)에서 누른 키면 무시
        숫자 0~6      → Class 지정 (선택 BBox가 있으면 Class 변경)
        Enter         → 미확정 BBox 확정
        방향키         → 선택 BBox 1px 이동 (Shift 10px) / 선택 없으면 ←→ 이미지 이동
        Ctrl + 방향키  → 선택 BBox 를 그 방향으로 늘림 / Alt + 방향키 → 그 방향 변을 안쪽으로 줄임
        Tab / Shift+Tab → 라벨 목록 순서로 다음 / 이전 BBox 선택 (마지막 다음은 처음)
        키패드 . / Ctrl+Space → 선택 BBox 를 화면 가운데로 (줌 유지)
        Delete / BackSpace → 선택 BBox 삭제 (키패드 Del 은 삭제가 아니라 시점 이동)
        A / D         → 이전 / 다음 이미지
        W / E / H     → 그리기 / 선택·이동 / Pan 모드
        F, + / -      → Fit, 확대 / 축소
        I             → HUD 편집기 열기
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
    ("Tab / Shift + Tab", "라벨 목록 순서로 다음 / 이전 BBox 선택 (끝에서 처음으로)"),
    ("키패드 . / Ctrl + Space", "선택한 BBox 를 화면 가운데로 (줌 배율 유지)"),
    ("Ctrl + 방향키", "선택한 BBox 를 그 방향으로 늘림 (0.0005씩)"),
    ("Alt + 방향키", "선택한 BBox 의 그 방향 변을 안쪽으로 줄임 (0.0005씩)"),
    ("A / D", "이전 / 다음 이미지 (선택 없을 땐 ← / →도 가능)"),
    ("W", "새 BBox 그리기 모드"), ("E", "선택·이동 모드"),
    ("H", "Pan 모드 (휠 클릭·우클릭 드래그는 항상 Pan)"),
    ("0 ~ 6", "선택한 BBox Class 변경 / 그릴 Class 선택"),
    ("Delete", "선택한 BBox 삭제"), ("Ctrl+Z", "Undo"), ("Ctrl+Shift+Z / Ctrl+Y", "Redo (Undo 한 것 다시 실행)"),
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
                         (("t", "T"), self.toggle_overlay), (("y", "Y"), self.redo_action)):
            for k in keys:
                bind(f"<Control-{k}>", lambda e, f=fn: (f(), "break")[1])
        # Ctrl+Z = Undo, Ctrl+Shift+Z = Redo
        # (Shift 를 누르면 대문자 Z 로 들어오므로 글자 대신 Shift 눌림 여부로 구분 → Caps Lock 켜져도 정상)
        for k in ("z", "Z"):
            bind(f"<Control-{k}>", lambda e: (self._on_ctrl_z(e), "break")[1])
        # Ctrl + Space = 선택 박스로 시점 이동 (키패드 . 와 같음, 글자 입력칸에서는 무시)
        bind("<Control-space>", lambda e: None if isinstance(e.widget, TEXT_INPUTS)
             else (self.center_on_selected(), "break")[1])
        # Tab = 다음 박스 선택, Shift+Tab = 이전 박스 선택 (원래 Tab 의 포커스 이동 대신)
        bind("<Tab>", lambda e: self._on_tab(e, 1))
        for seq in ("<Shift-Tab>", "<ISO_Left_Tab>"):     # Linux 는 Shift+Tab 이 ISO_Left_Tab 으로 들어옴
            try:
                bind(seq, lambda e: self._on_tab(e, -1))
            except tk.TclError:                          # Windows 에는 ISO_Left_Tab 이 없음
                pass
        # Ctrl + 방향키 = 선택 박스를 그 방향으로 늘림, Alt + 방향키 = 그 방향 변을 안쪽으로 줄임
        for k in ("Left", "Right", "Up", "Down"):
            bind(f"<Control-{k}>", lambda e, k=k: self._on_resize_key(e, k, True))
            bind(f"<Alt-{k}>", lambda e, k=k: self._on_resize_key(e, k, False))
        bind("<Control-Return>", lambda e: (self.save_and_next(), "break")[1])
        bind("<Control-KP_Enter>", lambda e: (self.save_and_next(), "break")[1])
        bind("<Key>", self._on_key)

    def center_on_selected(self):
        """선택한 BBox 가 화면 가운데 오도록 시점 이동 (줌 배율 유지)"""
        if self.selected is None:
            self.set_message("가운데로 볼 BBox를 먼저 선택하세요. (Tab 으로 선택)", "error")
            return
        if self.view.center_on_box(self.selected):
            self.set_message(f"선택 BBox 로 시점 이동 (줌 {self.view.scale * 100:.0f}% 유지)")

    def _on_tab(self, e, step):
        """Tab / Shift+Tab → 라벨 목록 순서로 박스 선택 (글자 입력칸에서는 원래 Tab 동작 유지)"""
        if isinstance(e.widget, TEXT_INPUTS):
            return None
        self.select_next_box(step)
        self.view.canvas.focus_set()
        return "break"

    def _on_resize_key(self, e, direction, grow):
        """Ctrl/Alt + 방향키 → 선택 박스 크기 조절 (글자 입력칸에서는 원래 키 동작 유지)"""
        if isinstance(e.widget, TEXT_INPUTS):
            return None
        self.resize_selected(direction, grow)
        return "break"

    def _on_ctrl_z(self, e):
        """Ctrl+Z → Undo, Ctrl+Shift+Z → Redo"""
        if e.state & 0x1:          # Shift
            self.redo_action()
        else:
            self.undo_action()

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
        elif k in ("KP_Decimal", "KP_Delete", "KP_Separator"):
            # 키패드 . (Num Lock 꺼지면 KP_Delete 로 들어옴) → 선택 박스로 시점 이동
            # ※ 키패드 Del 로 박스가 지워지지 않도록 삭제는 일반 Delete / BackSpace 만 사용
            self.center_on_selected()
        elif k in ("Delete", "BackSpace"):
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
