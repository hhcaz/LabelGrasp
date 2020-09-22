import math
import numpy as np
import matplotlib.path


def vec_from_line_to_point(
    line_point0: np.ndarray,
    line_point1: np.ndarray,
    out_point: np.ndarray
):
    vec01 = line_point1 - line_point0
    vec0x = out_point - line_point0

    vec01_norm2 = vec01[0]**2 + vec01[1]**2
    if vec01_norm2 < 1e-6:
        vec01_norm2 = 1e-6
    proj_vec = np.dot(vec01, vec0x) * vec01 / vec01_norm2

    vec = vec0x - proj_vec
    dist = np.linalg.norm(vec)
    cross_point = line_point0 + proj_vec

    return vec, dist, cross_point


def dist_from_line_to_point(
    line_point0: np.ndarray,
    line_point1: np.ndarray,
    out_point: np.ndarray
):
    vec01 = line_point1 - line_point0
    vec10 = line_point0 - line_point1
    vec0x = out_point - line_point0
    vec1x = out_point - line_point1

    if np.dot(vec01, vec0x) < 0:
        return np.linalg.norm(vec0x)
    if np.dot(vec10, vec1x) < 0:
        return np.linalg.norm(vec1x)
    return np.linalg.norm(np.cross(vec0x, vec1x)) / np.linalg.norm(vec01)


def judge_point_in_polygon(polygon_points, point, tolerance=0):
    polygon = matplotlib.path.Path(polygon_points)
    return polygon.contains_point(point, radius=tolerance)


def get_nearest_vertex(polygon_points, point):
    dists = np.hypot(polygon_points[:, 0] - point[0], polygon_points[:, 1] - point[1])
    idx = dists.argmin()
    return idx, dists[idx]


def norm_angle(a):
    while a <= -math.pi:
        a += math.pi * 2
    while a > math.pi:
        a -= math.pi * 2
    return a


class Struct(object):
    def __init__(self, **kwargs):
        self.__dict__.update(**kwargs)
