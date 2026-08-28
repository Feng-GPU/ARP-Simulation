from __future__ import annotations

import math

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QMenu,
)

from ..models import HostConfig


class RoundedRectItem(QGraphicsRectItem):
    def __init__(self, x: float, y: float, width: float, height: float, radius: float):
        super().__init__(x, y, width, height)
        self.radius = radius

    def paint(self, painter, option, widget=None):
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawRoundedRect(self.rect(), self.radius, self.radius)


class LinkItem(QGraphicsLineItem):
    def __init__(self):
        super().__init__()
        self.setAcceptHoverEvents(True)
        self.setToolTip("共享局域网链路")
        self.setZValue(-1)
        self._set_hovered(False)

    def _set_hovered(self, hovered: bool) -> None:
        color = QColor("#53758d") if hovered else QColor("#385267")
        width = 2.0 if hovered else 1.2
        self.setPen(QPen(color, width, Qt.PenStyle.DashLine))

    def hoverEnterEvent(self, event):
        self._set_hovered(True)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._set_hovered(False)
        super().hoverLeaveEvent(event)


class LanHub(RoundedRectItem):
    WIDTH = 160
    HEIGHT = 56

    def __init__(self, moved):
        super().__init__(0, 0, self.WIDTH, self.HEIGHT, 8)
        self._moved = moved
        self._activity = "IDLE"
        self.setPos(300, 267)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setToolTip("拖动可调整共享局域网总线位置")
        self.title = QGraphicsSimpleTextItem("共享局域网总线", self)
        self.title.setFont(QFont("Helvetica", 11, QFont.Weight.Bold))
        self.title.setPos(22, 9)
        self.subtitle = QGraphicsSimpleTextItem("Virtual LAN Bus", self)
        self.subtitle.setFont(QFont("Helvetica", 8))
        self.subtitle.setPos(38, 31)
        self.set_activity("IDLE")

    def center_point(self) -> QPointF:
        return self.sceneBoundingRect().center()

    def set_activity(self, activity: str) -> None:
        self._activity = activity
        styles = {
            "REQUEST": ("#4b341e", "#d9842d", "#ffe0b2", "#d9a66a"),
            "REPLY": ("#173f38", "#36a987", "#d6f3e9", "#75bca8"),
            "IDLE": ("#203242", "#617789", "#e2eaf0", "#8fa3b3"),
        }
        fill, border, title, subtitle = styles.get(activity, styles["IDLE"])
        self.setBrush(QBrush(QColor(fill)))
        self.setPen(QPen(QColor(border), 2 if activity != "IDLE" else 1.5))
        self.title.setBrush(QBrush(QColor(title)))
        self.subtitle.setBrush(QBrush(QColor(subtitle)))

    def hoverEnterEvent(self, event):
        if self._activity == "IDLE":
            self.setPen(QPen(QColor("#8ba3b5"), 2))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.set_activity(self._activity)
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self._moved()
        return super().itemChange(change, value)


