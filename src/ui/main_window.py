"""[카테고리] 메인 창 본체 — LabelingApp 클래스

LabelingApp 은 기능별 Mixin 을 조합해서 만든다. 기능을 찾을 때는 아래 표를 보면 된다.

    파일                                   Mixin             담당 기능
    src/ui/layout.py                       LayoutMixin       화면 배치 (툴바, 캔버스, 오른쪽 패널, 상태바)
    src/ui/shortcuts.py                    ShortcutMixin     단축키
    src/ui/file_actions.py                 LoadSaveMixin     폴더 열기, 이미지 로드, 저장, 미저장 경고
    src/ui/navigation.py                   NavigationMixin   이전 / 다음 / 특정 이미지 이동
    src/ui/panels.py                       PanelMixin        라벨 목록 표, 완료 목록, 진행률, CSV 정보 갱신
    src/bbox/bbox_manager.py               BoxEditMixin      BBox 추가·미확정·이동·삭제·Undo·선택
                                           ClassMixin        클래스 선택 / 변경
    src/review/review_rules.py             ReviewMixin       검수 규칙(6.2), Cross Review(6.3)
    src/review/review_filters.py           FilterMixin       REVIEW / EDITED / Cross Review 필터
    src/validation/validation_dialog.py    ValidationMixin   Validation 결과 창
    src/auth/logout.py                     SessionMixin      로그아웃

이 파일에는 상태 변수 초기화(__init__)와 여러 기능이 같이 쓰는 공통 함수만 둔다.

주요 상태 변수 (self.xxx)
    folder / image_names / cur      열린 폴더, 이미지 이름 목록, 현재 이미지 인덱스
    view_indices / filter_mode      필터 적용 후 보여줄 인덱스 목록, 현재 필터
    image / img_w / img_h           현재 이미지(PIL)와 크기
    boxes / selected                현재 이미지의 BBox 목록(원본 픽셀 좌표), 선택 인덱스
    undo                            Undo 스택
    ws                              Workspace — 역할별 저장 폴더·CSV 관리 (src/review/workspace.py)
    dirty / boxes_changed           미저장 여부, 이번에 BBox를 고쳤는지 (검수 규칙 판정용)
    status_var / scene_var          검수 상태, Scene Type (라디오 버튼과 연결)
"""
import tkinter as tk

from src import config as C
from src.auth.logout import SessionMixin
from src.bbox.bbox_manager import BoxEditMixin, ClassMixin
from src.bbox.bbox_model import Box, UndoStack
from src.review.review_filters import FilterMixin
from src.review.review_rules import ReviewMixin
from src.ui.file_actions import LoadSaveMixin
from src.ui.layout import LayoutMixin
from src.ui.navigation import NavigationMixin
from src.ui.panels import PanelMixin
from src.ui.shortcuts import ShortcutMixin
from src.validation.validation_dialog import ValidationMixin


class LabelingApp(LayoutMixin, ShortcutMixin, LoadSaveMixin, NavigationMixin, BoxEditMixin, ClassMixin, ReviewMixin, FilterMixin, PanelMixin, ValidationMixin, SessionMixin):
    """조각김치 이물검출 라벨링 메인 창"""

    # ============================================================ 초기화
    def __init__(self, root: tk.Tk, user_name: str, role: str, on_logout=None):
        """앱 상태 변수 초기화 → 화면 구성 → 단축키 연결 → 초기 화면 표시"""
        self.root = root
        self.user_name = user_name
        self.role = role
        self.on_logout = on_logout      # 로그아웃 후 로그인 화면을 띄우는 콜백
        self._bound: list[str] = []     # 로그아웃 시 해제할 root 단축키

        # ---- 작업 상태
        self.folder = None
        self.image_names: list[str] = []
        self.view_indices: list[int] = []    # 필터 적용된 이미지 인덱스
        self.filter_mode = None              # None / "REVIEW" / "EDITED" / "CROSS"(Cross Review 대상)
        self.cur = -1
        self.image = None
        self.img_w = self.img_h = 0
        self.boxes: list[Box] = []
        self.selected = None
        self.undo = UndoStack(C.UNDO_LIMIT)
        self.ws = None            # Workspace: 역할별 저장 폴더 / CSV 관리
        self.dirty = False
        self._loading = False
        self.boxes_changed = False     # 이번에 연 뒤 BBox/Class를 수정했는지 (PASS/REVIEWED 판정용)
        self._loaded_note = ""         # EDITED 저장 시 '수정 이유 기록' 확인용

        self.current_class = tk.IntVar(value=C.ENABLED_CLASSES[0])
        self.status_var = tk.StringVar()
        self.scene_var = tk.StringVar()
        self.assignee_var = tk.StringVar()
        self.reviewer_var = tk.StringVar()
        self.reviewer2_var = tk.StringVar()      # 2차 검수자 이름
        self.warn_unsaved = tk.BooleanVar(value=True)

        self._build_window()
        self._bind_shortcuts()
        self.status_var.trace_add("write", self._on_meta_var_changed)
        self.scene_var.trace_add("write", self._on_meta_var_changed)

        self._fill_user_fields(None)
        self.set_mode("draw")
        self.set_class(self.current_class.get(), from_user=False)
        self.refresh_all()
        self.view.canvas.focus_set()
        self.set_message("폴더 열기(Ctrl+O)로 작업할 이미지 폴더를 선택하세요.")

    # ============================================================ 공통 함수
    def set_message(self, text: str, level: str = "info"):
        """하단 상태바에 안내 문구 표시 (level: info / error / success → 색상)"""
        color = {"info": C.COLOR_MUTED, "error": C.COLOR_DANGER,
                 "success": C.COLOR_SUCCESS}.get(level, C.COLOR_MUTED)
        self.msg_lbl.configure(text=text, fg=color)

    def _set_dirty(self, value: bool):
        """미저장 여부 표시 갱신 (상태바 '● 미저장 변경사항', 창 제목 끝 '*')"""
        self.dirty = value
        self.dirty_lbl.configure(text="● 미저장 변경사항" if value else "")
        self.root.title(C.APP_TITLE + (" *" if value else ""))

    def set_mode(self, mode: str):
        """마우스 모드 전환(draw 그리기 / select 선택·이동 / pan 화면이동) + 툴바 버튼 강조"""
        self.view.set_mode(mode)
        for m, b in (("draw", self.draw_btn), ("select", self.select_btn), ("pan", self.pan_btn)):
            b.configure(style="ToolActive.TButton" if m == mode else "Tool.TButton")

    def toggle_overlay(self):
        """BBox 정보 HUD 표시/숨김 (Ctrl+T)"""
        shown = self.view.toggle_overlay()
        self.set_message(f"BBox 정보 HUD {'표시' if shown else '숨김'} (Ctrl+T)")
