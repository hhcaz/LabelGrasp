import math
import time
import numpy as np
import matplotlib.path

from PyQt5.QtGui import *
from PyQt5.QtCore import *

import utils
import copy


class GraspRectDispConfig(object):
    gripper_size_color = QColor(0, 255, 0)
    gripper_size_hovering_color = QColor(0, 255, 0)
    gripper_size_selected_color = QColor(0, 255, 0)

    gripper_open_color = QColor(255, 255, 0)
    gripper_open_hovering_color = QColor(255, 255, 0)
    gripper_open_selected_color = QColor(255, 255, 0)

    line_width = 2
    line_hovering_width = 3
    line_selected_width = 4

    P_SQUARE, P_ROUND = 0, 1
    point_shape = P_ROUND
    point_highlight_shape = P_SQUARE

    point_size = 8
    point_color = QColor(255, 0, 0)
    point_highlight_color = QColor(255, 255, 255)  # for both hovering and selected

    fill_alpha = 0.0
    fill_hovering_alpha = 0.3
    fill_selected_alpha = 0.5

    # Pen
    gripper_size_pen = QPen(gripper_size_color, line_width)
    gripper_size_hovering_pen = QPen(gripper_size_hovering_color, line_hovering_width)
    gripper_size_selected_pen = QPen(gripper_size_selected_color, line_selected_width)

    gripper_open_pen = QPen(gripper_open_color, line_width)
    gripper_open_hovering_pen = QPen(gripper_open_hovering_color, line_hovering_width)
    gripper_open_selected_pen = QPen(gripper_open_selected_color, line_selected_width)


class GraspRectBuilder(object):
    def __init__(self):
        self.points = np.zeros((4, 2), dtype=np.float)
        self.determined_num = 0
        self.grasp = GraspRect(self.points)

    def processPoint(self, pos: QPointF, button: Qt.MouseButton):
        assert isinstance(pos, QPointF), "Only support QPointF."
        point = np.array([pos.x(), pos.y()], dtype=np.float)

        if button == Qt.RightButton:
            self.determined_num = 0
            return False

        if self.determined_num == 0:
            self.points[:] = point

            if button == Qt.LeftButton:
                self.determined_num += 1

        elif self.determined_num == 1:
            self.points[1] = point
            self.points[2] = self.points[1]
            self.points[3] = self.points[0]

            dist = np.linalg.norm(self.points[1] - self.points[0])
            if (button == Qt.LeftButton) and (dist > 1):
                self.determined_num += 1

        elif self.determined_num == 2:
            vec, dist, _ = utils.vec_from_line_to_point(self.points[0], self.points[1], point)

            self.points[2] = self.points[1] + vec
            self.points[3] = self.points[0] + vec

            if (button == Qt.LeftButton) and (dist > 1):
                self.determined_num += 2

        self.grasp.setPoints(self.points)

    def isBuilding(self):
        return 1 <= self.determined_num <= 3

    def isFinished(self):
        return self.determined_num == 4

    def reset(self):
        self.determined_num = 0
        self.points = np.zeros((4, 2), dtype=np.float)
        self.grasp = GraspRect(self.points)

    def fetchResult(self):
        grasp = self.grasp
        self.reset()
        return grasp

    def paint(self, painter: QPainter):
        if self.determined_num == 0:
            return
        self.grasp.paint(painter)


# namedtuple cannot be pickled by qt
# Grasp = namedtuple('_GraspTuple', ['center', 'gripper_size', 'gripper_open', 'angle'])
class Grasp(object):
    def __init__(self, center, gripper_size, gripper_open, angle):
        self.center = center
        self.gripper_size = gripper_size
        self.gripper_open = gripper_open
        self.angle = angle

    def __repr__(self):
        return "center = {}, gripper_size = {:.3f}, gripper_open = {:.3f}, angle = {:.3f}"\
            .format(self.center, self.gripper_size, self.gripper_open, self.angle)

    def __eq__(self, other):
        if not isinstance(other, Grasp):
            return False
        return np.all(self.center == other.center) \
            and (self.gripper_size == other.gripper_size) \
            and (self.gripper_open == other.gripper_open) \
            and (self.angle == other.angle)

    def __ne__(self, other):
        if not isinstance(other, Grasp):
            return True
        return np.any(self.center != other.center) \
            or (self.gripper_size != other.gripper_size) \
            or (self.gripper_open != other.gripper_open) \
            or (self.angle != other.angle)


