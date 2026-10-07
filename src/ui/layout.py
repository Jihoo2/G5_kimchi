"""[카테고리] 화면 배치 — 메인 창의 모든 위젯을 만들고 배치한다. (동작 로직은 다른 Mixin에 있음)

의사 코드
    _build_window():
        창 크기·최소 크기 설정, 닫기(X) → on_close 연결
        툴바 / 가운데 / 오른쪽 패널(스크롤) / 상태바 생성
    _build_toolbar():
        [폴더 열기][저장][저장 후 다음][이전][다음] | [Fit][Zoom+][Zoom-][Pan][Undo][Validation]
        오른쪽: 라벨 도구 [+ 새 BBox][선택·이동][삭제]
    _build_center():
        파일 이름 + 진행률(현재/전체) + 완료율 바
        이미지 캔버스(ImageCanvas)
        하단 썸네일 목록(ThumbnailStrip)
    _build_right():
        클래스 선택 → 라벨 완료 이미지 → 라벨 목록 표 → 검수 상태 | 작업자 정보
        → Scene Type | Issue/Note → CSV 저장 정보 → 필터/QA 도구
    _build_statusbar():
        안내 메시지 | 미저장 표시 | 로그인 사용자 | [단축키 ?]
"""
import tkinter as tk
from tkinter import ttk

from src import config as C
from src.ui.canvas import ImageCanvas
from src.ui.theme import FONTS
from src.ui.thumbnails import ThumbnailStrip
from src.ui.widgets import make_card, ScrollableFrame, ToggleSwitch, Tooltip


