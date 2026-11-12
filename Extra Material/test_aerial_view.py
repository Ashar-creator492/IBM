"""
test_aerial_view.py -- terrain + new map_engine options (depot / manual EW zones / radius range).
Run:  python test_aerial_view.py
"""
import numpy as np

import aerial_view as A
from map_engine import generate_mission


def test_terrain_deterministic_and_normalised():
    a, b, c = A.make_terrain(42), A.make_terrain(42), A.make_terrain(43)
    assert a.shape == (110, 110) and np.array_equal(a, b) and not np.array_equal(a, c)
    assert abs(a.min()) < 1e-9 and abs(a.max() - 1) < 1e-9
    f = A.aerial_field(a)
    assert f.shape == a.shape and f.min() >= 0 and f.max() <= 1 and np.isfinite(f).all()


def test_elevation_lookup_edges():
    t = A.make_terrain(1)
    e = A.elevation_at(t, np.array([0, 100, 50.0]), np.array([0, 100, 50.0]), relief=6.0)
    assert e.shape == (3,) and (e >= 0).all() and (e <= 6.0).all()


def test_depot_override_keeps_other_nodes():
    base = generate_mission(12, 3, seed=7)
    m = generate_mission(12, 3, seed=7, depot=(5.0, 95.0))
    assert tuple(m.coords[0]) == (5.0, 95.0)
    assert np.array_equal(m.coords[1:], base.coords[1:]) and np.array_equal(m.threat_centers, base.threat_centers)
    assert tuple(generate_mission(6, 2, seed=1, depot=(-10, 400)).coords[0]) == (0.0, 100.0)   # clipped to grid


def test_manual_zones_and_radius_range():
    m = generate_mission(8, 5, seed=3, zones=[(30, 40, 12), (60, 65, 10)])
    assert len(m.threat_radii) == 2 and list(m.threat_radii) == [12.0, 10.0]
    assert generate_mission(8, 0, seed=3, zones=[]).W.shape == (8, 8)
    m2 = generate_mission(8, 4, seed=3, radius_range=(20.0, 20.0))
    assert np.allclose(m2.threat_radii, 20.0)
    # default call must be unchanged so the saved benchmark cache stays valid
    d = generate_mission(10, 3, seed=42)
    assert np.array_equal(d.coords, generate_mission(10, 3, seed=42, depot=None, zones=None).coords)


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v(); print("ok", k)
