"""[카테고리] 로그아웃 — 메인 화면을 정리하고 로그인 화면으로 돌아간다.
(로그인 화면 자체는 src/auth/login.py)

의사 코드
    logout():
        미저장 변경 있으면 maybe_save(), 없으면 '로그아웃할까요?' 확인
        teardown() → on_logout(이름, 역할) 콜백 → src/auth/login.py 의 show_login 이 로그인 화면 표시
    teardown():
        root에 연결한 단축키 해제 → 모든 위젯 삭제 → 창 설정 초기화
"""
from tkinter import messagebox


class SessionMixin:
    """로그아웃 기능 (LabelingApp에 섞여 들어감 — self는 LabelingApp)"""

    def logout(self):
        """로그아웃: 미저장 확인(또는 확인 창) → 메인 화면 정리 → 로그인 화면으로 복귀(on_logout 콜백)"""
        if self.dirty and self.warn_unsaved.get():
            if not self.maybe_save():          # 저장/버리기/취소 선택
                return
        elif not messagebox.askyesno("로그아웃", f"{self.user_name}님, 로그아웃할까요?",
                                     parent=self.root):
            return
        self.teardown()
        if self.on_logout:
            self.on_logout(self.user_name, self.role)

    def teardown(self):
        """메인 창의 위젯·단축키를 모두 정리 (root 창은 유지)"""
        r = self.root
        for seq in self._bound:
            r.unbind(seq)
        self._bound.clear()
        for w in r.winfo_children():
            w.destroy()
        r.protocol("WM_DELETE_WINDOW", r.destroy)
        r.minsize(1, 1)
        for i in range(3):                     # grid 설정 초기화
            r.rowconfigure(i, weight=0)
        r.columnconfigure(0, weight=0)
