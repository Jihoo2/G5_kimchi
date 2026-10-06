"""[카테고리] BBox 수정 패널 — HUD를 더블클릭하거나 I 키를 누르면 그 자리에 뜨는 입력창

의사 코드
    open(x, y):
        선택 BBox의 Class, 정규화 좌표(X중심, Y중심, 너비, 높이)를 입력칸에 채움
        HUD를 숨기고 그 위치에 패널 표시 (화면 밖으로 나가지 않게 보정)
    apply():   Enter
        숫자·범위(0~1, 너비·높이 > 0) 확인 → app.update_box_from_overlay() 로 BBox 수정
    close():   Esc / 캔버스 클릭 / 줌·팬
        패널 숨기고 HUD 다시 표시
    refresh():
        선택한 BBox가 바뀌면 패널을 닫고, 아니면 HUD만 다시 그림
"""
import tkinter as tk
from tkinter import ttk

from src import config as C
from src.ui.theme import FONTS


class BoxEditor(tk.Frame):
    """HUD 더블클릭(또는 I키) 시 그 자리에 뜨는 BBox 수정 패널. Enter 적용 / Esc 취소"""
    FIELDS = [("cx", "X(중심)"), ("cy", "Y(중심)"), ("w", "너비"), ("h", "높이")]
    BG, FG, MUTED = "#111827", "#F9FAFB", "#9CA3AF"

    def __init__(self, master, app):
        """Class 드롭다운 + 좌표 입력칸 4개 생성, Enter/Esc 연결"""
        super().__init__(master, bg=self.BG, highlightbackground=C.COLOR_ACCENT,
                         highlightthickness=1, padx=10, pady=8)
        self.app = app
        self.view = master
        self.is_open = False
        self._idx = None

        tk.Label(self, text="BBox 수정", font=FONTS["bold"], bg=self.BG, fg=self.FG).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        tk.Label(self, text="Class", font=FONTS["small"], bg=self.BG, fg=self.MUTED).grid(
            row=1, column=0, sticky="w", padx=(0, 10))
        self.cls_combo = ttk.Combobox(self, state="readonly", width=18, font=FONTS["small"],
                                      values=[f"{cid}  {C.CLASS_NAMES[cid]}" for cid in C.ENABLED_CLASSES])
        self.cls_combo.grid(row=1, column=1, sticky="w", pady=1)

        self.vars, self.entries = {}, []
        for r, (key, label) in enumerate(self.FIELDS, start=2):
            tk.Label(self, text=label, font=FONTS["small"], bg=self.BG, fg=self.MUTED).grid(
                row=r, column=0, sticky="w", padx=(0, 10))
            v = tk.StringVar()
            ent = ttk.Entry(self, textvariable=v, width=12, font=FONTS["small"])
            ent.grid(row=r, column=1, sticky="w", pady=1)
            self.vars[key] = v
            self.entries.append(ent)
        for w in [self.cls_combo] + self.entries:
            w.bind("<Return>", lambda e: (self.apply(), "break")[1])
            w.bind("<KP_Enter>", lambda e: (self.apply(), "break")[1])
            w.bind("<Escape>", lambda e: (self.close(), "break")[1])
        tk.Label(self, text="Enter 적용 · Esc 취소", font=FONTS["small"], bg=self.BG,
                 fg=self.MUTED).grid(row=6, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def open(self, x, y):
        """선택 박스 값을 채우고 (x, y) 위치에 패널 표시"""
        app = self.app
        sel = app.selected
        if sel is None or app.image is None:
            return
        b = app.boxes[sel]
        c, cx, cy, w, h = b.to_yolo(*app.image.size)
        self.cls_combo.set(f"{c}  {C.CLASS_NAMES.get(c, '?')}")
        for key, val in zip(("cx", "cy", "w", "h"), (cx, cy, w, h)):
            self.vars[key].set(f"{val:.4f}")
        self._idx = sel
        self.is_open = True
        self.view.canvas.delete("hud")
        self.place(x=x, y=y)
        self.update_idletasks()
        cw, ch = self.view._canvas_size()     # 화면 밖으로 나가지 않게
        self.place(x=max(4, min(x, cw - self.winfo_reqwidth() - 4)),
                   y=max(4, min(y, ch - self.winfo_reqheight() - 4)))
        self.entries[0].focus_set()
        self.entries[0].select_range(0, "end")

    def close(self):
        """패널 닫고 HUD 다시 표시"""
        if not self.is_open:
            return
        self.is_open = False
        self._idx = None
        self.place_forget()
        self.view.canvas.focus_set()
        self.view.draw_hud()

    def refresh(self):
        """선택이 바뀌거나 해제되면 편집기를 닫고 HUD 갱신"""
        if self.is_open and self.app.selected != self._idx:
            self.close()
        else:
            self.view.draw_hud()

    def apply(self):
        """입력값 검사 후 BBox 수정 (Enter)"""
        app = self.app
        if app.selected is None:
            self.close()
            return
        try:
            vals = {k: float(v.get()) for k, v in self.vars.items()}
        except ValueError:
            app.set_message("좌표는 0~1 사이 숫자로 입력하세요.", "error")
            return
        if any(not 0 <= x <= 1 for x in vals.values()) or vals["w"] <= 0 or vals["h"] <= 0:
            app.set_message("좌표는 0~1 범위, 너비/높이는 0보다 커야 합니다.", "error")
            return
        text = self.cls_combo.get()
        cid = int(text.split()[0]) if text else app.boxes[app.selected].cls
        self.is_open = False          # 적용 후 갱신 시 HUD가 다시 그려지도록 먼저 닫음 처리
        self._idx = None
        self.place_forget()
        app.update_box_from_overlay(cid, vals["cx"], vals["cy"], vals["w"], vals["h"])
        self.view.canvas.focus_set()
