import sys
import math
import numpy as np

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from grasp import GraspRect


class HTMLDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super(HTMLDelegate, self).__init__()
        self.doc = QTextDocument(self)

    def paint(self, painter, option, index):
        painter.save()

        options = QStyleOptionViewItem(option)

        self.initStyleOption(options, index)
        self.doc.setHtml(options.text)
        options.text = ""

        style = (
            QApplication.style()
            if options.widget is None
            else options.widget.style()
        )
        style.drawControl(QStyle.CE_ItemViewItem, options, painter)

        ctx = QAbstractTextDocumentLayout.PaintContext()

        if option.state & QStyle.State_Selected:
            ctx.palette.setColor(
                QPalette.Text,
                option.palette.color(
                    QPalette.Active, QPalette.HighlightedText
                ),
            )
        else:
            ctx.palette.setColor(
                QPalette.Text,
                option.palette.color(QPalette.Active, QPalette.Text),
            )

        textRect = style.subElementRect(QStyle.SE_ItemViewItemText, options)

        if index.column() != 0:
            textRect.adjust(5, 0, 0, 0)

        thefuckyourshitup_constant = 4
        margin = (option.rect.height() - options.fontMetrics.height()) // 2
        margin = margin - thefuckyourshitup_constant
        textRect.setTop(textRect.top() + margin)

        painter.translate(textRect.topLeft())
        painter.setClipRect(textRect.translated(-textRect.topLeft()))
        self.doc.documentLayout().draw(painter, ctx)

        painter.restore()

    def sizeHint(self, option, index):
        thefuckyourshitup_constant = 4
        return QSize(
            self.doc.idealWidth(),
            self.doc.size().height() - thefuckyourshitup_constant,
        )


class LabelListWidgetItem(QStandardItem):
    def __init__(self, shape: GraspRect = None):
        super(LabelListWidgetItem, self).__init__()
        self.setCheckable(True)
        self.setCheckState(Qt.Checked)
        self.setEditable(False)
        self.setTextAlignment(Qt.AlignBottom)
        self.setDragEnabled(True)
        self.setDropEnabled(False)

        self.setShape(shape)
        self.updateText()

    def setShape(self, shape: GraspRect):
        self.setData(shape, Qt.UserRole + 1)

    def updateText(self):
        data = self.shape()
        if not isinstance(data, GraspRect):
            self.setText("unavailable data type: {}".format(type(data)))
        else:
            color = data.getFillColor()
            text = '{} <font color="#{:02x}{:02x}{:02x}">●</font>'\
                .format(data.id(), color.red(), color.green(), color.blue())
            self.setText(text)

    def shape(self) -> GraspRect:
        return self.data(Qt.UserRole + 1)

    def clone(self):
        return LabelListWidgetItem(self.shape())

    def __repr__(self):
        data = self.shape()
        if not isinstance(data, GraspRect):
            return "unavailable data type: {}".format(type(data))
        else:
            return repr(data)

    def __hash__(self):
        return id(self)