class LayoutMixin:
    """화면 배치(레이아웃) 기능 (LabelingApp에 섞여 들어감 — self는 LabelingApp)"""

    def _build_window(self):
        """메인 창 크기·그리드 설정 후 툴바 / 가운데 / 오른쪽 패널 / 상태바 생성"""
        r = self.root
        r.title(C.APP_TITLE)
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        w, h = min(1720, sw - 40), min(1040, sh - 80)
        r.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 3)}")
        r.minsize(1360, 760)
        r.protocol("WM_DELETE_WINDOW", self.on_close)
        r.columnconfigure(0, weight=1)
        r.rowconfigure(1, weight=1)

        self._build_toolbar()

        main = tk.Frame(r, bg=C.COLOR_BG)
        main.grid(row=1, column=0, sticky="nsew", padx=8)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)

        center = tk.Frame(main, bg=C.COLOR_BG)
        center.grid(row=0, column=0, sticky="nsew")
        self._build_center(center)

        right = ScrollableFrame(main)
        right.grid(row=0, column=1, sticky="ns", padx=(8, 0))
        self._build_right(right.inner)

        self._build_statusbar()

    def _build_toolbar(self):
        """상단 툴바: 폴더·저장·이동·줌·Pan·Undo·Validation + 라벨 도구(새 BBox / 선택·이동 / 삭제)"""
        bar = tk.Frame(self.root, bg=C.COLOR_PANEL,
                       highlightbackground=C.COLOR_BORDER, highlightthickness=1)
        bar.grid(row=0, column=0, sticky="ew", padx=8, pady=8)

        def btn(parent, text, cmd, tip=None):
            b = ttk.Button(parent, text=text, command=cmd, style="Tool.TButton")
            b.pack(side="left", padx=3, pady=6)
            if tip:
                Tooltip(b, tip)
            return b

        btn(bar, "폴더 열기", self.open_folder, "작업할 이미지 폴더 선택 (Ctrl+O)")
        btn(bar, "저장", self.save, "YOLO TXT + CSV 상태 저장 (Ctrl+S)")
        btn(bar, "저장 후 다음", self.save_and_next, "저장하고 다음 이미지로 (Ctrl+Enter)")
        btn(bar, "← 이전", self.go_prev, "이전 이미지 (← / A)")
        btn(bar, "다음 →", self.go_next, "다음 이미지 (→ / D)")
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6, pady=8)
        btn(bar, "Fit", lambda: self.view.fit(), "이미지를 화면에 맞추기 (F)")
        btn(bar, "Zoom +", lambda: self.view.zoom(C.ZOOM_STEP), "확대 (+ / 마우스 휠)")
        btn(bar, "Zoom -", lambda: self.view.zoom(1 / C.ZOOM_STEP), "축소 (- / 마우스 휠)")
        self.pan_btn = btn(bar, "Pan", lambda: self.set_mode("pan"),
                           "확대 상태에서 화면 이동 (H)\n휠 클릭·우클릭 드래그는 항상 Pan")
        btn(bar, "↶ Undo", self.undo_action, "마지막 작업 취소 (Ctrl+Z)")
        btn(bar, "✓ Validation", self.run_validation, "TXT 형식·좌표·Class 오류 검사")

        # 라벨 도구 그룹 (디자인의 '+' 버튼)
        grp = tk.Frame(bar, bg=C.COLOR_PANEL)
        grp.pack(side="right", padx=6)
        tk.Label(grp, text="라벨 도구", bg=C.COLOR_PANEL, fg=C.COLOR_MUTED,
                 font=FONTS["small"]).pack(side="left", padx=(0, 4))
        hint = "새 BBox를 그리고, 선택한 BBox를 이동하거나 삭제할 수 있습니다."
        self.draw_btn = btn(grp, "+ 새 BBox", lambda: self.set_mode("draw"),
                            f"{hint}\n드래그로 새 BBox 그리기 (W)")
        self.select_btn = btn(grp, "선택·이동", lambda: self.set_mode("select"),
                              f"{hint}\nBBox 클릭 후 드래그로 이동, 모서리·테두리로 크기 조절 (E)")
        btn(grp, "삭제", self.delete_selected, f"{hint}\n선택한 BBox 삭제 (Delete)")

    def _build_center(self, center):
        """가운데 영역: 파일명·진행률 바 / 이미지 캔버스 / 하단 썸네일 목록"""
        center.columnconfigure(0, weight=1)
        center.rowconfigure(1, weight=1)

        info = tk.Frame(center, bg=C.COLOR_PANEL,
                        highlightbackground=C.COLOR_BORDER, highlightthickness=1)
        info.grid(row=0, column=0, sticky="ew")
        self.file_lbl = tk.Label(info, text="파일 이름 :  -", bg=C.COLOR_PANEL, font=FONTS["title"])
        self.file_lbl.pack(side="left", padx=10, pady=8)
        prog = tk.Frame(info, bg=C.COLOR_PANEL)
        prog.pack(side="right", padx=10)
        self.pos_lbl = tk.Label(prog, text="진행률  0 / 0", bg=C.COLOR_PANEL, font=FONTS["bold"])
        self.pos_lbl.pack(side="left", padx=(0, 12))
        self.progress = ttk.Progressbar(prog, style="Done.Horizontal.TProgressbar",
                                        length=180, maximum=100)
        self.progress.pack(side="left")
        self.pct_lbl = tk.Label(prog, text="완료 0%", bg=C.COLOR_PANEL, fg=C.COLOR_MUTED,
                                font=FONTS["small"], width=9, anchor="w")
        self.pct_lbl.pack(side="left", padx=(6, 0))
        Tooltip(self.progress, "라벨 저장이 완료된 이미지 비율")

        self.view = ImageCanvas(center, self)
        self.view.grid(row=1, column=0, sticky="nsew", pady=6)

        self.strip_card = make_card(center, "이미지 목록 (0개)")
        self.strip_card.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        self.thumbs = ThumbnailStrip(self.strip_card.body, self)
        self.thumbs.pack(fill="x")

    def _build_right(self, right):
        # 1) 클래스 선택
        """오른쪽 패널: 클래스 선택, 라벨 완료 목록, 라벨 목록 표, 검수 상태, 작업자 정보,
        Scene Type, Issue/Note, CSV 저장 정보, 필터/QA 도구
        """
        c1 = make_card(right, "클래스 선택")
        c1.pack(fill="x", pady=(0, 6))
        self.class_combo = ttk.Combobox(
            c1.body, state="readonly", font=FONTS["base"],
            values=[f"{cid}  {C.CLASS_NAMES[cid]}" for cid in C.ENABLED_CLASSES])
        self.class_combo.pack(fill="x", pady=(0, 6))
        self.class_combo.bind("<<ComboboxSelected>>", self._on_class_combo)

        lst = tk.Frame(c1.body, bg=C.COLOR_PANEL,
                       highlightbackground=C.COLOR_BORDER, highlightthickness=1)
        lst.pack(fill="x")
        self.class_rows = {}
        for cid, name, color, enabled in C.CLASSES:
            row = tk.Frame(lst, bg=C.COLOR_PANEL, cursor="hand2" if enabled else "")
            row.pack(fill="x")
            sw = tk.Frame(row, bg=color, width=12, height=12,
                          highlightthickness=1, highlightbackground=color)
            sw.pack(side="left", padx=(8, 8), pady=4)
            lbl = tk.Label(row, text=f"{cid}   {name}", bg=C.COLOR_PANEL, anchor="w",
                           fg=C.COLOR_TEXT if enabled else "#A0A7B2", font=FONTS["base"])
            lbl.pack(side="left", fill="x", expand=True)
            key = tk.Label(row, text=f"[{cid}]" if enabled else "", bg=C.COLOR_PANEL,
                           fg=C.COLOR_MUTED, font=FONTS["small"])
            key.pack(side="right", padx=8)
            if enabled:
                for w in (row, sw, lbl, key):
                    w.bind("<Button-1>", lambda e, c=cid: self._on_class_click(c))
            self.class_rows[cid] = (row, sw, lbl, key, color, enabled)

        # 2) 라벨 완료 이미지
        c2 = make_card(right, "라벨 완료 이미지")
        c2.pack(fill="x", pady=(0, 6))
        self.done_count_lbl = tk.Label(c2.head, text="이미지 0 / 0", bg=C.COLOR_PANEL,
                                       fg=C.COLOR_MUTED, font=FONTS["small"])
        self.done_count_lbl.pack(side="right")
        lf = tk.Frame(c2.body, bg=C.COLOR_PANEL)
        lf.pack(fill="x")
        self.done_list = tk.Listbox(lf, height=4, font=FONTS["small"], activestyle="none",
                                    selectbackground=C.COLOR_ACCENT, selectforeground="white",
                                    highlightthickness=1, highlightbackground=C.COLOR_BORDER,
                                    relief="flat", exportselection=False)
        dsb = ttk.Scrollbar(lf, orient="vertical", command=self.done_list.yview)
        self.done_list.configure(yscrollcommand=dsb.set)
        self.done_list.pack(side="left", fill="x", expand=True)
        dsb.pack(side="right", fill="y")
        self.done_list.bind("<<ListboxSelect>>", self._on_done_select)
        self._done_names: list[str] = []

        # 3) 라벨 목록
        self.labels_card = make_card(right, "라벨 목록 (0개)")
        self.labels_card.pack(fill="x", pady=(0, 6))
        tf = tk.Frame(self.labels_card.body, bg=C.COLOR_PANEL)
        tf.pack(fill="x")
        cols = ("no", "cls", "pos", "state")
        self.tree = ttk.Treeview(tf, columns=cols, show="headings", height=5, selectmode="browse")
        for col, text, width, anchor in (("no", "No", 36, "center"), ("cls", "클래스", 150, "w"),
                                         ("pos", "위치 (x, y, w, h)", 140, "center"),
                                         ("state", "상태", 56, "center")):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor=anchor, stretch=False)
        tsb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tsb.set)
        self.tree.pack(side="left", fill="x", expand=True)
        tsb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # 4) 검수 상태 | 작업자 정보
        row4 = tk.Frame(right, bg=C.COLOR_BG)
        row4.pack(fill="x", pady=(0, 6))
        c4 = make_card(row4, "검수 상태")
        c4.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.status_radios = {}
        for s in C.STATUSES:
            rb = ttk.Radiobutton(c4.body, text=s, value=s, variable=self.status_var)
            rb.pack(anchor="w", pady=1)
            Tooltip(rb, C.STATUS_DESC[s])
            self.status_radios[s] = rb
        if self.role != C.ROLE_REVIEWER:
            for s_ in C.REVIEWER_ONLY_STATUSES:
                self.status_radios[s_].state(["disabled"])
        self.save_dir_lbl = tk.Label(c4.body, text="", bg=C.COLOR_PANEL, fg=C.COLOR_MUTED,
                                     font=FONTS["small"], justify="left")
        self.save_dir_lbl.pack(anchor="w", pady=(4, 0))
        self.cr_lbl = tk.Label(c4.body, text="", bg=C.COLOR_PANEL, fg="#B45309",
                               font=FONTS["small"], justify="left", wraplength=190)
        self.cr_lbl.pack(anchor="w", pady=(2, 0))

        c5 = make_card(row4, "작업자 정보")
        c5.pack(side="left", fill="both", expand=True)
        tk.Label(c5.body, text="작업자 :", bg=C.COLOR_PANEL).grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(c5.body, textvariable=self.assignee_var, state="readonly", width=12).grid(
            row=0, column=1, sticky="w", pady=3)
        tk.Label(c5.body, text="검수자 :", bg=C.COLOR_PANEL).grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(c5.body, textvariable=self.reviewer_var, state="readonly", width=12).grid(
            row=1, column=1, sticky="w", pady=3)
        login_row = tk.Frame(c5.body, bg=C.COLOR_PANEL)
        login_row.grid(row=2, column=0, columnspan=2, sticky="we", pady=(6, 0))
        tk.Label(login_row, text=f"로그인: {self.user_name} ({C.ROLE_LABELS[self.role]})",
                 bg=C.COLOR_PANEL, fg=C.COLOR_ACCENT, font=FONTS["small"]).pack(side="left")
        logout_btn = ttk.Button(login_row, text="로그아웃", style="Small.TButton", command=self.logout)
        logout_btn.pack(side="right", padx=(8, 0))
        Tooltip(logout_btn, "로그인 화면으로 돌아갑니다\n(저장하지 않은 변경사항이 있으면 먼저 확인)")

        # 5) Scene Type | Issue / Note
        row5 = tk.Frame(right, bg=C.COLOR_BG)
        row5.pack(fill="x", pady=(0, 6))
        c6 = make_card(row5, "Scene Type")
        c6.pack(side="left", fill="both", expand=True, padx=(0, 6))
        for code, label in C.SCENE_TYPES:
            ttk.Radiobutton(c6.body, text=label, value=code,
                            variable=self.scene_var).pack(anchor="w", pady=1)
        c7 = make_card(row5, "Issue / Note")
        c7.pack(side="left", fill="both", expand=True)
        self.note = tk.Text(c7.body, height=5, width=20, font=FONTS["small"], wrap="word",
                            relief="flat", highlightthickness=1,
                            highlightbackground=C.COLOR_BORDER, highlightcolor=C.COLOR_ACCENT)
        self.note.pack(fill="both", expand=True)
        self.note.bind("<<Modified>>", self._on_note_modified)

        # 6) CSV 저장 정보
        c8 = make_card(right, "CSV 저장 정보")
        c8.pack(fill="x", pady=(0, 6))
        self.csv_lbl = tk.Label(c8.body, text="", font=FONTS["mono"], justify="left", anchor="w",
                                bg="#F7F9FC", padx=8, pady=6)
        self.csv_lbl.pack(fill="x")

        # 7) 필터 / QA 도구
        c9 = make_card(right, "필터 / QA 도구")
        c9.pack(fill="x")
        self.todo_btn = ttk.Button(c9.body, text="미완료만 보기", style="Small.TButton",
                                   command=lambda: self.set_filter("TODO"))
        self.todo_btn.pack(side="left", padx=(0, 4))
        Tooltip(self.todo_btn, "내 역할로 아직 저장하지 않은 이미지만 목록에 표시\n"
                               "(작업자로 폴더를 열면 자동으로 켜짐, 다시 누르면 전체 보기)")
        self.review_btn = ttk.Button(c9.body, text="REVIEW만 보기", style="Small.TButton",
                                     command=lambda: self.set_filter("REVIEW"))
        self.review_btn.pack(side="left", padx=(0, 4))
        self.edited_btn = ttk.Button(c9.body, text="EDITED만 보기", style="Small.TButton",
                                     command=lambda: self.set_filter("EDITED"))
        self.edited_btn.pack(side="left", padx=(0, 4))
        self.cross_btn = ttk.Button(c9.body, text="Cross Review 대상", style="Small.TButton",
                                    command=lambda: self.set_filter("CROSS"))
        self.cross_btn.pack(side="left")
        Tooltip(self.cross_btn, "100% 교차검수 대상: 수정·신규 라벨(EDITED), REVIEW였던 이미지,\n"
                                "Class 4 발견, Empty Label (검수자 기록 기준)")
        self.warn_lbl = tk.Label(c9.body, text="미저장 경고 : ON", bg=C.COLOR_PANEL,
                                 font=FONTS["small"])
        self.warn_lbl.pack(side="right")
        ToggleSwitch(c9.body, self.warn_unsaved, command=self._on_warn_toggle).pack(
            side="right", padx=6)

    def _build_statusbar(self):
        """하단 상태바: 안내 메시지, 미저장 표시, 로그인 사용자, 단축키 도움말 버튼"""
        sb = tk.Frame(self.root, bg=C.COLOR_PANEL,
                      highlightbackground=C.COLOR_BORDER, highlightthickness=1)
        sb.grid(row=2, column=0, sticky="ew", padx=8, pady=(4, 8))
        self.msg_lbl = tk.Label(sb, text="", anchor="w", bg=C.COLOR_PANEL,
                                fg=C.COLOR_MUTED, font=FONTS["small"])
        self.msg_lbl.pack(side="left", fill="x", expand=True, padx=10, pady=4)
        ttk.Button(sb, text="단축키 ?", style="Small.TButton",
                   command=self.show_shortcuts).pack(side="right", padx=6, pady=2)
        tk.Label(sb, text=f"{C.ROLE_LABELS[self.role]}: {self.user_name}", bg=C.COLOR_PANEL,
                 fg=C.COLOR_TEXT, font=FONTS["small"]).pack(side="right", padx=8)
        self.dirty_lbl = tk.Label(sb, text="", bg=C.COLOR_PANEL, fg=C.COLOR_DANGER,
                                  font=FONTS["bold"])
        self.dirty_lbl.pack(side="right", padx=8)
