"""[카테고리] 공용 위젯 — 여러 화면에서 같이 쓰는 작은 부품

    ToggleSwitch     ON/OFF 스위치 (로그인 역할 선택, 미저장 경고)
    Tooltip          마우스를 올리면 잠시 후 설명 표시
    make_card()      파란 세로 바 + 제목이 있는 흰색 패널 (오른쪽 패널의 각 카드)
    ScrollableFrame  내용이 화면보다 길면 스크롤바가 생기는 프레임 (오른쪽 패널)
"""
import tkinter as tk
from tkinter import ttk

from src import config as C
from src.ui.theme import FONTS


class ToggleSwitch(tk.Canvas):
    """BooleanVar와 연결되는 ON/OFF 스위치"""

    def __init__(self, master, variable: tk.BooleanVar, command=None,
                 width=44, height=22, bg=C.COLOR_PANEL):
        """BooleanVar 와 연결, 클릭하면 토글"""
        super().__init__(master, width=width, height=height, bg=bg,
                         highlightthickness=0, cursor="hand2")
        self.var = variable
        self.command = command
        self._sw_width, self._sw_height = width, height
        self.bind("<Button-1>", self._toggle)
        self.var.trace_add("write", lambda *_: self._draw())
        self._draw()

    def _draw(self):
        """알약 모양 배경 + 흰 동그라미 그리기"""
        self.delete("all")
        w, h = self._sw_width, self._sw_height
        on = bool(self.var.get())
        color = C.COLOR_ACCENT if on else "#C5CBD3"
        self.create_oval(0, 0, h, h, fill=color, outline=color)
        self.create_oval(w - h, 0, w, h, fill=color, outline=color)
        self.create_rectangle(h / 2, 0, w - h / 2, h, fill=color, outline=color)
        x = w - h + 3 if on else 3
        self.create_oval(x, 3, x + h - 6, h - 3, fill="white", outline="white")

    def _toggle(self, _e=None):
        """값 반전 후 command 호출"""
        self.var.set(not self.var.get())
        if self.command:
            self.command()


class Tooltip:
    """위젯에 마우스를 올리면 설명 표시"""
    def __init__(self, widget, text: str, delay: int = 450):
        """Enter/Leave 이벤트 연결"""
        self.widget, self.text, self.delay = widget, text, delay
        self._after = None
        self.tip = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _e=None):
        """delay 후 표시 예약"""
        self._cancel()
        self._after = self.widget.after(self.delay, self._show)

    def _cancel(self):
        """예약 취소"""
        if self._after:
            self.widget.after_cancel(self._after)
            self._after = None

    def _show(self):
        """설명 창 표시"""
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.text, justify="left", bg="#1F2937", fg="white",
                 font=FONTS["small"], padx=8, pady=5).pack()

    def _hide(self, _e=None):
        """설명 창 닫기"""
        self._cancel()
        if self.tip:
            self.tip.destroy()
            self.tip = None


def make_card(parent, title: str) -> tk.Frame:
    """파란 세로 바 + 제목이 있는 흰색 패널. .head / .title_lbl / .body 속성 제공"""
    outer = tk.Frame(parent, bg=C.COLOR_PANEL,
                     highlightbackground=C.COLOR_BORDER, highlightthickness=1)
    head = tk.Frame(outer, bg=C.COLOR_PANEL)
    head.pack(fill="x", padx=8, pady=(6, 4))
    tk.Frame(head, bg=C.COLOR_ACCENT, width=4, height=16).pack(side="left", padx=(0, 6))
    title_lbl = tk.Label(head, text=title, bg=C.COLOR_PANEL, fg=C.COLOR_ACCENT,
                         font=FONTS["title"])
    title_lbl.pack(side="left")
    body = tk.Frame(outer, bg=C.COLOR_PANEL)
    body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
    outer.head, outer.title_lbl, outer.body = head, title_lbl, body
    return outer


class ScrollableFrame(tk.Frame):
    """세로로 내용이 넘칠 때만 스크롤바가 나타나는 프레임. 자식은 .inner 에 배치"""

    def __init__(self, master, bg=C.COLOR_BG, fill_width: bool = False):
        """캔버스 안에 inner 프레임을 넣고 크기 변경 감지
        fill_width=True: 내용 폭을 프레임 폭에 맞춤 (분할 창에서 폭을 바꾸면 내용도 함께 넓어지고 좁아짐)"""
        super().__init__(master, bg=bg)
        self.fill_width = fill_width
        self._width_set = False
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner.bind("<Configure>", self._update)
        self.canvas.bind("<Configure>", self._update)

    def _update(self, _e=None):
        """스크롤 영역 갱신, 넘칠 때만 스크롤바 표시"""
        if self.fill_width:
            if not self._width_set:                      # 처음 한 번만 내용 폭으로 시작
                self.canvas.configure(width=self.inner.winfo_reqwidth())
                self._width_set = True
            w = self.canvas.winfo_width()
            if w > 1:
                self.canvas.itemconfigure(self._win, width=w)
        else:
            self.canvas.configure(width=self.inner.winfo_reqwidth())
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        need = self.inner.winfo_reqheight() > self.canvas.winfo_height() > 1
        if need and not self.vsb.winfo_ismapped():
            self.vsb.pack(side="right", fill="y", before=self.canvas)
        elif not need and self.vsb.winfo_ismapped():
            self.vsb.pack_forget()
            self.canvas.yview_moveto(0)
