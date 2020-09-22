from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from typing import List


class FileListItem(QStandardItem):
    def __init__(self, filname: str):
        super(FileListItem, self).__init__()
        self.setCheckable(True)
        self.setCheckState(Qt.Unchecked)  # unchecked items will not be saved in the final results
        self.setEditable(False)
        self.setTextAlignment(Qt.AlignBottom)
        self.setDragEnabled(False)
        self.setDropEnabled(False)

        self.setData(filname, Qt.UserRole + 1)
        self.setData(True, Qt.UserRole + 2)  # saved state
        self.setText(filname)

    def filename(self):
        return self.data(Qt.UserRole + 1)

    def savedState(self):
        return self.data(Qt.UserRole + 2)

    def setSavedState(self, saved=True):
        self.setData(saved, Qt.UserRole + 2)
        filename = self.data(Qt.UserRole + 1)
        self.setText(("*" if not saved else "") + filename)


class FileListWidget(QListView):

    filesSelectionChanged = pyqtSignal(list, list)
    fileLabeledChanged = pyqtSignal(int, bool)  # int: index, bool: whether has been labeled

    def __init__(self):
        super(FileListWidget, self).__init__()
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragDropMode(QAbstractItemView.NoDragDrop)

        item_model = QStandardItemModel(self)
        item_model.setItemPrototype(FileListItem(""))
        self.setModel(item_model)

        self.selectionModel().selectionChanged.connect(self._filesSelectionChangedEmit)
        self.model().itemChanged.connect(self._fileLabeledChangedEmit)

    def addFiles(self, files: List[str]):
        for f in files:
            item = FileListItem(f)
            item.setSavedState(True)
            self.model().appendRow(item)

    def clear(self):
        self.model().clear()

    def _filesSelectionChangedEmit(self, selected: QItemSelection, deselected: QItemSelection):
        selected_file_idx = [i.row() for i in selected.indexes()]
        deselected_file_idx = [i.row() for i in deselected.indexes()]

        assert len(selected_file_idx) <= 1, "Single selection mode."
        assert len(deselected_file_idx) <= 1, "Single selection mode."

        print("[INFO] [from file_list] Emit selected = {}, deselected = {}"
              .format(selected_file_idx, deselected_file_idx))
        self.filesSelectionChanged.emit(selected_file_idx, deselected_file_idx)

    def _fileLabeledChangedEmit(self, item: FileListItem):
        print("[INFO] [from file_list] Emit file index = {}, has labeled = {}"
              .format(item.index().row(), item.checkState() > 0))
        self.fileLabeledChanged.emit(item.index().row(), item.checkState() > 0)

    def selectNext(self):
        if self.model().rowCount() == 0:
            return None, None

        selected = [i.row() for i in self.selectedIndexes()]
        assert len(selected) <= 1, "Single selection mode."

        selection = QItemSelection()
        if len(selected) == 0:
            current_select = None
            next_select = 0
        else:
            current_select = selected[0]
            next_select = (selected[0] + 1) % self.model().rowCount()

        index = self.model().index(next_select, 0)
        selection.select(index, index)

        self.selectionModel().select(self.selectionModel().selection(), QItemSelectionModel.Deselect)
        self.selectionModel().select(selection, QItemSelectionModel.Select)
        return current_select, next_select

    def selectPrev(self):
        if self.model().rowCount() == 0:
            return None, None

        selected = [i.row() for i in self.selectedIndexes()]
        assert len(selected) <= 1, "Single selection mode."

        selection = QItemSelection()
        if len(selected) == 0:
            current_select = None
            prev_select = self.model().rowCount() - 1
        else:
            current_select = selected[0]
            prev_select = (selected[0] - 1) % self.model().rowCount()

        index = self.model().index(prev_select, 0)
        selection.select(index, index)

        self.selectionModel().select(self.selectionModel().selection(), QItemSelectionModel.Deselect)
        self.selectionModel().select(selection, QItemSelectionModel.Select)
        return current_select, prev_select

    def checkAll(self):
        for item in self:
            item.setCheckState(Qt.Checked)

    def uncheckAll(self):
        for item in self:
            item.setCheckState(Qt.Unchecked)

    def __len__(self):
        return self.model().rowCount()

    def __getitem__(self, i) -> FileListItem:
        return self.model().item(i)

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]
