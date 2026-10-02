import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

# ==========================================
# 1. 전역 세션 및 클래스 정의
# ==========================================
class AppSession:
    user_name = ""
    user_role = "WORKER"  # "WORKER" 또는 "REVIEWER"

# ==========================================
# 2. [Step 1] 로그인 창 (시작 화면)
# ==========================================
class LoginWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("라벨링 도구 - 로그인")
        self.root.geometry("360x220")
        self.root.resizable(False, False)

        # 토글/라디오 버튼 (작업자 / 검수자)
        self.role_var = tk.StringVar(value="작업자")
        role_frame = ttk.LabelFrame(root, text="역할 선택")
        role_frame.pack(pady=10, padx=20, fill="x")
        
        rb_worker = ttk.Radiobutton(role_frame, text="작업자", value="작업자", variable=self.role_var)
        rb_reviewer = ttk.Radiobutton(role_frame, text="검수자", value="검수자", variable=self.role_var)
        rb_worker.pack(side="left", padx=20, pady=5)
        rb_reviewer.pack(side="left", padx=20, pady=5)

        # 이름 입력란
        input_frame = ttk.Frame(root)
        input_frame.pack(pady=10, padx=20, fill="x")
        ttk.Label(input_frame, text="이름: ").pack(side="left")
        self.ent_name = ttk.Entry(input_frame)
        self.ent_name.pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.ent_name.focus()

        # 로그인 버튼
        btn_login = ttk.Button(root, text="로그인", command=self.on_login)
        btn_login.pack(pady=10)

        # Enter키 로그인 지원
        self.root.bind("<Return>", lambda event: self.on_login())

    def on_login(self):
        name = self.ent_name.get().strip()
        if not name:
            messagebox.showwarning("경고", "이름을 입력해주세요.")
            return
        
        AppSession.user_name = name
        AppSession.user_role = self.role_var.get()
        
        # 로그인 창 닫고 메인 앱 실행
        self.root.destroy()
        run_main_app()