class GraspRect(object):
    """
        p3          ^   e2      p2
        ------------|------------
        |           | angle     |
     e3 |    center |-----------|-e1-> gripper_open
        |                       |
        -------------------------
        p0   e0  gripper_size   p1
    """

    edge_select_tolerance = GraspRectDispConfig.line_selected_width / 2.
    vertex_select_tolerance = GraspRectDispConfig.point_size / 2.

    def __init__(self, points: np.ndarray = None):
        super(GraspRect, self).__init__()
        self._id = "{:.7f}".format(time.perf_counter())

        if points is None:
            self._points = np.zeros((4, 2))
            self._grasp = Grasp(np.zeros(2), 0., 0., 0.)
            self._edges = self.computeEdgesFromPoints(self._points)
        else:
            self._grasp = self.computeGraspFromPoints(points)
            self._points = self.computePointsFromGrasp(self._grasp)  # (4, 2)
            self._edges = self.computeEdgesFromPoints(self._points)  # (4, 2, 2)
            # edge: 4 lines; line: 2 points; point: 2 coordinates;

        # 可视状态
        self._visible = True

        # 选中状态
        self._selected = False
        self._selected_point_idx = None
        self._selected_edge_idx = None

        # 指针停留状态
        self._hovering = False
        self._hovering_point_idx = None
        self._hovering_edge_idx = None

        # 记录指针
        self._pre_cursor_pos = None

        # flags
        self._selected_changed = False
        self._visible_changed = False
        self._area_changed = False

    def __repr__(self):
        return "GraspRect: id = {}, content = {}".format(self._id, self._grasp)

    def copy(self, new_id=False):
        copied = GraspRect(None)
        copied.setGrasp(self.grasp())
        if not new_id:
            copied._id = self.id()
        return copied

    def id(self):
        return self._id

    def grasp(self):
        return copy.copy(self._grasp)

    def setPoints(self, points: np.ndarray):
        if (self._points != points).any():
            self._grasp = self.computeGraspFromPoints(points)
            self._points = self.computePointsFromGrasp(self._grasp)
            self._edges = self.computeEdgesFromPoints(self._points)
            self._area_changed = True

    def setGrasp(self, grasp: Grasp):
        if self._grasp != grasp:
            self._grasp = copy.copy(grasp)
            self._points = self.computePointsFromGrasp(self._grasp)
            self._edges = self.computeEdgesFromPoints(self._points)
            self._area_changed = True

    def points(self):
        return self._points.copy()

    def edges(self):
        return self._edges.copy()

    def visible(self):
        return self._visible

    def setVisible(self, visible=True):
        if self._visible != visible:
            self._visible = visible
            # if not self._visible:
            #     self.resetSelected()
            self._visible_changed = True

    def selected(self):
        # 只选中区域本身
        return self._selected

    def setSelected(self, select=True):
        if self._selected != select:
            self._selected = select
            self._selected_changed = True

    def selectedAnything(self):
        # 区域、边、点
        return self._selected \
               or (self._selected_point_idx is not None) \
               or (self._selected_edge_idx is not None)

    def resetSelected(self):
        self._selected_point_idx = None
        self._selected_edge_idx = None
        self.setSelected(False)

    def hovering(self):
        return self._hovering

    def hoveringAnything(self):
        return self._hovering \
               or (self._hovering_point_idx is not None) \
               or (self._hovering_edge_idx is not None)

    def resetHovering(self):
        self._hovering_point_idx = None
        self._hovering_edge_idx = None
        self._hovering = False

    def setCursorPos(self, pos: QPointF):
        self._pre_cursor_pos = pos

    def selectedChanged(self):
        return self._selected_changed

    def resetSelectedChanged(self):
        self._selected_changed = False

    def visibleChanged(self):
        return self._visible_changed

    def resetVisibleChanged(self):
        self._visible_changed = False

    def areaChanged(self):
        return self._area_changed

    def resetAreaChanged(self):
        self._area_changed = False

    def resetChanged(self):
        self._selected_changed = False
        self._visible_changed = False
        self._area_changed = False

    @classmethod
    def computeGraspFromPoints(cls, points) -> Grasp:
        center = points.mean(axis=0)
        gripper_size = math.hypot(points[0, 0] - points[1, 0], points[0, 1] - points[1, 1])
        gripper_open = math.hypot(points[1, 0] - points[2, 0], points[1, 1] - points[2, 1])

        if gripper_open > gripper_size:
            angle = math.atan2(points[1, 1] - points[2, 1], points[1, 0] - points[2, 0])
        else:
            angle = math.atan2(points[0, 1] - points[1, 1], points[0, 0] - points[1, 0]) + math.pi / 2.
            angle = utils.norm_angle(angle)

        return Grasp(center, gripper_size, gripper_open, angle)

    @classmethod
    def computePointsFromGrasp(cls, grasp: Grasp):
        vec_ul = (grasp.gripper_open / 2. * math.cos(grasp.angle) +
                  grasp.gripper_size / 2. * math.cos(grasp.angle + math.pi / 2.),
                  grasp.gripper_open / 2. * math.sin(grasp.angle) +
                  grasp.gripper_size / 2. * math.sin(grasp.angle + math.pi / 2.))

        vec_ur = (grasp.gripper_open / 2. * math.cos(grasp.angle) -
                  grasp.gripper_size / 2. * math.cos(grasp.angle + math.pi / 2.),
                  grasp.gripper_open / 2. * math.sin(grasp.angle) -
                  grasp.gripper_size / 2. * math.sin(grasp.angle + math.pi / 2.))

        p0 = grasp.center - vec_ur
        p1 = grasp.center - vec_ul
        p2 = grasp.center + vec_ur
        p3 = grasp.center + vec_ul

        return np.array([p0, p1, p2, p3], dtype=np.float)

    @classmethod
    def computeEdgesFromPoints(cls, points: np.ndarray):
        return np.stack((points, points[[1, 2, 3, 0]]), axis=1)

    def getNearestVertex(self, pos: QPointF):
        dists = np.hypot(self._points[:, 0] - pos.x(), self._points[:, 1] - pos.y())
        idx = np.argmin(dists)
        return idx, dists[idx]

    def getNearestEdge(self, pos: QPointF):
        out_point = np.array([pos.x(), pos.y()], dtype=np.float)
        dists = [utils.dist_from_line_to_point(line[0], line[1], out_point)
                 for line in self._edges]
        idx = np.argmin(dists)
        return idx, dists[idx]

    def containsPoint(self, pos: QPointF):
        polygon = matplotlib.path.Path(self._points)
        return polygon.contains_point((pos.x(), pos.y()))

    def checkPos(self, pos: QPointF):
        # 根据鼠标点的坐标判断是否在矩形内、矩形周围、某个点周围、某条线周围。
        # 判断的优先级为 在矩形内=点>线（点线互相排斥，至少一个为None），
        # 前面三个只要任意一个满足就可以认为在矩形附近为真（near_rect=True）
        point_idx, edge_idx = None, None
        idx, dist = self.getNearestVertex(pos)
        if dist < self.vertex_select_tolerance:
            point_idx = idx
        else:
            idx, dist = self.getNearestEdge(pos)
            if dist < self.edge_select_tolerance:
                edge_idx = idx

        in_shape = self.containsPoint(pos)
        near_shape = (point_idx is not None) or (edge_idx is not None) or in_shape

        return in_shape, near_shape, point_idx, edge_idx

    def checkPosAndSelect(self, pos: QPointF, shape_only=True):
        if not self._visible:
            return

        if shape_only:
            self._selected_point_idx = None
            self._selected_edge_idx = None
            self.setSelected(self.containsPoint(pos))
        else:
            in_shape, near_shape, point_idx, edge_idx = self.checkPos(pos)
            self._selected_point_idx = point_idx
            self._selected_edge_idx = edge_idx
            self.setSelected(near_shape)

    def checkPosAndHover(self, pos: QPointF, shape_only=True):
        if not self._visible:
            return

        if shape_only:
            self._hovering_point_idx = None
            self._hovering_edge_idx = None
            self._hovering = self.containsPoint(pos)
        else:
            in_shape, near_shape, point_idx, edge_idx = self.checkPos(pos)
            self._hovering_point_idx = point_idx
            self._hovering_edge_idx = edge_idx
            self._hovering = near_shape

    def checkSelectedAndMove(self, pos: QPointF):
        if self._selected_point_idx is not None:
            self.movePointUpdate(self._selected_point_idx, pos)
        elif self._selected_edge_idx is not None:
            self.moveEdgeUpdate(self._selected_edge_idx, pos)
        elif self._selected:
            self.moveWholeUpdate(pos)

    def checkSelectedAndRotate(self, pos: QPointF):
        if self._selected:
            self.rotateWholeUpdate(pos)

    def movePointUpdate(self, select_idx, new_pos: QPointF):
        """给定选中点的下标和新位置，更新整个 grasp， 被 mouseMoveUpdate() 调用"""
        oppo_idx = (select_idx + 2) % 4  # 获得对角点坐标
        gripper_open_line = (self._points[oppo_idx],
                             self._points[oppo_idx]
                             + np.array([math.cos(self._grasp.angle), math.sin(self._grasp.angle)]))

        gripper_size_line = (self._points[oppo_idx],
                             self._points[oppo_idx] + np.array([math.cos(self._grasp.angle + math.pi / 2.),
                                                                math.sin(self._grasp.angle + math.pi / 2.)]))

        new_point = np.array([new_pos.x(), new_pos.y()], dtype=np.float)
        _, new_gripper_size, _ = utils.vec_from_line_to_point(*gripper_open_line, new_point)
        _, new_gripper_open, _ = utils.vec_from_line_to_point(*gripper_size_line, new_point)
        new_center = (new_point + self._points[oppo_idx]) / 2.

        new_grasp = Grasp(new_center, new_gripper_size, new_gripper_open, self._grasp.angle)
        self.setGrasp(new_grasp)
        # 更新的逻辑为：从鼠标点向对角点的两条边作垂足，两条垂线的长度就是新的 gripper_size 和新的 gripper_open，
        # 鼠标点到对角点的中心点就是新的 grasp 的中心

    def moveEdgeUpdate(self, select_idx, new_pos: QPointF):
        """给定选中边的下标和新位置，更新整个 grasp，被 mouseMoveUpdate() 调用"""
        oppo_idx = (select_idx + 2) % 4
        if oppo_idx % 2 == 0:  # 选中了代表了 gripper_size 的边
            oppo_line = (self._points[oppo_idx], self._points[(oppo_idx + 1) % 4])  # 获取对边
            # 参考边为对边所在的直线，取了长度为1是为了防止对边太长或太短带来的数值计算上的问题
            ref_line = (self._points[oppo_idx],
                        self._points[oppo_idx] + np.array([math.cos(self._grasp.angle + math.pi / 2.),
                                                           math.sin(self._grasp.angle + math.pi / 2.)]))

            new_point = np.array([new_pos.x(), new_pos.y()], dtype=np.float)
            vec, new_gripper_open, cross_point = utils.vec_from_line_to_point(*ref_line, new_point)
            new_center = (oppo_line[0] + oppo_line[1]) / 2. + vec / 2.

            new_grasp = Grasp(new_center, self._grasp.gripper_size, new_gripper_open, self._grasp.angle)
            self.setGrasp(new_grasp)
            # 更新的逻辑为：先获取对边作为参考边，然后作鼠标点到参考边的垂线，垂线的距离为新的 gripper_open 长度，
            # 鼠标点到垂足的中点就是新的 grasp 的中心

        else:  # 选中了代表了 gripper_open 的边
            oppo_line = (self._points[oppo_idx], self._points[(oppo_idx + 1) % 4])  # 获取对边
            # 参考边为对边所在的直线，取了长度为1是为了防止对边太长或太短带来的数值计算上的问题
            ref_line = (self._points[oppo_idx],
                        self._points[oppo_idx]
                        + np.array([math.cos(self._grasp.angle), math.sin(self._grasp.angle)]))

            new_point = np.array([new_pos.x(), new_pos.y()], dtype=np.float)
            vec, new_gripper_size, cross_point = utils.vec_from_line_to_point(*ref_line, new_point)
            new_center = (oppo_line[0] + oppo_line[1]) / 2. + vec / 2.

            new_grasp = Grasp(new_center, new_gripper_size, self._grasp.gripper_open, self._grasp.angle)
            self.setGrasp(new_grasp)
            # 更新的逻辑为：先获取对边作为参考边，然后作鼠标点到参考边的垂线，垂线的距离为新的 gripper_size 长度，
            # 鼠标点到垂足的中点就是新的 grasp 的中点

    def moveWholeUpdate(self, pos: QPointF):
        """移动整个 grasp，被 mouseMoveUpdate() 调用"""
        if self._pre_cursor_pos is None:
            self._pre_cursor_pos = pos
        delta_pos = np.array([pos.x() - self._pre_cursor_pos.x(),
                              pos.y() - self._pre_cursor_pos.y()], dtype=np.float)
        new_center = self._grasp.center + delta_pos
        new_grasp = Grasp(new_center, self._grasp.gripper_size, self._grasp.gripper_open, self._grasp.angle)
        self.setGrasp(new_grasp)

    def rotateWholeUpdate(self, pos: QPointF):
        if self._pre_cursor_pos is None:
            self._pre_cursor_pos = pos
        pre_angle = math.atan2(self._pre_cursor_pos.x() - self._grasp.center[0],
                               self._pre_cursor_pos.y() - self._grasp.center[1])
        cur_angle = math.atan2(pos.x() - self._grasp.center[0],
                               pos.y() - self._grasp.center[1])
        delta_angle = utils.norm_angle(cur_angle - pre_angle)
        new_angle = utils.norm_angle(self._grasp.angle - delta_angle)
        new_grasp = Grasp(self._grasp.center, self._grasp.gripper_size, self._grasp.gripper_open, new_angle)
        self.setGrasp(new_grasp)

    def getFillColor(self) -> QColor:
        hue = int(self._grasp.angle * 180. / math.pi) % 180 * 2
        # if hue <= 0: hue += 360
        # if hue > 360: hue -= 360
        alpha = GraspRectDispConfig.fill_selected_alpha if self._selected \
            else (GraspRectDispConfig.fill_hovering_alpha if self._hovering
                  else GraspRectDispConfig.fill_alpha)
        fill_color = QColor.fromHslF(hue / 360., 1., 0.5, alpha)
        return fill_color

    def paint(self, painter: QPainter):
        if not self._visible:
            return

        line_path = QPainterPath()
        vrtx_path = QPainterPath()
        vrtx_path.setFillRule(Qt.WindingFill)

        line_path.moveTo(self._points[0, 0], self._points[0, 1])
        for i in range(1, 4):
            line_path.lineTo(self._points[i, 0], self._points[i, 1])

        for i in range(4):
            highlight_point_shape = (i == self._hovering_point_idx) or (i == self._selected_point_idx)
            point_shape = GraspRectDispConfig.point_highlight_shape if highlight_point_shape \
                else GraspRectDispConfig.point_shape
            if point_shape == GraspRectDispConfig.P_SQUARE:
                vrtx_path.addRect(self._points[i, 0] - GraspRectDispConfig.point_size / 2.,
                                  self._points[i, 1] - GraspRectDispConfig.point_size / 2.,
                                  GraspRectDispConfig.point_size, GraspRectDispConfig.point_size)
            else:
                vrtx_path.addEllipse(self._points[i, 0] - GraspRectDispConfig.point_size / 2.,
                                     self._points[i, 1] - GraspRectDispConfig.point_size / 2.,
                                     GraspRectDispConfig.point_size, GraspRectDispConfig.point_size)

        # First fill the rect
        fill_color = self.getFillColor()
        painter.fillPath(line_path, fill_color)

        # Second draw edges
        for i in range(4):
            if i % 2 == 0:
                pen = GraspRectDispConfig.gripper_size_selected_pen if i == self._selected_edge_idx \
                    else (GraspRectDispConfig.gripper_size_hovering_pen if i == self._hovering_edge_idx
                          else GraspRectDispConfig.gripper_size_pen)
            else:
                pen = GraspRectDispConfig.gripper_open_selected_pen if i == self._selected_edge_idx \
                    else (GraspRectDispConfig.gripper_open_hovering_pen if i == self._hovering_edge_idx
                          else GraspRectDispConfig.gripper_open_pen)
            edge = self._edges[i]
            painter.setPen(pen)
            single_edge_path = QPainterPath()
            single_edge_path.moveTo(edge[0, 0], edge[0, 1])
            single_edge_path.lineTo(edge[1, 0], edge[1, 1])
            painter.drawPath(single_edge_path)

        # Finally draw points
        highlight_point_color = (self._hovering_point_idx is not None) or (self._selected_point_idx is not None)
        point_color = GraspRectDispConfig.point_highlight_color if highlight_point_color \
            else GraspRectDispConfig.point_color
        painter.fillPath(vrtx_path, point_color)

    def export(self):
        points = self.points()
        grasp = self.grasp()

        return {
            "id": self.id(),
            "points": points.tolist(),
            "center": grasp.center.tolist(),
            "gripper_size": float(grasp.gripper_size),
            "gripper_open": float(grasp.gripper_open),
            "angle": float(grasp.angle)
        }