class LabelListWidget(QListView):
    itemDoubleClicked = pyqtSignal(LabelListWidgetItem)
    shapesSelectionChanged = pyqtSignal(list, list)  # (list of shape id, list of shape id)
    shapeVisibleChanged = pyqtSignal(str, bool)  # 形状前面的小勾勾 (shape_id, checked)

    # 拖放的“放”发生时需要发射的信号，意味着顺序已经改变
    shapesOrderChanged = pyqtSignal(dict, dict)  # (old_id2idx, new_id2idx)
    shapesAdded = pyqtSignal(list)  # list of shape (GraspRect)
    shapesRemoved = pyqtSignal(list)  # list of shape id
    shapesAreaChanged = pyqtSignal(list)  # list of shape (GraspRect)

    reconnectCanvasDataRequest = pyqtSignal()

    # Signal: shapeOrderChanged -> canvas 改变图层
    # Signal: shapesRemoved -> canvas 删除图形
    # Signal: shapesArea -> canvas 更改形状

    def __init__(self, parent=None):
        super(LabelListWidget, self).__init__(parent)

        self.setItemDelegate(HTMLDelegate())
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)

        item_model = QStandardItemModel(self)
        item_model.setItemPrototype(LabelListWidgetItem(GraspRect()))
        self.setModel(item_model)

        self.doubleClicked.connect(
            lambda index:
            self.itemDoubleClicked.emit(self.model().itemFromIndex(index))
        )

        self.selectionModel().selectionChanged.connect(self._shapesSelectionChangedEmit)
        self.selectionModel().selectionChanged.connect(self._scrollToLastSelected)
        self.model().itemChanged.connect(self._shapeVisibleChangedEmit)

        self.viewport().installEventFilter(self)
        self.installEventFilter(self)  # use to judge order changed

        self.id2idx = dict()
        self.dropped = False

    def _shapesSelectionChangedEmit(self, selected: QItemSelection, deselected: QItemSelection):
        selected_shape_ids = [self.model().itemFromIndex(i).shape().id() for i in selected.indexes()]
        deselcted_shape_ids = [self.model().itemFromIndex(i).shape().id() for i in deselected.indexes()]
        print("[INFO] [from label_list] Emit selected = {}, deselected = {}"
              .format(selected_shape_ids, deselcted_shape_ids))
        self.shapesSelectionChanged.emit(selected_shape_ids, deselcted_shape_ids)

    def _shapeVisibleChangedEmit(self, item: LabelListWidgetItem):
        print("[INFO] [from label_list] Emit shape id = {}, visible = {}"
              .format(item.shape().id(), item.checkState() > 0))
        self.shapeVisibleChanged.emit(item.shape().id(), item.checkState() > 0)

    def _scrollToLastSelected(self, selected: QItemSelection):
        indexes = selected.indexes()
        if len(indexes):
            self.scrollTo(indexes[-1], QAbstractItemView.EnsureVisible)

    def addShapes(self, shapes: list):
        added_shapes = []
        for shape in shapes:
            assert isinstance(shape, GraspRect)
            # shape = shape.copy(new_id=False)
            # QStandItemModel不能存储local variable
            if shape.id() not in self.id2idx:
                self.id2idx[shape.id()] = self.model().rowCount()
                self.model().appendRow(LabelListWidgetItem(shape))
                added_shapes.append(shape)

        if added_shapes:
            self.scrollToBottom()
            print("[INFO] [from list_view] Emit added shapes, ids = {}"
                  .format([shape.id() for shape in added_shapes]))
            self.shapesAdded.emit(added_shapes)

    def removeShapes(self, shape_ids: list):
        removed_shape_ids = []
        removed_indexes = []
        for shape_id in shape_ids:
            if shape_id in self.id2idx:
                idx = self.id2idx.pop(shape_id)
                removed_indexes.append(idx)
                removed_shape_ids.append(shape_id)

        for idx in sorted(removed_indexes, reverse=True):
            self.model().removeRow(idx)

        if removed_shape_ids:
            self.id2idx = {item.shape().id(): i for i, item in enumerate(self)}
            print("[INFO] [from list_view] Emit removed shape ids, ids = {}"
                  .format(removed_shape_ids))
            self.shapesRemoved.emit(removed_shape_ids)

    # def clear(self):
    #     self.removeShapes(list(self.id2idx.keys()))
    #
    # def export(self):
    #     return [item.shape().export() for item in self]

    def changeShapesSelection(self, select: list, deselect: list):
        """ Change shape selection
        :param select: list of shape ids.
        :param deselect: list of shape ids.
        """
        item_model = self.model()

        selection = QItemSelection()
        for shape_id in select:
            if shape_id not in self.id2idx:
                continue
            index = item_model.index(self.id2idx[shape_id], 0)
            selection.select(index, index)

        deselection = QItemSelection()
        for shape_id in deselect:
            if shape_id not in self.id2idx:
                continue
            index = item_model.index(self.id2idx[shape_id], 0)
            deselection.select(index, index)

        self.selectionModel().select(selection, QItemSelectionModel.Select)
        self.selectionModel().select(deselection, QItemSelectionModel.Deselect)

    def updateShapesArea(self, shapes: list):
        for shape in shapes:
            assert isinstance(shape, GraspRect)
            if shape.id() not in self.id2idx:
                continue
            item = self.model().item(self.id2idx[shape.id()])

            if item.shape() is not shape:
                item.setShape(shape)
            item.updateText()

    def reconnectCanvasData(self, shapes: list):
        for shape in shapes:
            assert isinstance(shape, GraspRect)
            if shape.id() not in self.id2idx:
                continue
            item = self.model().item(self.id2idx[shape.id()])
            if item.shape() is not shape:
                item.setShape(shape)
                item.updateText()

    def _checkShapesOrderChangedAndEmit(self):
        old_id2idx = self.id2idx
        new_id2idx = {item.shape().id(): i for i, item in enumerate(self)}
        if old_id2idx != new_id2idx:
            self.id2idx = new_id2idx
            print("[INFO] [from list_view] Item num = {}".format(len(self)))
            print("[INFO] [from list_view] Emit shape order change, old = {}, new = {}"
                  .format(old_id2idx, new_id2idx))
            self.shapesOrderChanged.emit(old_id2idx, new_id2idx)
            print("[INFO] [from list_view] Emit reconnectCanvasDataRequest")
            self.reconnectCanvasDataRequest.emit()

    def eventFilter(self, obj: QObject, e: QEvent) -> bool:
        if (e.type() == QEvent.Drop) and (obj is self.viewport()):
            self.dropped = True
        elif (e.type() == QEvent.ChildRemoved) and (obj is self):
            if self.dropped:
                self.dropped = False
                self._checkShapesOrderChangedAndEmit()
        return super(LabelListWidget, self).eventFilter(obj, e)

    def keyPressEvent(self, e: QKeyEvent):
        super(LabelListWidget, self).keyPressEvent(e)

        if e.isAutoRepeat():
            return

        if e.key() == Qt.Key_Delete:
            remove_shape_ids = []
            for index in self.selectedIndexes():
                item = self[index.row()]
                remove_shape_ids.append(item.shape().id())

            if len(remove_shape_ids):
                self.removeShapes(remove_shape_ids)

    def __len__(self):
        return self.model().rowCount()

    def __getitem__(self, i) -> LabelListWidgetItem:
        return self.model().item(i)

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]
