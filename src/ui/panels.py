"""[카테고리] 화면 갱신 — 파일명·진행률, 라벨 목록 표, 라벨 완료 목록, CSV 정보

의사 코드
    refresh_all():
        파일명 / 진행률 / 필터 버튼 강조
        → refresh_table → refresh_completed → refresh_csv_info → HUD → 썸네일
    refresh_table():       박스마다 [No, Class, 위치(x,y,w,h), 상태(미확정/선택됨/신규/수정)]
    refresh_completed():   내 역할 CSV에 기록된 이미지를 저장 순서대로 + 완료율 바
    refresh_csv_info():    저장될 status / assignee / reviewer / scene_type 미리보기
"""
import os

from src import config as C


class PanelMixin:
    """화면 갱신(패널) 기능 (LabelingApp에 섞여 들어감 — self는 LabelingApp)"""

    def refresh_all(self):
        """화면 전체 갱신: 파일명·진행률·필터 버튼·라벨 표·완료 목록·CSV 정보·HUD·썸네일"""
        total = len(self.image_names)
        if 0 <= self.cur < total:
            shown = getattr(self, "viewing_result", None)
            tail = f"     [저장 결과 보기: {shown}]" if shown else ""
            self.file_lbl.configure(text=f"파일 이름 :  {self.image_names[self.cur]}{tail}")
            self.pos_lbl.configure(text=f"진행률  {self.cur + 1} / {total}")
        else:
            self.file_lbl.configure(text="파일 이름 :  -")
            self.pos_lbl.configure(text="진행률  0 / 0")

        suffix = f" · {self._filter_label(self.filter_mode)}만 보기" if self.filter_mode else ""
        self.strip_card.title_lbl.configure(
            text=f"{self._folder_title()} 이미지 목록 ({len(self.view_indices)}개){suffix}")
        self.review_btn.configure(
            style="SmallActive.TButton" if self.filter_mode == "REVIEW" else "Small.TButton")
        self.edited_btn.configure(
            style="SmallActive.TButton" if self.filter_mode == "EDITED" else "Small.TButton")
        self.todo_btn.configure(
            style="SmallActive.TButton" if self.filter_mode == "TODO" else "Small.TButton")
        self.cross_btn.configure(
            style="SmallActive.TButton" if self.filter_mode == "CROSS" else "Small.TButton")

        self.refresh_table()
        self.refresh_completed()
        self.refresh_csv_info()
        self.view.overlay.refresh()
        self.thumbs.render(follow=True)

    def _folder_title(self) -> str:
        """이미지 목록 제목에 쓸 '지금 연 폴더' 이름
            결과 폴더(작업자/, 작업자/review/, 검수자/pass/ …) → 작업자/review 처럼 경로로
            그 외 → 폴더 이름 (예: 이물검출_학습데이터1)"""
        if not self.folder:
            return ""
        if self.ws is not None and self.ws.is_result_folder:
            return self.ws.rel(self.ws.src)
        return os.path.basename(os.path.normpath(self.folder))

    def refresh_table(self):
        """오른쪽 '라벨 목록' 표 다시 그리기"""
        self.tree.delete(*self.tree.get_children())
        for i, b in enumerate(self.boxes):
            if b.pending:
                state = "미확정"
            elif i == self.selected:
                state = "선택됨"
            else:
                state = {"new": "신규", "modified": "수정"}.get(b.state, "")
            self.tree.insert("", "end", iid=str(i), values=(
                i + 1, f"{b.cls} {C.CLASS_NAMES.get(b.cls, '?')}",
                f"[{round(b.x1)}, {round(b.y1)}, {round(b.w)}, {round(b.h)}]", state))
        if self.selected is not None:
            self.tree.selection_set(str(self.selected))
            self.tree.see(str(self.selected))
        self.labels_card.title_lbl.configure(text=f"라벨 목록 ({len(self.boxes)}개)")

    def _on_tree_select(self, _e=None):
        """라벨 목록 표에서 행 클릭 → 해당 BBox 선택"""
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx != self.selected:          # 사용자가 직접 클릭한 경우만
            self.select_box(idx)
            self.view.canvas.focus_set()  # 바로 숫자키/Delete 사용 가능하게

    def refresh_completed(self):
        """'라벨 완료 이미지' 목록 + 완료 진행률 바 갱신 (로그인한 역할의 폴더 기준)"""
        total = len(self.image_names)
        metas = self.ws.own_store.completed(set(self.image_names)) if self.ws else []
        self._done_names = [m.filename for m in metas]
        self.done_list.delete(0, "end")
        for k, m in enumerate(metas, 1):
            self.done_list.insert("end", f"{k:>3}.  {m.filename}   [{m.status}]")
        cur_name = self.image_names[self.cur] if 0 <= self.cur < total else None
        if cur_name in self._done_names:
            i = self._done_names.index(cur_name)
            self.done_list.selection_set(i)
            self.done_list.see(i)
        elif metas:
            self.done_list.see("end")
        self.done_count_lbl.configure(text=f"이미지 {len(metas)} / {total}")
        pct = len(metas) / total * 100 if total else 0
        self.progress["value"] = pct
        self.pct_lbl.configure(text=f"완료 {pct:.1f}%")

    def _on_done_select(self, _e=None):
        """완료 목록 클릭 → 해당 이미지의 '저장 결과'(내 역할 폴더의 이미지 + TXT) 표시"""
        sel = self.done_list.curselection()
        if not sel:
            return
        name = self._done_names[sel[0]]
        if name in self.image_names:
            self.open_result(self.image_names.index(name))
        self.refresh_completed()           # 이동이 취소된 경우 선택 복원
        self.view.canvas.focus_set()

    def refresh_csv_info(self):
        """'CSV 저장 정보' 패널 갱신 (저장될 값 미리보기)"""
        self._refresh_save_dir()
        self.csv_lbl.configure(text=(
            f"status     = {self.status_var.get() or '(저장 시 자동)'}\n"
            f"assignee   = {self.assignee_var.get() or '-'}\n"
            f"reviewer   = {self.reviewer_var.get() or '-'}\n"
            f"scene_type = {self.scene_var.get() or '(저장 시 자동)'}"))
