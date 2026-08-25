from __future__ import annotations

import math
from typing import Iterable


def _ring_area_m2(ring: list[list[float]]) -> float:
    """Shoelace area on lon/lat ring with latitude correction."""
    if len(ring) < 3:
        return 0.0
    closed = ring[:-1] if ring[0] == ring[-1] else ring
    if len(closed) < 3:
        return 0.0
    mean_lat = sum(p[1] for p in closed) / len(closed)
    lat_scale = 111_320.0
    lon_scale = 111_320.0 * math.cos(math.radians(mean_lat))
    area = 0.0
    for i in range(len(closed)):
        x1, y1 = closed[i][0] * lon_scale, closed[i][1] * lat_scale
        x2, y2 = closed[(i + 1) % len(closed)][0] * lon_scale, closed[(i + 1) % len(closed)][1] * lat_scale
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def _inside(p: tuple[float, float], edge_start: tuple[float, float], edge_end: tuple[float, float]) -> bool:
    return (edge_end[0] - edge_start[0]) * (p[1] - edge_start[1]) - (edge_end[1] - edge_start[1]) * (
        p[0] - edge_start[0]
    ) >= 0


def _intersection(
    s: tuple[float, float],
    e: tuple[float, float],
    edge_start: tuple[float, float],
    edge_end: tuple[float, float],
) -> tuple[float, float]:
    dc = (s[0] - e[0], s[1] - e[1])
    dp = (edge_start[0] - edge_end[0], edge_start[1] - edge_end[1])
    n1 = s[0] * e[1] - s[1] * e[0]
    n2 = edge_start[0] * edge_end[1] - edge_start[1] * edge_end[0]
    denom = dc[0] * dp[1] - dc[1] * dp[0]
    if abs(denom) < 1e-15:
        return s
    x = (n1 * dp[0] - n2 * dc[0]) / denom
    y = (n1 * dp[1] - n2 * dc[1]) / denom
    return (x, y)


def _clip_polygon(subject: list[tuple[float, float]], clip_edge: tuple[tuple[float, float], tuple[float, float]]) -> list[tuple[float, float]]:
    if not subject:
        return []
    output: list[tuple[float, float]] = []
    edge_start, edge_end = clip_edge
    prev = subject[-1]
    for curr in subject:
        prev_inside = _inside(prev, edge_start, edge_end)
        curr_inside = _inside(curr, edge_start, edge_end)
        if curr_inside:
            if not prev_inside:
                output.append(_intersection(prev, curr, edge_start, edge_end))
            output.append(curr)
        elif prev_inside:
            output.append(_intersection(prev, curr, edge_start, edge_end))
        prev = curr
    return output


def _to_ring(coords: list[list[float]]) -> list[tuple[float, float]]:
    ring = coords[:-1] if coords and coords[0] == coords[-1] else coords
    return [(float(p[0]), float(p[1])) for p in ring]


def intersect_polygon_area_m2(ring_a: list[list[float]], ring_b: list[list[float]]) -> float:
    """
    Intersection area between two simple polygons (lon/lat rings) via Sutherland-Hodgman.
    Deterministic; suitable for convex / simply-shaped change regions.
    """
    subject = _to_ring(ring_a)
    clip = _to_ring(ring_b)
    if len(subject) < 3 or len(clip) < 3:
        return 0.0
    output = subject
    for i in range(len(clip)):
        edge = (clip[i], clip[(i + 1) % len(clip)])
        output = _clip_polygon(output, edge)
        if not output:
            return 0.0
    return _ring_area_m2([[p[0], p[1]] for p in output] + [[output[0][0], output[0][1]]])


def overlap_fraction_of_child(parent_ring: list[list[float]], child_ring: list[list[float]]) -> float:
    """Fraction of child polygon area that intersects the parent polygon."""
    child_area = _ring_area_m2(child_ring)
    if child_area <= 0:
        return 0.0
    intersection = intersect_polygon_area_m2(parent_ring, child_ring)
    return round(intersection / child_area, 4)


def polygon_area_km2(ring: list[list[float]]) -> float:
    return round(_ring_area_m2(ring) / 1_000_000.0, 6)
