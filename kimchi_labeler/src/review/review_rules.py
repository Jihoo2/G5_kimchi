"""[카테고리] 검수 — 6.2 전수 검수 규칙 / 6.3 100% Cross Review

의사 코드
    _check_review_rules():  (검수자가 저장할 때)
        PASS     : 박스를 고쳤거나 Class 4가 있으면 불가
        EDITED   : 고친 게 없으면 불가 / 수정 이유(Note) 기록 필수
        REVIEW   : 애매한 점(Note) 기록 필수 — 추측하지 않고 재확인
        REVIEWED : Cross Review 대상에만, 고쳤으면 불가(→ EDITED 재수정),
                   Class 4 남아 있으면 불가, 직전 처리자 본인은 불가
    _show_cross_review_info():
        Cross Review 대상(EDITED·REVIEW였던 이미지·Class 4·Empty Label)이면 사유·처리자 표시
    _refresh_save_dir():
        현재 상태로 저장 시 폴더 안내 (예: 검수자/pass/)
"""
from src import config as C


class ReviewMixin:
    """검수 규칙 · Cross Review 기능 (LabelingApp에 섞여 들어감 — self는 LabelingApp)"""

    def _show_cross_review_info(self, name):
        """검수자 화면: Cross Review 대상이면 사유와 직전 처리자를 안내"""
        if self.role != C.ROLE_REVIEWER or self.ws is None:
            self.cr_lbl.configure(text="")
            return
        if not self.ws.is_result_folder:          # 원본 폴더: 저장된 검수/작업 기록은 표시하지 않음
            self.cr_lbl.configure(text="원본 폴더 (저장된 작업 결과는 표시하지 않음)\n"
                                       "작업 결과 검수는 작업자/ 폴더를 열어서 진행")
            return
        reasons = self.ws.cross_review_reasons(name)
        if not reasons:
            m = self.ws.reviewer_store.get(name)
            if m:
                self.cr_lbl.configure(text="")
                return
            w = self.ws.worker_store.get(name)
            if w and w.status == "REVIEW":             # 작업자가 확인을 요청한 이미지
                issue = (w.note or "").strip().replace("\n", " ")
                issue = issue if len(issue) <= 40 else issue[:40] + "…"
                self.cr_lbl.configure(text=f"작업자 REVIEW 요청 ({w.assignee}): {issue}\n"
                                           "2단계 검수 대기 (PASS / EDITED / REVIEW)")
                self.set_message(f"[작업자 REVIEW 요청] {w.assignee}: {issue}")
            else:
                self.cr_lbl.configure(text="2단계 검수 대기 (PASS / EDITED / REVIEW)")
            return
        m = self.ws.reviewer_store.get(name)
        who = f" · 처리: {m.reviewer}" if m and m.reviewer else ""
        self.cr_lbl.configure(text=f"Cross Review 대상: {', '.join(reasons)}{who}\n"
                                   "정상 → REVIEWED / 오류 → 수정 후 EDITED(재수정)")
        self.set_message(f"[Cross Review 대상] {', '.join(reasons)}{who} · "
                         "정상이면 REVIEWED, 오류면 수정 후 EDITED로 저장 → 다시 Review")

    def _check_review_rules(self, name):
        """검수 절차(6.2 / 6.3) 위반 시 안내 문구, 통과하면 None"""
        status = self.status_var.get()
        note = self.note.get("1.0", "end-1c").strip()
        classes = [b.cls for b in self.boxes]
        has_unused = any(c in C.UNUSED_CLASSES for c in classes)
        prev = self.ws.reviewer_store.get(name)          # 이번 저장 전 검수 기록

        if status == "PASS":
            if self.boxes_changed:
                return ("BBox/Class를 수정했으므로 PASS가 아닙니다.\n"
                        "→ EDITED로 저장하고 수정 이유를 Issue/Note에 기록하세요.")
            if has_unused:
                return ("Class 4(사용 안 함)가 있어 PASS할 수 없습니다.\n"
                        "→ 올바른 Class로 수정(EDITED)하거나, 애매하면 REVIEW로 저장하세요.")

        elif status == "EDITED":
            if not self.boxes_changed and not (prev and prev.status == "EDITED"):
                return ("수정한 BBox/Class가 없습니다.\n"
                        "→ 정상이면 PASS(2단계) 또는 REVIEWED(Cross Review)로 저장하세요.")
            if self.boxes_changed and (not note or note == self._loaded_note):
                return ("EDITED는 수정 이유 기록이 필수입니다.\n"
                        "→ Issue/Note에 무엇을 왜 수정했는지 적어주세요.\n"
                        "   예) 누락된 나뭇가지 1개 추가, Class 1→2 수정")

        elif status == "REVIEW":
            if not note:
                return ("REVIEW는 추측하지 않고 다른 작업자와 재확인하는 단계입니다.\n"
                        "→ Issue/Note에 무엇이 애매한지 기록하세요.")

        elif status == "REVIEWED":
            if not self.ws.cross_review_reasons(name):
                return ("REVIEWED는 Cross Review 대상(EDITED·REVIEW·Class 4·Empty Label)에만\n"
                        "사용합니다. 2단계 검수라면 PASS / EDITED / REVIEW를 선택하세요.")
            if self.boxes_changed:
                return ("Cross Review 중 수정했다면 REVIEWED가 아닙니다.\n"
                        "→ EDITED(재수정)로 저장하고 이유를 기록하면 다시 Review 대상이 됩니다.")
            if has_unused:
                return "Class 4가 남아 있어 REVIEWED할 수 없습니다. → 수정 후 EDITED로 저장하세요."
            if prev and prev.reviewer and prev.reviewer == self.user_name:
                return (f"이 이미지는 {self.user_name}님이 직접 {prev.status} 처리했습니다.\n"
                        "100% Cross Review는 다른 검수자가 확인해야 합니다.")
        return None

    def _on_meta_var_changed(self, *_):
        """검수 상태 / Scene Type 변경 → 미저장 표시 + CSV 정보 갱신"""
        if self._loading or self.cur < 0:
            return
        self._set_dirty(True)
        self.refresh_csv_info()

    def _on_note_modified(self, _e=None):
        """Issue/Note 입력 → 미저장 표시"""
        if not self.note.edit_modified():
            return
        self.note.edit_modified(False)
        if self._loading or self.cur < 0:
            return
        self._set_dirty(True)

    def _refresh_save_dir(self):
        """현재 상태로 저장했을 때의 저장 위치 안내 문구 갱신"""
        st = self.status_var.get()
        if self.ws is None:
            text = ""
        elif self.role == C.ROLE_REVIEWER:
            if st:
                with_img = C.COPY_IMAGE_REVIEWER and st not in C.REVIEWER_NO_IMAGE_STATUSES
                text = (f"저장 위치: {self.ws.rel(self.ws.target_dir(st))}/ "
                        f"({'이미지+TXT' if with_img else 'TXT만'})")
            else:
                text = "저장 전 상태 선택 필요"
        else:
            text = f"저장 위치: {self.ws.rel(self.ws.target_dir(st))}/"
            if st == "REVIEW":
                text += "\n(이미지 + 라벨 + 리뷰노트)"
        self.save_dir_lbl.configure(text=text)
