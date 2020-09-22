import numpy as np

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from grasp import GraspRect, GraspRectBuilder


class PainterGen(object):
    def __init__(self):
        self.origin = QPointF(0., 0.)
        self.scale = 1.
        # self.base_scale = 1.

    # def setBaseScale(self, base_scale=1.0):
    #     self.base_scale = base_scale

    def widgetToPainter(self, pos: QPointF) -> QPointF:
        assert isinstance(pos, QPointF), "Only support QPointF."
        return (pos - self.origin) / self.scale

    def scaleAt(self, pos: QPointF, delta_scale, widget_logic=False):
        assert isinstance(pos, QPointF), "Only support QPointF."
        if widget_logic:
            pos = self.widgetToPainter(pos)

        # new_scale = self.scale + delta_scale
        new_scale = self.scale * (1 + delta_scale)

        # if new_scale < 0.1 * self.base_scale: new_scale = 0.1 * self.base_scale
        # if new_scale > 10. * self.base_scale: new_scale = 10. * self.base_scale

        new_origin = self.origin + pos * (self.scale - new_scale)

        self.scale = new_scale
        self.origin = new_origin

    def move(self, delta_pos: QPointF, widget_logic=False):
        assert isinstance(delta_pos, QPointF), "Only support QPointF."
        if widget_logic:
            self.origin += delta_pos
        else:
            self.origin += delta_pos * self.scale

    def getPainter(self, device):
        painter = QPainter(device)
        painter.translate(self.origin)
        painter.scale(self.scale, self.scale)

        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        return painter

    def fitWidgetWidth(self, widget_size: QSize, image_size: QSize):
        widget_width, widget_height = widget_size.width(), widget_size.height()
        image_width, image_height = image_size.width(), image_size.height()

        scale = widget_width / image_width
        scaled_image_height = scale * image_height

        self.origin.setX(0)
        self.origin.setY(widget_height / 2. - scaled_image_height / 2.)
        self.scale = scale
        print("[INFO] [from canvas] Fit widget width triggered.")

    def fitWidgetHeight(self, widget_size: QSize, image_size: QSize):
        widget_width, widget_height = widget_size.width(), widget_size.height()
        image_width, image_height = image_size.width(), image_size.height()

        scale = widget_height / image_height
        scaled_image_width = scale * image_width

        self.origin.setY(0)
        self.origin.setX(widget_width / 2. - scaled_image_width / 2.)
        self.scale = scale
        print("[INFO] [from canvas] Fit widget height triggered.")

    def fitWidget(self, widget_size: QSize, image_size: QSize):
        widget_width, widget_height = widget_size.width(), widget_size.height()
        image_width, image_height = image_size.width(), image_size.height()
        w_scale = widget_width / image_width
        h_scale = widget_height / image_height

        if w_scale <= h_scale:
            self.fitWidgetWidth(widget_size, image_size)
        else:
            self.fitWidgetHeight(widget_size, image_size)

    def fitOriginSize(self, widget_size: QSize, image_size: QSize):
        widget_width, widget_height = widget_size.width(), widget_size.height()
        image_width, image_height = image_size.width(), image_size.height()

        self.origin.setX(widget_width / 2. - image_width / 2.)
        self.origin.setY(widget_height / 2. - image_height / 2.)
        self.scale = 1.


