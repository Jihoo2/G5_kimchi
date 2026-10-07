"""[카테고리] 이미지 캔버스 — 이미지 표시, 줌/팬, 마우스로 BBox 그리기·선택·이동·크기 조절, 정보 HUD

좌표 규칙 (가장 중요)
    BBox는 항상 '원본 이미지 픽셀 좌표'로 보관 (app.boxes)
    화면 좌표 = offset + 이미지 좌표 × scale     → to_canvas() / to_image() 두 함수로만 변환
    → 줌·팬을 해도 저장되는 좌표는 변하지 않음

의사 코드
    render():                     화면에 보이는 부분만 잘라서 확대/축소해 그림 (큰 이미지도 빠름)
        → draw_boxes() → draw_hud()
    마우스 누름 (_on_press):
        HUD 위             → 무시 (더블클릭 = 편집기)
        Pan 모드           → 화면 이동 시작
        선택 박스 모서리·테두리 → 크기 조절 시작 (테두리는 그 방향만)
        선택 박스 안쪽      → 이동 시작 (모드 상관없음)
        선택·이동 모드      → 클릭한 박스 선택
        그리기 모드        → 미확정 박스가 있으면 막음, 없으면 새 박스 그리기 시작
    마우스 드래그 (_on_drag):    그리기 미리보기 / 이동 / 크기 조절 (처음 움직일 때 Undo 저장)
    마우스 놓음 (_on_release):
        그리기: 거의 안 움직였으면 '클릭 = 박스 선택', 아니면 app.add_box()
        이동·크기 조절: app.box_changed()
    휠: 마우스 위치 기준 확대/축소   /   휠 클릭·우클릭 드래그: 언제나 Pan
    draw_hud():  선택 박스 옆에 반투명 정보 카드 (Class, 정규화 좌표, 픽셀 좌표)
                 아래 이미지를 어둡게 합성해서 반투명처럼 보이게 함 (Tk는 투명도 미지원)
"""
import math

import tkinter as tk
from PIL import Image, ImageDraw, ImageTk
from tkinter import font as tkfont

from src import config as C
from src.bbox.bbox_editor import BoxEditor
from src.bbox.bbox_model import Box
from src.ui.theme import FONTS


try:
    BILINEAR, NEAREST = Image.Resampling.BILINEAR, Image.Resampling.NEAREST
except AttributeError:  # Pillow < 9.1
    BILINEAR, NEAREST = Image.BILINEAR, Image.NEAREST


MODE_CURSORS = {"draw": "crosshair", "select": "arrow", "pan": "hand2"}


