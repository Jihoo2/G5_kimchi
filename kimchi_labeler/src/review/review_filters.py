"""[카테고리] 필터 / QA — REVIEW만 / EDITED만 / Cross Review 대상만 보기

의사 코드
    set_filter(mode):
        같은 버튼이면 해제, 해당 이미지가 없으면 안내
        view_indices 다시 계산 → 현재 이미지가 목록에 없으면 첫 이미지로 이동
    _match_filter(name, mode):
        CROSS → Workspace.cross_review_reasons(name)가 있으면 대상
        그 외 → 표시용 상태(effective_meta)가 mode와 같으면 대상
"""
from tkinter import messagebox


class FilterMixin:
    """필터 기능 (LabelingApp에 섞여 들어감 — self는 LabelingApp)"""

    def set_filter(self, mode: str):
        """REVIEW / EDITED / Cross Review 대상 필터 켜기·끄기 (같은 버튼 다시 누르면 해제)"""
        if not self.ws:
            self.set_message("먼저 폴더를 여세요.", "error")
            return
        new = None if self.filter_mode == mode else mode
        if new and not any(self._match_filter(n, new) for n in self.image_names):
            messagebox.showinfo("필터", f"{self._filter_label(new)} 이미지가 없습니다.", parent=self.root)
            return
        self.filter_mode = new
        self._apply_filter_list()
        if self.view_indices and self.cur not in self.view_indices:
            self.goto(self.view_indices[0])
        self.refresh_all()
        self.set_message(f"{self._filter_label(new)}만 보기" if new else "전체 이미지 보기")

    @staticmethod
    def _filter_label(mode):
        """필터 이름을 화면 표시용 문자열로"""
        return "Cross Review 대상" if mode == "CROSS" else (mode or "")

    def _match_filter(self, name, mode) -> bool:
        """이미지가 필터 조건에 맞는지 판단"""
        if mode == "CROSS":
            return bool(self.ws.cross_review_reasons(name))
        m = self.ws.effective_meta(name)
        return bool(m) and m.status == mode

    def _apply_filter_list(self):
        """필터 조건으로 view_indices(화면에 보여줄 이미지 인덱스 목록) 계산"""
        if self.filter_mode and self.ws:
            idxs = [i for i, n in enumerate(self.image_names)
                    if self._match_filter(n, self.filter_mode)]
            if idxs:
                self.view_indices = idxs
                return
            self.filter_mode = None
        self.view_indices = list(range(len(self.image_names)))
