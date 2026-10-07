"""[카테고리] BBox 관리 — 박스 추가 · 미확정/확정 · 이동 · 삭제 · Undo · 선택 · Class 지정
(마우스 처리는 src/ui/canvas.py, 여기는 '박스 데이터를 바꾸는' 부분)

의사 코드
    add_box(박스):                드래그로 그린 박스
        Undo 저장 → 현재 Class 지정 → '미확정'으로 추가 → 선택
    confirm_pending():  Enter    미확정 해제
    cancel_pending():   Esc      미확정 박스 삭제
    nudge_selected(dx, dy):      방향키로 선택 박스 이동 (이미지 밖으로 못 나감)
    resize_selected(방향, grow): Ctrl+방향키 그 방향으로 늘림 / Alt+방향키 그 방향 변을 안쪽으로 (0.0005씩)
    delete_selected():  Delete   선택 박스 삭제
    undo_action():      Ctrl+Z   Undo 스택에서 이전 박스 목록 복원
    redo_action():      Ctrl+Shift+Z / Ctrl+Y   Undo 했던 변경 다시 실행 (새로 수정하면 Redo 기록은 사라짐)
    update_box_from_overlay():   HUD 수정 패널 입력값으로 박스 수정
    select_box(idx):             미확정 박스가 있으면 그 박스만 선택 가능
    select_next_box(step):       Tab 다음 박스 / Shift+Tab 이전 박스 (끝에서 처음으로 순환)
    _after_boxes_changed():      (위 모든 변경 뒤 공통)
        미저장 표시 → 상태가 비었거나 PASS/REVIEWED면 EDITED로 → 화면 갱신

    set_class(cid, from_user):   (ClassMixin)
        사용 안 하는 Class(4)면 안내 후 중단
        현재 Class 갱신 → 드롭다운·클래스 목록 강조
        사용자가 직접 바꿨고 선택 박스가 있으면 → 그 박스의 Class 변경 (Undo 저장)
"""
from src import config as C
from src.bbox.bbox_model import Box


