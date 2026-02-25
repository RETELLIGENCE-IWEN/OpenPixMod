from __future__ import annotations
from typing import Optional, Callable, Tuple

from PySide6.QtCore import Qt, QPoint, QRectF, QTimer
from PySide6.QtGui import (
    QPainter, QImage, QPixmap, QColor, QPen, QBrush
)
from PySide6.QtWidgets import QWidget

class CanvasWidget(QWidget):
    """
    Shows output canvas preview (QImage) with view zoom/pan.
    Supports:
      - left-drag: move image (calls on_move_image(dx, dy) in output-canvas px)
      - wheel: view zoom
      - ctrl+wheel: image zoom (calls on_scale_image(factor))
      - middle-drag: pan view
      - eyedropper mode: click to sample color from source via callback
    """
    def __init__(
        self,
        on_move_image: Callable[[float, float], None],
        on_scale_image: Callable[[float], None],
        on_pick_color_at_canvas_pos: Callable[[int, int], None],
        on_pick_drag_at_canvas_pos: Optional[Callable[[int, int], None]] = None,
        on_pick_finish: Optional[Callable[[], None]] = None,
        on_paint_start_at_canvas_pos: Optional[Callable[[int, int], None]] = None,
        on_paint_drag_at_canvas_pos: Optional[Callable[[int, int], None]] = None,
        on_paint_finish: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self._preview: Optional[QImage] = None
        self._out_size: Tuple[int, int] = (512, 512)

        # View transform
        self._view_zoom = 1.0
        self._view_pan_x = 0.0
        self._view_pan_y = 0.0

        # Interaction
        self._dragging_left = False
        self._dragging_mid = False
        self._dragging_pick = False
        self._dragging_paint = False
        self._last_pos = QPoint()
        self._last_pick_canvas_xy: Optional[Tuple[int, int]] = None
        self._last_paint_canvas_xy: Optional[Tuple[int, int]] = None

        self.eyedropper_enabled = False
        self.paint_enabled = False
        self.show_pixel_grid = False
        self._selection_enabled = False
        self._selection_rect_canvas: Optional[Tuple[float, float, float, float]] = None
        self._selection_invert = False
        self._lasso_points_canvas: list[Tuple[float, float]] = []

        self._on_move_image = on_move_image
        self._on_scale_image = on_scale_image
        self._on_pick_color_at_canvas_pos = on_pick_color_at_canvas_pos
        self._on_pick_drag_at_canvas_pos = on_pick_drag_at_canvas_pos
        self._on_pick_finish = on_pick_finish
        self._on_paint_start_at_canvas_pos = on_paint_start_at_canvas_pos
        self._on_paint_drag_at_canvas_pos = on_paint_drag_at_canvas_pos
        self._on_paint_finish = on_paint_finish

        self._ants_phase = 0.0
        self._ants_timer = QTimer(self)
        self._ants_timer.setInterval(120)
        self._ants_timer.timeout.connect(self._advance_ants)

        self.setAcceptDrops(True)

    def set_preview(self, qimg: Optional[QImage], out_size: Tuple[int, int]) -> None:
        self._preview = qimg
        self._out_size = out_size
        self.update()

    def set_selection_overlay(
        self,
        enabled: bool,
        rect_canvas: Optional[Tuple[float, float, float, float]],
        invert: bool = False,
        lasso_points_canvas: Optional[list[Tuple[float, float]]] = None,
    ) -> None:
        self._selection_enabled = bool(enabled)
        self._selection_rect_canvas = rect_canvas
        self._selection_invert = bool(invert)
        self._lasso_points_canvas = list(lasso_points_canvas or [])
        if self._selection_enabled and self._selection_rect_canvas is not None:
            if not self._ants_timer.isActive():
                self._ants_timer.start()
        elif self._ants_timer.isActive():
            self._ants_timer.stop()
        self.update()

    def reset_view(self) -> None:
        self._view_zoom = 1.0
        self._view_pan_x = 0.0
        self._view_pan_y = 0.0
        self.update()

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        # Background
        p.fillRect(self.rect(), QColor(30, 30, 30))

        if self._preview is None:
            p.setPen(QPen(QColor(220, 220, 220)))
            p.drawText(self.rect(), Qt.AlignCenter, "Drop an image or File → Open…")
            return

        # Compute where the output canvas is drawn in widget coords
        out_w, out_h = self._out_size
        # Center in widget
        cx = self.width() * 0.5 + self._view_pan_x
        cy = self.height() * 0.5 + self._view_pan_y

        draw_w = out_w * self._view_zoom
        draw_h = out_h * self._view_zoom
        x0 = cx - draw_w * 0.5
        y0 = cy - draw_h * 0.5

        # Checkerboard underlay (to visualize transparency)
        self._draw_checkerboard(p, QRectF(x0, y0, draw_w, draw_h), int(16 * self._view_zoom))

        # Draw preview
        pm = QPixmap.fromImage(self._preview)
        p.drawPixmap(int(x0), int(y0), int(draw_w), int(draw_h), pm)

        # Canvas border
        p.setPen(QPen(QColor(240, 240, 240), 1))
        p.drawRect(QRectF(x0, y0, draw_w, draw_h))

        if self.show_pixel_grid and self._view_zoom >= 8.0:
            self._draw_pixel_grid(p, x0, y0, draw_w, draw_h, out_w, out_h)

        if self._selection_enabled and self._selection_rect_canvas is not None:
            self._draw_selection_overlay(p, x0, y0, draw_w, draw_h, out_w, out_h)
        if self._lasso_points_canvas:
            self._draw_lasso_preview(p, x0, y0, draw_w, draw_h, out_w, out_h)

        # Help overlay
        p.setPen(QPen(QColor(220, 220, 220)))
        msg = "Wheel: view zoom | Middle-drag: pan view | Ctrl+Wheel: image zoom | Left-drag: move image"
        if self.eyedropper_enabled:
            msg = "Eyedropper ON: click image to sample color | " + msg
        elif self.paint_enabled:
            msg = "Paint tool ON: drag to paint alpha mask | " + msg
        p.drawText(10, self.height() - 10, msg)

    def _draw_checkerboard(self, p: QPainter, r: QRectF, cell: int) -> None:
        if cell < 4:
            cell = 4
        c1 = QColor(60, 60, 60)
        c2 = QColor(90, 90, 90)

        x0 = int(r.left())
        y0 = int(r.top())
        x1 = int(r.right())
        y1 = int(r.bottom())

        for y in range(y0, y1, cell):
            for x in range(x0, x1, cell):
                use_c1 = ((x // cell) + (y // cell)) % 2 == 0
                p.fillRect(x, y, cell, cell, c1 if use_c1 else c2)

    def _widget_to_canvas_xy(self, pos: QPoint) -> Optional[Tuple[int, int]]:
        """
        Convert widget coords to output-canvas pixel coords.
        Returns None if outside canvas.
        """
        out_w, out_h = self._out_size
        cx = self.width() * 0.5 + self._view_pan_x
        cy = self.height() * 0.5 + self._view_pan_y

        draw_w = out_w * self._view_zoom
        draw_h = out_h * self._view_zoom
        x0 = cx - draw_w * 0.5
        y0 = cy - draw_h * 0.5

        x = pos.x()
        y = pos.y()
        if x < x0 or y < y0 or x > x0 + draw_w or y > y0 + draw_h:
            return None

        # Normalize into canvas coords
        u = (x - x0) / draw_w
        v = (y - y0) / draw_h
        cx_px = int(u * out_w)
        cy_px = int(v * out_h)
        cx_px = max(0, min(out_w - 1, cx_px))
        cy_px = max(0, min(out_h - 1, cy_px))
        return (cx_px, cy_px)

    def _draw_pixel_grid(
        self,
        p: QPainter,
        x0: float,
        y0: float,
        draw_w: float,
        draw_h: float,
        out_w: int,
        out_h: int,
    ) -> None:
        if out_w <= 0 or out_h <= 0:
            return
        p.setPen(QPen(QColor(255, 255, 255, 45), 1))
        step_x = draw_w / float(out_w)
        step_y = draw_h / float(out_h)
        for ix in range(1, out_w):
            x = int(round(x0 + ix * step_x))
            p.drawLine(x, int(y0), x, int(y0 + draw_h))
        for iy in range(1, out_h):
            y = int(round(y0 + iy * step_y))
            p.drawLine(int(x0), y, int(x0 + draw_w), y)

    def _draw_selection_overlay(
        self,
        p: QPainter,
        x0: float,
        y0: float,
        draw_w: float,
        draw_h: float,
        out_w: int,
        out_h: int,
    ) -> None:
        if out_w <= 0 or out_h <= 0:
            return
        cx, cy, cw, ch = self._selection_rect_canvas
        # Canvas px -> widget px
        rx = x0 + (cx / float(out_w)) * draw_w
        ry = y0 + (cy / float(out_h)) * draw_h
        rw = (cw / float(out_w)) * draw_w
        rh = (ch / float(out_h)) * draw_h
        if rw <= 0 or rh <= 0:
            return

        if self._selection_invert:
            p.fillRect(QRectF(x0, y0, draw_w, draw_h), QColor(0, 0, 0, 60))
            p.fillRect(QRectF(rx, ry, rw, rh), QColor(0, 0, 0, 0))
        else:
            # Shade outside selection
            p.fillRect(QRectF(x0, y0, draw_w, max(0.0, ry - y0)), QColor(0, 0, 0, 60))
            p.fillRect(QRectF(x0, ry + rh, draw_w, max(0.0, y0 + draw_h - (ry + rh))), QColor(0, 0, 0, 60))
            p.fillRect(QRectF(x0, ry, max(0.0, rx - x0), rh), QColor(0, 0, 0, 60))
            p.fillRect(QRectF(rx + rw, ry, max(0.0, x0 + draw_w - (rx + rw)), rh), QColor(0, 0, 0, 60))

        outer = QPen(QColor(255, 255, 255), 2)
        outer.setDashPattern([4, 4])
        outer.setDashOffset(self._ants_phase)
        p.setPen(outer)
        p.drawRect(QRectF(rx, ry, rw, rh))

        inner = QPen(QColor(0, 0, 0), 2)
        inner.setDashPattern([4, 4])
        inner.setDashOffset(self._ants_phase + 4.0)
        p.setPen(inner)
        p.drawRect(QRectF(rx, ry, rw, rh))

    def _draw_lasso_preview(
        self,
        p: QPainter,
        x0: float,
        y0: float,
        draw_w: float,
        draw_h: float,
        out_w: int,
        out_h: int,
    ) -> None:
        if out_w <= 0 or out_h <= 0:
            return
        pts: list[QPoint] = []
        for cx, cy in self._lasso_points_canvas:
            x = int(round(x0 + (cx / float(out_w)) * draw_w))
            y = int(round(y0 + (cy / float(out_h)) * draw_h))
            pts.append(QPoint(x, y))
        if not pts:
            return

        p.setPen(QPen(QColor(80, 210, 255), 2))
        for i in range(1, len(pts)):
            p.drawLine(pts[i - 1], pts[i])

        p.setBrush(QBrush(QColor(80, 210, 255)))
        for pt in pts:
            p.drawEllipse(pt, 3, 3)

    def wheelEvent(self, e) -> None:
        delta = e.angleDelta().y()
        if delta == 0:
            return

        if e.modifiers() & Qt.ControlModifier:
            # Image zoom
            factor = 1.1 if delta > 0 else (1.0 / 1.1)
            self._on_scale_image(factor)
            e.accept()
            return

        # View zoom
        factor = 1.1 if delta > 0 else (1.0 / 1.1)
        self._view_zoom = max(0.05, min(20.0, self._view_zoom * factor))
        self.update()
        e.accept()

    def mousePressEvent(self, e) -> None:
        self._last_pos = e.position().toPoint()

        if e.button() == Qt.LeftButton:
            if self.eyedropper_enabled:
                canvas_xy = self._widget_to_canvas_xy(self._last_pos)
                if canvas_xy is not None:
                    self._on_pick_color_at_canvas_pos(canvas_xy[0], canvas_xy[1])
                    self._dragging_pick = True
                    self._last_pick_canvas_xy = canvas_xy
                return
            if self.paint_enabled:
                canvas_xy = self._widget_to_canvas_xy(self._last_pos)
                if canvas_xy is not None and self._on_paint_start_at_canvas_pos is not None:
                    self._on_paint_start_at_canvas_pos(canvas_xy[0], canvas_xy[1])
                    self._dragging_paint = True
                    self._last_paint_canvas_xy = canvas_xy
                return
            self._dragging_left = True
        elif e.button() == Qt.MiddleButton:
            self._dragging_mid = True

    def mouseMoveEvent(self, e) -> None:
        pos = e.position().toPoint()
        dx = pos.x() - self._last_pos.x()
        dy = pos.y() - self._last_pos.y()
        self._last_pos = pos

        if self._dragging_left:
            # Convert widget pixels to canvas pixels based on view zoom
            if self._view_zoom > 1e-6:
                self._on_move_image(dx / self._view_zoom, dy / self._view_zoom)
        elif self._dragging_pick:
            if self._on_pick_drag_at_canvas_pos is not None:
                canvas_xy = self._widget_to_canvas_xy(pos)
                if canvas_xy is not None and canvas_xy != self._last_pick_canvas_xy:
                    self._on_pick_drag_at_canvas_pos(canvas_xy[0], canvas_xy[1])
                    self._last_pick_canvas_xy = canvas_xy
        elif self._dragging_paint:
            if self._on_paint_drag_at_canvas_pos is not None:
                canvas_xy = self._widget_to_canvas_xy(pos)
                if canvas_xy is not None and canvas_xy != self._last_paint_canvas_xy:
                    self._on_paint_drag_at_canvas_pos(canvas_xy[0], canvas_xy[1])
                    self._last_paint_canvas_xy = canvas_xy
        elif self._dragging_mid:
            self._view_pan_x += dx
            self._view_pan_y += dy
            self.update()

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            self._dragging_left = False
            if self._dragging_pick:
                self._dragging_pick = False
                self._last_pick_canvas_xy = None
                if self._on_pick_finish is not None:
                    self._on_pick_finish()
            if self._dragging_paint:
                self._dragging_paint = False
                self._last_paint_canvas_xy = None
                if self._on_paint_finish is not None:
                    self._on_paint_finish()
        elif e.button() == Qt.MiddleButton:
            self._dragging_mid = False

    def _advance_ants(self) -> None:
        self._ants_phase = (self._ants_phase + 1.0) % 8.0
        self.update()