# ==========================================
# 3. [Step 2~5] 메인 라벨링 프로그램
# ==========================================
class LabelingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("교과 7 - 조각김치 이물검출 라벨링 도구")
        self.root.geometry("1400x900")

        # 전역 상태 변수
        self.image_files = []
        self.current_idx = 0
        self.annotations = []  # [(x1, y1, x2, y2, class_name)]
        self.canvas_mode = "PAN"  # "DRAW" 또는 "PAN"
        self.show_overlay = True
        
        # 캔버스 보조 변수
        self.start_x = None
        self.start_y = None
        self.current_rect = None
        self.crosshair_h = None
        self.crosshair_v = None

        # UI 생성 및 단축키 바인딩
        self.build_top_toolbar()
        self.build_main_layout()
        self.bind_shortcuts()
        self.update_session_display()

    # --------------------------------------
    # UI 생성 (상단 툴바, 캔버스, 사이드바, 하단)
    # --------------------------------------
    def build_top_toolbar(self):
        toolbar = ttk.Frame(self.root, padding=5)
        toolbar.pack(side="top", fill="x")

        ttk.Button(toolbar, text="📁 폴더 열기", command=self.open_folder).pack(side="left", padx=2)
        ttk.Button(toolbar, text="💾 저장 (Ctrl+S)", command=self.save_annotation).pack(side="left", padx=2)
        ttk.Button(toolbar, text="💾▶ 저장 후 다음", command=self.save_and_next).pack(side="left", padx=2)
        ttk.Button(toolbar, text="← 이전", command=lambda: self.navigate_image(-1)).pack(side="left", padx=2)
        ttk.Button(toolbar, text="다음 →", command=lambda: self.navigate_image(1)).pack(side="left", padx=2)
        
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=5)

        ttk.Button(toolbar, text="🔍 Fit", command=lambda: print("Zoom Fit")).pack(side="left", padx=2)
        ttk.Button(toolbar, text="🔍 Zoom +", command=lambda: print("Zoom In")).pack(side="left", padx=2)
        ttk.Button(toolbar, text="🔍 Zoom -", command=lambda: print("Zoom Out")).pack(side="left", padx=2)
        ttk.Button(toolbar, text="✋ Pan Mode", command=self.set_pan_mode).pack(side="left", padx=2)
        ttk.Button(toolbar, text="➕ Add Box", command=self.set_draw_mode).pack(side="left", padx=2)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=5)

        ttk.Button(toolbar, text="↩ Undo (Ctrl+Z)", command=lambda: print("Undo")).pack(side="left", padx=2)
        ttk.Button(toolbar, text="✅ Validation", command=self.run_validation).pack(side="left", padx=2)
        ttk.Button(toolbar, text="❓ 도움말 (F1)", command=self.show_help).pack(side="left", padx=2)

        self.lbl_progress = ttk.Label(toolbar, text="진행률: 0 / 0")
        self.lbl_progress.pack(side="right", padx=10)

    def build_main_layout(self):
        # 메인 영역 (캔버스 + 우측 패널)
        main_paned = ttk.PanedWindow(self.root, orient="horizontal")
        main_paned.pack(fill="both", expand=True)

        # [좌측] 캔버스 및 하단 썸네일 영역
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=4)

        # 캔버스 생성
        self.canvas = tk.Canvas(left_frame, bg="#2b2b2b", cursor="cross")
        self.canvas.pack(fill="both", expand=True)

        # 마우스 이벤트 연결
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)

        # [하단] 썸네일 스트립 / QA 필터
        bottom_frame = ttk.LabelFrame(left_frame, text="이미지 목록 & QA 필터", height=100)
        bottom_frame.pack(fill="x", side="bottom", padx=5, pady=5)

        filter_btn_frame = ttk.Frame(bottom_frame)
        filter_btn_frame.pack(side="left", padx=5)
        ttk.Button(filter_btn_frame, text="전체 보기", command=lambda: self.apply_filter("ALL")).pack(anchor="w")
        ttk.Button(filter_btn_frame, text="REVIEW만 보기", command=lambda: self.apply_filter("REVIEW")).pack(anchor="w")
        ttk.Button(filter_btn_frame, text="EDITED만 보기", command=lambda: self.apply_filter("EDITED")).pack(anchor="w")

        # [우측] 사이드바 패널
        right_frame = ttk.Frame(main_paned, width=320)
        main_paned.add(right_frame, weight=1)

        # 1. 클래스 선택
        cls_frame = ttk.LabelFrame(right_frame, text="클래스 선택")
        cls_frame.pack(fill="x", padx=5, pady=5)
        self.classes = ["0 나뭇잎·종이류", "1 플라스틱류·돌·금속류", "2 나뭇가지류", "3 벌레류", "4 고무장갑", "5 병해·갈변", "6 파·고추"]
        self.cbo_class = ttk.Combobox(cls_frame, values=self.classes, state="readonly")
        self.cbo_class.current(2)
        self.cbo_class.pack(fill="x", padx=5, pady=5)

        # 2. 라벨 목록 표 (Treeview)
        list_frame = ttk.LabelFrame(right_frame, text="라벨 목록")
        list_frame.pack(fill="both", expand=True, padx=5, pady=5)

        cols = ("No", "클래스", "위치(x,y,w,h)")
        self.tree_labels = ttk.Treeview(list_frame, columns=cols, show="headings", height=6)
        for col in cols:
            self.tree_labels.heading(col, text=col)
            self.tree_labels.column(col, width=80)
        self.tree_labels.pack(fill="both", expand=True)

        # 3. 검수 상태 및 작업자 정보
        meta_frame = ttk.LabelFrame(right_frame, text="검수 & 작업자 정보")
        meta_frame.pack(fill="x", padx=5, pady=5)

        self.qa_status_var = tk.StringVar(value="EDITED")
        for status in ["PASS", "EDITED", "REVIEW", "REVIEWED"]:
            ttk.Radiobutton(meta_frame, text=status, value=status, variable=self.qa_status_var).pack(anchor="w", padx=5)

        self.lbl_worker_info = ttk.Label(meta_frame, text="작업자: - | 검수자: -")
        self.lbl_worker_info.pack(pady=5)

        # 4. Issue / Note
        note_frame = ttk.LabelFrame(right_frame, text="Issue / Note")
        note_frame.pack(fill="x", padx=5, pady=5)
        self.txt_note = tk.Text(note_frame, height=3)
        self.txt_note.pack(fill="x", padx=5, pady=5)

    # --------------------------------------
    # 단축키 바인딩 (Shortcut Manager)
    # --------------------------------------
    def bind_shortcuts(self):
        self.root.bind("<Control-s>", lambda e: self.save_annotation())
        self.root.bind("<Control-S>", lambda e: self.save_annotation())
        self.root.bind("<Left>", lambda e: self.navigate_image(-1))
        self.root.bind("<Right>", lambda e: self.navigate_image(1))
        self.root.bind("<Control-t>", lambda e: self.toggle_overlay())
        self.root.bind("<Control-T>", lambda e: self.toggle_overlay())
        self.root.bind("<Delete>", lambda e: self.delete_selected_label())
        self.root.bind("<F1>", lambda e: self.show_help())

        # Ctrl + 숫자키 (1~7) 바인딩
        for i in range(1, 8):
            self.root.bind(f"<Control-Key-{i}>", lambda e, idx=i-1: self.quick_set_class(idx))

    # --------------------------------------
    # 로직 및 이벤트 핸들러
    # --------------------------------------
    def update_session_display(self):
        if AppSession.user_role == "작업자":
            self.lbl_worker_info.config(text=f"작업자: {AppSession.user_name} | 검수자: (미검수)")
        else:
            self.lbl_worker_info.config(text=f"작업자: (기존값) | 검수자: {AppSession.user_name}")

    def open_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            valid_exts = (".png", ".jpg", ".jpeg", ".bmp")
            self.image_files = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(valid_exts)]
            self.image_files.sort()
            
            if self.image_files:
                self.current_idx = 0
                self.load_current_image()
            else:
                messagebox.showinfo("알림", "선택한 폴더에 이미지 파일이 없습니다.")

    def load_current_image(self):
        if not self.image_files:
            return
        
        path = self.image_files[self.current_idx]
        self.lbl_progress.config(text=f"진행률: {self.current_idx + 1} / {len(self.image_files)}")
        
        # 이미지 렌더링
        img = Image.open(path)
        img.thumbnail((900, 600))
        self.tk_img = ImageTk.PhotoImage(img)
        
        self.canvas.delete("all")
        self.canvas.create_image(10, 10, anchor="nw", image=self.tk_img)
        self.annotations.clear()
        self.refresh_treeview()

    def set_draw_mode(self):
        self.canvas_mode = "DRAW"
        self.canvas.config(cursor="cross")

    def set_pan_mode(self):
        self.canvas_mode = "PAN"
        self.canvas.config(cursor="fleur")

    def on_mouse_move(self, event):
        if self.show_overlay:
            self.canvas.delete("crosshair")
            w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
            self.canvas.create_line(0, event.y, w, event.y, fill="yellow", dash=(2, 2), tags="crosshair")
            self.canvas.create_line(event.x, 0, event.x, h, fill="yellow", dash=(2, 2), tags="crosshair")

    def on_mouse_down(self, event):
        if self.canvas_mode == "DRAW":
            self.start_x = event.x
            self.start_y = event.y
            self.current_rect = self.canvas.create_rectangle(
                self.start_x, self.start_y, event.x, event.y, outline="red", width=2, tags="bbox"
            )

    def on_mouse_drag(self, event):
        if self.canvas_mode == "DRAW" and self.current_rect:
            self.canvas.coords(self.current_rect, self.start_x, self.start_y, event.x, event.y)

    def on_mouse_up(self, event):
        if self.canvas_mode == "DRAW" and self.current_rect:
            x1, y1, x2, y2 = self.start_x, self.start_y, event.x, event.y
            x, y = min(x1, x2), min(y1, y2)
            w, h = abs(x2 - x1), abs(y2 - y1)
            
            if w > 5 and h > 5: # 너무 작은 박스 방지
                selected_cls = self.cbo_class.get()
                self.annotations.append((x, y, w, h, selected_cls))
                self.refresh_treeview()
            else:
                self.canvas.delete(self.current_rect)
            
            self.current_rect = None
            self.set_pan_mode() # BBox 생성 완료 후 이동 모드로 전환

    def refresh_treeview(self):
        for item in self.tree_labels.get_children():
            self.tree_labels.delete(item)
        for idx, (x, y, w, h, cls) in enumerate(self.annotations, 1):
            self.tree_labels.insert("", "end", values=(idx, cls, f"[{x}, {y}, {w}, {h}]"))

    def delete_selected_label(self):
        selected = self.tree_labels.selection()
        if selected:
            idx = self.tree_labels.index(selected[0])
            del self.annotations[idx]
            self.refresh_treeview()
            # 캔버스 재시작
            self.load_current_image()

    def navigate_image(self, delta):
        if not self.image_files:
            return
        new_idx = self.current_idx + delta
        if 0 <= new_idx < len(self.image_files):
            self.current_idx = new_idx
            self.load_current_image()

    def save_annotation(self):
        if not self.image_files:
            return
        curr_file = os.path.basename(self.image_files[self.current_idx])
        note = self.txt_note.get("1.0", "end-1c").strip()
        status = self.qa_status_var.get()
        
        # 실제 환경에서는 파일/DB 저장 로직 작성
        messagebox.showinfo("저장 완료", f"[{curr_file}]\n작업자: {AppSession.user_name}\n상태: {status}\n라벨 수: {len(self.annotations)}개 저장되었습니다.")

    def save_and_next(self):
        self.save_annotation()
        self.navigate_image(1)

    def toggle_overlay(self):
        self.show_overlay = not self.show_overlay
        if not self.show_overlay:
            self.canvas.delete("crosshair")

    def quick_set_class(self, idx):
        if idx < len(self.classes):
            self.cbo_class.current(idx)

    def run_validation(self):
        if not self.annotations:
            messagebox.showwarning("Validation 경고", "현재 이미지에 라벨링된 바운딩 박스가 없습니다.")
        else:
            messagebox.showinfo("Validation 성공", "오류가 발견되지 않았습니다.")

    def apply_filter(self, filter_type):
        messagebox.showinfo("필터 적용", f"'{filter_type}' 조건으로 리스트를 필터링합니다.")

    def show_help(self):
        help_text = (
            "단축키 안내:\n"
            "- Ctrl + S : 현재 작업 저장\n"
            "- ← / → : 이전 / 다음 이미지 이동\n"
            "- Ctrl + T : 커서 십자선 오버레이 On/Off\n"
            "- Ctrl + 1~7 : 클래스 빠른 선택\n"
            "- Delete : 선택한 라벨 박스 삭제\n"
            "- F1 : 도움말 창 표시"
        )
        messagebox.showinfo("도움말 및 단축키 안내", help_text)


# ==========================================
# 4. 엔트리 포인트 (실행 시작)
# ==========================================
def run_main_app():
    app_root = tk.Tk()
    app = LabelingApp(app_root)
    app_root.mainloop()

if __name__ == "__main__":
    login_root = tk.Tk()
    login_app = LoginWindow(login_root)
    login_root.mainloop()