import os

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

here = os.path.dirname(os.path.abspath(__file__))


def new_action(parent, text, slot=None, shortcut=None, icon=None):
    a = QAction(text, parent)

    if icon is not None:
        icon_path = os.path.join(here, "icons", icon)
        a.setIconText(text.replace(" ", "\n"))
        a.setIcon(QIcon(icon_path))

    if shortcut is not None:
        if isinstance(shortcut, (list, tuple)):
            a.setShortcuts(shortcut)
        else:
            a.setShortcut(shortcut)

    if slot is not None:
        a.triggered.connect(slot)

    return a


def add_actions(widget: QWidget, actions):
    for action in actions:
        if action is None:
            widget.addSeparator()
        elif isinstance(action, QMenu):
            widget.addMenu(action)
        else:
            widget.addAction(action)