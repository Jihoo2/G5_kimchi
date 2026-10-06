"""[카테고리] 하단 이미지 목록(썸네일)

의사 코드
    render():
        화면 폭에 들어가는 개수만큼, 현재 이미지가 보이도록 시작 위치 조정
        썸네일마다: 이미지(+라벨 박스) / 현재 이미지 파란 테두리 / 상태 배지 / 파일 이름
        클릭 → app.goto(해당 이미지)
    _thumb():
        캐시에 있으면 재사용 (최대 THUMB_CACHE_MAX개, 오래된 것부터 삭제)
        JPEG 축소 디코딩(draft)으로 빠르게 로드 → 라벨 박스를 그려서 PhotoImage 생성
    invalidate():  저장 후 해당 이미지 썸네일 다시 만들기
"""
import os
from collections import OrderedDict

import tkinter as tk
from PIL import Image, ImageDraw, ImageOps, ImageTk
from tkinter import ttk

from src import config as C
from src.ui.theme import FONTS
from src.yolo.yolo_loader import parse_yolo_line


TW, TH = C.THUMB_W, C.THUMB_H


class ThumbnailStrip(tk.Frame):
    """하단 썸네일 목록 (app = LabelingApp)"""
    GAP = 12

    def __init__(self, master, app):
        """‹ › 버튼 + 캔버스 생성, 휠로 한 칸씩 이동"""
        super().__init__(master, bg=C.COLOR_PANEL)
        self.app = app
        self.start = 0
        self.cache: "OrderedDict[str, object]" = OrderedDict()

        self.prev_btn = ttk.Button(self, text="‹", width=2, style="Small.TButton",
                                   command=lambda: self.page(-1))
        self.prev_btn.pack(side="left", fill="y")
        self.next_btn = ttk.Button(self, text="›", width=2, style="Small.TButton",
                                   command=lambda: self.page(1))
        self.next_btn.pack(side="right", fill="y")
        self.canvas = tk.Canvas(self, height=TH + 30, bg=C.COLOR_PANEL, highlightthickness=0)
        self.canvas.pack(side="left", fill="x", expand=True, padx=4)
        self.canvas.bind("<Configure>", lambda e: self.render(follow=False))
        self.canvas.bind("<Button-4>", lambda e: self.shift(-1))
        self.canvas.bind("<Button-5>", lambda e: self.shift(1))
        self.canvas.bind("<MouseWheel>", lambda e: self.shift(-1 if e.delta > 0 else 1))

    # ------------------------------------------------------------
    def slots(self) -> int:
        """화면 폭에 들어가는 썸네일 개수"""
        w = self.canvas.winfo_width()
        return max(1, (w - self.GAP) // (TW + self.GAP)) if w > 1 else 5

    def page(self, direction: int):
        """한 페이지 이동 (‹ ›)"""
        self.shift(direction * self.slots())

    def shift(self, n: int):
        """n칸 이동"""
        self.start += n
        self.render(follow=False)

    def invalidate(self, idx: int):
        """해당 이미지 썸네일 캐시 삭제 (저장 후 다시 생성)"""
        if self.app.folder and 0 <= idx < len(self.app.image_names):
            self.cache.pop(os.path.join(self.app.folder, self.app.image_names[idx]), None)

    def clear_cache(self):
        """캐시 전체 삭제 (폴더 바꿀 때)"""
        self.cache.clear()

    # ------------------------------------------------------------
    def render(self, follow: bool = True):
        """보이는 범위의 썸네일 그리기 (follow=True면 현재 이미지가 보이도록)"""
        c = self.canvas
        c.delete("all")
        view = self.app.view_indices
        if not view:
            c.create_text(12, (TH + 30) / 2, anchor="w", text="이미지가 없습니다",
                          fill=C.COLOR_MUTED, font=FONTS["small"])
            self.prev_btn.state(["disabled"])
            self.next_btn.state(["disabled"])
            return

        n = self.slots()
        if follow and self.app.cur in view:
            pos = view.index(self.app.cur)
            if pos < self.start or pos >= self.start + n:
                self.start = pos - n // 2
        self.start = max(0, min(self.start, max(0, len(view) - n)))

        shown = view[self.start:self.start + n]
        cw = max(self.canvas.winfo_width(), 1)
        x0 = max(self.GAP / 2, (cw - (len(shown) * (TW + self.GAP) - self.GAP)) / 2)
        y = 6
        for j, idx in enumerate(shown):
            x = x0 + j * (TW + self.GAP)
            tag = f"t{idx}"
            name = self.app.image_names[idx]
            photo = self._thumb(idx)
            if photo is not None:
                c.create_image(x, y, image=photo, anchor="nw", tags=tag)
            else:
                c.create_rectangle(x, y, x + TW, y + TH, fill="#E5E7EB", outline="", tags=tag)
                c.create_text(x + TW / 2, y + TH / 2, text="불러오기 실패",
                              fill=C.COLOR_MUTED, font=FONTS["small"], tags=tag)

            is_cur = idx == self.app.cur
            c.create_rectangle(x - 2, y - 2, x + TW + 2, y + TH + 2,
                               outline=C.COLOR_ACCENT if is_cur else C.COLOR_BORDER,
                               width=3 if is_cur else 1, tags=tag)

            meta = self.app.ws.effective_meta(name) if self.app.ws else None
            if meta and meta.status:     # 상태 배지
                color = C.STATUS_COLORS.get(meta.status, C.COLOR_MUTED)
                t = c.create_text(x + TW - 6, y + 5, anchor="ne", text=meta.status,
                                  fill="white", font=FONTS["tag"], tags=tag)
                bb = c.bbox(t)
                r = c.create_rectangle(bb[0] - 4, bb[1] - 1, bb[2] + 4, bb[3] + 1,
                                       fill=color, outline=color, tags=tag)
                c.tag_lower(r, t)

            short = name if len(name) <= 24 else "…" + name[-23:]
            c.create_text(x + TW / 2, y + TH + 13, text=short,
                          fill=C.COLOR_ACCENT if is_cur else C.COLOR_TEXT,
                          font=FONTS["tag"] if is_cur else FONTS["small"], tags=tag)
            c.tag_bind(tag, "<Button-1>", lambda e, i=idx: self.app.goto(i))
            c.tag_bind(tag, "<Enter>", lambda e: c.configure(cursor="hand2"))
            c.tag_bind(tag, "<Leave>", lambda e: c.configure(cursor=""))

        self.prev_btn.state(["!disabled"] if self.start > 0 else ["disabled"])
        self.next_btn.state(["!disabled"] if self.start + n < len(view) else ["disabled"])

    def _thumb(self, idx: int):
        """썸네일 이미지 생성 또는 캐시에서 꺼내기"""
        path = os.path.join(self.app.folder, self.app.image_names[idx])
        if path in self.cache:
            self.cache.move_to_end(path)
            return self.cache[path]
        photo = None
        try:
            with Image.open(path) as im:
                im.draft("RGB", (TW * 2, TH * 2))     # JPEG는 축소 디코딩으로 빠르게
                im = ImageOps.exif_transpose(im).convert("RGB")
                im.thumbnail((TW, TH))
            base = Image.new("RGB", (TW, TH), "#E5E7EB")
            ox, oy = (TW - im.width) // 2, (TH - im.height) // 2
            base.paste(im, (ox, oy))
            txt, _ = self.app.ws.resolve_label(self.app.image_names[idx])
            self._draw_label_boxes(base, txt, ox, oy, im.width, im.height)
            photo = ImageTk.PhotoImage(base)
        except Exception:
            photo = None
        self.cache[path] = photo
        while len(self.cache) > C.THUMB_CACHE_MAX:
            self.cache.popitem(last=False)
        return photo

    @staticmethod
    def _draw_label_boxes(img, txt, ox, oy, w, h):
        """썸네일 위에 라벨 박스 그리기"""
        if not txt or not os.path.exists(txt):
            return
        draw = ImageDraw.Draw(img)
        try:
            with open(txt, encoding="utf-8") as f:
                lines = f.readlines()
        except (OSError, UnicodeDecodeError):
            return
        for line in lines:
            try:
                c, cx, cy, bw, bh = parse_yolo_line(line.strip())
            except ValueError:
                continue
            x1 = ox + (cx - bw / 2) * w
            y1 = oy + (cy - bh / 2) * h
            draw.rectangle([x1, y1, x1 + bw * w, y1 + bh * h],
                           outline=C.CLASS_COLORS.get(c, "#FFFFFF"), width=2)