class BoxEditMixin:
    """BBox 편집 기능 (LabelingApp에 섞여 들어감 — self는 LabelingApp)"""

    def push_undo(self):
        """현재 BBox 목록을 Undo 스택에 저장 (BBox를 바꾸기 직전에 호출)"""
        self.undo.push(self.boxes)

    def add_box(self, box: Box):
        """드래그로 그린 새 BBox 추가 → '미확정' 상태로 선택 (Enter 확정 / Esc 취소)"""
        self.push_undo()
        box.cls = self.current_class.get()
        box.state = "new"
        box.pending = True
        self.boxes.append(box)
        self.selected = len(self.boxes) - 1
        self._after_boxes_changed()
        self.set_message("미확정 BBox: 박스 안을 드래그해 이동, 모서리·테두리로 크기 조절, 방향키로 미세 이동, "
                         "숫자키로 Class 변경 → Enter 확정 / Esc 취소")

    def pending_index(self):
        """미확정 BBox의 인덱스 (없으면 None)"""
        return next((i for i, b in enumerate(self.boxes) if b.pending), None)

    def confirm_pending(self):
        """미확정 BBox 확정 (Enter)"""
        idx = self.pending_index()
        if idx is None:
            return False
        b = self.boxes[idx]
        for box in self.boxes:
            box.pending = False
        self.selected = None
        self.view.draw_boxes()
        self.refresh_table()
        self.view.overlay.refresh()
        self.set_message(f"BBox 확정: {b.cls} {C.CLASS_NAMES.get(b.cls, '?')} · 다음 BBox를 그리세요",
                         "success")
        return True

    def cancel_pending(self):
        """미확정 BBox 취소·삭제 (Esc)"""
        idx = self.pending_index()
        if idx is None:
            return
        self.push_undo()
        self.boxes.pop(idx)
        self.selected = None
        self._after_boxes_changed()
        self.set_message("미확정 BBox를 취소했습니다.")

    def resize_selected(self, direction: str, grow: bool = True):
        """선택 박스의 direction 쪽 변을 RESIZE_STEP(기본 0.0005, 정규화) 만큼 바깥/안쪽으로
            Ctrl + 방향키 → grow=True  : 그 방향으로 늘어남   (예: Ctrl+→ 오른쪽 변이 오른쪽으로)
            Alt  + 방향키 → grow=False : 그 방향 변이 안쪽으로 (예: Alt+→ 오른쪽 변이 왼쪽으로)
        이미지 밖으로는 못 늘어나고, 최소 크기보다 작아지면 줄이지 않음"""
        if self.selected is None or self.image is None:
            self.set_message("크기를 바꿀 BBox를 먼저 선택하세요.", "error")
            return
        b = self.boxes[self.selected]
        W, H = self.img_w, self.img_h
        horizontal = direction in ("Left", "Right")
        d = C.RESIZE_STEP * (W if horizontal else H) * (1 if grow else -1)
        x1, y1, x2, y2 = b.x1, b.y1, b.x2, b.y2
        if direction == "Right":
            x2 = min(W, x2 + d)
        elif direction == "Left":
            x1 = max(0.0, x1 - d)
        elif direction == "Up":
            y1 = max(0.0, y1 - d)
        elif direction == "Down":
            y2 = min(H, y2 + d)
        if x2 - x1 < C.MIN_BOX_PX or y2 - y1 < C.MIN_BOX_PX:
            self.set_message("더 이상 줄일 수 없습니다 (최소 크기).", "error")
            return
        if (x1, y1, x2, y2) == (b.x1, b.y1, b.x2, b.y2):
            self.set_message("이미지 끝이라 더 늘릴 수 없습니다.", "error")
            return
        self.push_undo()
        b.x1, b.y1, b.x2, b.y2 = x1, y1, x2, y2
        self.box_changed(self.selected)
        _, _, _, w, h = b.to_yolo(W, H)
        self.set_message(f"BBox {'늘림' if grow else '줄임'} ({direction}) · W {w:.4f}  H {h:.4f}")

    def nudge_selected(self, dx, dy):
        """방향키 이동 (원본 이미지 픽셀 단위)"""
        if self.selected is None or self.image is None:
            return
        b = self.boxes[self.selected]
        dx = min(max(dx, -b.x1), self.img_w - b.x2)
        dy = min(max(dy, -b.y1), self.img_h - b.y2)
        if dx == 0 and dy == 0:
            return
        self.push_undo()
        b.x1 += dx
        b.x2 += dx
        b.y1 += dy
        b.y2 += dy
        self.box_changed(self.selected)

    def box_changed(self, idx: int):
        """BBox 이동/크기 조절이 끝난 뒤 호출: 상태를 '수정'으로 표시"""
        if 0 <= idx < len(self.boxes) and self.boxes[idx].state != "new":
            self.boxes[idx].state = "modified"
        self._after_boxes_changed()

    def delete_selected(self):
        """선택한 BBox 삭제 (Delete)"""
        if self.selected is None:
            self.set_message("삭제할 BBox를 먼저 선택하세요.", "error")
            return
        self.push_undo()
        b = self.boxes.pop(self.selected)
        self.selected = None
        self._after_boxes_changed()
        self.set_message(f"BBox 삭제: {b.cls} {C.CLASS_NAMES.get(b.cls, '?')} (Ctrl+Z로 되돌리기)")

    def undo_action(self, silent: bool = False):
        """마지막 BBox 변경 되돌리기 (Ctrl+Z)
        silent=True: 캔버스가 잘못된 조작을 자동으로 되돌릴 때 → Redo 기록을 남기지 않음"""
        snap = self.undo.pop() if silent else self.undo.undo(self.boxes)
        if snap is None:
            if not silent:
                self.set_message("되돌릴 작업이 없습니다.")
            return
        self.boxes = snap
        if self.selected is not None and self.selected >= len(self.boxes):
            self.selected = None
        self._after_boxes_changed()
        if not silent:
            self.set_message(f"Undo 완료 · 남은 Undo {len(self.undo)}개 · Redo {self.undo.redo_count}개")

    def redo_action(self):
        """Undo 했던 BBox 변경 다시 실행 (Ctrl+Shift+Z / Ctrl+Y)"""
        snap = self.undo.redo(self.boxes)
        if snap is None:
            self.set_message("다시 실행할 작업이 없습니다.")
            return
        self.boxes = snap
        if self.selected is not None and self.selected >= len(self.boxes):
            self.selected = None
        self._after_boxes_changed()
        self.set_message(f"Redo 완료 · 남은 Undo {len(self.undo)}개 · Redo {self.undo.redo_count}개")

    def update_box_from_overlay(self, cid, cx, cy, w, h):
        """HUD 편집기에서 입력한 Class / 정규화 좌표로 선택 BBox 수정"""
        if self.selected is None or self.image is None:
            return
        if cid not in C.ENABLED_CLASSES:
            self.set_message(f"{cid}번 클래스는 사용하지 않습니다.", "error")
            return
        new = Box.from_yolo(cid, cx, cy, w, h, self.img_w, self.img_h)
        if new.w < C.MIN_BOX_PX or new.h < C.MIN_BOX_PX:
            self.set_message("BBox가 너무 작습니다.", "error")
            self.view.overlay.refresh()
            return
        self.push_undo()
        b = self.boxes[self.selected]
        b.cls, b.x1, b.y1, b.x2, b.y2 = new.cls, new.x1, new.y1, new.x2, new.y2
        if b.state != "new":
            b.state = "modified"
        self.set_class(cid, from_user=False)
        self._after_boxes_changed()
        self.set_message("입력한 값으로 BBox를 수정했습니다.")

    def _after_boxes_changed(self):
        """BBox가 바뀐 뒤 공통 처리
        미저장 표시 → 상태 EDITED 자동 지정 → 캔버스·라벨 표·HUD·CSV 정보 갱신
        """
        self._set_dirty(True)
        self.boxes_changed = True
        # 수정·추가·삭제 → EDITED (Cross Review 중 오류를 고치면 '재수정' = EDITED → 다시 Review)
        if self.status_var.get() in ("", "PASS", "REVIEWED"):
            self.status_var.set("EDITED")
        self.view.draw_boxes()
        self.refresh_table()
        self.view.overlay.refresh()
        self.refresh_csv_info()

    def select_next_box(self, step: int = 1):
        """Tab: 라벨 목록 순서대로 다음 박스 선택 (마지막 다음은 처음), Shift+Tab: 이전 박스
        아무것도 선택 안 했으면 Tab → 첫 번째, Shift+Tab → 마지막"""
        n = len(self.boxes)
        if n == 0:
            self.set_message("선택할 BBox가 없습니다.")
            return
        if self.selected is None:
            idx = 0 if step > 0 else n - 1
        else:
            idx = (self.selected + step) % n
        self.select_box(idx)
        if self.selected is not None:
            b = self.boxes[self.selected]
            self.set_message(f"BBox {self.selected + 1}/{n} 선택: {b.cls} {C.CLASS_NAMES.get(b.cls, '?')}"
                             "  (Tab 다음 · Shift+Tab 이전)")

    def select_box(self, idx):
        """BBox 선택 (미확정 BBox가 있으면 다른 박스로 바꿀 수 없음)"""
        if idx is not None and not 0 <= idx < len(self.boxes):
            idx = None
        p = self.pending_index()
        if p is not None and idx != p:
            self.set_message("미확정 BBox가 있습니다. Enter로 확정하거나 Esc로 취소하세요.", "error")
            idx = p
        self.selected = idx
        if idx is not None:
            self.set_class(self.boxes[idx].cls, from_user=False)
        self.view.draw_boxes()
        self.refresh_table()
        self.view.overlay.refresh()


