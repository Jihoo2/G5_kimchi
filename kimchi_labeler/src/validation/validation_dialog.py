"""[카테고리] Validation — 라벨 파일 자동 검사 (검사 로직은 src/validation/validator.py)

의사 코드
    run_validation():
        폴더 미선택이면 안내 / 미저장이면 저장 여부 확인
        validate_folder(현재 역할 기준 라벨) → 결과 창
    _show_validation(결과):
        요약(오류 N / 경고 N) + 표(파일, 줄, 수준, 내용)
        더블클릭 → 해당 이미지로 이동
"""
import tkinter as tk
from tkinter import messagebox, ttk

from src import config as C
from src.ui.theme import FONTS
from src.validation.validator import validate_folder


class ValidationMixin:
    """Validation 기능 (LabelingApp에 섞여 들어감 — self는 LabelingApp)"""

    def run_validation(self):
        """Validation 실행: (미저장 시 저장 여부 확인) → 전체 라벨 검사 → 결과 창"""
        if not self.folder:
            self.set_message("먼저 폴더를 여세요.", "error")
            return
        if self.dirty and messagebox.askyesno(
                "Validation", "현재 이미지에 저장하지 않은 변경사항이 있습니다.\n저장 후 검사할까요?",
                parent=self.root):
            self.save()
        issues = validate_folder(self.image_names, self.ws.resolve_label,
                                 self.ws.folder_meta, [self.ws.src])   # 연 폴더 기준으로 검사
        self._show_validation(issues)

    def _show_validation(self, issues):
        """Validation 결과 창 (항목 더블클릭 → 해당 이미지로 이동)"""
        win = tk.Toplevel(self.root)
        win.title("Validation 결과")
        win.geometry("820x480")
        win.transient(self.root)
        win.configure(bg=C.COLOR_PANEL)

        n_err = sum(1 for i in issues if i["level"] == "ERROR")
        n_warn = len(issues) - n_err
        summary = (f"검사 이미지 {len(self.image_names)}장   오류 {n_err}건   경고 {n_warn}건"
                   if issues else f"검사 이미지 {len(self.image_names)}장   문제 없음 ✓")
        tk.Label(win, text=summary, bg=C.COLOR_PANEL, font=FONTS["title"],
                 fg=C.COLOR_DANGER if n_err else (C.COLOR_TEXT if n_warn else C.COLOR_SUCCESS)
                 ).pack(anchor="w", padx=12, pady=(10, 2))
        tk.Label(win, text="항목을 더블클릭하면 해당 이미지로 이동합니다.", bg=C.COLOR_PANEL,
                 fg=C.COLOR_MUTED, font=FONTS["small"]).pack(anchor="w", padx=12, pady=(0, 6))

        frame = tk.Frame(win, bg=C.COLOR_PANEL)
        frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        cols = ("file", "line", "level", "msg")
        tree = ttk.Treeview(frame, columns=cols, show="headings")
        for col, text, width in (("file", "파일", 230), ("line", "줄", 50),
                                 ("level", "수준", 70), ("msg", "내용", 430)):
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="center" if col in ("line", "level") else "w")
        sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        tree.tag_configure("ERROR", foreground=C.COLOR_DANGER)
        tree.tag_configure("WARN", foreground="#B45309")
        for it in issues:
            tree.insert("", "end", values=(it["file"], it["line"], it["level"], it["msg"]),
                        tags=(it["level"],))

        def jump(_e=None):
            sel = tree.selection()
            if not sel:
                return
            fname = tree.item(sel[0], "values")[0]
            if fname in self.image_names:
                self.goto(self.image_names.index(fname))
        tree.bind("<Double-1>", jump)
        ttk.Button(win, text="닫기", style="Tool.TButton", command=win.destroy).pack(
            anchor="e", padx=12, pady=(0, 10))
