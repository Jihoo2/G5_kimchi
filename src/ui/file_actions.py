"""[카테고리] 폴더 열기 · 이미지 로드 · 저장 · 미저장 경고

의사 코드
    open_folder():
        미저장 확인 → 폴더 선택 → 이미지 목록 → Workspace(역할별 저장 폴더 규칙) 생성
        내 역할 CSV에 기록이 없는 첫 이미지부터 열기
    load_index(idx):
        이미지 열기 (EXIF 회전 반영 → YOLO 좌표와 일치)
        라벨 TXT 찾기:  작업자 = 작업자/ → 원본
                        검수자 = 검수자/(pass·edited·review·reviewed) → 작업자/ → 원본
        검수 상태 / Scene / Note / 작업자·검수자 이름 표시
        Undo·선택·미저장 초기화 → Cross Review 안내 → 화면 갱신
    save():
        검수자: 상태 미선택 또는 검수 규칙 위반이면 안내 후 중단
        미확정 BBox 자동 확정
        작업자는 상태를 항상 EDITED, Scene 미선택이면 박스 유무로 자동 지정
        Workspace.save_label → 역할·상태별 폴더에 TXT 저장 (작업자는 이미지 복사본도)
        label_status.csv 기록 → 썸네일·목록 갱신
    maybe_save():   (이미지 이동·폴더 열기·종료·로그아웃 전에 호출)
        변경 없음 또는 미저장 경고 OFF → 그냥 진행
        아니면 [예: 저장 후 진행 / 아니오: 버리고 진행 / 취소: 머무름]
"""
import os

from PIL import Image, ImageOps
from tkinter import filedialog, messagebox

from src import config as C
from src.review.status_store import ImageMeta
from src.review.workspace import Workspace
from src.yolo.yolo_loader import list_images, load_yolo