class ClassMixin:
    """클래스 선택 기능 (LabelingApp에 섞여 들어감 — self는 LabelingApp)"""

    def _on_class_click(self, cid: int):
        """클래스 목록 클릭 / 숫자키 → 해당 Class 지정"""
        self.set_class(cid, from_user=True)

    def _on_class_combo(self, _e=None):
        """클래스 드롭다운 선택 → 해당 Class 지정"""
        self.set_class(C.ENABLED_CLASSES[self.class_combo.current()], from_user=True)
        self.view.canvas.focus_set()

    def set_class(self, cid: int, from_user: bool = True):
        """from_user=True: 선택된 BBox가 있으면 그 Class를 변경 (숫자키/클릭)"""
        if cid not in C.ENABLED_CLASSES:
            if from_user:
                self.set_message(f"{cid}번 '{C.CLASS_NAMES.get(cid, '?')}' 클래스는 사용하지 않습니다.",
                                 "error")
            return
        self.current_class.set(cid)
        self.class_combo.current(C.ENABLED_CLASSES.index(cid))
        for c, (row, sw, lbl, key, color, enabled) in self.class_rows.items():
            active = c == cid
            bg = C.COLOR_ACCENT if active else C.COLOR_PANEL
            row.configure(bg=bg)
            lbl.configure(bg=bg, fg="white" if active else (C.COLOR_TEXT if enabled else "#A0A7B2"))
            key.configure(bg=bg, fg="white" if active else C.COLOR_MUTED)
            sw.configure(highlightbackground="white" if active else color)

        if from_user and self.selected is not None:
            b = self.boxes[self.selected]
            if b.cls != cid:
                self.push_undo()
                old = b.cls
                b.cls = cid
                if b.state != "new":
                    b.state = "modified"
                self._after_boxes_changed()
                self.set_message(f"Class 변경: {C.CLASS_NAMES[old]} → {C.CLASS_NAMES[cid]}")