class HostNode(RoundedRectItem):
    WIDTH = 178
    HEIGHT = 96

    def __init__(self, config: HostConfig, clicked, moved, edit_requested, source_requested, target_requested):
        super().__init__(-self.WIDTH / 2, -self.HEIGHT / 2, self.WIDTH, self.HEIGHT, 8)
        self.host_id = config.host_id
        self._clicked = clicked
        self._moved = moved
        self._edit_requested = edit_requested
        self._source_requested = source_requested
        self._target_requested = target_requested
        self._status = "IDLE"
        self._hovered = False
        self.setBrush(QBrush(QColor("#17344c")))
        self.setPen(QPen(QColor("#4c8baa"), 1.6))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.SizeAllCursor)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 95))
        self.setGraphicsEffect(shadow)
        self.status_dot = QGraphicsEllipseItem(-75, -34, 9, 9, self)
        self.status_dot.setBrush(QBrush(QColor("#55b6d4")))
        self.status_dot.setPen(QPen(Qt.PenStyle.NoPen))
        self.name_label = QGraphicsSimpleTextItem(self)
        self.name_label.setBrush(QBrush(QColor("#f4f8fa")))
        self.name_label.setFont(QFont("Helvetica", 11, QFont.Weight.Bold))
        self.name_label.setPos(-61, -39)
        self.status_label = QGraphicsSimpleTextItem(self)
        self.status_label.setFont(QFont("Helvetica", 7, QFont.Weight.Bold))
        self.status_label.setPos(47, -37)
        self.divider = QGraphicsLineItem(-75, -15, 75, -15, self)
        self.divider.setPen(QPen(QColor("#36556b"), 1))
        self.address_label = QGraphicsSimpleTextItem(self)
        self.address_label.setBrush(QBrush(QColor("#b7cad6")))
        self.address_label.setFont(QFont("Menlo", 8))
        self.address_label.setPos(-75, -7)
        self.update_label(config)
        self.set_status("IDLE")
        self.setPos(config.x, config.y)

    def update_label(self, config: HostConfig) -> None:
        self.name_label.setText(config.name)
        self.address_label.setText(f"IP    {config.ip}\nMAC   {config.mac}")

    def set_status(self, status: str) -> None:
        self._status = status
        styles = {
            "BROADCASTING": ("#273746", "#f4a340", "#ffc46f"),
            "REPLYING": ("#213b3a", "#3fb18f", "#70d6b7"),
            "RESOLVED": ("#213b3a", "#3fb18f", "#70d6b7"),
            "PAUSED": ("#354351", "#728392", "#a7b3bd"),
            "TIMEOUT": ("#5b2929", "#d86661", "#f19a96"),
            "IDLE": ("#17344c", "#4c8baa", "#55b6d4"),
        }
        fill, border, dot = styles.get(status, styles["IDLE"])
        self.setBrush(QBrush(QColor(fill)))
        pen_color = QColor("#d6e6ee") if self.isSelected() else QColor(border)
        self.setPen(QPen(pen_color, 2.6 if self.isSelected() else (2.1 if self._hovered else 1.6)))
        self.status_dot.setBrush(QBrush(QColor(dot)))
        names = {
            "IDLE": "空闲", "BROADCASTING": "广播", "REPLYING": "应答",
            "RESOLVED": "完成", "PAUSED": "暂停", "TIMEOUT": "超时",
        }
        self.status_label.setText(names.get(status, status))
        self.status_label.setBrush(QBrush(QColor(dot)))

    def set_selected_visual(self, selected: bool) -> None:
        self.setSelected(selected)
        color = "#d6e6ee" if selected else {
            "BROADCASTING": "#f4a340", "REPLYING": "#3fb18f", "RESOLVED": "#3fb18f",
            "PAUSED": "#728392", "TIMEOUT": "#d86661",
        }.get(self._status, "#4c8baa")
        self.setPen(QPen(QColor(color), 2.6 if selected else 1.6))

    def mousePressEvent(self, event):
        self._clicked(self.host_id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self._edit_requested(self.host_id)
        event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu()
        source_action = menu.addAction("设为源主机")
        target_action = menu.addAction("设为目标主机")
        menu.addSeparator()
        edit_action = menu.addAction("编辑主机…")
        chosen = menu.exec(event.screenPos())
        if chosen is source_action:
            self._source_requested(self.host_id)
        elif chosen is target_action:
            self._target_requested(self.host_id)
        elif chosen is edit_action:
            self._edit_requested(self.host_id)
        event.accept()

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.set_status(self._status)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.set_status(self._status)
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            pos = value
            self._moved(self.host_id, pos.x(), pos.y())
        return super().itemChange(change, value)


class TopologyView(QGraphicsView):
    host_clicked = Signal(str)
    host_moved = Signal(str, float, float)
    host_edit_requested = Signal(str)
    host_source_requested = Signal(str)
    host_target_requested = Signal(str)
    zoom_changed = Signal(int)

    MIN_ZOOM = 1.0
    MAX_ZOOM = 3.0
    WHEEL_SENSITIVITY = 0.00065
    CONTENT_RECT = QRectF(0, 0, 760, 590)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setBackgroundBrush(QBrush(QColor("#0e1b27")))
        self.setSceneRect(self.CONTENT_RECT.adjusted(-180, -140, 180, 140))
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setToolTip("滚轮缩放拓扑；拖动空白处平移；双击空白处恢复默认比例")
        self.nodes: dict[str, HostNode] = {}
        self.links: dict[str, LinkItem] = {}
        self.hub: LanHub | None = None
        self._animations: list[QVariantAnimation] = []
        self._active_packet_count = 0
        self._zoom_factor = 1.0
        self._view_center = QPointF(self.CONTENT_RECT.center())
        self._pan_active = False
        self._pan_last_pos = None

    def drawBackground(self, painter: QPainter, rect) -> None:
        super().drawBackground(painter, rect)
        painter.save()
        painter.setPen(QPen(QColor("#172a39"), 1))
        grid = 36
        left = int(rect.left()) - int(rect.left()) % grid
        top = int(rect.top()) - int(rect.top()) % grid
        for x in range(left, int(rect.right()) + grid, grid):
            painter.drawLine(x, rect.top(), x, rect.bottom())
        for y in range(top, int(rect.bottom()) + grid, grid):
            painter.drawLine(rect.left(), y, rect.right(), y)
        painter.restore()

    def set_hosts(self, configs: list[HostConfig]) -> None:
        for animation in self._animations:
            animation.stop()
        self._animations.clear()
        self.scene.clear()
        self.nodes.clear()
        self.links.clear()
        self._active_packet_count = 0
        self._zoom_factor = 1.0
        self._draw_hub()
        for config in configs:
            node = HostNode(
                config,
                self.host_clicked.emit,
                self.host_moved.emit,
                self.host_edit_requested.emit,
                self.host_source_requested.emit,
                self.host_target_requested.emit,
            )
            self.scene.addItem(node)
            self.nodes[config.host_id] = node
        self._draw_links()
        QTimer.singleShot(0, self.reset_view)

    def resizeEvent(self, event) -> None:
        center = QPointF(self._view_center)
        super().resizeEvent(event)
        if self._zoom_factor > self.MIN_ZOOM:
            self.centerOn(center)
            QTimer.singleShot(0, lambda saved_center=QPointF(center): self.centerOn(saved_center))
        else:
            self._fit_scene(self.CONTENT_RECT.center())

    def _fit_scene(self, center: QPointF | None = None) -> None:
        self.resetTransform()
        self.fitInView(self.CONTENT_RECT, Qt.AspectRatioMode.KeepAspectRatio)
        self.scale(self._zoom_factor, self._zoom_factor)
        self.centerOn(center or self.sceneRect().center())
        self._view_center = self.mapToScene(self.viewport().rect().center())

    def reset_view(self) -> None:
        self._zoom_factor = self.MIN_ZOOM
        self._fit_scene(self.CONTENT_RECT.center())
        self._update_pan_cursor()
        self.zoom_changed.emit(100)

    def zoom_in(self) -> None:
        self._set_zoom(self._zoom_factor * 1.12, self.viewport().rect().center())

    def zoom_out(self) -> None:
        self._set_zoom(self._zoom_factor / 1.12, self.viewport().rect().center())

    def _set_zoom(self, requested_zoom: float, anchor_pos) -> None:
        new_zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, requested_zoom))
        if abs(new_zoom - self._zoom_factor) < 0.0001:
            return
        if new_zoom <= self.MIN_ZOOM:
            self.reset_view()
            return

        anchor_scene_before = self.mapToScene(anchor_pos)
        ratio = new_zoom / self._zoom_factor
        self.scale(ratio, ratio)
        self._zoom_factor = new_zoom
        anchor_scene_after = self.mapToScene(anchor_pos)
        center_after_scale = self.mapToScene(self.viewport().rect().center())
        anchor_correction = anchor_scene_before - anchor_scene_after
        self.centerOn(center_after_scale + anchor_correction)
        self._view_center = self.mapToScene(self.viewport().rect().center())
        self._update_pan_cursor()
        self.zoom_changed.emit(round(self._zoom_factor * 100))

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if not delta:
            delta = event.pixelDelta().y() * 4
        if delta:
            factor = math.exp(delta * self.WHEEL_SENSITIVITY)
            self._set_zoom(self._zoom_factor * factor, event.position().toPoint())
        event.accept()

    def mousePressEvent(self, event) -> None:
        is_middle = event.button() == Qt.MouseButton.MiddleButton
        is_empty_left = (
            event.button() == Qt.MouseButton.LeftButton
            and self._interactive_item_at(event.position().toPoint()) is None
        )
        if self._zoom_factor > self.MIN_ZOOM and (is_middle or is_empty_left):
            self._pan_active = True
            self._pan_last_pos = event.position()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._pan_active and self._pan_last_pos is not None:
            movement = event.position() - self._pan_last_pos
            self._pan_last_pos = event.position()
            horizontal = self.horizontalScrollBar()
            vertical = self.verticalScrollBar()
            horizontal.setValue(horizontal.value() - round(movement.x()))
            vertical.setValue(vertical.value() - round(movement.y()))
            self._view_center = self.mapToScene(self.viewport().rect().center())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._pan_active:
            self._pan_active = False
            self._pan_last_pos = None
            self._update_pan_cursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _update_pan_cursor(self) -> None:
        cursor = Qt.CursorShape.OpenHandCursor if self._zoom_factor > self.MIN_ZOOM else Qt.CursorShape.ArrowCursor
        self.viewport().setCursor(cursor)

    def _host_node_at(self, point) -> HostNode | None:
        item = self.itemAt(point)
        while item is not None:
            if isinstance(item, HostNode):
                return item
            item = item.parentItem()
        return None

    def _interactive_item_at(self, point):
        item = self.itemAt(point)
        while item is not None:
            if isinstance(item, (HostNode, LanHub)):
                return item
            item = item.parentItem()
        return None

    def mouseDoubleClickEvent(self, event) -> None:
        if self._interactive_item_at(event.position().toPoint()) is None:
            self.reset_view()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _draw_hub(self) -> None:
        self.hub = LanHub(self.update_positions)
        self.scene.addItem(self.hub)
        self.hub.setZValue(0)

    def _draw_links(self) -> None:
        if not self.hub:
            return
        hub_center = self.hub.center_point()
        for host_id, node in self.nodes.items():
            line = LinkItem()
            line.setLine(node.pos().x(), node.pos().y(), hub_center.x(), hub_center.y())
            self.scene.addItem(line)
            self.links[host_id] = line

    def update_positions(self) -> None:
        if not self.hub:
            return
        hub_center = self.hub.center_point()
        for host_id, line in self.links.items():
            node = self.nodes.get(host_id)
            if node:
                line.setLine(node.pos().x(), node.pos().y(), hub_center.x(), hub_center.y())

    def reset_layout(self) -> None:
        positions = [(170, 145), (590, 145), (170, 445), (590, 445), (105, 295), (655, 295)]
        if self.hub:
            self.hub.setPos(300, 267)
        for node, (x, y) in zip(self.nodes.values(), positions):
            node.setPos(x, y)
        self.update_positions()
        self.reset_view()

    def select_host(self, host_id: str) -> None:
        for current_id, node in self.nodes.items():
            node.set_selected_visual(current_id == host_id)

    def set_host_status(self, host_id: str, status: str) -> None:
        node = self.nodes.get(host_id)
        if node:
            node.set_status(status)

    def animate_packet(self, packet, mode: str, host_configs: dict[str, HostConfig]) -> None:
        source = self.nodes.get(packet.source_host_id)
        if not source or not self.hub:
            return
        if mode == "broadcast":
            targets = [node for host_id, node in self.nodes.items() if host_id != packet.source_host_id]
            color = QColor("#f4a340")
            activity = "REQUEST"
        else:
            target = self.nodes.get(packet.destination_host_id or "")
            targets = [target] if target else []
            color = QColor("#44c3a0")
            activity = "REPLY"

        self._active_packet_count += 1
        self.hub.set_activity(activity)

        def finish_packet():
            self._active_packet_count = max(0, self._active_packet_count - 1)
            if self._active_packet_count == 0 and self.hub:
                self.hub.set_activity("IDLE")

        def start_second_phase():
            if not targets:
                finish_packet()
                return
            remaining = {"count": len(targets)}

            def target_arrived():
                remaining["count"] -= 1
                if remaining["count"] == 0:
                    finish_packet()

            for target_node in targets:
                self._animate_route(
                    lambda: self.hub.center_point() if self.hub else QPointF(),
                    lambda node=target_node: node.pos(),
                    color,
                    780,
                    target_arrived,
                )

        self._animate_route(
            lambda node=source: node.pos(),
            lambda: self.hub.center_point() if self.hub else QPointF(),
            color,
            520,
            start_second_phase,
        )

    def _animate_route(self, start_provider, end_provider, color: QColor, duration: int, on_finished) -> None:
        line = QGraphicsLineItem()
        line.setPen(QPen(color, 2.6))
        line.setOpacity(0.82)
        line.setZValue(1)
        self.scene.addItem(line)

        token = QGraphicsItemGroup()
        glow_color = QColor(color)
        glow_color.setAlpha(65)
        glow = QGraphicsEllipseItem(-10, -10, 20, 20, token)
        glow.setPen(QPen(Qt.PenStyle.NoPen))
        glow.setBrush(QBrush(glow_color))
        dot = QGraphicsEllipseItem(-5, -5, 10, 10, token)
        dot.setPen(QPen(QColor("#ffffff"), 1.1))
        dot.setBrush(QBrush(color))
        token.setZValue(2)
        self.scene.addItem(token)

        animation = QVariantAnimation(self)
        animation.setDuration(duration)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._animations.append(animation)

        def update(progress):
            start = start_provider()
            end = end_provider()
            line.setLine(start.x(), start.y(), end.x(), end.y())
            token.setPos(start + (end - start) * float(progress))

        animation.valueChanged.connect(update)
        update(0.0)

        def finish():
            if token.scene():
                self.scene.removeItem(token)
            if animation in self._animations:
                self._animations.remove(animation)
            self._fade_route(line)
            on_finished()

        animation.finished.connect(finish)
        animation.start()

    def _fade_route(self, line: QGraphicsLineItem) -> None:
        fade = QVariantAnimation(self)
        fade.setDuration(220)
        fade.setStartValue(line.opacity())
        fade.setEndValue(0.0)
        fade.valueChanged.connect(line.setOpacity)
        self._animations.append(fade)

        def remove_line():
            if line.scene():
                self.scene.removeItem(line)
            if fade in self._animations:
                self._animations.remove(fade)

        fade.finished.connect(remove_line)
        fade.start()
