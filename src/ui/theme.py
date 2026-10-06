"""[카테고리] 화면 스타일 — 한글 폰트, 버튼·표·진행률 바 스타일

의사 코드
    setup_theme(root):     (main.py 에서 가장 먼저 호출)
        설치된 폰트 중 한글 폰트 선택 (NanumGothic → Noto Sans CJK → 맑은 고딕 ...)
        FONTS 사전에 base / bold / title / small / mono 등 등록 → 다른 파일에서 FONTS["bold"] 처럼 사용
        ttk 스타일 등록: Tool(툴바), ToolActive(선택된 모드), Accent(로그인), Small(필터) 등
"""
import tkinter as tk
from tkinter import font as tkfont, ttk

from src import config as C


FONTS: dict = {}


def _pick(root, candidates):
    """후보 폰트 중 설치된 첫 번째"""
    families = set(tkfont.families(root))
    for fam in candidates:
        if fam in families:
            return fam
    return candidates[-1]


def setup_theme(root: tk.Tk) -> dict:
    """폰트 선택·FONTS 등록·ttk 스타일 설정"""
    fam = _pick(root, C.FONT_CANDIDATES)
    mono = _pick(root, C.MONO_CANDIDATES)
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkTooltipFont"):
        try:
            tkfont.nametofont(name).configure(family=fam, size=10)
        except tk.TclError:
            pass

    FONTS.update(
        base=(fam, 10), bold=(fam, 10, "bold"), title=(fam, 11, "bold"),
        big=(fam, 16, "bold"), small=(fam, 9), tag=(fam, 9, "bold"), mono=(mono, 9),
    )
    root.configure(bg=C.COLOR_BG)

    s = ttk.Style(root)
    try:
        s.theme_use("clam")
    except tk.TclError:
        pass
    s.configure(".", font=FONTS["base"], background=C.COLOR_PANEL, foreground=C.COLOR_TEXT)
    s.configure("TFrame", background=C.COLOR_PANEL)

    s.configure("Tool.TButton", padding=(10, 5), background="#F7F9FC", bordercolor=C.COLOR_BORDER)
    s.map("Tool.TButton", background=[("active", "#E6EEFB")])
    s.configure("ToolActive.TButton", padding=(10, 5), background=C.COLOR_ACCENT,
                foreground="white", bordercolor=C.COLOR_ACCENT)
    s.map("ToolActive.TButton", background=[("active", C.COLOR_ACCENT_DARK)],
          foreground=[("active", "white")])

    s.configure("Accent.TButton", padding=(14, 7), background=C.COLOR_ACCENT,
                foreground="white", font=FONTS["bold"])
    s.map("Accent.TButton", background=[("active", C.COLOR_ACCENT_DARK)])

    s.configure("Small.TButton", padding=(8, 3), font=FONTS["small"], background="#F7F9FC")
    s.configure("SmallActive.TButton", padding=(8, 3), font=FONTS["small"],
                background=C.COLOR_ACCENT, foreground="white")
    s.map("SmallActive.TButton", background=[("active", C.COLOR_ACCENT_DARK)],
          foreground=[("active", "white")])

    s.configure("Treeview", rowheight=22, font=FONTS["small"],
                background="white", fieldbackground="white")
    s.configure("Treeview.Heading", font=FONTS["small"], background="#F3F5F9")
    s.map("Treeview", background=[("selected", C.COLOR_ACCENT)],
          foreground=[("selected", "white")])

    s.configure("TRadiobutton", background=C.COLOR_PANEL, font=FONTS["base"])
    s.configure("TEntry", padding=3)
    s.configure("TCombobox", padding=3)
    s.configure("Done.Horizontal.TProgressbar", troughcolor="#E5E7EB",
                background=C.COLOR_SUCCESS, bordercolor="#E5E7EB",
                lightcolor=C.COLOR_SUCCESS, darkcolor=C.COLOR_SUCCESS)
    return FONTS
