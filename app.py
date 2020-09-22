import os
import sys
import glob
import json
import time

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from typing import List

from canvas import Canvas
from label_list import LabelListWidget
from file_list import FileListWidget
from tool_bar import ToolBar

import utils
import action

# IMAGE_EXTENTIONS = [
#     "{}".format(fmt.data().decode("ascii").lower())
#     for fmt in QImageReader.supportedImageFormats()
# ]

IMAGE_EXTENTIONS = ["jpg", "png"]


class MainWindow(QMainWindow):
    def __init__(self):
        super(QWidget, self).__init__()
        self.setWindowTitle("My Label Tool")

        self.canvas = Canvas(self)
        self.dirty = False  # set True indicates there exists unsaved changes

        self.label_list = LabelListWidget()
        self.shape_dock = QDockWidget(self.tr(u"Grasp list"), self)
        self.shape_dock.setObjectName(u"Grasp list")
        self.shape_dock.setWidget(self.label_list)

        # connection
        self.canvas.shapesAdded.connect(self.label_list.addShapes)
        self.canvas.shapesRemoved.connect(self.label_list.removeShapes)
        self.canvas.shapesSelectionChanged.connect(self.label_list.changeShapesSelection)
        self.canvas.shapesAreaChanged.connect(self.label_list.updateShapesArea)

        # self.label_list.shapesAdded.connect(self.canvas.addShapes)
        self.label_list.shapesRemoved.connect(self.canvas.removeShapes)
        self.label_list.shapesSelectionChanged.connect(self.canvas.changeShapesSelection)
        self.label_list.shapeVisibleChanged.connect(self.canvas.changeShapesVisible)
        self.label_list.shapesOrderChanged.connect(self.canvas.changeShapesOrder)
        self.label_list.reconnectCanvasDataRequest.connect(self._reconnectCanvasAndLabel)

        self.file_list = FileListWidget()
        self.file_list.filesSelectionChanged.connect(
            self._changeFilesSelection
        )
        self.file_list.fileLabeledChanged.connect(
            self._changeFileLabeled
        )  # 是否完成标注
        self.file_dock = QDockWidget(self.tr(u"File list"), self)
        self.file_dock.setObjectName(u"File list")
        self.file_dock.setWidget(self.file_list)

        # set dirty
        self.canvas.shapesAdded.connect(self.setDirty)
        self.canvas.shapesRemoved.connect(self.setDirty)
        self.canvas.shapesAreaChanged.connect(self.setDirty)
        self.label_list.shapesRemoved.connect(self.setDirty)
        self.label_list.shapesOrderChanged.connect(self.setDirty)
        self.file_list.fileLabeledChanged.connect(self.setDirty)

        # setup ui
        features = QDockWidget.DockWidgetFeatures()

        self.shape_dock.setFeatures(features | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable)
        self.shape_dock.setVisible(True)

        self.file_dock.setFeatures(features | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable)
        self.file_dock.setVisible(True)

        self.setCentralWidget(self.canvas)
        self.addDockWidget(Qt.RightDockWidgetArea, self.file_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.shape_dock)

        # project result
        self.image_folder = None
        self.image_files = None
        self.output_folder = None
        self.output_name = None
        # image_file_name = os.path.join(image_folder, image_files[working_idx])

        self.results = {
            "image_folder": "unknown",
            "image_files": {}
        }

        # results:
        #   image_folder: xxx
        #   image_files:
        #       "00001.jpg":
        #           "labeled": True
        #           "shapes":
        #               [
        #                   {"id": xxx, "points": xxx},
        #                   {"id": xxx, "points": xxx},
        #                   ...
        #               ],
        #       "00002.jpg":
        #           ...

        openProject = action.new_action(
            self,
            self.tr("Open Project"),
            lambda: self.importProject(self.openProjectDialog()),
            None,
            "open-project.png"
        )

        saveProject = action.new_action(
            self,
            self.tr("Save Project"),
            self.saveProject,
            "Ctrl+S",
            "save.png"
        )

        openImages = action.new_action(
            self,
            self.tr("Open Images"),
            lambda: self.importImages(self.openImagesDialog()),
            # lambda: self.openImagesDialog(),
            None,
            "open-images.png"
        )

        openDir = action.new_action(
            self,
            self.tr("Open Dir"),
            lambda: self.importDirImages(self.openDirDialog()),
            None,
            "open-dir.png"
        )

        openPrevImg = action.new_action(
            self,
            self.tr("Prev Image"),
            self.openPrevImg,
            "A",
            "prev.png"
        )

        openNextImg = action.new_action(
            self,
            self.tr("Next Image"),
            self.openNextImg,
            "D",
            "next.png"
        )

        createMode = action.new_action(
            self,
            self.tr("Create Mode"),
            lambda: self.canvas.setMode(self.canvas.CREATE),
            "Ctrl+N",
            "create.png"
        )

        editMode = action.new_action(
            self,
            self.tr("Edit Mode"),
            lambda: self.canvas.setMode(self.canvas.EDIT),
            "Ctrl+E",
            "edit.png"
        )

        fitWindow = action.new_action(
            self,
            self.tr("Fit Window"),
            lambda: self.canvas.adjustPainter("fit_window"),
            None,
            "fit-window.png"
        )

        # fitWidth = action.new_action(
        #     self,
        #     self.tr("Fit Width"),
        #     lambda: self.canvas.adjustPainter("fit_width"),
        #     None,
        #     "fit-width.png"
        # )
        #
        # fitHeight = action.new_action(
        #     self,
        #     self.tr("Fit Height"),
        #     lambda: self.canvas.adjustPainter("fit_height"),
        #     None,
        #     "fit-height.png"
        # )

        fitOrigin = action.new_action(
            self,
            self.tr("Origin Size"),
            lambda: self.canvas.adjustPainter("origin_size"),
            None,
            "origin-size.png"
        )

        changeOutputDir = action.new_action(
            self,
            self.tr("Change Output Dir"),
            self.changeOutputDir,
            None,
            "open-dir.png"
        )

        self.actions = utils.Struct(
            openPrevImg=openPrevImg,
            openNextImg=openNextImg
        )

        self.tool_bar = self.addToolBar_(
            "Tools",
            [
                openProject,
                # openImages,
                openDir,
                openPrevImg,
                openNextImg,
                saveProject,
                createMode,
                editMode,
                fitWindow,
                # fitHeight,
                # fitWidth,
                fitOrigin
            ]
        )

        self.menus = utils.Struct(
            file=self.addMenu(self.tr("File")),
            edit=self.addMenu(self.tr("Edit")),
            view=self.addMenu(self.tr("View"))
        )

        action.add_actions(
            self.menus.file,
            [
                openProject,
                openImages,
                openDir,
                None,
                saveProject,
                changeOutputDir
            ]
        )

        action.add_actions(
            self.menus.edit,
            [
                createMode,
                editMode
            ]
        )

        action.add_actions(
            self.menus.view,
            [
                fitWindow,
                # fitHeight,
                # fitWidth,
                fitOrigin
            ]
        )

    def _reconnectCanvasAndLabel(self):
        self.label_list.reconnectCanvasData(self.canvas.shapes)

    def _changeFilesSelection(self, selected, deselected):
        assert len(selected) <= 1, "Single selection mode"
        assert len(deselected) <= 1, "Single selection mode"

        if len(deselected):
            # save current work
            print("[INFO] [from_app] Saving current work...")
            current_file = self.image_files[deselected[0]]
            self.results["image_files"][current_file]["shapes"] = self.canvas.exportShapes()

        if len(selected):
            # load new file
            current_file = self.image_files[selected[0]]
            print("[INFO] [from_app] Loading data for image {}...".format(current_file))
            if current_file not in self.results["image_files"]:
                self.canvas.clear()
            else:
                self.canvas.loadShapes(self.results["image_files"][current_file]["shapes"])

            if self.image_folder is not None:  # relative path
                self.canvas.loadImage(os.path.join(self.image_folder, current_file))
            else:  # absolute path
                self.canvas.loadImage(current_file)
        self.setClean()

    def _changeFileLabeled(self, index: int, labeled: bool):
        file = self.image_files[index]
        self.results["image_files"][file]["labeled"] = labeled

    def setDirty(self):
        self.dirty = True

    def setClean(self):
        self.dirty = False

    def isDirty(self):
        return self.dirty

    def addMenu(self, title, actions=None):
        menu = self.menuBar().addMenu(title)
        if actions:
            action.add_actions(menu, actions)
        return menu

    def addToolBar_(self, title, actions=None):
        tool_bar = ToolBar(title)
        tool_bar.setObjectName("{}ToolBar".format(title))

        tool_bar.setOrientation(Qt.Vertical)
        tool_bar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        if actions:
            action.add_actions(tool_bar, actions)
        self.addToolBar(Qt.LeftToolBarArea, tool_bar)
        return tool_bar

    def openProjectDialog(self):
        path = QFileDialog.getOpenFileName(
            self,
            self.tr("Open Project"),
            "./",
            self.tr("Project File (*.json)")
        )[0]
        return path

    def openImagesDialog(self):
        paths = QFileDialog.getOpenFileNames(
            self,
            self.tr("Open Images"),
            "./",
            self.tr("Image Files ({})"
                    .format(" ".join(["*." + ext for ext in IMAGE_EXTENTIONS])))
        )[0]
        return paths

    def openDirDialog(self):
        path = QFileDialog.getExistingDirectory(
            self,
            self.tr("Open Directory"),
            "./",
            # QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            # QFileDialog.DontUseNativeDialog | QFileDialog.DontResolveSymlinks
            # QFileDialog.DontResolveSymlinks
            QFileDialog.ShowDirsOnly
        )
        if len(path) == 0:
            path = None
        print("[INFO] [from app] Choose dir = {}".format(path))
        return path

    def importProject(self, path: str):
        if not path:
            return

        # clean the current content
        self.file_list.clear()
        self.canvas.clear()

        with open(path, "r", encoding="utf-8") as j:
            self.results = json.load(j)

        self.image_folder = self.results["image_folder"].lower() \
            if self.results["image_folder"].lower() != "absolute_path" \
            else None

        self.image_files = list(self.results["image_files"].keys())
        self.image_files.sort()

        # check if file exists
        if self.image_folder is None:  # absolute path
            found, not_found = [], []
            for file in self.image_files:
                if os.path.exists(file):
                    found.append(file)
                else:
                    not_found.append(file)

            self.image_files = found

            if len(not_found):
                box = QMessageBox(self)
                box.setIcon(QMessageBox.Warning)
                box.setText("{} file(s) cannot be found.".format(len(not_found)))
                box.setInformativeText("Do you want the project to keep them?")
                box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                box.setDefaultButton(QMessageBox.No)
                box.setDetailedText(
                    "The following file(s) cannot be found:\n\n" +
                    "\n".join(["  - " + f for f in not_found])
                )
                ret = box.exec()
                if ret == QMessageBox.No:
                    for f in not_found:
                        self.results["image_files"].pop(f)

        else:  # relative path
            if not os.path.exists(self.image_folder):
                box = QMessageBox(self)
                box.setIcon(QMessageBox.Critical)
                box.setText("Directory not found. Import project failed.")
                box.setInformativeText("Select directory: {}".format(self.image_folder))
                box.setStandardButtons(QMessageBox.Ok)
                box.setDefaultButton(QMessageBox.Ok)
                box.exec()

                return

            else:
                found, not_found = [], []
                for file in self.image_files:
                    if os.path.exists(os.path.join(self.image_folder, file)):
                        found.append(file)
                    else:
                        not_found.append(file)

                self.image_files = found

                if len(not_found):
                    box = QMessageBox(self)
                    box.setIcon(QMessageBox.Warning)
                    box.setText("{} file(s) in directory \"{}\" cannot be found."
                                .format(len(not_found), self.image_folder))
                    box.setInformativeText("Do you want the project to keep them?")
                    box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                    box.setDefaultButton(QMessageBox.No)
                    box.setDetailedText(
                        "The following file(s) cannot be found:\n\n" +
                        "\n".join(["  - " + f for f in not_found])
                    )
                    ret = box.exec()
                    if ret == QMessageBox.No:
                        for f in not_found:
                            self.results["image_files"].pop(f)

        self.file_list.addFiles(self.image_files)
        for i, file in enumerate(self.image_files):
            self.file_list[i].setCheckState(Qt.Checked if self.results["image_files"][file]["labeled"]
                                            else Qt.Unchecked)
        self.file_list.selectNext()

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setText("Continue working on this opened project?")
        box.setInformativeText("If not, you may have to choose another output path"
                               " when you save the project.")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.Yes)

        ret = box.exec()
        if ret == QMessageBox.Yes:
            self.output_folder, self.output_name = os.path.split(path)
            if self.output_folder == "":
                self.output_folder = "."
            self.setClean()
        else:
        	self.setDirty()

    def importImages(self, paths: List[str]):
        if len(paths) == 0:
            return

        # clean the current content
        self.file_list.clear()
        self.canvas.clear()

        self.image_folder = None
        self.image_files = paths
        self.image_files.sort()
        self.file_list.addFiles(self.image_files)

        self.results = {
            "image_folder": "absolute_path",
            "image_files": {
                f: {
                    "labeled": False,
                    "shapes": []
                } for f in self.image_files
            }
        }
        self.file_list.selectNext()
        self.setDirty()

    def importDirImages(self, path: str):
        if not path:
            return

        # clean the current content
        self.file_list.clear()
        self.canvas.clear()
        # self.label_list.clear()
        # label_list will automatically clear since its .removeShapes()
        # has been connected to canvas' .removeShapes()

        # load new files
        self.image_folder = path
        self.image_files = []
        for ext in IMAGE_EXTENTIONS:  # ["jpg", "png"]
            self.image_files.extend(glob.glob(os.path.join(
                self.image_folder,
                "*.{}".format(ext)
            )))
        self.image_files = [os.path.split(f)[-1] for f in self.image_files]  # remove dir
        self.image_files.sort()
        self.file_list.addFiles(self.image_files)
        self.results = {
            "image_folder": path,
            "image_files": {
                f: {
                    "labeled": False,
                    "shapes": []
                } for f in self.image_files
            }
        }
        self.file_list.selectNext()
        self.setDirty()

    def openNextImg(self):
        print("[INFO] Open next image triggered.")
        current_select, next_select = self.file_list.selectNext()
        # self.changeFilesSelection() will be triggered to process canvas.
        if current_select is not None:
            self.file_list[current_select].setCheckState(Qt.Checked)
            # may trigger setDirty() if check state changes

    def openPrevImg(self):
        print("[INFO] Open previous image triggered.")
        current_select, prev_select = self.file_list.selectPrev()
        # self._changeFilesSelection() will be triggered to process canvas.
        if current_select is not None:
            self.file_list[current_select].setCheckState(Qt.Checked)

    def saveProject(self):
        print("[INFO] [from app] Saving current work...")
        selected = [i.row() for i in self.file_list.selectedIndexes()]
        assert len(selected) <= 1, "Single selection mode."
        if len(selected):
            current_file = self.image_files[selected[0]]
            self.results["image_files"][current_file]["shapes"] = self.canvas.exportShapes()
            self.file_list[selected[0]].setCheckState(Qt.Checked)

        if self.output_folder is None:
            self.output_folder = self.openDirDialog()
            if self.output_folder is None:
                return None  # cancel saving if None selected

            time_stamp = time.strftime("%m%d%H%M%S", time.localtime())
            self.output_name = "proj_" + time_stamp + ".json"

        path = os.path.join(self.output_folder, self.output_name)
        print("[INFO] [from app] Saving project to {}...".format(path))
        with open(path, "w", encoding="utf-8") as j:
            json.dump(self.results, j, ensure_ascii=False, indent=4)
        self.setClean()  # set clean, no unsaved changes
        return path

    def changeOutputDir(self):
        self.output_folder = self.openDirDialog()
        return self.output_folder

    def resizeEvent(self, e: QResizeEvent):
        super(MainWindow, self).resizeEvent(e)
        self.canvas.adjustPainter("fit_window")

    def closeEvent(self, e: QCloseEvent):
        if not self.dirty:  # no unsaved changes
            e.accept()

        else:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Question)
            box.setText("Save before closing? Or press cancel to back to canvas.")
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            box.setDefaultButton(QMessageBox.Yes)
            ret = box.exec()

            if ret == QMessageBox.Yes:
                out_path = self.saveProject()
                if out_path is None:
                    box = QMessageBox(self)
                    box.setIcon(QMessageBox.Information)
                    box.setText("Saving project canceled. Will go back to canvas.")
                    box.setStandardButtons(QMessageBox.Ok)
                    box.setDefaultButton(QMessageBox.Ok)
                    box.exec()
                    e.ignore()
                else:
                    e.accept()
            elif ret == QMessageBox.No:
                e.accept()
            else:
                e.ignore()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()
