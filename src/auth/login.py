"""[카테고리] 로그인 — 로그인 화면 표시, 역할 선택, 메인 화면 전환

의사 코드
    show_login(root, 이전 이름, 이전 역할):          ← main.py 와 로그아웃 시 호출
        창 제목·크기를 로그인용으로 설정
        LoginFrame 표시 (이전 이름·역할이 있으면 미리 채움)
        로그인 성공 시:
            로그인 화면 제거 → LabelingApp(root, 이름, 역할) 생성
            로그아웃하면 다시 show_login 으로 돌아오도록 콜백 전달

    LoginFrame:
        [역할]  작업자 ●─ 검수자   (토글 스위치)
        [이름]  ____________       (Enter 로도 로그인)
        [로그인] → 이름이 비었으면 경고, 아니면 on_login(이름, 역할)

역할에 따른 차이 (자세한 규칙은 src/review/review_rules.py, src/review/workspace.py)
    작업자: 결과를 작업자/ 에 저장, 상태는 EDITED(기본) 또는 REVIEW(이슈 기록 → 검수자 확인 요청)
    검수자: PASS / EDITED / REVIEW / REVIEWED 선택, 검수자/<상태>/ 에 저장
"""
import tkinter as tk
from tkinter import messagebox, ttk

from src import config as C
from src.ui.main_window import LabelingApp
from src.ui.theme import FONTS
from src.ui.widgets import ToggleSwitch


LOGIN_SIZE = (500, 360)   # 로그인 창 크기 (가로, 세로)


def show_login(root: tk.Tk, last_name: str = "", last_role: str = C.ROLE_WORKER) -> None:
    """로그인 화면 표시. 프로그램 시작 시, 그리고 로그아웃 후 다시 호출된다."""
    root.title(f"{C.APP_TITLE} - 로그인")
    w, h = LOGIN_SIZE
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    try:                                   # 메인 창에서 최대화했던 상태 해제 (Linux)
        root.attributes("-zoomed", False)
    except tk.TclError:
        pass
    root.state("normal")
    root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 3}")
    root.resizable(False, False)

    def on_login(name: str, role: str) -> None:
        """로그인 성공 → 로그인 화면을 지우고 메인 라벨링 창 생성"""
        login.destroy()
        root.resizable(True, True)
        root.app = LabelingApp(root, name, role,          # root.app: 객체 참조 유지용
                               on_logout=lambda n, r: show_login(root, n, r))

    login = LoginFrame(root, on_login, default_name=last_name, default_role=last_role)
    login.pack(fill="both", expand=True)
    root.app = None


class LoginFrame(tk.Frame):
    """로그인 입력 화면 (역할 토글 + 이름 + 로그인 버튼)"""

    def __init__(self, master, on_login, default_name: str = "", default_role: str = C.ROLE_WORKER):
        super().__init__(master, bg=C.COLOR_BG)
        self.on_login = on_login
        self.is_reviewer = tk.BooleanVar(value=default_role == C.ROLE_REVIEWER)  # False=작업자
        self.name_var = tk.StringVar(value=default_name)

        card = tk.Frame(self, bg=C.COLOR_PANEL,
                        highlightbackground=C.COLOR_BORDER, highlightthickness=1)
        card.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(card, text="조각김치 이물검출 라벨링 도구", font=FONTS["big"],
                 bg=C.COLOR_PANEL, fg=C.COLOR_TEXT).grid(
            row=0, column=0, columnspan=2, padx=32, pady=(26, 4))
        tk.Label(card, text="역할을 선택하고 이름을 입력하세요", font=FONTS["small"],
                 bg=C.COLOR_PANEL, fg=C.COLOR_MUTED).grid(
            row=1, column=0, columnspan=2, pady=(0, 18))

        # 역할 토글
        tk.Label(card, text="역할", font=FONTS["bold"], bg=C.COLOR_PANEL).grid(
            row=2, column=0, sticky="w", padx=(32, 12), pady=6)
        role = tk.Frame(card, bg=C.COLOR_PANEL)
        role.grid(row=2, column=1, sticky="w", padx=(0, 32), pady=6)
        self.worker_lbl = tk.Label(role, text="작업자", bg=C.COLOR_PANEL)
        self.worker_lbl.pack(side="left")
        ToggleSwitch(role, self.is_reviewer).pack(side="left", padx=10)
        self.reviewer_lbl = tk.Label(role, text="검수자", bg=C.COLOR_PANEL)
        self.reviewer_lbl.pack(side="left")
        self.is_reviewer.trace_add("write", lambda *_: self._update_role())
        self._update_role()

        # 이름
        tk.Label(card, text="이름", font=FONTS["bold"], bg=C.COLOR_PANEL).grid(
            row=3, column=0, sticky="w", padx=(32, 12), pady=6)
        entry = ttk.Entry(card, textvariable=self.name_var, width=24, font=FONTS["base"])
        entry.grid(row=3, column=1, sticky="we", padx=(0, 32), pady=6)
        entry.bind("<Return>", lambda e: self._login())
        entry.bind("<KP_Enter>", lambda e: self._login())

        ttk.Button(card, text="로그인", style="Accent.TButton", command=self._login).grid(
            row=4, column=0, columnspan=2, sticky="we", padx=32, pady=(16, 28))
        entry.focus_set()
        entry.icursor("end")

    def _update_role(self):
        """토글 상태에 따라 '작업자' / '검수자' 글자 강조"""
        rev = self.is_reviewer.get()
        on = dict(fg=C.COLOR_ACCENT, font=FONTS["bold"])
        off = dict(fg=C.COLOR_MUTED, font=FONTS["base"])
        self.worker_lbl.configure(**(off if rev else on))
        self.reviewer_lbl.configure(**(on if rev else off))

    def _login(self):
        """로그인 버튼 / Enter: 이름 확인 후 on_login(이름, 역할) 호출"""
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("로그인", "이름을 입력하세요.", parent=self)
            return
        role = C.ROLE_REVIEWER if self.is_reviewer.get() else C.ROLE_WORKER
        self.on_login(name, role)
