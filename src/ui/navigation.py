"""[카테고리] 이미지 이동 — 이전 / 다음 / 특정 이미지로 이동

의사 코드
    go_next() / go_prev():
        필터가 켜져 있으면 필터 목록(view_indices) 기준으로 다음/이전 찾기
        처음·마지막이면 안내만
    goto(idx):
        같은 이미지면 무시 → maybe_save() 통과 시 load_index(idx)
"""



class NavigationMixin:
    """이미지 이동 기능 (LabelingApp에 섞여 들어감 — self는 LabelingApp)"""

    def go_next(self):
        """다음 이미지로 이동 (필터가 켜져 있으면 필터 목록 기준)"""
        view = self.view_indices
        if not view:
            return
        if self.cur in view:
            pos = view.index(self.cur)
            if pos >= len(view) - 1:
                self.set_message("마지막 이미지입니다.")
                return
            target = view[pos + 1]
        else:
            target = next((i for i in view if i > self.cur), view[-1])
        self.goto(target)

    def go_prev(self):
        """이전 이미지로 이동 (필터가 켜져 있으면 필터 목록 기준)"""
        view = self.view_indices
        if not view:
            return
        if self.cur in view:
            pos = view.index(self.cur)
            if pos == 0:
                self.set_message("첫 번째 이미지입니다.")
                return
            target = view[pos - 1]
        else:
            target = next((i for i in reversed(view) if i < self.cur), view[0])
        self.goto(target)

    def goto(self, idx: int):
        """지정한 이미지로 이동 (미저장 변경이 있으면 먼저 확인)"""
        if idx == self.cur or not self.image_names:
            return
        if not self.maybe_save():
            return
        self.load_index(idx)
