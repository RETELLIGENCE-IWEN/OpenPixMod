from __future__ import annotations
from copy import deepcopy
from pathlib import Path
from typing import Optional
import numpy as np
from PIL import Image

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QImage, QKeySequence, QIcon, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFileDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QSlider, QCheckBox, QPushButton, QMessageBox, QDockWidget, QDoubleSpinBox, QComboBox, QInputDialog,
    QGroupBox, QScrollArea
)

from core.state import ProjectState, PaletteColor
from core.io import load_image_rgba, save_image
from core.project_io import save_project, load_project
from core.compositor import composite_to_canvas
from core.batch import batch_export_with_state
from core.selection import (
    magic_wand_mask,
    color_range_mask,
    polygon_mask,
    bounding_rect,
    combine_selection_masks,
)
from ui.canvas_widget import CanvasWidget
from ui.palette_widget import PaletteWidget

def pil_rgba_to_qimage(img: Image.Image) -> QImage:
    img = img.convert("RGBA")
    w, h = img.size
    data = img.tobytes("raw", "RGBA")
    qimg = QImage(data, w, h, QImage.Format_RGBA8888)
    # Important: keep a copy because Python-owned bytes may be freed
    return qimg.copy()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._logo_path = Path(__file__).resolve().parent.parent / "assets" / "Logo.png"
        if self._logo_path.exists():
            self.setWindowIcon(QIcon(str(self._logo_path)))
        self.setWindowTitle("OpenPixMod v0.2")

        self.state = ProjectState()
        self._src_img: Optional[Image.Image] = None
        self._preview_img: Optional[Image.Image] = None
        self._project_path: Optional[str] = None
        self._undo_stack: list[tuple[ProjectState, Optional[np.ndarray], list[tuple[int, int]]]] = []
        self._redo_stack: list[tuple[ProjectState, Optional[np.ndarray], list[tuple[int, int]]]] = []
        self._history_limit = 100
        self._restoring_state = False
        self._snapshots: dict[str, tuple[ProjectState, Optional[np.ndarray], list[tuple[int, int]]]] = {}
        self._pick_mode: str = "eyedropper"
        self._selection_mask: Optional[np.ndarray] = None
        self._lasso_points: list[tuple[int, int]] = []

        self._act_undo: Optional[QAction] = None
        self._act_redo: Optional[QAction] = None

        # Central
        self.canvas = CanvasWidget(
            on_move_image=self._move_image,
            on_scale_image=self._scale_image,
            on_pick_color_at_canvas_pos=self._pick_color_at_canvas_xy,
            on_pick_drag_at_canvas_pos=self._pick_drag_at_canvas_xy,
            on_pick_finish=self._pick_finish,
        )
        self.canvas.setAcceptDrops(True)

        central = QWidget()
        lay = QVBoxLayout()
        lay.addWidget(self.canvas)
        central.setLayout(lay)
        self.setCentralWidget(central)

        # Menu
        self._build_menu()

        # Right-side controls dock
        self._build_controls_dock()

        self.setAcceptDrops(True)
        self.resize(1200, 800)
        self._rerender()
        self._sync_ui_from_state()
        self._update_status()

    # ---------------------------
    # Menu / Actions
    # ---------------------------
    def _build_menu(self) -> None:
        open_act = QAction("Open??, self)
        open_act.setShortcut(QKeySequence.StandardKey.Open)
        open_act.triggered.connect(self.open_file)

        save_act = QAction("Save As??, self)
        save_act.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_act.triggered.connect(self.save_as)

        open_project_act = QAction("Open Project...", self)
        open_project_act.triggered.connect(self.open_project)

        save_project_act = QAction("Save Project As...", self)
        save_project_act.triggered.connect(self.save_project_as)

        batch_export_act = QAction("Batch Export...", self)
        batch_export_act.triggered.connect(self.batch_export)

        reset_view = QAction("Reset View", self)
        reset_view.triggered.connect(self.canvas.reset_view)

        self._act_undo = QAction("Undo", self)
        self._act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self._act_undo.triggered.connect(self._undo)

        self._act_redo = QAction("Redo", self)
        self._act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self._act_redo.triggered.connect(self._redo)

        fit_act = QAction("Fit Image to Canvas", self)
        fit_act.setShortcut("F")
        fit_act.triggered.connect(self._fit_image_to_canvas)

        center_act = QAction("Center Image", self)
        center_act.setShortcut("C")
        center_act.triggered.connect(self._center_image)

        quit_act = QAction("Quit", self)
        quit_act.setShortcut(QKeySequence.StandardKey.Quit)
        quit_act.triggered.connect(self.close)

        mfile = self.menuBar().addMenu("File")
        mfile.addAction(open_act)
        mfile.addAction(open_project_act)
        mfile.addAction(save_act)
        mfile.addAction(save_project_act)
        mfile.addAction(batch_export_act)
        mfile.addSeparator()
        mfile.addAction(quit_act)

        medit = self.menuBar().addMenu("Edit")
        medit.addAction(self._act_undo)
        medit.addAction(self._act_redo)

        mview = self.menuBar().addMenu("View")
        mview.addAction(reset_view)
        mview.addAction(fit_act)
        mview.addAction(center_act)

    def keyPressEvent(self, e) -> None:
        if self.eyedropper_btn.isChecked() and self._pick_mode == "lasso":
            if e.key() in (Qt.Key_Return, Qt.Key_Enter):
                self._close_lasso()
                e.accept()
                return
            if e.key() == Qt.Key_Escape:
                self._clear_lasso()
                e.accept()
                return
        super().keyPressEvent(e)

    # ---------------------------
    # Controls dock
    # ---------------------------
    def _build_controls_dock(self) -> None:
        dock = QDockWidget("Controls", self)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        root = QWidget()
        root_lay = QVBoxLayout(root)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        panel = QWidget()
        v = QVBoxLayout(panel)

        if self._logo_path.exists():
            logo_label = QLabel()
            logo_label.setAlignment(Qt.AlignCenter)
            logo_pm = QPixmap(str(self._logo_path))
            if not logo_pm.isNull():
                logo_label.setPixmap(logo_pm.scaled(180, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                v.addWidget(logo_label)

        g_canvas, gl_canvas = self._make_group("Canvas")
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("W"))
        self.out_w = QSpinBox()
        self.out_w.setRange(1, 8192)
        self.out_w.setValue(self.state.out_w)
        self.out_w.valueChanged.connect(self._on_out_size_widget_changed)
        size_row.addWidget(self.out_w)
        size_row.addWidget(QLabel("H"))
        self.out_h = QSpinBox()
        self.out_h.setRange(1, 8192)
        self.out_h.setValue(self.state.out_h)
        self.out_h.valueChanged.connect(self._on_out_size_widget_changed)
        size_row.addWidget(self.out_h)
        self.apply_size_btn = QPushButton("Apply")
        self.apply_size_btn.clicked.connect(self._apply_out_size)
        size_row.addWidget(self.apply_size_btn)
        gl_canvas.addLayout(size_row)
        self.auto_apply_size = QCheckBox("Auto-apply size changes")
        self.auto_apply_size.setChecked(False)
        self.auto_apply_size.stateChanged.connect(lambda *_: None)
        gl_canvas.addWidget(self.auto_apply_size)
        self.trim_btn = QPushButton("Trim Transparent")
        self.trim_btn.clicked.connect(self._trim_transparent)
        gl_canvas.addWidget(self.trim_btn)
        v.addWidget(g_canvas)

        g_tx, gl_tx = self._make_group("Transform")
        scale_row = QHBoxLayout()
        scale_row.addWidget(QLabel("Scale"))
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(1.0, 5000.0)
        self.scale_spin.setDecimals(1)
        self.scale_spin.setSingleStep(1.0)
        self.scale_spin.setSuffix("%")
        self.scale_spin.setValue(self.state.img_scale * 100.0)
        self.scale_spin.valueChanged.connect(self._on_scale_spin_changed)
        scale_row.addWidget(self.scale_spin, 1)
        gl_tx.addLayout(scale_row)
        pos_row = QHBoxLayout()
        pos_row.addWidget(QLabel("X"))
        self.pos_x_spin = QDoubleSpinBox()
        self.pos_x_spin.setRange(-20000.0, 20000.0)
        self.pos_x_spin.setDecimals(1)
        self.pos_x_spin.setValue(self.state.img_off_x)
        self.pos_x_spin.valueChanged.connect(self._on_position_spin_changed)
        pos_row.addWidget(self.pos_x_spin, 1)
        pos_row.addWidget(QLabel("Y"))
        self.pos_y_spin = QDoubleSpinBox()
        self.pos_y_spin.setRange(-20000.0, 20000.0)
        self.pos_y_spin.setDecimals(1)
        self.pos_y_spin.setValue(self.state.img_off_y)
        self.pos_y_spin.valueChanged.connect(self._on_position_spin_changed)
        pos_row.addWidget(self.pos_y_spin, 1)
        gl_tx.addLayout(pos_row)
        tx_btn_row = QHBoxLayout()
        self.fit_btn = QPushButton("Fit")
        self.fit_btn.clicked.connect(self._fit_image_to_canvas)
        tx_btn_row.addWidget(self.fit_btn)
        self.center_btn = QPushButton("Center")
        self.center_btn.clicked.connect(self._center_image)
        tx_btn_row.addWidget(self.center_btn)
        self.reset_tx_btn = QPushButton("Reset")
        self.reset_tx_btn.clicked.connect(self._reset_transform)
        tx_btn_row.addWidget(self.reset_tx_btn)
        gl_tx.addLayout(tx_btn_row)
        tf_row = QHBoxLayout()
        self.rot_l_btn = QPushButton("Rotate -90")
        self.rot_l_btn.clicked.connect(lambda: self._rotate_image(-90))
        tf_row.addWidget(self.rot_l_btn)
        self.rot_r_btn = QPushButton("Rotate +90")
        self.rot_r_btn.clicked.connect(lambda: self._rotate_image(90))
        tf_row.addWidget(self.rot_r_btn)
        self.flip_h_btn = QPushButton("Flip H")
        self.flip_h_btn.clicked.connect(self._flip_horizontal)
        tf_row.addWidget(self.flip_h_btn)
        self.flip_v_btn = QPushButton("Flip V")
        self.flip_v_btn.clicked.connect(self._flip_vertical)
        tf_row.addWidget(self.flip_v_btn)
        gl_tx.addLayout(tf_row)
        v.addWidget(g_tx)

        g_sel, gl_sel = self._make_group("Selection")
        self.sel_enable_chk = QCheckBox("Enable Rectangle Selection")
        self.sel_enable_chk.toggled.connect(self._on_selection_changed)
        gl_sel.addWidget(self.sel_enable_chk)
        self.sel_invert_chk = QCheckBox("Invert Selection")
        self.sel_invert_chk.toggled.connect(self._on_selection_changed)
        gl_sel.addWidget(self.sel_invert_chk)
        pick_mode_row = QHBoxLayout()
        pick_mode_row.addWidget(QLabel("Pick Tool"))
        self.pick_mode_combo = QComboBox()
        self.pick_mode_combo.addItem("Eyedropper", userData="eyedropper")
        self.pick_mode_combo.addItem("Magic Wand", userData="wand")
        self.pick_mode_combo.addItem("Color Range", userData="color_range")
        self.pick_mode_combo.addItem("Lasso", userData="lasso")
        self.pick_mode_combo.currentIndexChanged.connect(self._on_pick_mode_changed)
        pick_mode_row.addWidget(self.pick_mode_combo, 1)
        gl_sel.addLayout(pick_mode_row)
        wand_row = QHBoxLayout()
        wand_row.addWidget(QLabel("Pick Tol"))
        self.sel_pick_tol_spin = QSpinBox()
        self.sel_pick_tol_spin.setRange(0, 441)
        self.sel_pick_tol_spin.setValue(40)
        wand_row.addWidget(self.sel_pick_tol_spin, 1)
        self.wand_contig_chk = QCheckBox("Contiguous")
        self.wand_contig_chk.setChecked(True)
        wand_row.addWidget(self.wand_contig_chk)
        gl_sel.addLayout(wand_row)
        op_row = QHBoxLayout()
        op_row.addWidget(QLabel("Selection Op"))
        self.sel_op_combo = QComboBox()
        self.sel_op_combo.addItem("Replace", userData="replace")
        self.sel_op_combo.addItem("Add", userData="add")
        self.sel_op_combo.addItem("Subtract", userData="subtract")
        self.sel_op_combo.addItem("Intersect", userData="intersect")
        op_row.addWidget(self.sel_op_combo, 1)
        gl_sel.addLayout(op_row)
        lasso_row = QHBoxLayout()
        self.lasso_close_btn = QPushButton("Close/Apply Lasso")
        self.lasso_close_btn.clicked.connect(self._close_lasso)
        lasso_row.addWidget(self.lasso_close_btn)
        self.lasso_clear_btn = QPushButton("Clear Lasso")
        self.lasso_clear_btn.clicked.connect(self._clear_lasso)
        lasso_row.addWidget(self.lasso_clear_btn)
        gl_sel.addLayout(lasso_row)
        sel_row1 = QHBoxLayout()
        sel_row1.addWidget(QLabel("X"))
        self.sel_x_spin = QSpinBox()
        self.sel_x_spin.setRange(0, 20000)
        self.sel_x_spin.valueChanged.connect(self._on_selection_changed)
        sel_row1.addWidget(self.sel_x_spin)
        sel_row1.addWidget(QLabel("Y"))
        self.sel_y_spin = QSpinBox()
        self.sel_y_spin.setRange(0, 20000)
        self.sel_y_spin.valueChanged.connect(self._on_selection_changed)
        sel_row1.addWidget(self.sel_y_spin)
        gl_sel.addLayout(sel_row1)
        sel_row2 = QHBoxLayout()
        sel_row2.addWidget(QLabel("W"))
        self.sel_w_spin = QSpinBox()
        self.sel_w_spin.setRange(0, 20000)
        self.sel_w_spin.valueChanged.connect(self._on_selection_changed)
        sel_row2.addWidget(self.sel_w_spin)
        sel_row2.addWidget(QLabel("H"))
        self.sel_h_spin = QSpinBox()
        self.sel_h_spin.setRange(0, 20000)
        self.sel_h_spin.valueChanged.connect(self._on_selection_changed)
        sel_row2.addWidget(self.sel_h_spin)
        gl_sel.addLayout(sel_row2)
        self.sel_full_btn = QPushButton("Select Full Canvas")
        self.sel_full_btn.clicked.connect(self._select_full_canvas)
        gl_sel.addWidget(self.sel_full_btn)
        v.addWidget(g_sel)

        g_key, gl_key = self._make_group("Background Key + Mask")
        self.keep_palette = QCheckBox("Keep palette when opening new image")
        self.keep_palette.setChecked(False)
        gl_key.addWidget(self.keep_palette)
        self.eyedropper_btn = QPushButton("Eyedropper: OFF")
        self.eyedropper_btn.setCheckable(True)
        self.eyedropper_btn.toggled.connect(self._on_eyedropper_toggled)
        gl_key.addWidget(self.eyedropper_btn)
        tol_row = QHBoxLayout()
        self.tol = QSlider(Qt.Horizontal)
        self.tol.setRange(0, 441)
        self.tol.setValue(self.state.tolerance)
        self.tol.valueChanged.connect(self._on_tol_slider_changed)
        self.tol_spin = QSpinBox()
        self.tol_spin.setRange(0, 441)
        self.tol_spin.setValue(self.state.tolerance)
        self.tol_spin.valueChanged.connect(self._on_tol_spin_changed)
        self.tol_val = QLabel(str(self.state.tolerance))
        self.tol_val.setMinimumWidth(40)
        self.tol_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        tol_row.addWidget(self.tol, 1)
        tol_row.addWidget(self.tol_spin, 0)
        tol_row.addWidget(self.tol_val, 0)
        gl_key.addLayout(tol_row)
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode"))
        self.color_mode = QComboBox()
        self.color_mode.addItem("RGB Distance", userData="rgb")
        self.color_mode.addItem("HSV Range", userData="hsv")
        self.color_mode.currentIndexChanged.connect(self._on_color_mode_changed)
        mode_row.addWidget(self.color_mode, 1)
        gl_key.addLayout(mode_row)
        hsv_h_row = QHBoxLayout()
        hsv_h_row.addWidget(QLabel("H Tol"))
        self.hsv_h_spin = QSpinBox()
        self.hsv_h_spin.setRange(0, 180)
        self.hsv_h_spin.setValue(int(self.state.hsv_h_tol))
        self.hsv_h_spin.valueChanged.connect(self._on_hsv_tolerance_changed)
        hsv_h_row.addWidget(self.hsv_h_spin, 1)
        gl_key.addLayout(hsv_h_row)
        hsv_s_row = QHBoxLayout()
        hsv_s_row.addWidget(QLabel("S Tol"))
        self.hsv_s_spin = QSpinBox()
        self.hsv_s_spin.setRange(0, 255)
        self.hsv_s_spin.setValue(int(self.state.hsv_s_tol))
        self.hsv_s_spin.valueChanged.connect(self._on_hsv_tolerance_changed)
        hsv_s_row.addWidget(self.hsv_s_spin, 1)
        gl_key.addLayout(hsv_s_row)
        hsv_v_row = QHBoxLayout()
        hsv_v_row.addWidget(QLabel("V Tol"))
        self.hsv_v_spin = QSpinBox()
        self.hsv_v_spin.setRange(0, 255)
        self.hsv_v_spin.setValue(int(self.state.hsv_v_tol))
        self.hsv_v_spin.valueChanged.connect(self._on_hsv_tolerance_changed)
        hsv_v_row.addWidget(self.hsv_v_spin, 1)
        gl_key.addLayout(hsv_v_row)
        self._hsv_rows = [hsv_h_row, hsv_s_row, hsv_v_row]
        self._set_hsv_controls_enabled(self.state.color_key_mode == "hsv")
        grow_row = QHBoxLayout()
        grow_row.addWidget(QLabel("Grow/Shrink"))
        self.grow = QSlider(Qt.Horizontal)
        self.grow.setRange(-20, 20)
        self.grow.setValue(int(self.state.mask_grow_shrink))
        self.grow.valueChanged.connect(self._on_grow_slider_changed)
        self.grow_spin = QSpinBox()
        self.grow_spin.setRange(-20, 20)
        self.grow_spin.setValue(int(self.state.mask_grow_shrink))
        self.grow_spin.valueChanged.connect(self._on_grow_spin_changed)
        self.grow_val = QLabel(str(int(self.state.mask_grow_shrink)))
        self.grow_val.setMinimumWidth(45)
        grow_row.addWidget(self.grow, 1)
        grow_row.addWidget(self.grow_spin, 0)
        grow_row.addWidget(self.grow_val, 0)
        gl_key.addLayout(grow_row)
        feather_row = QHBoxLayout()
        feather_row.addWidget(QLabel("Feather"))
        self.feather = QSlider(Qt.Horizontal)
        self.feather.setRange(0, 20)
        self.feather.setValue(int(self.state.mask_feather_radius))
        self.feather.valueChanged.connect(self._on_feather_slider_changed)
        self.feather_spin = QSpinBox()
        self.feather_spin.setRange(0, 20)
        self.feather_spin.setValue(int(self.state.mask_feather_radius))
        self.feather_spin.valueChanged.connect(self._on_feather_spin_changed)
        self.feather_val = QLabel(str(int(self.state.mask_feather_radius)))
        self.feather_val.setMinimumWidth(45)
        feather_row.addWidget(self.feather, 1)
        feather_row.addWidget(self.feather_spin, 0)
        feather_row.addWidget(self.feather_val, 0)
        gl_key.addLayout(feather_row)
        islands_row = QHBoxLayout()
        islands_row.addWidget(QLabel("Remove islands < px"))
        self.islands_spin = QSpinBox()
        self.islands_spin.setRange(0, 2000000)
        self.islands_spin.setSingleStep(10)
        self.islands_spin.setValue(int(self.state.remove_islands_min_size))
        self.islands_spin.valueChanged.connect(self._on_islands_changed)
        islands_row.addWidget(self.islands_spin, 1)
        gl_key.addLayout(islands_row)
        self.palette_widget = PaletteWidget(
            on_changed=self._sync_palette_from_widget,
            on_add_color_request=self._turn_on_eyedropper,
        )
        gl_key.addWidget(self.palette_widget)
        v.addWidget(g_key)

        g_adj, gl_adj = self._make_group("Adjustments + Rendering")
        op_row = QHBoxLayout()
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(0, 100)
        self.opacity.setValue(int(round(self.state.opacity * 100)))
        self.opacity.valueChanged.connect(self._on_opacity_slider_changed)
        self.opacity_spin = QSpinBox()
        self.opacity_spin.setRange(0, 100)
        self.opacity_spin.setSuffix("%")
        self.opacity_spin.setValue(int(round(self.state.opacity * 100)))
        self.opacity_spin.valueChanged.connect(self._on_opacity_spin_changed)
        self.opacity_val = QLabel(f"{int(round(self.state.opacity * 100))}%")
        self.opacity_val.setMinimumWidth(55)
        op_row.addWidget(self.opacity, 1)
        op_row.addWidget(self.opacity_spin, 0)
        op_row.addWidget(self.opacity_val, 0)
        gl_adj.addLayout(op_row)
        self.hq = QCheckBox("High quality resample (Lanczos)")
        self.hq.setChecked(self.state.high_quality_resample)
        self.hq.stateChanged.connect(self._on_hq_changed)
        gl_adj.addWidget(self.hq)
        px_row = QHBoxLayout()
        self.nearest_chk = QCheckBox("Nearest Neighbor")
        self.nearest_chk.toggled.connect(self._on_nearest_toggled)
        px_row.addWidget(self.nearest_chk)
        self.grid_chk = QCheckBox("Pixel Grid")
        self.grid_chk.toggled.connect(self._on_grid_toggled)
        px_row.addWidget(self.grid_chk)
        gl_adj.addLayout(px_row)
        self.brightness_spin = QDoubleSpinBox()
        self.brightness_spin.setRange(0.1, 3.0)
        self.brightness_spin.setSingleStep(0.1)
        self.brightness_spin.setValue(self.state.brightness)
        self.brightness_spin.valueChanged.connect(self._on_adjustments_changed)
        self._add_labeled_row(gl_adj, "Brightness", self.brightness_spin)
        self.contrast_spin = QDoubleSpinBox()
        self.contrast_spin.setRange(0.1, 3.0)
        self.contrast_spin.setSingleStep(0.1)
        self.contrast_spin.setValue(self.state.contrast)
        self.contrast_spin.valueChanged.connect(self._on_adjustments_changed)
        self._add_labeled_row(gl_adj, "Contrast", self.contrast_spin)
        self.saturation_spin = QDoubleSpinBox()
        self.saturation_spin.setRange(0.0, 3.0)
        self.saturation_spin.setSingleStep(0.1)
        self.saturation_spin.setValue(self.state.saturation)
        self.saturation_spin.valueChanged.connect(self._on_adjustments_changed)
        self._add_labeled_row(gl_adj, "Saturation", self.saturation_spin)
        self.gamma_spin = QDoubleSpinBox()
        self.gamma_spin.setRange(0.1, 3.0)
        self.gamma_spin.setSingleStep(0.1)
        self.gamma_spin.setValue(self.state.gamma)
        self.gamma_spin.valueChanged.connect(self._on_adjustments_changed)
        self._add_labeled_row(gl_adj, "Gamma", self.gamma_spin)
        v.addWidget(g_adj)

        g_flow, gl_flow = self._make_group("Workflow")
        snap_row = QHBoxLayout()
        self.snapshot_combo = QComboBox()
        snap_row.addWidget(self.snapshot_combo, 1)
        self.snap_save_btn = QPushButton("Save Snap")
        self.snap_save_btn.clicked.connect(self._save_snapshot)
        snap_row.addWidget(self.snap_save_btn)
        self.snap_load_btn = QPushButton("Load Snap")
        self.snap_load_btn.clicked.connect(self._load_snapshot)
        snap_row.addWidget(self.snap_load_btn)
        gl_flow.addLayout(snap_row)
        self.compare_chk = QCheckBox("Before/After Compare")
        self.compare_chk.setChecked(False)
        self.compare_chk.toggled.connect(self._rerender)
        gl_flow.addWidget(self.compare_chk)
        v.addWidget(g_flow)

        v.addStretch(1)
        scroll.setWidget(panel)
        root_lay.addWidget(scroll)
        dock.setWidget(root)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

    # ---------------------------
    # File IO
    # ---------------------------
    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp *.tif *.tiff)"
        )
        if not path:
            return
        self._load_path(path)

    def save_as(self) -> None:
        if self._preview_img is None:
            QMessageBox.information(self, "Nothing to save", "Load an image first.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Save As", "", "PNG (*.png);;JPG (*.jpg *.jpeg);;WEBP (*.webp);;TIFF (*.tif *.tiff)"
        )
        if not path:
            return

        # Render full-res export from current state
        export_img = composite_to_canvas(
            src_rgba_pil=self._src_img,
            out_size=(self.state.out_w, self.state.out_h),
            img_scale=self.state.img_scale,
            img_offset=(self.state.img_off_x, self.state.img_off_y),
            rotation_deg=self.state.rotation_deg,
            palette_rgbs=self.state.enabled_palette_rgbs(),
            tolerance=self.state.tolerance,
            opacity=self.state.opacity,
            color_key_mode=self.state.color_key_mode,
            hsv_h_tol=self.state.hsv_h_tol,
            hsv_s_tol=self.state.hsv_s_tol,
            hsv_v_tol=self.state.hsv_v_tol,
            mask_grow_shrink=self.state.mask_grow_shrink,
            mask_feather_radius=self.state.mask_feather_radius,
            remove_islands_min_size=self.state.remove_islands_min_size,
            high_quality=self.state.high_quality_resample,
            nearest_neighbor=self.state.nearest_neighbor,
            brightness=self.state.brightness,
            contrast=self.state.contrast,
            saturation=self.state.saturation,
            gamma=self.state.gamma,
            selection_enabled=self.state.selection_enabled,
            selection_invert=self.state.selection_invert,
            selection_rect=(self.state.sel_x, self.state.sel_y, self.state.sel_w, self.state.sel_h),
            selection_mask=self._selection_mask,
        )

        try:
            ext = Path(path).suffix.lower()
            if ext in {".jpg", ".jpeg"}:
                # JPG has no alpha, so flatten onto white.
                flat = Image.new("RGB", export_img.size, (255, 255, 255))
                flat.paste(export_img.convert("RGBA"), mask=export_img.split()[3])
                flat.save(path, quality=95)
            else:
                save_image(path, export_img)
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))
            return

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "OpenPixMod Project (*.opm);;JSON (*.json)"
        )
        if not path:
            return

        try:
            loaded_state = load_project(path)
        except Exception as e:
            QMessageBox.critical(self, "Open project failed", str(e))
            return

        loaded_img: Optional[Image.Image] = None
        src_error: Optional[str] = None
        if loaded_state.src_path:
            try:
                loaded_img = load_image_rgba(loaded_state.src_path)
            except Exception as e:
                src_error = str(e)

        self.state = loaded_state
        self._src_img = loaded_img
        self._project_path = path
        self._selection_mask = None
        self._lasso_points = []
        if self._src_img is not None and self.state.selection_enabled:
            self._selection_mask = self._rect_state_to_mask()
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._update_undo_redo_actions()
        self._sync_ui_from_state()
        self._rerender()

        if src_error is not None:
            QMessageBox.warning(
                self,
                "Project loaded with missing source",
                f"Project opened, but source image could not be loaded:\n{src_error}",
            )

    def save_project_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project As", "", "OpenPixMod Project (*.opm);;JSON (*.json)"
        )
        if not path:
            return
        if not (path.lower().endswith(".opm") or path.lower().endswith(".json")):
            path += ".opm"
        try:
            save_project(path, self.state)
        except Exception as e:
            QMessageBox.critical(self, "Save project failed", str(e))
            return
        self._project_path = path

    def _load_path(self, path: str) -> None:
        try:
            img = load_image_rgba(path)
        except Exception as e:
            QMessageBox.critical(self, "Open failed", str(e))
            return

        self.state.src_path = path
        self._src_img = img
        self._project_path = None
        self._selection_mask = None
        self._lasso_points = []

        if not self.keep_palette.isChecked():
            self.state.palette = []
            self.palette_widget.listw.blockSignals(True)
            self.palette_widget.listw.clear()
            self.palette_widget.listw.blockSignals(False)

        # Optional: turn off eyedropper on load
        self.eyedropper_btn.setChecked(False)

        # Reset transforms for new image
        self.state.img_scale = 1.0
        self.state.img_off_x = 0.0
        self.state.img_off_y = 0.0

        # Optional: auto-set output to image size (common convenience)
        self.state.out_w = img.width
        self.state.out_h = img.height
        self.out_w.blockSignals(True)
        self.out_h.blockSignals(True)
        self.out_w.setValue(self.state.out_w)
        self.out_h.setValue(self.state.out_h)
        self.out_w.blockSignals(False)
        self.out_h.blockSignals(False)

        self._undo_stack.clear()
        self._redo_stack.clear()
        self._update_undo_redo_actions()
        self._sync_ui_from_state()
        self._rerender()

    # ---------------------------
    # Drag & drop support
    # ---------------------------
    def dragEnterEvent(self, e) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e) -> None:
        urls = e.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        if path:
            self._load_path(path)

    def _push_undo_state(self) -> None:
        if self._restoring_state:
            return
        mask_copy = None if self._selection_mask is None else self._selection_mask.copy()
        lasso_copy = list(self._lasso_points)
        self._undo_stack.append((deepcopy(self.state), mask_copy, lasso_copy))
        if len(self._undo_stack) > self._history_limit:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._update_undo_redo_actions()

    def _apply_state(
        self,
        state: ProjectState,
        selection_mask: Optional[np.ndarray],
        lasso_points: list[tuple[int, int]],
    ) -> None:
        self._restoring_state = True
        self.state = deepcopy(state)
        self._selection_mask = None if selection_mask is None else selection_mask.copy()
        self._lasso_points = list(lasso_points)
        self._sync_ui_from_state()
        self._restoring_state = False
        self._rerender()

    def _undo(self) -> None:
        if not self._undo_stack:
            return
        cur_mask = None if self._selection_mask is None else self._selection_mask.copy()
        self._redo_stack.append((deepcopy(self.state), cur_mask, list(self._lasso_points)))
        prev_state, prev_mask, prev_lasso = self._undo_stack.pop()
        self._apply_state(prev_state, prev_mask, prev_lasso)
        self._update_undo_redo_actions()

    def _redo(self) -> None:
        if not self._redo_stack:
            return
        cur_mask = None if self._selection_mask is None else self._selection_mask.copy()
        self._undo_stack.append((deepcopy(self.state), cur_mask, list(self._lasso_points)))
        nxt_state, nxt_mask, nxt_lasso = self._redo_stack.pop()
        self._apply_state(nxt_state, nxt_mask, nxt_lasso)
        self._update_undo_redo_actions()

    def _update_undo_redo_actions(self) -> None:
        if self._act_undo is not None:
            self._act_undo.setEnabled(bool(self._undo_stack))
        if self._act_redo is not None:
            self._act_redo.setEnabled(bool(self._redo_stack))

    def _sync_ui_from_state(self) -> None:
        self.out_w.blockSignals(True)
        self.out_h.blockSignals(True)
        self.out_w.setValue(int(self.state.out_w))
        self.out_h.setValue(int(self.state.out_h))
        self.out_w.blockSignals(False)
        self.out_h.blockSignals(False)

        self.tol.blockSignals(True)
        self.tol_spin.blockSignals(True)
        self.tol.setValue(int(self.state.tolerance))
        self.tol_spin.setValue(int(self.state.tolerance))
        self.tol.blockSignals(False)
        self.tol_spin.blockSignals(False)
        self.tol_val.setText(str(int(self.state.tolerance)))

        mode_index = self.color_mode.findData(self.state.color_key_mode)
        if mode_index < 0:
            mode_index = 0
        self.color_mode.blockSignals(True)
        self.color_mode.setCurrentIndex(mode_index)
        self.color_mode.blockSignals(False)

        self.hsv_h_spin.blockSignals(True)
        self.hsv_s_spin.blockSignals(True)
        self.hsv_v_spin.blockSignals(True)
        self.hsv_h_spin.setValue(int(self.state.hsv_h_tol))
        self.hsv_s_spin.setValue(int(self.state.hsv_s_tol))
        self.hsv_v_spin.setValue(int(self.state.hsv_v_tol))
        self.hsv_h_spin.blockSignals(False)
        self.hsv_s_spin.blockSignals(False)
        self.hsv_v_spin.blockSignals(False)
        self._set_hsv_controls_enabled(self.state.color_key_mode == "hsv")

        self.sel_enable_chk.blockSignals(True)
        self.sel_invert_chk.blockSignals(True)
        self.sel_x_spin.blockSignals(True)
        self.sel_y_spin.blockSignals(True)
        self.sel_w_spin.blockSignals(True)
        self.sel_h_spin.blockSignals(True)
        self.sel_enable_chk.setChecked(bool(self.state.selection_enabled))
        self.sel_invert_chk.setChecked(bool(self.state.selection_invert))
        self.sel_x_spin.setValue(int(self.state.sel_x))
        self.sel_y_spin.setValue(int(self.state.sel_y))
        self.sel_w_spin.setValue(int(self.state.sel_w))
        self.sel_h_spin.setValue(int(self.state.sel_h))
        self.sel_enable_chk.blockSignals(False)
        self.sel_invert_chk.blockSignals(False)
        self.sel_x_spin.blockSignals(False)
        self.sel_y_spin.blockSignals(False)
        self.sel_w_spin.blockSignals(False)
        self.sel_h_spin.blockSignals(False)

        pick_idx = self.pick_mode_combo.findData(self._pick_mode)
        if pick_idx < 0:
            pick_idx = 0
        self.pick_mode_combo.blockSignals(True)
        self.pick_mode_combo.setCurrentIndex(pick_idx)
        self.pick_mode_combo.blockSignals(False)

        self.grow.blockSignals(True)
        self.grow_spin.blockSignals(True)
        self.grow.setValue(int(self.state.mask_grow_shrink))
        self.grow_spin.setValue(int(self.state.mask_grow_shrink))
        self.grow.blockSignals(False)
        self.grow_spin.blockSignals(False)
        self.grow_val.setText(str(int(self.state.mask_grow_shrink)))

        self.feather.blockSignals(True)
        self.feather_spin.blockSignals(True)
        self.feather.setValue(int(self.state.mask_feather_radius))
        self.feather_spin.setValue(int(self.state.mask_feather_radius))
        self.feather.blockSignals(False)
        self.feather_spin.blockSignals(False)
        self.feather_val.setText(str(int(self.state.mask_feather_radius)))

        self.islands_spin.blockSignals(True)
        self.islands_spin.setValue(int(self.state.remove_islands_min_size))
        self.islands_spin.blockSignals(False)

        pct = int(round(self.state.opacity * 100))
        self.opacity.blockSignals(True)
        self.opacity_spin.blockSignals(True)
        self.opacity.setValue(pct)
        self.opacity_spin.setValue(pct)
        self.opacity.blockSignals(False)
        self.opacity_spin.blockSignals(False)
        self.opacity_val.setText(f"{pct}%")

        self.scale_spin.blockSignals(True)
        self.scale_spin.setValue(self.state.img_scale * 100.0)
        self.scale_spin.blockSignals(False)
        self.pos_x_spin.blockSignals(True)
        self.pos_y_spin.blockSignals(True)
        self.pos_x_spin.setValue(self.state.img_off_x)
        self.pos_y_spin.setValue(self.state.img_off_y)
        self.pos_x_spin.blockSignals(False)
        self.pos_y_spin.blockSignals(False)

        self.hq.blockSignals(True)
        self.hq.setChecked(bool(self.state.high_quality_resample))
        self.hq.blockSignals(False)

        self.nearest_chk.blockSignals(True)
        self.nearest_chk.setChecked(bool(self.state.nearest_neighbor))
        self.nearest_chk.blockSignals(False)
        self.grid_chk.blockSignals(True)
        self.grid_chk.setChecked(bool(self.state.show_pixel_grid))
        self.grid_chk.blockSignals(False)
        self.canvas.show_pixel_grid = bool(self.state.show_pixel_grid)

        self.brightness_spin.blockSignals(True)
        self.contrast_spin.blockSignals(True)
        self.saturation_spin.blockSignals(True)
        self.gamma_spin.blockSignals(True)
        self.brightness_spin.setValue(float(self.state.brightness))
        self.contrast_spin.setValue(float(self.state.contrast))
        self.saturation_spin.setValue(float(self.state.saturation))
        self.gamma_spin.setValue(float(self.state.gamma))
        self.brightness_spin.blockSignals(False)
        self.contrast_spin.blockSignals(False)
        self.saturation_spin.blockSignals(False)
        self.gamma_spin.blockSignals(False)

        self.palette_widget.listw.blockSignals(True)
        self.palette_widget.listw.clear()
        for p in self.state.palette:
            self.palette_widget.add_color(p.rgb)
            it = self.palette_widget.listw.item(self.palette_widget.listw.count() - 1)
            it.setCheckState(Qt.Checked if p.enabled else Qt.Unchecked)
        self.palette_widget.listw.blockSignals(False)

    def _update_status(self) -> None:
        src_size = f"{self._src_img.width}x{self._src_img.height}" if self._src_img is not None else "none"
        if self.state.color_key_mode == "hsv":
            key_info = f"HSV(H:{self.state.hsv_h_tol},S:{self.state.hsv_s_tol},V:{self.state.hsv_v_tol})"
        else:
            key_info = f"RGB Dist:{self.state.tolerance}"
        msg = (
            f"Source: {src_size} | Canvas: {self.state.out_w}x{self.state.out_h} | "
            f"Image Scale: {self.state.img_scale * 100:.1f}% Rot:{self.state.rotation_deg} | Offset: ({self.state.img_off_x:.1f}, {self.state.img_off_y:.1f}) | "
            f"Sel: {'ON' if self.state.selection_enabled else 'OFF'} | Key: {key_info} | Opacity: {self.state.opacity * 100:.0f}%"
        )
        self.statusBar().showMessage(msg)

    def _make_group(self, title: str) -> tuple[QGroupBox, QVBoxLayout]:
        g = QGroupBox(title)
        gl = QVBoxLayout()
        g.setLayout(gl)
        return g, gl

    def _add_labeled_row(self, layout: QVBoxLayout, label: str, widget: Optional[QWidget]) -> None:
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        if widget is not None:
            row.addWidget(widget, 1)
        layout.addLayout(row)

    def _selection_rect_on_output_canvas(self) -> Optional[tuple[float, float, float, float]]:
        if self._src_img is None:
            return None
        if self.state.rotation_deg % 360 != 0:
            return None
        rect = None
        if self._selection_mask is not None:
            rect = bounding_rect(self._selection_mask)
        if rect is None:
            rect = (self.state.sel_x, self.state.sel_y, self.state.sel_w, self.state.sel_h)
        sx, sy, sw, sh = rect
        if sw <= 0 or sh <= 0:
            return None
        src_w, src_h = self._src_img.size
        if src_w <= 0 or src_h <= 0:
            return None
        scale = max(0.01, float(self.state.img_scale))
        img_w = src_w * scale
        img_h = src_h * scale
        x0 = self.state.out_w * 0.5 - img_w * 0.5 + self.state.img_off_x
        y0 = self.state.out_h * 0.5 - img_h * 0.5 + self.state.img_off_y
        rx = x0 + (sx / float(src_w)) * img_w
        ry = y0 + (sy / float(src_h)) * img_h
        rw = (sw / float(src_w)) * img_w
        rh = (sh / float(src_h)) * img_h
        return (rx, ry, rw, rh)

    def _lasso_points_on_output_canvas(self) -> list[tuple[float, float]]:
        if self._src_img is None or self.state.rotation_deg % 360 != 0:
            return []
        src_w, src_h = self._src_img.size
        if src_w <= 0 or src_h <= 0:
            return []
        scale = max(0.01, float(self.state.img_scale))
        img_w = src_w * scale
        img_h = src_h * scale
        x0 = self.state.out_w * 0.5 - img_w * 0.5 + self.state.img_off_x
        y0 = self.state.out_h * 0.5 - img_h * 0.5 + self.state.img_off_y
        out: list[tuple[float, float]] = []
        for sx, sy in self._lasso_points:
            ox = x0 + (float(sx) / float(src_w)) * img_w
            oy = y0 + (float(sy) / float(src_h)) * img_h
            out.append((ox, oy))
        return out

    def _apply_new_selection_mask(self, incoming_mask: np.ndarray) -> None:
        op = str(self.sel_op_combo.currentData() or "replace")
        combined = combine_selection_masks(self._selection_mask, incoming_mask, op)
        self._selection_mask = combined
        rect = bounding_rect(combined)
        if rect is None:
            self.state.selection_enabled = False
            self.state.sel_x = self.state.sel_y = self.state.sel_w = self.state.sel_h = 0
            return
        self.state.selection_enabled = True
        self.state.selection_invert = False
        self.state.sel_x, self.state.sel_y, self.state.sel_w, self.state.sel_h = rect

    def _rect_state_to_mask(self) -> Optional[np.ndarray]:
        if self._src_img is None:
            return None
        w, h = self._src_img.size
        mask = np.zeros((h, w), dtype=bool)
        x0 = max(0, int(self.state.sel_x))
        y0 = max(0, int(self.state.sel_y))
        x1 = min(w, int(self.state.sel_x + self.state.sel_w))
        y1 = min(h, int(self.state.sel_y + self.state.sel_h))
        if x1 > x0 and y1 > y0:
            mask[y0:y1, x0:x1] = True
        return mask

    def _close_lasso(self) -> None:
        if self._src_img is None or len(self._lasso_points) < 3:
            return
        w, h = self._src_img.size
        incoming = polygon_mask((h, w), self._lasso_points)
        self._push_undo_state()
        self._apply_new_selection_mask(incoming)
        self._lasso_points = []
        self._sync_ui_from_state()
        self._rerender()

    def _clear_lasso(self) -> None:
        self._lasso_points = []
        self.statusBar().showMessage("Lasso points cleared.", 2000)

    def _on_adjustments_changed(self, _) -> None:
        self._push_undo_state()
        self.state.brightness = float(self.brightness_spin.value())
        self.state.contrast = float(self.contrast_spin.value())
        self.state.saturation = float(self.saturation_spin.value())
        self.state.gamma = float(self.gamma_spin.value())
        self._rerender()

    def _rotate_image(self, delta_deg: int) -> None:
        self._push_undo_state()
        self.state.rotation_deg = (int(self.state.rotation_deg) + int(delta_deg)) % 360
        self._rerender()

    def _flip_horizontal(self) -> None:
        if self._src_img is None:
            return
        self._push_undo_state()
        self._src_img = self._src_img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        self._rerender()

    def _flip_vertical(self) -> None:
        if self._src_img is None:
            return
        self._push_undo_state()
        self._src_img = self._src_img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        self._rerender()

    def _trim_transparent(self) -> None:
        if self._preview_img is None:
            return
        bbox = self._preview_img.getbbox()
        if bbox is None:
            return
        self._push_undo_state()
        cropped = self._preview_img.crop(bbox)
        self.state.out_w = int(cropped.width)
        self.state.out_h = int(cropped.height)
        self.state.img_off_x = 0.0
        self.state.img_off_y = 0.0
        self.out_w.setValue(self.state.out_w)
        self.out_h.setValue(self.state.out_h)
        self._rerender()

    def _on_nearest_toggled(self, on: bool) -> None:
        if bool(on) != self.state.nearest_neighbor:
            self._push_undo_state()
            self.state.nearest_neighbor = bool(on)
        self._rerender()

    def _on_grid_toggled(self, on: bool) -> None:
        self.state.show_pixel_grid = bool(on)
        self.canvas.show_pixel_grid = bool(on)
        self.canvas.update()

    def _save_snapshot(self) -> None:
        name, ok = QInputDialog.getText(self, "Save Snapshot", "Snapshot name:")
        if not ok or not name.strip():
            return
        nm = name.strip()
        mask_copy = None if self._selection_mask is None else self._selection_mask.copy()
        self._snapshots[nm] = (deepcopy(self.state), mask_copy, list(self._lasso_points))
        if self.snapshot_combo.findText(nm) < 0:
            self.snapshot_combo.addItem(nm)
        self.snapshot_combo.setCurrentText(nm)

    def _load_snapshot(self) -> None:
        nm = self.snapshot_combo.currentText().strip()
        if not nm or nm not in self._snapshots:
            return
        self._push_undo_state()
        st, mk, lp = self._snapshots[nm]
        self._apply_state(deepcopy(st), None if mk is None else mk.copy(), list(lp))

    def batch_export(self) -> None:
        in_dir = QFileDialog.getExistingDirectory(self, "Batch Input Folder")
        if not in_dir:
            return
        out_dir = QFileDialog.getExistingDirectory(self, "Batch Output Folder")
        if not out_dir:
            return
        count = batch_export_with_state(in_dir, out_dir, self.state)
        QMessageBox.information(self, "Batch Export", f"Exported {count} images.")

    # ---------------------------
    # State updates
    # ---------------------------
    def _on_selection_changed(self, _) -> None:
        enabled = bool(self.sel_enable_chk.isChecked())
        invert = bool(self.sel_invert_chk.isChecked())
        x = int(self.sel_x_spin.value())
        y = int(self.sel_y_spin.value())
        w = int(self.sel_w_spin.value())
        h = int(self.sel_h_spin.value())
        cur = (
            self.state.selection_enabled,
            self.state.selection_invert,
            self.state.sel_x,
            self.state.sel_y,
            self.state.sel_w,
            self.state.sel_h,
        )
        nxt = (enabled, invert, x, y, w, h)
        if cur != nxt:
            self._push_undo_state()
            self.state.selection_enabled = enabled
            self.state.selection_invert = invert
            self.state.sel_x = x
            self.state.sel_y = y
            self.state.sel_w = w
            self.state.sel_h = h
            if enabled:
                self._selection_mask = self._rect_state_to_mask()
            else:
                self._selection_mask = None
            self._rerender()

    def _on_pick_mode_changed(self, index: int) -> None:
        self._pick_mode = str(self.pick_mode_combo.itemData(index) or "eyedropper")
        if self.eyedropper_btn.isChecked():
            self.eyedropper_btn.setText(f"Pick: ON ({self._pick_mode})")
        if self._pick_mode != "lasso":
            self._lasso_points = []

    def _select_full_canvas(self) -> None:
        self._push_undo_state()
        if self._src_img is not None:
            sw, sh = self._src_img.size
        else:
            sw, sh = self.state.out_w, self.state.out_h
        self.state.selection_enabled = True
        self.state.selection_invert = False
        self.state.sel_x = 0
        self.state.sel_y = 0
        self.state.sel_w = int(sw)
        self.state.sel_h = int(sh)
        self._selection_mask = self._rect_state_to_mask()
        self._lasso_points = []
        self._sync_ui_from_state()
        self._rerender()

    def _set_hsv_controls_enabled(self, enabled: bool) -> None:
        self.hsv_h_spin.setEnabled(enabled)
        self.hsv_s_spin.setEnabled(enabled)
        self.hsv_v_spin.setEnabled(enabled)

    def _on_color_mode_changed(self, index: int) -> None:
        mode = str(self.color_mode.itemData(index) or "rgb")
        if mode != self.state.color_key_mode:
            self._push_undo_state()
            self.state.color_key_mode = mode
        self._set_hsv_controls_enabled(mode == "hsv")
        self._rerender()

    def _on_hsv_tolerance_changed(self, _) -> None:
        h = int(self.hsv_h_spin.value())
        s = int(self.hsv_s_spin.value())
        v = int(self.hsv_v_spin.value())
        if (h, s, v) != (self.state.hsv_h_tol, self.state.hsv_s_tol, self.state.hsv_v_tol):
            self._push_undo_state()
            self.state.hsv_h_tol = h
            self.state.hsv_s_tol = s
            self.state.hsv_v_tol = v
            self._rerender()

    def _on_scale_spin_changed(self, v: float) -> None:
        self._push_undo_state()
        self.state.img_scale = max(0.01, min(50.0, float(v) / 100.0))
        self._rerender()

    def _on_position_spin_changed(self, _) -> None:
        self._push_undo_state()
        self.state.img_off_x = float(self.pos_x_spin.value())
        self.state.img_off_y = float(self.pos_y_spin.value())
        self._rerender()

    def _set_tol_value(self, v: int) -> None:
        v = int(v)
        v = max(0, min(441, v))
        if not self._restoring_state and v != self.state.tolerance:
            self._push_undo_state()
        self.state.tolerance = v

        self.tol.blockSignals(True)
        self.tol.setValue(v)
        self.tol.blockSignals(False)

        self.tol_spin.blockSignals(True)
        self.tol_spin.setValue(v)
        self.tol_spin.blockSignals(False)

        self.tol_val.setText(str(v))
        self._rerender()

    def _on_tol_slider_changed(self, v: int) -> None:
        self._set_tol_value(v)

    def _on_tol_spin_changed(self, v: int) -> None:
        self._set_tol_value(v)

    def _set_grow_value(self, v: int) -> None:
        v = int(v)
        v = max(-20, min(20, v))
        if not self._restoring_state and v != self.state.mask_grow_shrink:
            self._push_undo_state()
        self.state.mask_grow_shrink = v

        self.grow.blockSignals(True)
        self.grow.setValue(v)
        self.grow.blockSignals(False)

        self.grow_spin.blockSignals(True)
        self.grow_spin.setValue(v)
        self.grow_spin.blockSignals(False)

        self.grow_val.setText(str(v))
        self._rerender()

    def _on_grow_slider_changed(self, v: int) -> None:
        self._set_grow_value(v)

    def _on_grow_spin_changed(self, v: int) -> None:
        self._set_grow_value(v)

    def _set_feather_value(self, v: int) -> None:
        v = int(v)
        v = max(0, min(20, v))
        if not self._restoring_state and v != self.state.mask_feather_radius:
            self._push_undo_state()
        self.state.mask_feather_radius = v

        self.feather.blockSignals(True)
        self.feather.setValue(v)
        self.feather.blockSignals(False)

        self.feather_spin.blockSignals(True)
        self.feather_spin.setValue(v)
        self.feather_spin.blockSignals(False)

        self.feather_val.setText(str(v))
        self._rerender()

    def _on_feather_slider_changed(self, v: int) -> None:
        self._set_feather_value(v)

    def _on_feather_spin_changed(self, v: int) -> None:
        self._set_feather_value(v)

    def _on_islands_changed(self, v: int) -> None:
        v = max(0, int(v))
        if not self._restoring_state and v != self.state.remove_islands_min_size:
            self._push_undo_state()
        self.state.remove_islands_min_size = v
        self._rerender()

    def _set_opacity_percent(self, pct: int) -> None:
        pct = int(pct)
        pct = max(0, min(100, pct))
        if not self._restoring_state and (pct / 100.0) != self.state.opacity:
            self._push_undo_state()
        self.state.opacity = pct / 100.0

        self.opacity.blockSignals(True)
        self.opacity.setValue(pct)
        self.opacity.blockSignals(False)

        self.opacity_spin.blockSignals(True)
        self.opacity_spin.setValue(pct)
        self.opacity_spin.blockSignals(False)

        self.opacity_val.setText(f"{pct}%")
        self._rerender()

    def _on_opacity_slider_changed(self, v: int) -> None:
        self._set_opacity_percent(v)

    def _on_opacity_spin_changed(self, v: int) -> None:
        self._set_opacity_percent(v)

    def _on_hq_changed(self, _) -> None:
        if not self._restoring_state and bool(self.hq.isChecked()) != self.state.high_quality_resample:
            self._push_undo_state()
        self.state.high_quality_resample = bool(self.hq.isChecked())
        self._rerender()

    def _on_eyedropper_toggled(self, on: bool) -> None:
        self.canvas.eyedropper_enabled = on
        self.eyedropper_btn.setText(f"Pick: ON ({self._pick_mode})" if on else "Pick: OFF")
        self.canvas.update()

    def _turn_on_eyedropper(self) -> None:
        self.eyedropper_btn.setChecked(True)

    def _sync_palette_from_widget(self) -> None:
        if not self._restoring_state:
            self._push_undo_state()
        items = self.palette_widget.colors()
        self.state.palette = [PaletteColor(rgb=rgb, enabled=enabled) for (rgb, enabled) in items]
        self._rerender()

    def _on_out_size_widget_changed(self) -> None:
        # Only apply immediately if auto-apply is enabled
        if getattr(self, "auto_apply_size", None) is not None and self.auto_apply_size.isChecked():
            self._apply_out_size()

    def _apply_out_size(self) -> None:
        if not self._restoring_state and (
            int(self.out_w.value()) != self.state.out_w or int(self.out_h.value()) != self.state.out_h
        ):
            self._push_undo_state()
        self.state.out_w = int(self.out_w.value())
        self.state.out_h = int(self.out_h.value())
        self._rerender()

    # ---------------------------
    # Canvas interactions
    # ---------------------------
    def _fit_image_to_canvas(self) -> None:
        if self._src_img is None:
            return
        src_w, src_h = self._src_img.size
        if src_w <= 0 or src_h <= 0:
            return
        self._push_undo_state()
        sx = self.state.out_w / float(src_w)
        sy = self.state.out_h / float(src_h)
        self.state.img_scale = max(0.01, min(50.0, min(sx, sy)))
        self.state.img_off_x = 0.0
        self.state.img_off_y = 0.0
        self._rerender()

    def _center_image(self) -> None:
        self._push_undo_state()
        self.state.img_off_x = 0.0
        self.state.img_off_y = 0.0
        self._rerender()

    def _reset_transform(self) -> None:
        self._push_undo_state()
        self.state.img_scale = 1.0
        self.state.img_off_x = 0.0
        self.state.img_off_y = 0.0
        self._rerender()

    def _move_image(self, dx_canvas_px: float, dy_canvas_px: float) -> None:
        self.state.img_off_x += float(dx_canvas_px)
        self.state.img_off_y += float(dy_canvas_px)
        self._rerender()

    def _scale_image(self, factor: float) -> None:
        self.state.img_scale = max(0.02, min(50.0, self.state.img_scale * float(factor)))
        self._rerender()

    def _pick_color_at_canvas_xy(self, cx: int, cy: int) -> None:
        """
        Given a pixel coordinate in output canvas, map it back into the transformed source image,
        then sample the original source pixel color and add to palette.
        """
        if self._src_img is None:
            return

        src_xy = self._canvas_to_source_xy(cx, cy)
        if src_xy is None:
            return
        sx, sy = src_xy

        r, g, b, a = self._src_img.getpixel((sx, sy))
        if self._pick_mode == "eyedropper":
            self.palette_widget.add_color((int(r), int(g), int(b)))
            self._sync_palette_from_widget()
            return

        if self._pick_mode == "lasso":
            self._append_lasso_point(sx, sy)
            if len(self._lasso_points) >= 2:
                xs = [p[0] for p in self._lasso_points]
                ys = [p[1] for p in self._lasso_points]
                self.state.selection_enabled = True
                self.state.selection_invert = False
                self.state.sel_x = int(min(xs))
                self.state.sel_y = int(min(ys))
                self.state.sel_w = int(max(xs) - min(xs) + 1)
                self.state.sel_h = int(max(ys) - min(ys) + 1)
                self._rerender()
            self.statusBar().showMessage(
                f"Lasso points: {len(self._lasso_points)} (click Close/Apply Lasso to finish).",
                1500,
            )
            return

        arr = np.array(self._src_img.convert("RGB"), dtype=np.uint8)
        tol = int(self.sel_pick_tol_spin.value())
        if self._pick_mode == "wand":
            sel_mask = magic_wand_mask(
                arr,
                (sx, sy),
                tolerance=tol,
                contiguous=bool(self.wand_contig_chk.isChecked()),
            )
        else:
            sel_mask = color_range_mask(arr, (sx, sy), tolerance=tol)

        rect = bounding_rect(sel_mask)
        if rect is None:
            return

        self._push_undo_state()
        self._apply_new_selection_mask(sel_mask)
        self._sync_ui_from_state()
        self._rerender()

    def _pick_drag_at_canvas_xy(self, cx: int, cy: int) -> None:
        if self._pick_mode != "lasso" or self._src_img is None:
            return
        src = self._canvas_to_source_xy(cx, cy)
        if src is None:
            return
        sx, sy = src
        self._append_lasso_point(sx, sy)
        if len(self._lasso_points) >= 2:
            xs = [p[0] for p in self._lasso_points]
            ys = [p[1] for p in self._lasso_points]
            self.state.selection_enabled = True
            self.state.selection_invert = False
            self.state.sel_x = int(min(xs))
            self.state.sel_y = int(min(ys))
            self.state.sel_w = int(max(xs) - min(xs) + 1)
            self.state.sel_h = int(max(ys) - min(ys) + 1)
            self._rerender()

    def _pick_finish(self) -> None:
        # Lasso is explicitly applied by button or Enter.
        return

    def _append_lasso_point(self, sx: int, sy: int) -> None:
        if self._lasso_points:
            lx, ly = self._lasso_points[-1]
            if abs(int(sx) - int(lx)) + abs(int(sy) - int(ly)) < 2:
                return
        self._lasso_points.append((int(sx), int(sy)))

    def _canvas_to_source_xy(self, cx: int, cy: int) -> Optional[tuple[int, int]]:
        if self._src_img is None:
            return None
        out_w, out_h = self.state.out_w, self.state.out_h
        src_w, src_h = self._src_img.size
        scale = max(0.01, self.state.img_scale)
        img_w = src_w * scale
        img_h = src_h * scale
        canvas_cx = out_w * 0.5
        canvas_cy = out_h * 0.5
        x0 = canvas_cx - img_w * 0.5 + self.state.img_off_x
        y0 = canvas_cy - img_h * 0.5 + self.state.img_off_y
        if cx < x0 or cy < y0 or cx >= x0 + img_w or cy >= y0 + img_h:
            return None
        u = (cx - x0) / img_w
        v = (cy - y0) / img_h
        sx = max(0, min(src_w - 1, int(u * src_w)))
        sy = max(0, min(src_h - 1, int(v * src_h)))
        return (sx, sy)

    # ---------------------------
    # Rendering
    # ---------------------------
    def _rerender(self) -> None:
        compare_before = getattr(self, "compare_chk", None) is not None and self.compare_chk.isChecked()
        self._preview_img = composite_to_canvas(
            src_rgba_pil=self._src_img,
            out_size=(self.state.out_w, self.state.out_h),
            img_scale=self.state.img_scale,
            img_offset=(self.state.img_off_x, self.state.img_off_y),
            rotation_deg=self.state.rotation_deg,
            palette_rgbs=self.state.enabled_palette_rgbs(),
            tolerance=0 if compare_before else self.state.tolerance,
            opacity=self.state.opacity,
            color_key_mode=self.state.color_key_mode,
            hsv_h_tol=self.state.hsv_h_tol,
            hsv_s_tol=self.state.hsv_s_tol,
            hsv_v_tol=self.state.hsv_v_tol,
            mask_grow_shrink=0 if compare_before else self.state.mask_grow_shrink,
            mask_feather_radius=0 if compare_before else self.state.mask_feather_radius,
            remove_islands_min_size=0 if compare_before else self.state.remove_islands_min_size,
            high_quality=self.state.high_quality_resample,
            nearest_neighbor=self.state.nearest_neighbor,
            brightness=1.0 if compare_before else self.state.brightness,
            contrast=1.0 if compare_before else self.state.contrast,
            saturation=1.0 if compare_before else self.state.saturation,
            gamma=1.0 if compare_before else self.state.gamma,
            selection_enabled=False if compare_before else self.state.selection_enabled,
            selection_invert=self.state.selection_invert,
            selection_rect=(self.state.sel_x, self.state.sel_y, self.state.sel_w, self.state.sel_h),
            selection_mask=None if compare_before else self._selection_mask,
        )
        qimg = pil_rgba_to_qimage(self._preview_img)
        self.canvas.set_preview(qimg, (self.state.out_w, self.state.out_h))
        self.canvas.set_selection_overlay(
            enabled=bool(self.state.selection_enabled and self.state.sel_w > 0 and self.state.sel_h > 0),
            rect_canvas=self._selection_rect_on_output_canvas(),
            invert=bool(self.state.selection_invert),
            lasso_points_canvas=self._lasso_points_on_output_canvas(),
        )
        self.scale_spin.blockSignals(True)
        self.scale_spin.setValue(self.state.img_scale * 100.0)
        self.scale_spin.blockSignals(False)
        self.pos_x_spin.blockSignals(True)
        self.pos_y_spin.blockSignals(True)
        self.pos_x_spin.setValue(self.state.img_off_x)
        self.pos_y_spin.setValue(self.state.img_off_y)
        self.pos_x_spin.blockSignals(False)
        self.pos_y_spin.blockSignals(False)
        self._update_undo_redo_actions()
        self._update_status()

