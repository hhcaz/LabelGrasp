from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *


class ToolBar(QToolBar):
    def __init__(self, title):
        super(ToolBar, self).__init__(title)
        self.layout().setSpacing(0)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)

    def addAction(self, action):
        if isinstance(action, QWidgetAction):
            return super(ToolBar, self).addAction(action)

        button = QToolButton()
        button.setDefaultAction(action)
        button.setToolButtonStyle(self.toolButtonStyle())
        self.addWidget(button)

        # center align
        for i in range(self.layout().count()):
            if isinstance(self.layout().itemAt(i).widget(), QToolButton):
                self.layout().itemAt(i).setAlignment(Qt.AlignCenter)
