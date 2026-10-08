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
        if self.role not in C.REVIEW_ROLES or self.ws is None:
            self.cr_lbl.configure(text="")
            return
        # 원본 폴더: 저장된 검수/작업 기록은 표시하지 않음 (단, 라벨 완료 목록에서 저장 결과를 보는 중이면 표시)
        if not (self.ws.is_result_folder or getattr(self, "viewing_result", None)):
            self.cr_lbl.configure(text="원본 폴더 (저장된 작업 결과는 표시하지 않음)\n"
                                       "작업 결과 검수는 작업자/ 폴더를 열어서 진행")
            return
        if self.role == C.ROLE_REVIEWER2:             # 2차 검수자: 1차 검수 결과 안내
            m1, m2 = self.ws.reviewer_store.get(name), self.ws.reviewer2_store.get(name)
            if m2:
                self.cr_lbl.configure(text=f"2차 검수 완료: {m2.status}")
            elif m1:
                note = (m1.note or "").strip().replace("\n", " ")
                note = (" · " + (note if len(note) <= 30 else note[:30] + "…")) if note else ""
                self.cr_lbl.configure(text=f"1차 검수: {m1.status} ({m1.reviewer}){note}\n"
                                           "정상 → REVIEWED / 정상(라벨 문제없음) → PASS / 수정 → EDITED")
            else:
                self.cr_lbl.configure(text="1차 검수 기록 없음 — 1차 검수 후 진행하세요")
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
                                   "→ 2차 검수자가 확인 (REVIEWED / PASS / EDITED)")
        self.set_message(f"[Cross Review 대상] {', '.join(reasons)}{who} · 2차 검수자 확인 대상")

    def _check_review_rules(self, name):
        """검수 규칙 위반 시 안내 문구, 통과하면 None (검수자 · 2차 검수자가 저장할 때)
            공통      : 내 역할이 쓸 수 없는 상태는 저장 불가 (검수자 REVIEWED ✕, 2차 검수자 REVIEW ✕)
            PASS      : 박스를 고쳤거나 Class 4 가 있으면 불가
            EDITED    : 고친 게 하나도 없으면 불가 (이슈 노트는 없어도 저장 가능)
            REVIEW    : (검수자) 애매한 점을 Issue/Note 에 기록 필수
            REVIEWED  : (2차 검수자) 1차 검수 기록이 있어야 함, 고쳤으면 EDITED,
                        Class 4 가 남아 있으면 불가, 1차 검수자 본인은 불가"""
        status = self.status_var.get()
        note = self.note.get("1.0", "end-1c").strip()
        classes = [b.cls for b in self.boxes]
        has_unused = any(c in C.UNUSED_CLASSES for c in classes)
        prev = self.ws.reviewer_store.get(name)          # 1차 검수 기록

        allowed = C.ROLE_STATUSES.get(self.role, ())
        if status not in allowed:
            return (f"{C.ROLE_LABELS[self.role]}은(는) {status} 를 선택할 수 없습니다.\n"
                    f"→ 선택 가능: {' / '.join(allowed)}")

        if status == "PASS":
            if self.boxes_changed:
                return ("BBox/Class를 수정했으므로 PASS가 아닙니다.\n"
                        "→ EDITED로 저장하세요.")
            if has_unused:
                return ("Class 4(사용 안 함)가 있어 PASS할 수 없습니다.\n"
                        "→ 올바른 Class로 수정해서 EDITED로 저장하세요.")

        elif status == "EDITED":
            own_prev = self.ws.own_meta(name)
            if not self.boxes_changed and not (
                    (own_prev and own_prev.status == "EDITED") or (prev and prev.status == "EDITED")):
                return ("수정한 BBox/Class가 없습니다.\n"
                        "→ 라벨이 정상이면 PASS" + (" 또는 REVIEWED" if self.role == C.ROLE_REVIEWER2 else "")
                        + " 로 저장하세요.")

        elif status == "REVIEW":
            if not note:
                return ("REVIEW는 추측하지 않고 다른 작업자와 재확인하는 단계입니다.\n"
                        "→ Issue/Note에 무엇이 애매한지 기록하세요.")

        elif status == "REVIEWED":
            if not prev:
                return ("REVIEWED는 1차 검수 결과를 확인하는 상태입니다.\n"
                        "이 이미지에는 1차 검수 기록이 없습니다. → 1차 검수 후 진행하세요.")
            if self.boxes_changed:
                return ("2차 검수 중 수정했다면 REVIEWED가 아닙니다.\n"
                        "→ EDITED로 저장하세요.")
            if has_unused:
                return "Class 4가 남아 있어 REVIEWED할 수 없습니다. → 수정 후 EDITED로 저장하세요."
            if prev.reviewer and prev.reviewer == self.user_name:
                return (f"이 이미지는 {self.user_name}님이 1차 검수({prev.status})를 했습니다.\n"
                        "2차 검수는 다른 사람이 확인해야 합니다.")
        return None

    def _on_meta_var_changed(self, *_):
        """검수 상태 / Scene Type 변경 → 미저장 표시 + CSV 정보 갱신
        검수 상태를 REVIEW → PASS 로 바꾸면 이슈 노트를 비움 (REVIEW 때 적은 애매한 점은 PASS 에 맞지 않음)"""
        new_status = self.status_var.get()
        old_status = getattr(self, "_prev_status", "")
        self._prev_status = new_status               # 이미지 로드 중에 바뀐 값도 기억해 둠
        if self._loading or self.cur < 0:
            return
        if self.scene_var.get():                     # 사용자가 고른 Scene Type → 다음 이미지에서 유지
            self._last_scene = self.scene_var.get()
        if (old_status == "REVIEW" and new_status == "PASS"
                and self.note.get("1.0", "end-1c").strip()):
            self.note.delete("1.0", "end")
            self.set_message("REVIEW → PASS 로 변경: 이슈 노트를 비웠습니다. (Ctrl+Z 로는 복구되지 않음)")
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
        elif self.role in C.REVIEW_ROLES:
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