class ImageCanvas(tk.Frame):
    """이미지 + BBox + HUD 를 그리는 캔버스 (app = LabelingApp)"""
    HANDLE = 5          # 리사이즈 핸들 반지름(px)
    EDGE_TOL = 5        # 테두리(변) 잡기 허용 거리(px)
    EDGE_MIN_PX = 24    # 화면에서 이보다 작은 변은 테두리 조절 끔 (작은 박스도 이동 가능하게)
    RESIZE_CURSORS = {"n": "sb_v_double_arrow", "s": "sb_v_double_arrow",
                      "w": "sb_h_double_arrow", "e": "sb_h_double_arrow"}   # 모서리는 'sizing'

    def __init__(self, master, app):
        """캔버스·줌 표시·HUD 편집기 생성, 마우스/휠 이벤트 연결"""
        super().__init__(master, bg=C.COLOR_CANVAS)
        self.app = app
        self.canvas = tk.Canvas(self, bg=C.COLOR_CANVAS, highlightthickness=0, takefocus=1)
        self.canvas.pack(fill="both", expand=True)

        self.image = None          # PIL.Image (원본)
        self._tk_img = None        # 표시용 PhotoImage 참조 유지(GC 방지)
        self.scale, self.ox, self.oy = 1.0, 0.0, 0.0
        self.mode = "draw"
        self._drag = None
        self._render_pending = False
        self._fitted = True        # True면 창 크기 변경 시 자동 Fit

        # 우하단 줌 배율 표시
        self.zoom_lbl = tk.Label(self, text="-", bg="#111827", fg="white",
                                 font=FONTS["bold"], padx=8, pady=3)
        self.zoom_lbl.place(relx=1.0, rely=1.0, x=-12, y=-12, anchor="se")

        # 선택 BBox 옆에 따라다니는 반투명 정보 HUD (Ctrl+T) + 더블클릭 편집기
        self._disp = None          # 화면에 그려진 이미지(PIL) — HUD 반투명 합성용
        self._disp_origin = (0, 0)
        self._hud_img = None
        self._hud_rect = None      # (x, y, w, h) 캔버스 좌표
        self.overlay_visible = True
        self.overlay = BoxEditor(self, app)     # app이 overlay.refresh()로 호출

        c = self.canvas
        c.bind("<Configure>", self._on_resize)
        c.bind("<ButtonPress-1>", self._on_press)
        c.bind("<B1-Motion>", self._on_drag)
        c.bind("<ButtonRelease-1>", self._on_release)
        for b in ("2", "3"):   # 휠 클릭 / 우클릭 드래그 = 언제나 Pan
            c.bind(f"<ButtonPress-{b}>", self._pan_start)
            c.bind(f"<B{b}-Motion>", self._pan_move)
            c.bind(f"<ButtonRelease-{b}>", self._pan_end)
        c.bind("<MouseWheel>", self._on_wheel)       # Windows/macOS
        c.bind("<Button-4>", self._on_wheel)         # Linux(WSLg) 휠 위
        c.bind("<Button-5>", self._on_wheel)         # Linux(WSLg) 휠 아래
        c.bind("<Motion>", self._on_motion)
        c.bind("<Leave>", lambda e: c.delete("guide"))

    # ------------------------------------------------------------ 정보 HUD
    def toggle_overlay(self) -> bool:
        """HUD 표시/숨김 (Ctrl+T), 바뀐 상태 반환"""
        self.overlay_visible = not self.overlay_visible
        self.overlay.close()
        self.draw_hud()
        return self.overlay_visible

    def open_editor(self):
        """HUD 자리에 BBox 수정 패널 열기 (더블클릭 / I)"""
        if self.app.selected is None:
            self.app.set_message("먼저 BBox를 선택하세요.", "error")
            return
        if self._hud_rect is None:
            self.overlay_visible = True
            self.draw_hud()
        x, y = self._hud_rect[:2] if self._hud_rect else (12, 12)
        self.overlay.open(x, y)

    def _hud_background(self, x, y, w, h, accent):
        """HUD 아래 이미지를 어둡게 합성 → 반투명처럼 보이는 배경"""
        base = Image.new("RGB", (w, h), C.COLOR_CANVAS)
        if self._disp is not None:
            dx, dy = self._disp_origin
            base.paste(self._disp, (int(round(dx - x)), int(round(dy - y))))
        dark = Image.blend(base, Image.new("RGB", (w, h), "#0B1220"), 0.62)
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=8, fill=255)
        out = Image.composite(dark, base, mask)
        d = ImageDraw.Draw(out)
        d.rounded_rectangle([0, 0, w - 1, h - 1], radius=8, outline=accent, width=1)
        d.rectangle([0, 8, 2, h - 9], fill=accent)       # 왼쪽 클래스 색 바
        return ImageTk.PhotoImage(out)

    def draw_hud(self):
        """선택 박스 옆에 정보 카드 그리기 (오른쪽 → 왼쪽 → 아래 순으로 자리 찾기)"""
        c = self.canvas
        c.delete("hud")
        self._hud_rect = None
        sel = self.app.selected
        if (not self.overlay_visible or self.overlay.is_open or self.image is None
                or sel is None or sel >= len(self.app.boxes)):
            return
        b = self.app.boxes[sel]
        W, H = self.image.size
        cid, cx, cy, bw, bh = b.to_yolo(W, H)
        color = C.CLASS_COLORS.get(cid, "#FFFFFF")
        title = f"{cid}  {C.CLASS_NAMES.get(cid, '?')}" + ("  · 미확정" if b.pending else "")
        lines = [
            (title, FONTS["bold"], "white"),
            (f"X {cx:.4f}    Y {cy:.4f}", FONTS["mono"], "#E5E7EB"),
            (f"W {bw:.4f}    H {bh:.4f}", FONTS["mono"], "#E5E7EB"),
            (f"px [{round(b.x1)}, {round(b.y1)}, {round(b.w)}, {round(b.h)}]", FONTS["mono"], "#9CA3AF"),
            ("더블클릭 / I : 수정", FONTS["small"], "#9CA3AF"),
        ]
        pad, gap = 10, 3
        metrics = [(self._font(f).measure(t), self._font(f).metrics("linespace"))
                   for t, f, _ in lines]
        w = int(max(m[0] for m in metrics) + pad * 2 + 4)
        h = int(sum(m[1] for m in metrics) + gap * (len(lines) - 1) + pad * 2)

        # 위치: 박스 오른쪽 위 → 공간 없으면 왼쪽 → 그래도 없으면 박스 아래
        cw, ch = self._canvas_size()
        x1, y1 = self.to_canvas(b.x1, b.y1)
        x2, y2 = self.to_canvas(b.x2, b.y2)
        if x2 + 12 + w <= cw:
            x = x2 + 12
        elif x1 - 12 - w >= 0:
            x = x1 - 12 - w
        else:
            x = min(max(x1, 4), cw - w - 4)
        y = min(max(y1, 4), ch - h - 4)
        if x1 - 12 - w < 0 and x2 + 12 + w > cw and y2 + 12 + h <= ch:
            y = y2 + 12
        x, y = int(x), int(y)

        self._hud_img = self._hud_background(x, y, w, h, color)
        c.create_image(x, y, image=self._hud_img, anchor="nw", tags="hud")
        ty = y + pad
        for (text, f, fg), (_, lh) in zip(lines, metrics):
            c.create_text(x + pad + 4, ty, text=text, font=f, fill=fg, anchor="nw", tags="hud")
            ty += lh + gap
        c.tag_bind("hud", "<Double-Button-1>", lambda e: self.open_editor())
        c.tag_bind("hud", "<Enter>", lambda e: self._update_cursor("hand2"))
        c.tag_bind("hud", "<Leave>", lambda e: self._update_cursor())
        self._hud_rect = (x, y, w, h)

    def _font(self, spec):
        """폰트 측정 객체 캐시 (드래그 중 매번 만들지 않도록)"""
        cache = self.__dict__.setdefault("_font_cache", {})
        if spec not in cache:
            cache[spec] = tkfont.Font(root=self, font=spec)
        return cache[spec]

    def _on_hud(self, cx, cy) -> bool:
        """(cx, cy) 가 HUD 위인지"""
        r = self._hud_rect
        return bool(r) and r[0] <= cx <= r[0] + r[2] and r[1] <= cy <= r[1] + r[3]

    # ------------------------------------------------------------ 좌표 변환
    def to_canvas(self, x, y):
        """이미지 픽셀 좌표 → 화면 좌표"""
        return self.ox + x * self.scale, self.oy + y * self.scale

    def to_image(self, cx, cy):
        """화면 좌표 → 이미지 픽셀 좌표"""
        return (cx - self.ox) / self.scale, (cy - self.oy) / self.scale

    def clamp_img(self, x, y):
        """이미지 좌표를 이미지 범위 안으로"""
        W, H = self.image.size
        return min(max(x, 0.0), W), min(max(y, 0.0), H)

    def _canvas_size(self):
        """캔버스 크기 (아직 안 그려졌으면 기본값)"""
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        return (w if w > 1 else 900), (h if h > 1 else 600)

    # ------------------------------------------------------------ 뷰
    def set_mode(self, mode: str):
        """마우스 모드 변경 (draw / select / pan)"""
        self.mode = mode
        self.canvas.delete("guide")
        self._update_cursor()

    def _update_cursor(self, cursor=None):
        """마우스 커서 모양 변경"""
        self.canvas.configure(cursor=cursor or MODE_CURSORS.get(self.mode, "arrow"))

    def set_image(self, img):
        """새 이미지 표시 → 화면에 맞추기"""
        self.image = img
        self._drag = None
        self.canvas.update_idletasks()
        self.fit()

    def fit(self):
        """이미지 전체가 보이도록 배율·위치 계산 (F)"""
        self._fitted = True
        if self.image is not None:
            cw, ch = self._canvas_size()
            W, H = self.image.size
            self.scale = max(min(cw / W, ch / H) * 0.98, 1e-3)
            self.ox = (cw - W * self.scale) / 2
            self.oy = (ch - H * self.scale) / 2
        self.request_render()

    def zoom(self, factor, cx=None, cy=None):
        """(cx, cy) 화면 지점을 고정한 채 확대/축소"""
        if self.image is None:
            return
        if cx is None:
            cw, ch = self._canvas_size()
            cx, cy = cw / 2, ch / 2
        ix, iy = self.to_image(cx, cy)
        new = min(max(self.scale * factor, C.ZOOM_MIN), C.ZOOM_MAX)
        if new == self.scale:
            return
        self.scale = new
        self.ox, self.oy = cx - ix * new, cy - iy * new
        self._fitted = False
        self.request_render()

    def _on_resize(self, _e):
        """창 크기 변경: Fit 상태면 다시 맞추고, 아니면 다시 그리기"""
        if self._fitted:
            self.fit()
        else:
            self.request_render()

    def request_render(self):
        """다시 그리기 예약 (여러 번 요청해도 한 번만 그림)"""
        if not self._render_pending:
            self._render_pending = True
            self.after_idle(self.render)

    def render(self):
        """화면에 보이는 영역만 잘라서 리사이즈 → 큰 이미지 확대 시에도 빠름"""
        self._render_pending = False
        c = self.canvas
        c.delete("all")
        cw, ch = self._canvas_size()
        if self.image is None:
            c.create_text(cw / 2, ch / 2, text="폴더 열기(Ctrl+O)로 이미지 폴더를 선택하세요",
                          fill="#9CA3AF", font=FONTS["title"])
            self.zoom_lbl.configure(text="-")
            return

        W, H = self.image.size
        s = self.scale
        self._disp = None
        x0 = max(0, math.floor(-self.ox / s))
        y0 = max(0, math.floor(-self.oy / s))
        x1 = min(W, math.ceil((cw - self.ox) / s))
        y1 = min(H, math.ceil((ch - self.oy) / s))
        if x1 > x0 and y1 > y0:
            crop = self.image.crop((x0, y0, x1, y1))
            dw = max(1, int(round((x1 - x0) * s)))
            dh = max(1, int(round((y1 - y0) * s)))
            crop = crop.resize((dw, dh), NEAREST if s >= 2.5 else BILINEAR)
            self._disp = crop
            self._disp_origin = (self.ox + x0 * s, self.oy + y0 * s)
            self._tk_img = ImageTk.PhotoImage(crop)
            c.create_image(self.ox + x0 * s, self.oy + y0 * s, image=self._tk_img,
                           anchor="nw", tags="img")
        bx1, by1 = self.to_canvas(0, 0)
        bx2, by2 = self.to_canvas(W, H)
        c.create_rectangle(bx1, by1, bx2, by2, outline="#4B5563", tags="img")
        self.draw_boxes()
        self.zoom_lbl.configure(text=f"{s * 100:.0f}%")

    def draw_boxes(self):
        """모든 BBox + 클래스 태그 + 선택 박스 핸들 그리기 (미확정은 점선)"""
        c = self.canvas
        c.delete("box")
        if self.image is None:
            return
        sel = self.app.selected
        for i, b in enumerate(self.app.boxes):
            color = C.CLASS_COLORS.get(b.cls, "#FFFFFF")
            x1, y1 = self.to_canvas(b.x1, b.y1)
            x2, y2 = self.to_canvas(b.x2, b.y2)
            is_sel = i == sel
            c.create_rectangle(x1, y1, x2, y2, outline=color, width=3 if (is_sel or b.pending) else 2,
                               dash=(8, 4) if b.pending else None, tags="box")
            if is_sel:
                c.create_rectangle(x1 - 3, y1 - 3, x2 + 3, y2 + 3, outline="white",
                                   dash=(4, 3), tags="box")

            # 클래스명 태그 (위쪽 공간이 없으면 박스 안쪽에)
            name = C.CLASS_NAMES.get(b.cls, f"class {b.cls}")
            if b.pending:
                name += "  · 미확정 (Enter 확정 / Esc 취소)"
            if y1 - 20 < 0:
                ty, anchor = y1 + 4, "nw"
            else:
                ty, anchor = y1 - 4, "sw"
            t = c.create_text(x1 + 5, ty, text=name, anchor=anchor, fill="white",
                              font=FONTS["tag"], tags="box")
            bb = c.bbox(t)
            r = c.create_rectangle(bb[0] - 5, bb[1] - 1, bb[2] + 5, bb[3] + 1,
                                   fill=color, outline=color, tags="box")
            c.tag_lower(r, t)

            if is_sel:
                h = self.HANDLE
                for hx, hy in ((x1, y1), (x2, y1), (x1, y2), (x2, y2)):          # 모서리 핸들
                    c.create_rectangle(hx - h, hy - h, hx + h, hy + h, fill="white",
                                       outline=color, width=2, tags="box")
                mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                e = h - 1
                edges = []
                if x2 - x1 >= self.EDGE_MIN_PX:                                   # 위·아래 변 가운데
                    edges += [(mx, y1), (mx, y2)]
                if y2 - y1 >= self.EDGE_MIN_PX:                                   # 왼쪽·오른쪽 변 가운데
                    edges += [(x1, my), (x2, my)]
                for hx, hy in edges:
                    c.create_rectangle(hx - e, hy - e, hx + e, hy + e, fill="white",
                                       outline=color, width=1, tags="box")
        self.draw_hud()

    # ------------------------------------------------------------ hit test
    def _handle_at(self, cx, cy):
        """(cx, cy) 가 선택 박스의 크기 조절 위치면 방향 문자열, 아니면 None
            모서리 → 'nw' / 'ne' / 'sw' / 'se'  (가로·세로 동시 조절)
            테두리 → 'n' / 's' / 'w' / 'e'      (그 방향만 조절)
        박스가 화면에서 너무 작으면 테두리 판정은 끔 → 안쪽을 잡아 이동할 공간 확보"""
        sel = self.app.selected
        if sel is None or self.image is None or sel >= len(self.app.boxes):
            return None
        b = self.app.boxes[sel]
        x1, y1 = self.to_canvas(b.x1, b.y1)
        x2, y2 = self.to_canvas(b.x2, b.y2)
        r = self.HANDLE + 3
        for name, (hx, hy) in (("nw", (x1, y1)), ("ne", (x2, y1)),
                               ("sw", (x1, y2)), ("se", (x2, y2))):
            if abs(cx - hx) <= r and abs(cy - hy) <= r:
                return name
        t = self.EDGE_TOL
        in_x = x1 + r < cx < x2 - r            # 위·아래 변: 모서리 핸들 사이 구간
        in_y = y1 + r < cy < y2 - r            # 왼쪽·오른쪽 변
        if x2 - x1 >= self.EDGE_MIN_PX and in_x:
            if abs(cy - y1) <= t:
                return "n"
            if abs(cy - y2) <= t:
                return "s"
        if y2 - y1 >= self.EDGE_MIN_PX and in_y:
            if abs(cx - x1) <= t:
                return "w"
            if abs(cx - x2) <= t:
                return "e"
        return None

    def _inside(self, idx, cx, cy) -> bool:
        """(cx, cy) 가 idx 박스 안인지 (가장자리 여유 3px)"""
        if self.image is None or not 0 <= idx < len(self.app.boxes):
            return False
        b = self.app.boxes[idx]
        ix, iy = self.to_image(cx, cy)
        tol = 3 / self.scale
        return b.x1 - tol <= ix <= b.x2 + tol and b.y1 - tol <= iy <= b.y2 + tol

    def _box_at(self, cx, cy):
        """겹친 박스가 있으면 가장 작은 박스를 우선 선택"""
        if self.image is None:
            return None
        ix, iy = self.to_image(cx, cy)
        tol = 3 / self.scale
        hits = [(b.area(), i) for i, b in enumerate(self.app.boxes)
                if b.x1 - tol <= ix <= b.x2 + tol and b.y1 - tol <= iy <= b.y2 + tol]
        return min(hits)[1] if hits else None

    # ------------------------------------------------------------ 마우스
    def _on_press(self, e):
        """마우스 누름 → 어떤 동작(그리기/이동/크기조절/선택/Pan)을 시작할지 결정"""
        self.canvas.focus_set()
        self.canvas.delete("guide")
        if self.image is None:
            return
        if self._on_hud(e.x, e.y):
            return
        if self.overlay.is_open:
            self.overlay.close()
        if self.mode == "pan":
            self._pan_start(e)
            return

        handle = self._handle_at(e.x, e.y)
        if handle:
            self._drag = {"type": "resize", "handle": handle, "idx": self.app.selected,
                          "pushed": False, "p0": (e.x, e.y)}
            return

        sel = self.app.selected
        if sel is not None and self._inside(sel, e.x, e.y):     # 선택된 박스 = 어느 모드든 이동
            self._drag = {"type": "move", "idx": sel, "last": self.to_image(e.x, e.y),
                          "pushed": False, "p0": (e.x, e.y)}
            return

        if self.mode == "select":
            idx = self._box_at(e.x, e.y)
            self.app.select_box(idx)
            if idx is not None:
                self._drag = {"type": "move", "idx": idx, "last": self.to_image(e.x, e.y),
                              "pushed": False, "p0": (e.x, e.y)}
            return

        # draw 모드: 미확정 BBox가 있으면 새로 그리지 않음
        if self.app.pending_index() is not None:
            self._drag = {"type": "blocked", "p0": (e.x, e.y)}
            return
        self._drag = {"type": "draw", "start": self.clamp_img(*self.to_image(e.x, e.y)),
                      "p0": (e.x, e.y)}

    def _on_drag(self, e):
        """드래그 중: 그리기 미리보기 / 이동 / 크기 조절"""
        d = self._drag
        if not d:
            return
        t = d["type"]
        if t == "blocked":
            return
        if t == "pan":
            self._pan_move(e)
            return

        if t == "draw":
            ix, iy = self.clamp_img(*self.to_image(e.x, e.y))
            sx, sy = d["start"]
            self.canvas.delete("preview")
            x1, y1 = self.to_canvas(sx, sy)
            x2, y2 = self.to_canvas(ix, iy)
            color = C.CLASS_COLORS.get(self.app.current_class.get(), "white")
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=2,
                                         dash=(6, 3), tags="preview")
            self.canvas.create_text(max(x1, x2) + 6, max(y1, y2) + 6, anchor="nw",
                                    text=f"{abs(ix - sx):.0f} × {abs(iy - sy):.0f}",
                                    fill="white", font=FONTS["small"], tags="preview")
            return

        idx = d["idx"]
        if idx is None or idx >= len(self.app.boxes):
            return
        if not d["pushed"]:
            px, py = d["p0"]
            if abs(e.x - px) + abs(e.y - py) < 3:    # 단순 클릭은 수정으로 치지 않음
                return
            self.app.push_undo()
            d["pushed"] = True

        b = self.app.boxes[idx]
        W, H = self.image.size
        if t == "move":
            ix, iy = self.to_image(e.x, e.y)
            lx, ly = d["last"]
            dx = min(max(ix - lx, -b.x1), W - b.x2)
            dy = min(max(iy - ly, -b.y1), H - b.y2)
            b.x1 += dx
            b.x2 += dx
            b.y1 += dy
            b.y2 += dy
            d["last"] = (ix, iy)
        elif t == "resize":
            ix, iy = self.clamp_img(*self.to_image(e.x, e.y))
            h = d["handle"]
            if "w" in h:            # 'n', 's' 처럼 세로 방향만 있으면 가로는 그대로
                b.x1 = ix
            elif "e" in h:
                b.x2 = ix
            if "n" in h:            # 'w', 'e' 처럼 가로 방향만 있으면 세로는 그대로
                b.y1 = iy
            elif "s" in h:
                b.y2 = iy
            if b.x1 > b.x2:   # 반대편으로 넘어가면 핸들도 뒤집기
                b.x1, b.x2 = b.x2, b.x1
                h = h.translate(str.maketrans("we", "ew"))
            if b.y1 > b.y2:
                b.y1, b.y2 = b.y2, b.y1
                h = h.translate(str.maketrans("ns", "sn"))
            d["handle"] = h
        self.draw_boxes()

    def _on_release(self, e):
        """마우스 놓음: 박스 추가 또는 변경 확정"""
        d, self._drag = self._drag, None
        if not d:
            return
        t = d["type"]
        if t == "pan":
            self._pan_end(e)
            return

        if t == "blocked":
            self.app.set_message("미확정 BBox가 있습니다. Enter로 확정하거나 Esc로 취소한 뒤 새로 그리세요.",
                                 "error")
            return

        if t == "draw":
            self.canvas.delete("preview")
            px, py = d["p0"]
            if abs(e.x - px) < 4 and abs(e.y - py) < 4:      # 클릭 = 박스 선택
                self.app.select_box(self._box_at(e.x, e.y))
                return
            ix, iy = self.clamp_img(*self.to_image(e.x, e.y))
            sx, sy = d["start"]
            box = Box(0, sx, sy, ix, iy).normalize()
            if box.w < C.MIN_BOX_PX or box.h < C.MIN_BOX_PX:
                self.app.set_message("BBox가 너무 작아 추가하지 않았습니다.", "error")
                return
            self.app.add_box(box)
            return

        if d.get("pushed"):
            b = self.app.boxes[d["idx"]]
            if b.w < C.MIN_BOX_PX or b.h < C.MIN_BOX_PX:
                self.app.undo_action(silent=True)
                self.app.set_message("BBox가 너무 작아져 크기 조절을 취소했습니다.", "error")
            else:
                self.app.box_changed(d["idx"])

    def _pan_start(self, e):
        """화면 이동 시작"""
        self.overlay.close()
        self._drag = {"type": "pan", "x": e.x, "y": e.y}
        self._update_cursor("fleur")

    def _pan_move(self, e):
        """화면 이동 (드래그 중엔 이동만, 놓으면 다시 그림)"""
        d = self._drag
        if not d or d["type"] != "pan":
            return
        dx, dy = e.x - d["x"], e.y - d["y"]
        self.ox += dx
        self.oy += dy
        self.canvas.move("all", dx, dy)   # 드래그 중엔 이동만, 놓으면 다시 렌더
        d["x"], d["y"] = e.x, e.y
        self._fitted = False

    def _pan_end(self, _e):
        """화면 이동 끝 → 다시 그리기"""
        self._drag = None
        self._update_cursor()
        self.request_render()

    def _on_wheel(self, e):
        """휠: 마우스 위치 기준 확대/축소"""
        self.overlay.close()
        up = e.num == 4 or getattr(e, "delta", 0) > 0
        self.zoom(C.ZOOM_STEP if up else 1 / C.ZOOM_STEP, e.x, e.y)

    def _on_motion(self, e):
        """마우스 이동: 커서 모양 변경, 그리기 모드 보조선"""
        c = self.canvas
        c.delete("guide")
        if self.image is None or self._drag:
            return
        if self._on_hud(e.x, e.y):
            self._update_cursor("hand2")
            return
        handle = self._handle_at(e.x, e.y)
        if handle:
            self._update_cursor(self.RESIZE_CURSORS.get(handle, "sizing"))
            return
        sel = self.app.selected
        if ((sel is not None and self._inside(sel, e.x, e.y))
                or (self.mode == "select" and self._box_at(e.x, e.y) is not None)):
            self._update_cursor("fleur")
            return
        self._update_cursor()
        if self.mode == "draw":     # 그리기 보조선
            W, H = self.image.size
            ix, iy = self.to_image(e.x, e.y)
            if 0 <= ix <= W and 0 <= iy <= H:
                x1, y1 = self.to_canvas(0, 0)
                x2, y2 = self.to_canvas(W, H)
                c.create_line(x1, e.y, x2, e.y, fill="#FFFFFF", dash=(3, 4), tags="guide")
                c.create_line(e.x, y1, e.x, y2, fill="#FFFFFF", dash=(3, 4), tags="guide")
