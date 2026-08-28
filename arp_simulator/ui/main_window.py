from __future__ import annotations

import queue
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStyle,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..controller import SimulationController
from ..models import ArpOpcode, CacheChange, EventType, HostConfig, SimulationEvent
from .dialogs import HostDialog
from .topology_view import TopologyView


APP_STYLE = """
QMainWindow, QWidget#root { background: #f3f5f7; color: #17202a; }
QFrame#header { background: #ffffff; border-bottom: 1px solid #d9e0e6; }
QFrame#sidePanel, QFrame#detailPanel, QFrame#logPanel {
    background: #ffffff; border: 1px solid #d9e0e6; border-radius: 6px;
}
QLabel#appTitle { font-size: 20px; font-weight: 700; color: #16283a; }
QLabel#sectionTitle { font-size: 13px; font-weight: 700; color: #23384d; }
QLabel#muted { color: #748391; font-size: 12px; }
QLabel#hostName { font-size: 18px; font-weight: 700; color: #172b3d; }
QLabel#hostAddress { color: #536575; font-family: Menlo, Consolas, monospace; }
QLabel#legendRequest { color: #b85e00; font-weight: 600; }
QLabel#legendReply { color: #16745b; font-weight: 600; }
QPushButton {
    min-height: 30px; padding: 0 11px; border: 1px solid #cbd4dc;
    border-radius: 5px; background: #ffffff; color: #223344;
}
QPushButton:hover { background: #f0f4f7; border-color: #98a9b8; }
QPushButton:pressed { background: #e4eaef; }
QPushButton:disabled { color: #9aa6b0; background: #f4f6f8; border-color: #e0e5e9; }
QPushButton#primaryButton { background: #176b87; border-color: #176b87; color: #ffffff; font-weight: 700; }
QPushButton#primaryButton:hover { background: #125a73; }
QComboBox, QDoubleSpinBox {
    min-height: 31px; padding: 0 8px; border: 1px solid #cbd4dc;
    border-radius: 5px; background: #ffffff;
}
QComboBox:focus, QDoubleSpinBox:focus { border-color: #2a7f9e; }
QComboBox QAbstractItemView {
    background: #ffffff; color: #17202a; border: 1px solid #98a9b8;
    outline: 0; selection-background-color: #dcecf2; selection-color: #17202a;
}
QComboBox QAbstractItemView::item { min-height: 30px; padding: 3px 9px; }
QComboBox QAbstractItemView::item:hover { background: #dcecf2; color: #17202a; }
QTabWidget::pane { border: 1px solid #d9e0e6; background: #ffffff; }
QTabBar::tab { padding: 8px 18px; color: #5b6d7d; background: #eef2f5; }
QTabBar::tab:selected { color: #176b87; background: #ffffff; font-weight: 700; }
QTableWidget, QListWidget, QTextEdit {
    border: 1px solid #d9e0e6; background: #ffffff; alternate-background-color: #f7f9fa;
    selection-background-color: #dcecf2; selection-color: #17202a;
}
QHeaderView::section {
    background: #eef2f5; color: #3f5365; border: 0; border-right: 1px solid #d9e0e6;
    border-bottom: 1px solid #d9e0e6; padding: 7px; font-weight: 700;
}
QListWidget::item { min-height: 25px; padding: 2px 6px; border-bottom: 1px solid #edf0f2; }
QSplitter::handle { background: transparent; width: 6px; height: 6px; }
"""