class Canvas(QWidget):
    shapesAdded = pyqtSignal(list)  # list of shapes (GraspRect)
    shapesRemoved = pyqtSignal(list)  # list of shape ids

    # (selected, deselected)， list of shape id
    shapesSelectionChanged = pyqtSignal(list, list)
    shapesAreaChanged = pyqtSignal(list)  # list of shapes (GraspRect)

    CREATE, EDIT = 0, 1

    def __init__(self, parent=None):
        super(QWidget, self).__init__(parent)
        # self.setGeometry(10, 10, 1200, 800)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.WheelFocus)
        # self.resize(400, 260)

        self.mode = self.EDIT
        self.pre_pos = None
        self.pixmap = None  # QPixmap("./19.jpg")

        # 使用字典存储shape的id到列表下标的映射，加快处理速度
        self.shapes = list()
        self.id2idx = dict()

        self.pg = PainterGen()
        self.builder = GraspRectBuilder()

    def loadImage(self, path: str):
        self.pixmap = QPixmap(path)
        self.adjustPainter("fit_window")

    def addShapes(self, shapes: list):
        added_shapes = []
        for shape in shapes:
            assert isinstance(shape, GraspRect)
            if shape.id() not in self.id2idx:
                shape.resetChanged()
                self.id2idx[shape.id()] = len(self.shapes)
                self.shapes.append(shape)
                added_shapes.append(shape)

        if added_shapes:
            print("[INFO] [from canvas] Emit shapesAdded, ids = {}"
                  .format([shape.id() for shape in added_shapes]))
            self.shapesAdded.emit(added_shapes)
            self.update()

    def removeShapes(self, shape_ids: list):
        removed_shape_ids = []
        removed_indexes = []
        for shape_id in shape_ids:
            if shape_id in self.id2idx:
                idx = self.id2idx.pop(shape_id)
                removed_indexes.append(idx)
                removed_shape_ids.append(shape_id)

        for idx in sorted(removed_indexes, reverse=True):
            self.shapes.pop(idx)

        if removed_shape_ids:
            self.id2idx = {shape.id(): i for i, shape in enumerate(self.shapes)}
            print("[INFO] [from canvas] Emit shapesRemoved, ids = {}"
                  .format(removed_shape_ids))
            self.shapesRemoved.emit(removed_shape_ids)
            self.update()

    def clear(self):
        self.builder.reset()
        self.removeShapes(list(self.id2idx.keys()))

    def exportShapes(self):
        return [s.export() for s in self.shapes]

    def loadShapes(self, shapes):
        # shapes: list[dict], e.g.:
        # [
        #     {"id": xxx, "points": xxx},
        #     {"id": xxx, "points": xxx},
        #     ...
        # ],
        self.clear()
        self.addShapes([GraspRect(np.array(shape["points"])) for shape in shapes])

    def changeShapesSelection(self, select: list, deselect: list):
        for shape_id in select:
            if shape_id not in self.id2idx:
                continue
            idx = self.id2idx[shape_id]
            shape = self.shapes[idx]
            shape.setSelected(True)

        for shape_id in deselect:
            if shape_id not in self.id2idx:
                continue
            idx = self.id2idx[shape_id]
            shape = self.shapes[idx]
            shape.setSelected(False)

        self._checkShapesSelectionChangeAndEmit()
        self.update()

    def changeShapesVisible(self, shape_id: str, visible: bool):
        if shape_id in self.id2idx:
            idx = self.id2idx[shape_id]
            shape = self.shapes[idx]
            shape.setVisible(visible)
            self.update()

    def changeShapesOrder(self, old_id2idx: dict, new_id2idx: dict):
        if self.id2idx == old_id2idx:
            if old_id2idx == new_id2idx:
                print("[INFO] [from canvas] Shapes order not change, no need to reorder")
            else:
                new_shapes = [None] * len(self.shapes)
                for shape_id, new_idx in new_id2idx.items():
                    old_idx = self.id2idx[shape_id]
                    new_shapes[new_idx] = self.shapes[old_idx]
                self.shapes = new_shapes
                self.id2idx = new_id2idx
        else:
            if self.id2idx == new_id2idx:
                print("[INFO] [from canvas] Already the newest order")
            else:
                raise ValueError("[ERROR] [from canvas] Shapes order mess up!")

    def _checkShapesSelectionChangeAndEmit(self):
        # 鼠标按键操作会导致形状选中状态的改变，或者从CREATE切换至MODE也会导致选中状态的改变
        new_select_shape_ids = []
        new_deselect_shape_ids = []
        for shape in self.shapes:
            assert isinstance(shape, GraspRect)
            if shape.selectedChanged():
                if shape.selected():
                    new_select_shape_ids.append(shape.id())
                else:
                    new_deselect_shape_ids.append(shape.id())
                shape.resetSelectedChanged()

        if len(new_select_shape_ids) + len(new_deselect_shape_ids):
            print("[INFO] [from canvas] Emit shapesSelectionChanged, "
                  "select = {}, deselect = {}".format(new_select_shape_ids, new_deselect_shape_ids))
            self.shapesSelectionChanged.emit(new_select_shape_ids, new_deselect_shape_ids)

    def _checkShapesAreaChangeAndEmit(self):
        # 鼠标的移动可能会导致形状的改变
        new_modified_shapes = []
        for shape in self.shapes:
            assert isinstance(shape, GraspRect)
            if shape.areaChanged():
                new_modified_shapes.append(shape)
                shape.resetAreaChanged()

        if new_modified_shapes:
            print("[INFO] [from canvas] Emit shapesAreaChanged, ids = {}"
                  .format([shape.id() for shape in new_modified_shapes]))
            self.shapesAreaChanged.emit(new_modified_shapes)

    def _resetSelectedExcept(self, s: GraspRect = None):
        for shape in self.shapes:
            if (s is None) or (s.id() != shape.id()):
                shape.resetSelected()

    def _resetHoveringExcept(self, s: GraspRect = None):
        for shape in self.shapes:
            if (s is None) or (s.id() != shape.id()):
                shape.resetHovering()

    def _setShapeCursorPos(self, pos: QPointF):
        for shape in self.shapes:
            shape.setCursorPos(pos)

    def paintEvent(self, e: QMouseEvent) -> None:
        painter = self.pg.getPainter(self)

        if self.pixmap is not None:
            painter.drawPixmap(0, 0, self.pixmap)

        for shape in self.shapes:
            assert isinstance(shape, GraspRect)
            shape.paint(painter)

        self.builder.paint(painter)

        # if self.mode == self.CREATE:
        #     painter.setPen(QPen(Qt.green, 50))
        #     painter.drawPoint(0, 0)
        # elif self.mode == self.EDIT:
        #     painter.setPen(QPen(Qt.yellow, 50))
        #     painter.drawPoint(0, 0)

    def mousePressEvent(self, e: QMouseEvent) -> None:
        pos = e.localPos()
        painter_pos = self.pg.widgetToPainter(pos)
        press_control = int(e.modifiers()) & Qt.ControlModifier

        if e.button() == Qt.MidButton:
            self._setShapeCursorPos(painter_pos)
            self.pre_pos = pos
            return

        if self.mode == self.CREATE:
            self.builder.processPoint(painter_pos, e.button())
            if self.builder.isFinished():
                grasp_rect = self.builder.fetchResult()
                self.addShapes([grasp_rect])

        elif self.mode == self.EDIT:
            # ctrl + 左键 多选
            if press_control:
                if e.button() == Qt.LeftButton:
                    for shape in reversed(self.shapes):
                        assert isinstance(shape, GraspRect)
                        if not shape.visible():
                            continue
                        if not shape.selected():
                            shape.checkPosAndSelect(painter_pos, shape_only=True)
                            if shape.selected():
                                break

            else:  # 否则单选判断
                for shape in reversed(self.shapes):
                    assert isinstance(shape, GraspRect)
                    if not shape.visible():
                        continue
                    # 左键单击看判断点线面，右键单击时只判断是否在面内
                    if e.button() == Qt.LeftButton:
                        shape.checkPosAndSelect(painter_pos, shape_only=False)
                    elif e.button() == Qt.RightButton:
                        shape.checkPosAndSelect(painter_pos, shape_only=True)
                    if shape.selectedAnything():
                        self._resetSelectedExcept(shape)
                        self._resetHoveringExcept(shape)
                        break
            self._checkShapesSelectionChangeAndEmit()

        self._setShapeCursorPos(painter_pos)
        self.pre_pos = pos
        self.update()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        painter_pos = self.pg.widgetToPainter(e.localPos())
        if self.mode == self.EDIT:
            if e.button() == Qt.LeftButton:
                for shape in self.shapes:
                    shape._selected_point_idx = None
                    shape._selected_edge_idx = None
                for shape in reversed(self.shapes):
                    shape.checkPosAndHover(painter_pos, shape_only=False)
                    if shape.hoveringAnything():
                        self._resetHoveringExcept(shape)
                        break

        self.pre_pos = None
        self.update()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        pos = e.localPos()
        painter_pos = self.pg.widgetToPainter(pos)

        if int(e.buttons()) & Qt.MidButton:
            delta_pos = pos - self.pre_pos
            self.pg.move(delta_pos, widget_logic=True)

        else:
            painter_pos = self.pg.widgetToPainter(pos)  # 要放在self.pg更新之后
            if self.mode == self.CREATE:
                self.builder.processPoint(painter_pos, e.button())

            elif self.mode == self.EDIT:
                if int(e.buttons()) & Qt.LeftButton:
                    for shape in self.shapes:
                        assert isinstance(shape, GraspRect)
                        if not shape.visible():
                            continue
                        shape.checkSelectedAndMove(painter_pos)

                elif int(e.buttons()) & Qt.RightButton:
                    for shape in self.shapes:
                        assert isinstance(shape, GraspRect)
                        if not shape.visible():
                            continue
                        shape.checkSelectedAndRotate(painter_pos)

                else:
                    for shape in reversed(self.shapes):
                        assert isinstance(shape, GraspRect)
                        if not shape.visible():
                            continue
                        shape.checkPosAndHover(painter_pos, shape_only=False)
                        if shape.hoveringAnything():
                            self._resetHoveringExcept(shape)
                            break
                self._checkShapesAreaChangeAndEmit()

        self._setShapeCursorPos(painter_pos)
        self.pre_pos = pos
        self.update()

    def wheelEvent(self, e: QWheelEvent):
        pos = e.posF()
        delta_scale = e.angleDelta().y() / 120. * 0.2
        self.pg.scaleAt(pos, delta_scale, widget_logic=True)
        self.update()

    def keyPressEvent(self, e: QKeyEvent):
        super(Canvas, self).keyPressEvent(e)

        if e.isAutoRepeat():
            return

        if e.key() == Qt.Key_Delete:
            remove_shape_ids = [shape.id() for shape in self.shapes if shape.selected()]
            if len(remove_shape_ids):
                self.removeShapes(remove_shape_ids)

    def setMode(self, mode):
        if mode == self.CREATE:
            self.mode = self.CREATE
            for shape in self.shapes:
                shape.resetSelected()
                shape.resetHovering()

            # 如果切换模式的时候鼠标在画布内，那么也要改变图表形状
            if self.underMouse():
                QApplication.changeOverrideCursor(QCursor(Qt.CrossCursor))

        elif mode == self.EDIT:
            self.mode = self.EDIT
            self.builder.reset()
            if self.underMouse():
                QApplication.changeOverrideCursor(QCursor(Qt.ArrowCursor))

        self._checkShapesSelectionChangeAndEmit()
        self.update()

    def sizeHint(self):
        return QSize(1080, 720)

    def minimumSizeHint(self):
        return QSize(1080 // 2, 720 // 2)

    def adjustPainter(self, fit_type="fit_window"):
        options = ["fit_width", "fit_height", "fit_window", "origin_size"]
        assert fit_type.lower() in options, "fit_type support {}".format(options)

        if self.pixmap is None:
            return

        widget_size = self.size()
        image_size = self.pixmap.size()

        if fit_type.lower() == "fit_width":
            self.pg.fitWidgetWidth(widget_size, image_size)
        elif fit_type.lower() == "fit_height":
            self.pg.fitWidgetHeight(widget_size, image_size)
        elif fit_type.lower() == "fit_window":
            self.pg.fitWidget(widget_size, image_size)
        else:
            self.pg.fitOriginSize(widget_size, image_size)
        self.update()

    def enterEvent(self, e: QEvent):
        # QGuiApplication.restoreOverrideCursor()
        cursor = QCursor(Qt.CrossCursor) if self.mode == self.CREATE \
            else QCursor(Qt.ArrowCursor)
        QApplication.setOverrideCursor(cursor)

    def leaveEvent(self, e: QEvent):
        QApplication.restoreOverrideCursor()

    def focusOutEvent(self, e: QFocusEvent):
        QApplication.restoreOverrideCursor()