class LoadSaveMixin:
    """폴더 열기 · 이미지 로드 · 저장 기능 (LabelingApp에 섞여 들어감 — self는 LabelingApp)"""

    def open_folder(self):
        """이미지 폴더 선택 → 이미지 목록·Workspace(저장 폴더 규칙) 준비 → 미완료 첫 이미지부터 열기"""
        if not self.maybe_save():
            return
        folder = filedialog.askdirectory(title="작업할 이미지 폴더 선택", parent=self.root,
                                         initialdir=self.folder or os.path.expanduser("~"))
        if not folder:
            return
        names = list_images(folder)
        if not names:
            messagebox.showwarning("이미지 없음",
                                   f"폴더에 이미지({', '.join(C.IMAGE_EXTS)})가 없습니다.",
                                   parent=self.root)
            return
        try:
            ws = Workspace(folder, self.role)
        except Exception as ex:
            messagebox.showerror("CSV 오류", f"{C.STATUS_CSV_NAME} 을(를) 읽지 못했습니다.\n{ex}",
                                 parent=self.root)
            return

        self.folder, self.image_names, self.ws = folder, names, ws
        # 작업자: 이미 저장한 이미지는 목록에서 빼고 '미완료만' 보여줌 (완료 이미지는 라벨 완료 목록에서 열기)
        self.filter_mode = "TODO" if self.role != C.ROLE_REVIEWER else None
        self._apply_filter_list()                 # 미완료가 하나도 없으면 자동으로 전체 보기
        self.thumbs.clear_cache()
        own = ws.own_store
        start = next((i for i, n in enumerate(names)
                      if not (own.get(n) and own.get(n).status)), 0)
        self.cur = -1
        self.load_index(start)
        root_name = os.path.basename(ws.root)
        todo = sum(1 for n in names if not (own.get(n) and own.get(n).status))
        view = "미완료만 표시" if self.filter_mode == "TODO" else "전체 표시"
        self.set_message(f"{len(names)}장 중 미완료 {todo}장 ({view}) · 저장 위치: {root_name}/{ws.own_dir_label}/")

    def load_index(self, idx: int):
        """idx번째 이미지 열기
        이미지 로드(EXIF 회전 반영) → 라벨 TXT 로드(역할별 우선순위) → 검수 정보 표시 → 화면 갱신
        """
        if not self.image_names:
            return
        idx = max(0, min(idx, len(self.image_names) - 1))
        self.cur = idx
        name = self.image_names[idx]
        path = os.path.join(self.folder, name)

        try:
            with Image.open(path) as im:
                # EXIF 회전을 반영해야 YOLO 좌표가 학습 시 이미지와 일치함
                self.image = ImageOps.exif_transpose(im).convert("RGB")
        except Exception as ex:
            self.image, self.img_w, self.img_h, self.boxes = None, 0, 0, []
            self.set_message(f"이미지를 열 수 없습니다: {name} ({ex})", "error")
        else:
            self.img_w, self.img_h = self.image.size
            txt, src = self.ws.resolve_label(name)
            self.boxes, errors = load_yolo(txt, self.img_w, self.img_h) if txt else ([], [])
            if errors:
                more = f" 외 {len(errors) - 1}건" if len(errors) > 1 else ""
                self.set_message(f"TXT 일부를 읽지 못했습니다: {errors[0]}{more} → Validation으로 확인",
                                 "error")
            else:
                done_at = self.ws.saved_elsewhere(name)
                if done_at:
                    self.set_message(f"{name} · 원본 모습 표시 중 (이미 {done_at}/ 에 저장됨 → "
                                     f"수정하려면 {done_at}/ 폴더를 여세요)", "error")
                else:
                    self.set_message(f"{name} · BBox {len(self.boxes)}개 불러옴 (출처: {src})")

        own = self.ws.display_own_meta(name)          # 원본 폴더면 None (저장 결과를 표시하지 않음)
        # 검수자가 처음 여는 이미지: Scene/Note는 작업자 기록을 이어받고, 검수 상태는 비워둠
        base = own or self.ws.display_meta(name)
        self._loading = True
        try:
            self.status_var.set(own.status if own else "")
            self.scene_var.set(base.scene_type if base else "")
            self.note.delete("1.0", "end")
            if base and base.note:
                self.note.insert("1.0", base.note)
            self.note.edit_modified(False)
            self._fill_user_fields(name)
        finally:
            self._loading = False

        self.selected = None
        self.undo.clear()
        self.boxes_changed = False
        self._loaded_note = self.note.get("1.0", "end-1c").strip()
        self._set_dirty(False)
        self._show_cross_review_info(name)
        self.view.set_image(self.image)
        self.refresh_all()

    def _fill_user_fields(self, name):
        """로그인한 역할 칸에는 내 이름, 다른 칸에는 상대 역할 폴더의 기록 표시"""
        if name is None or self.ws is None:
            worker_meta = reviewer_meta = None
        else:
            shown = self.ws.is_result_folder           # 원본 폴더면 다른 폴더의 이름 기록을 표시하지 않음
            worker_meta = self.ws.worker_store.get(name) if shown else None
            reviewer_meta = self.ws.reviewer_store.get(name) if shown else None
        if self.role == C.ROLE_REVIEWER:
            self.assignee_var.set(worker_meta.assignee if worker_meta else "")
            self.reviewer_var.set(self.user_name)
        else:
            self.assignee_var.set(self.user_name)
            self.reviewer_var.set(reviewer_meta.reviewer if reviewer_meta else "")

    def save(self) -> bool:
        """현재 이미지 저장
        검수 규칙 확인 → 미확정 BBox 자동 확정 → 상태/Scene 기본값 → 역할별 폴더에 TXT(+이미지 복사)
        → label_status.csv 기록 → 화면 갱신
        """
        if self.cur < 0 or self.image is None:
            self.set_message("저장할 이미지가 없습니다.", "error")
            return False
        name = self.image_names[self.cur]

        # 검수자는 검수 상태를 반드시 선택해야 저장 (PASS/REVIEW는 검수자만)
        if self.role == C.ROLE_REVIEWER and not self.status_var.get():
            messagebox.showwarning("검수 상태 선택",
                                   "검수 상태를 선택한 뒤 저장하세요.\n\n"
                                   "정상 → PASS\n오류 수정 → EDITED (수정 이유 기록)\n"
                                   "애매함 → REVIEW (추측하지 않음)\n"
                                   "Cross Review 정상 → REVIEWED",
                                   parent=self.root)
            return False

        # 작업자 REVIEW: 이슈 내용 기록 필수 (검수자가 보고 판단할 수 있도록)
        if (self.role != C.ROLE_REVIEWER and self.status_var.get() == "REVIEW"
                and not self.note.get("1.0", "end-1c").strip()):
            msg = ("REVIEW는 검수자에게 확인을 요청하는 상태입니다.\n"
                   "→ Issue/Note에 어떤 점이 애매하거나 문제인지 적어주세요.\n"
                   "   예) 나뭇가지인지 파 줄기인지 구분이 어려움")
            messagebox.showwarning("작업 이슈 기록", msg, parent=self.root)
            self.set_message(msg.split("\n")[0], "error")
            return False

        if self.role == C.ROLE_REVIEWER:
            problem = self._check_review_rules(name)
            if problem:
                messagebox.showwarning("검수 규칙", problem, parent=self.root)
                self.set_message(problem.split("\n")[0], "error")
                return False

        # 원본 폴더에서 이미 저장한 이미지를 다시 저장하면 이전 작업을 덮어씀 → 확인
        done_at = self.ws.saved_elsewhere(name)
        if done_at and not messagebox.askyesno(
                "이미 저장된 이미지",
                f"'{name}' 은(는) 이미 {done_at}/ 에 저장되어 있습니다.\n"
                "지금 화면은 원본 폴더의 모습이라, 저장하면 이전 작업을 덮어씁니다.\n\n"
                f"이전 작업을 고치려면 {done_at}/ 폴더를 열어서 수정하세요.\n"
                "그래도 지금 내용으로 덮어쓸까요?",
                parent=self.root):
            self.set_message(f"저장 취소 · 이전 작업은 {done_at}/ 폴더에서 수정하세요.", "error")
            return False

        # 다른 이미지 폴더의 같은 이름 결과가 저장 폴더에 있으면 덮어쓰기 전에 확인
        other = self.ws.overwrite_conflict(name)
        if other is not None and not messagebox.askyesno(
                "같은 이름의 다른 결과",
                f"'{name}' 이름으로 저장된 다른 이미지 폴더의 결과가 있습니다.\n"
                f"  기존 결과의 이미지 폴더: {other or '(기록 없음)'}\n"
                f"  지금 연 이미지 폴더   : {self.ws.dataset}\n\n"
                "저장하면 기존 결과를 덮어씁니다. 계속할까요?",
                parent=self.root):
            self.set_message("저장을 취소했습니다. (다른 폴더의 같은 이름 결과 보존)", "error")
            return False

        auto_confirmed = self.pending_index() is not None
        if auto_confirmed:
            for b in self.boxes:
                b.pending = False
            self.selected = None

        self._loading = True    # 기본값 채울 때 dirty 트리거 방지
        if self.role != C.ROLE_REVIEWER and self.status_var.get() not in C.WORKER_STATUSES:
            self.status_var.set("EDITED")      # 작업자: REVIEW를 고르지 않았으면 EDITED
        if not self.scene_var.get():
            self.scene_var.set("kimchi_with_target" if self.boxes else "normal_kimchi")
        self._loading = False

        meta = ImageMeta(filename=name, status=self.status_var.get(),
                         assignee=self.assignee_var.get(), reviewer=self.reviewer_var.get(),
                         scene_type=self.scene_var.get(),
                         note=self.note.get("1.0", "end-1c").strip(),
                         num_boxes=len(self.boxes))
        try:
            saved = self.ws.save_label(name, self.boxes, self.img_w, self.img_h, meta.status)
            self.ws.own_store.update(meta)
            note_path = self.ws.save_issue_note(meta) if self.role != C.ROLE_REVIEWER else None
        except OSError as ex:
            messagebox.showerror("저장 실패", f"{name}\n{ex}", parent=self.root)
            return False

        for b in self.boxes:
            b.state = ""
        self.boxes_changed = False
        self._loaded_note = meta.note
        self._set_dirty(False)
        self._show_cross_review_info(name)
        self.thumbs.invalidate(self.cur)
        if self.filter_mode:
            self._apply_filter_list()
        self.refresh_all()
        extra = " (미확정 BBox 자동 확정)" if auto_confirmed else ""
        self.set_message(f"저장 완료: {self.ws.rel(saved)} · BBox {len(self.boxes)}개 · "
                         f"{meta.status}{extra}"
                         + (f" · 이슈노트: {self.ws.rel(note_path)}" if note_path else ""), "success")
        return True

    def save_and_next(self):
        """저장에 성공하면 다음 이미지로 이동 (Ctrl+Enter)"""
        if self.save():
            self.go_next()

    def maybe_save(self) -> bool:
        """이동 전 호출. True면 진행, False면 머무름"""
        if not self.dirty or not self.warn_unsaved.get():
            return True
        ans = messagebox.askyesnocancel(
            "미저장 경고",
            f"'{self.image_names[self.cur]}' 의 변경사항이 저장되지 않았습니다.\n\n"
            "예: 저장 후 이동\n아니오: 저장하지 않고 이동\n취소: 머무르기",
            parent=self.root)
        if ans is None:
            return False
        return self.save() if ans else True

    def on_close(self):
        """창 닫기(X): 미저장 확인 후 프로그램 종료"""
        if self.maybe_save():
            self.root.destroy()

    def _on_warn_toggle(self):
        """미저장 경고 ON/OFF 스위치 표시 갱신"""
        on = self.warn_unsaved.get()
        self.warn_lbl.configure(text=f"미저장 경고 : {'ON' if on else 'OFF'}")
        if not on:
            self.set_message("미저장 경고 OFF: 저장하지 않고 이동하면 변경사항이 사라집니다.", "error")