COMBO_POPUP_STYLE = """
QListView {
    background: #ffffff; color: #17202a; border: 1px solid #98a9b8;
    outline: 0; padding: 2px;
}
QListView::item { color: #17202a; background: #ffffff; min-height: 30px; padding: 3px 9px; }
QListView::item:hover { color: #17202a; background: #dcecf2; }
QListView::item:selected { color: #17202a; background: #dcecf2; }
QListView::item:selected:active { color: #17202a; background: #dcecf2; }
QListView::item:selected:!active { color: #17202a; background: #dcecf2; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ARP 地址解析协议仿真器")
        self.resize(1480, 920)
        self.setMinimumSize(1180, 720)
        self.controller = SimulationController()
        self.selected_host_id: str | None = None
        self._build_ui()
        self.setStyleSheet(APP_STYLE)
        self._refresh_hosts()
        self._update_runtime_state("未启动")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._drain_events)
        self.timer.start(80)

    def _icon(self, icon: QStyle.StandardPixmap):
        return self.style().standardIcon(icon)

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(62)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 10, 18, 10)
        title = QLabel("ARP 地址解析协议仿真器")
        title.setObjectName("appTitle")
        header_layout.addWidget(title)
        header_layout.addStretch()
        self.host_count_label = QLabel("4 台主机")
        self.host_count_label.setObjectName("muted")
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setMinimumWidth(78)
        header_layout.addWidget(self.host_count_label)
        header_layout.addSpacing(14)
        header_layout.addWidget(self.status_label)
        layout.addWidget(header)

        body_splitter = QSplitter(Qt.Orientation.Horizontal)
        body_splitter.setChildrenCollapsible(False)
        body_splitter.setContentsMargins(10, 10, 10, 4)
        control_panel = self._build_control_panel()
        control_scroll = QScrollArea()
        control_scroll.setWidget(control_panel)
        control_scroll.setWidgetResizable(True)
        control_scroll.setFrameShape(QFrame.Shape.NoFrame)
        control_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        control_scroll.setMinimumWidth(270)
        control_scroll.setMaximumWidth(330)
        body_splitter.addWidget(control_scroll)
        body_splitter.addWidget(self._build_topology_panel())
        body_splitter.addWidget(self._build_detail_panel())
        body_splitter.setStretchFactor(0, 0)
        body_splitter.setStretchFactor(1, 1)
        body_splitter.setStretchFactor(2, 0)
        body_splitter.setSizes([285, 735, 430])
        layout.addWidget(body_splitter, 1)
        layout.addWidget(self._build_log_panel(), 0)
        self._connect_actions()

    def _build_control_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("sidePanel")
        panel.setMinimumWidth(270)
        panel.setMaximumWidth(330)
        panel.setMinimumHeight(520)
        box = QVBoxLayout(panel)
        box.setContentsMargins(15, 15, 15, 15)
        box.setSpacing(12)

        section = QLabel("地址解析")
        section.setObjectName("sectionTitle")
        box.addWidget(section)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setVerticalSpacing(9)
        self.source_combo = QComboBox()
        self.target_combo = QComboBox()
        self.target_combo.setEditable(True)
        for combo in (self.source_combo, self.target_combo):
            popup = combo.view()
            popup.setStyleSheet(COMBO_POPUP_STYLE)
            palette = popup.palette()
            palette.setColor(QPalette.ColorRole.Highlight, QColor("#dcecf2"))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#17202a"))
            popup.setPalette(palette)
        self.target_combo.setToolTip("可直接输入一个局域网内不存在的 IPv4 地址以演示请求超时")
        form.addRow("源主机", self.source_combo)
        form.addRow("目标 IP", self.target_combo)
        box.addLayout(form)
        self.resolve_btn = QPushButton("发起 ARP 请求")
        self.resolve_btn.setObjectName("primaryButton")
        self.resolve_btn.setIcon(self._icon(QStyle.StandardPixmap.SP_ArrowForward))
        box.addWidget(self.resolve_btn)

        box.addSpacing(5)
        section = QLabel("运行控制")
        section.setObjectName("sectionTitle")
        box.addWidget(section)
        controls = QHBoxLayout()
        controls.setSpacing(6)
        self.start_btn = QPushButton("启动")
        self.start_btn.setIcon(self._icon(QStyle.StandardPixmap.SP_MediaPlay))
        self.pause_btn = QPushButton()
        self.pause_btn.setIcon(self._icon(QStyle.StandardPixmap.SP_MediaPause))
        self.pause_btn.setToolTip("暂停仿真")
        self.pause_btn.setFixedWidth(38)
        self.resume_btn = QPushButton()
        self.resume_btn.setIcon(self._icon(QStyle.StandardPixmap.SP_MediaPlay))
        self.resume_btn.setToolTip("继续仿真")
        self.resume_btn.setFixedWidth(38)
        self.reset_btn = QPushButton()
        self.reset_btn.setIcon(self._icon(QStyle.StandardPixmap.SP_BrowserReload))
        self.reset_btn.setToolTip("重置所有主机、缓存与线程")
        self.reset_btn.setFixedWidth(38)
        controls.addWidget(self.start_btn, 1)
        controls.addWidget(self.pause_btn)
        controls.addWidget(self.resume_btn)
        controls.addWidget(self.reset_btn)
        box.addLayout(controls)

        aging_form = QFormLayout()
        self.aging_spin = QDoubleSpinBox()
        self.aging_spin.setRange(5, 120)
        self.aging_spin.setValue(30)
        self.aging_spin.setSuffix(" 秒")
        aging_form.addRow("缓存老化", self.aging_spin)
        box.addLayout(aging_form)
        self.aging_btn = QPushButton("应用老化时间")
        box.addWidget(self.aging_btn)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color: #d9e0e6")
        box.addWidget(divider)
        section = QLabel("主机管理")
        section.setObjectName("sectionTitle")
        box.addWidget(section)
        self.add_btn = QPushButton("添加主机")
        self.add_btn.setIcon(self._icon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        self.edit_btn = QPushButton("编辑选中主机")
        self.edit_btn.setIcon(self._icon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        box.addWidget(self.add_btn)
        box.addWidget(self.edit_btn)
        box.addStretch()
        return panel

    def _build_topology_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("sidePanel")
        box = QVBoxLayout(panel)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)
        bar = QWidget()
        bar.setFixedHeight(46)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(13, 0, 13, 0)
        title = QLabel("局域网拓扑")
        title.setObjectName("sectionTitle")
        request_legend = QLabel("● ARP 请求")
        request_legend.setObjectName("legendRequest")
        reply_legend = QLabel("● ARP 应答")
        reply_legend.setObjectName("legendReply")
        self.zoom_out_btn = QPushButton("−")
        self.zoom_out_btn.setToolTip("缩小拓扑")
        self.zoom_out_btn.setFixedSize(30, 30)
        self.zoom_label = QLabel("100%")
        self.zoom_label.setObjectName("muted")
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_label.setMinimumWidth(42)
        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setToolTip("放大拓扑")
        self.zoom_in_btn.setFixedSize(30, 30)
        self.fit_view_btn = QPushButton()
        self.fit_view_btn.setIcon(self._icon(QStyle.StandardPixmap.SP_TitleBarMaxButton))
        self.fit_view_btn.setToolTip("适应窗口")
        self.fit_view_btn.setFixedSize(30, 30)
        self.layout_btn = QPushButton()
        self.layout_btn.setIcon(self._icon(QStyle.StandardPixmap.SP_BrowserReload))
        self.layout_btn.setToolTip("恢复默认拓扑布局")
        self.layout_btn.setFixedSize(30, 30)
        bar_layout.addWidget(title)
        bar_layout.addStretch()
        bar_layout.addWidget(self.zoom_out_btn)
        bar_layout.addWidget(self.zoom_label)
        bar_layout.addWidget(self.zoom_in_btn)
        bar_layout.addWidget(self.fit_view_btn)
        bar_layout.addWidget(self.layout_btn)
        bar_layout.addSpacing(14)
        bar_layout.addWidget(request_legend)
        bar_layout.addSpacing(12)
        bar_layout.addWidget(reply_legend)
        box.addWidget(bar)
        self.topology = TopologyView()
        self.zoom_out_btn.clicked.connect(self.topology.zoom_out)
        self.zoom_in_btn.clicked.connect(self.topology.zoom_in)
        self.fit_view_btn.clicked.connect(self.topology.reset_view)
        self.layout_btn.clicked.connect(self.topology.reset_layout)
        self.topology.zoom_changed.connect(self._update_zoom_controls)
        self._update_zoom_controls(100)
        box.addWidget(self.topology, 1)
        return panel

    def _update_zoom_controls(self, percent: int) -> None:
        self.zoom_label.setText(f"{percent}%")
        self.zoom_out_btn.setEnabled(percent > 100)
        self.zoom_in_btn.setEnabled(percent < 300)

    def _build_detail_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("detailPanel")
        panel.setMinimumWidth(390)
        box = QVBoxLayout(panel)
        box.setContentsMargins(14, 14, 14, 14)
        box.setSpacing(10)

        header = QHBoxLayout()
        identity = QVBoxLayout()
        identity.setSpacing(3)
        self.host_name_label = QLabel("请选择主机")
        self.host_name_label.setObjectName("hostName")
        self.host_address_label = QLabel("点击拓扑中的主机节点")
        self.host_address_label.setObjectName("hostAddress")
        identity.addWidget(self.host_name_label)
        identity.addWidget(self.host_address_label)
        self.host_state_label = QLabel("空闲")
        self.host_state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.host_state_label.setMinimumWidth(58)
        self._style_host_state("IDLE")
        header.addLayout(identity, 1)
        header.addWidget(self.host_state_label)
        box.addLayout(header)

        tabs = QTabWidget()
        cache_page = QWidget()
        cache_layout = QVBoxLayout(cache_page)
        cache_layout.setContentsMargins(0, 8, 0, 0)
        self.cache_table = QTableWidget(0, 5)
        self.cache_table.setHorizontalHeaderLabels(["目标 IP", "目标 MAC", "已学习", "剩余", "状态"])
        self.cache_table.setAlternatingRowColors(True)
        self.cache_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.cache_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header_view = self.cache_table.horizontalHeader()
        header_view.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.cache_table.verticalHeader().setVisible(False)
        cache_layout.addWidget(self.cache_table)
        tabs.addTab(cache_page, "ARP 缓存")

        packet_page = QWidget()
        packet_layout = QVBoxLayout(packet_page)
        packet_layout.setContentsMargins(0, 8, 0, 0)
        self.packet_detail = QTextEdit()
        self.packet_detail.setReadOnly(True)
        self.packet_detail.setPlaceholderText("点击底部的请求或应答日志查看完整报文字段")
        packet_layout.addWidget(self.packet_detail)
        tabs.addTab(packet_page, "报文详情")
        self.detail_tabs = tabs
        box.addWidget(tabs, 1)
        return panel

    def _build_log_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("logPanel")
        panel.setMinimumHeight(270)
        panel.setMaximumHeight(350)
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(12, 8, 12, 10)
        outer.setSpacing(6)
        header = QHBoxLayout()
        title = QLabel("协议事件时间线")
        title.setObjectName("sectionTitle")
        self.event_count_label = QLabel("0 条事件")
        self.event_count_label.setObjectName("muted")
        clear_btn = QPushButton()
        clear_btn.setIcon(self._icon(QStyle.StandardPixmap.SP_TrashIcon))
        clear_btn.setToolTip("清空日志")
        clear_btn.setFixedSize(34, 30)
        clear_btn.clicked.connect(self._clear_log)
        header.addWidget(title)
        header.addWidget(self.event_count_label)
        header.addStretch()
        header.addWidget(clear_btn)
        outer.addLayout(header)
        self.log_list = QListWidget()
        self.log_list.setAlternatingRowColors(True)
        self.log_list.itemClicked.connect(self._show_packet_detail)
        outer.addWidget(self.log_list)
        return panel

    def _connect_actions(self):
        self.start_btn.clicked.connect(self._start)
        self.pause_btn.clicked.connect(self._pause)
        self.resume_btn.clicked.connect(self._resume)
        self.reset_btn.clicked.connect(self._reset)
        self.resolve_btn.clicked.connect(self._resolve)
        self.aging_btn.clicked.connect(self._set_aging)
        self.add_btn.clicked.connect(self._add_host)
        self.edit_btn.clicked.connect(self._edit_host)
        self.source_combo.currentIndexChanged.connect(self._source_changed)
        self.topology.host_clicked.connect(self._select_host)
        self.topology.host_moved.connect(self._host_moved)
        self.topology.host_edit_requested.connect(self._edit_host_from_topology)
        self.topology.host_source_requested.connect(self._set_source_from_topology)
        self.topology.host_target_requested.connect(self._set_target_from_topology)

    def _refresh_hosts(self):
        configs = list(self.controller.configs.values())
        self.topology.set_hosts(configs)
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        self.source_combo.addItems([f"{c.name} ({c.ip})" for c in configs])
        self.source_combo.blockSignals(False)
        self.host_count_label.setText(f"{len(configs)} 台主机")
        self.add_btn.setEnabled(len(configs) < 6)
        self._source_changed()
        if self.selected_host_id not in self.controller.configs:
            self._select_host(configs[0].host_id if configs else None)

    def _source_changed(self):
        self.target_combo.clear()
        source_index = self.source_combo.currentIndex()
        for config in self.controller.configs.values():
            self.target_combo.addItem(config.ip, config.ip)
        if self.target_combo.count() > 1:
            self.target_combo.setCurrentIndex(1 if source_index == 0 else 0)

    def _update_runtime_state(self, text: str):
        self.status_label.setText(text)
        styles = {
            "运行中": ("#dff3ea", "#176b52", "#98d1bd"),
            "已暂停": ("#fff1d8", "#925300", "#e8c477"),
            "未启动": ("#edf1f4", "#61717f", "#cbd4dc"),
        }
        bg, fg, border = styles[text]
        self.status_label.setStyleSheet(
            f"background:{bg}; color:{fg}; border:1px solid {border}; border-radius:5px; padding:5px 10px; font-weight:700;"
        )
        running = self.controller.running
        paused = self.controller.paused
        self.start_btn.setEnabled(not running)
        self.pause_btn.setEnabled(running and not paused)
        self.resume_btn.setEnabled(running and paused)
        self.reset_btn.setEnabled(running)
        self.resolve_btn.setEnabled(running and not paused)

    def _start(self):
        self.controller.start()
        self._update_runtime_state("运行中")

    def _pause(self):
        self.controller.pause()
        self._update_runtime_state("已暂停")

    def _resume(self):
        self.controller.resume()
        self._update_runtime_state("运行中")

    def _reset(self):
        self.controller.reset()
        self._refresh_hosts()
        self._clear_log()
        self._update_runtime_state("运行中")

    def _resolve(self):
        if self.source_combo.currentIndex() < 0:
            return
        host_id = list(self.controller.configs)[self.source_combo.currentIndex()]
        target_ip = self.target_combo.currentData() or self.target_combo.currentText().strip()
        try:
            result = self.controller.resolve(host_id, target_ip)
            if result == "SELF":
                self._notice("目标 IP 属于源主机，无需 ARP 解析")
            elif result == "PENDING":
                self._notice("该目标的 ARP 请求正在等待应答")
        except (ValueError, RuntimeError) as exc:
            self._notice(str(exc))

    def _set_aging(self):
        try:
            self.controller.set_aging_seconds(self.aging_spin.value())
            self.aging_btn.setText("已应用")
            QTimer.singleShot(900, lambda: self.aging_btn.setText("应用老化时间"))
        except ValueError as exc:
            self._notice(str(exc))

    def _add_host(self):
        dialog = HostDialog(self)
        if dialog.exec():
            try:
                self.controller.add_host(*dialog.values())
                self._refresh_hosts()
            except ValueError as exc:
                self._notice(str(exc))

    def _edit_host(self):
        config = self.controller.configs.get(self.selected_host_id or "")
        if not config:
            self._notice("请先在拓扑中选择主机")
            return
        dialog = HostDialog(self, config)
        if dialog.exec():
            try:
                self.controller.update_host(config.host_id, *dialog.values())
                self._refresh_hosts()
            except ValueError as exc:
                self._notice(str(exc))

    def _edit_host_from_topology(self, host_id: str):
        self._select_host(host_id)
        self._edit_host()

    def _set_source_from_topology(self, host_id: str):
        host_ids = list(self.controller.configs)
        if host_id in host_ids:
            self.source_combo.setCurrentIndex(host_ids.index(host_id))
            self._select_host(host_id)

    def _set_target_from_topology(self, host_id: str):
        config = self.controller.configs.get(host_id)
        if not config:
            return
        index = self.target_combo.findData(config.ip)
        if index >= 0:
            self.target_combo.setCurrentIndex(index)
        else:
            self.target_combo.setEditText(config.ip)

    def _select_host(self, host_id: str | None):
        if not host_id:
            return
        self.selected_host_id = host_id
        self.topology.select_host(host_id)
        config = self.controller.configs[host_id]
        self.host_name_label.setText(config.name)
        self.host_address_label.setText(f"{config.ip}\n{config.mac}")
        status = self.controller.hosts.get(host_id).status if host_id in self.controller.hosts else "IDLE"
        self._style_host_state(status)
        self._refresh_cache()

    def _style_host_state(self, status: str):
        names = {
            "IDLE": "空闲", "BROADCASTING": "广播中", "REPLYING": "应答中",
            "RESOLVED": "已解析", "PAUSED": "已暂停", "TIMEOUT": "超时",
        }
        colors = {
            "BROADCASTING": ("#fff1d8", "#925300"), "REPLYING": ("#dff3ea", "#176b52"),
            "RESOLVED": ("#dff3ea", "#176b52"), "PAUSED": ("#edf1f4", "#61717f"),
            "TIMEOUT": ("#fce7e5", "#a33b37"), "IDLE": ("#e6f1f5", "#176b87"),
        }
        bg, fg = colors.get(status, colors["IDLE"])
        self.host_state_label.setText(names.get(status, status))
        self.host_state_label.setStyleSheet(
            f"background:{bg}; color:{fg}; border-radius:5px; padding:5px 8px; font-weight:700;"
        )

    def _host_moved(self, host_id: str, x: float, y: float):
        config = self.controller.configs.get(host_id)
        if config:
            self.controller.configs[host_id] = HostConfig(config.host_id, config.name, config.ip, config.mac, x, y)
            self.topology.update_positions()

    def _refresh_cache(self):
        entries = self.controller.cache_snapshot(self.selected_host_id or "")
        self.cache_table.setRowCount(len(entries))
        now = time.monotonic()
        state_names = {
            CacheChange.MISS: "未命中",
            CacheChange.NEW: "新增", CacheChange.UPDATED: "更新",
            CacheChange.HIT: "命中", CacheChange.EXPIRED: "超时",
        }
        for row, entry in enumerate(entries):
            values = [entry.ip, entry.mac, f"{now - entry.learned_at:.1f}s 前",
                      f"{max(0, self.controller.aging_seconds - (now - entry.last_seen)):.1f}s",
                      state_names.get(entry.state, entry.state.value)]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col in (2, 3, 4):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.cache_table.setItem(row, col, item)

    def _drain_events(self):
        self._refresh_cache()
        while True:
            try:
                event = self.controller.events.get_nowait()
            except queue.Empty:
                break
            self._handle_event(event)

    def _append_log(self, text: str, color: str, packet=None):
        item = QListWidgetItem(text)
        item.setForeground(QColor(color))
        if packet is not None:
            item.setData(Qt.ItemDataRole.UserRole, packet)
        self.log_list.addItem(item)
        self.log_list.scrollToBottom()
        self.event_count_label.setText(f"{self.log_list.count()} 条事件")

    def _host_name(self, host_id: str | None) -> str:
        if not host_id:
            return "广播"
        config = self.controller.configs.get(host_id)
        return config.name if config else host_id

    def _handle_event(self, event: SimulationEvent):
        payload = event.payload
        now_text = time.strftime("%H:%M:%S")
        if event.event_type is EventType.HOST_STATUS:
            status = payload["status"]
            self.topology.set_host_status(event.host_id, status)
            if event.host_id == self.selected_host_id:
                self._style_host_state(status)
            status_messages = {
                "BROADCASTING": "开始广播 ARP 请求",
                "REPLYING": "目标 IP 匹配，准备单播 ARP 应答",
                "RESOLVED": "收到 ARP 应答，地址解析完成",
            }
            if status in status_messages:
                color = "#b85e00" if status == "BROADCASTING" else "#16745b"
                self._append_log(f"{now_text}   {self._host_name(event.host_id)} · {status_messages[status]}", color)
            if status in {"REPLYING", "RESOLVED", "TIMEOUT"}:
                QTimer.singleShot(1600, lambda host_id=event.host_id: self._reset_host_visual(host_id))
        elif event.event_type in (EventType.PACKET_SENT, EventType.PACKET_RECEIVED):
            packet = payload["packet"]
            mode = payload.get("mode", "")
            direction = "发送" if event.event_type is EventType.PACKET_SENT else "接收"
            mode_name = "广播" if mode == "broadcast" else "单播"
            opcode_name = "ARP 请求" if packet.opcode is ArpOpcode.REQUEST else "ARP 应答"
            color = "#b85e00" if packet.opcode is ArpOpcode.REQUEST else "#16745b"
            self._append_log(
                f"{now_text}   #{packet.packet_id:<3}   {self._host_name(event.host_id)} {direction} {opcode_name} · {mode_name}",
                color, packet,
            )
            if event.event_type is EventType.PACKET_SENT:
                self.topology.animate_packet(packet, mode, self.controller.configs)
        elif event.event_type is EventType.CACHE_CHANGED:
            entry = payload.get("entry")
            if payload["change"] == "MISS":
                self._append_log(
                    f"{now_text}   {self._host_name(event.host_id)} 缓存未命中 · 查询 {payload['target_ip']}",
                    "#b85e00",
                )
            elif entry:
                names = {"NEW": "新增", "UPDATED": "更新", "HIT": "命中", "EXPIRED": "超时删除"}
                self._append_log(
                    f"{now_text}   {self._host_name(event.host_id)} 缓存{names.get(payload['change'], payload['change'])} · {entry.ip} → {entry.mac}",
                    "#476170",
                )
        elif event.event_type is EventType.ERROR:
            self._append_log(f"{now_text}   {self._host_name(event.host_id)} 错误 · {payload['message']}", "#a33b37")

    def _reset_host_visual(self, host_id: str):
        self.topology.set_host_status(host_id, "IDLE")
        if host_id == self.selected_host_id:
            self._style_host_state("IDLE")

    def _show_packet_detail(self, item: QListWidgetItem):
        packet = item.data(Qt.ItemDataRole.UserRole)
        if not packet:
            return
        opcode_name = "ARP 请求 (REQUEST)" if packet.opcode is ArpOpcode.REQUEST else "ARP 应答 (REPLY)"
        self.packet_detail.setPlainText("\n".join([
            f"报文编号        #{packet.packet_id}", f"操作类型        {opcode_name}", "",
            f"发送者 IP       {packet.sender_ip}", f"发送者 MAC      {packet.sender_mac}", "",
            f"目标 IP         {packet.target_ip}", f"目标 MAC        {packet.target_mac}", "",
            f"源主机          {self._host_name(packet.source_host_id)}",
            f"传输目标        {self._host_name(packet.destination_host_id) if packet.destination_host_id else '所有主机（广播）'}",
        ]))
        self.detail_tabs.setCurrentIndex(1)

    def _clear_log(self):
        self.log_list.clear()
        self.event_count_label.setText("0 条事件")
        self.packet_detail.clear()

    def _notice(self, text: str):
        QMessageBox.warning(self, "操作提示", text)

    def closeEvent(self, event):
        self.timer.stop()
        self.controller.close()
        event.accept()
