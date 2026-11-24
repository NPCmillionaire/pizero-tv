import numpy as np
import pytest

from modules.trippy import FIELDS, FW, FH, field, palette


@pytest.mark.parametrize("name", FIELDS)
def test_field_shape_320x180(name):
    v = field(name, 1.5)
    assert v.shape == (FW, FH) and v.dtype == np.float32
    assert np.isfinite(v).all() and v.min() >= 0 and v.max() <= 1


def test_palette_uint8():
    p = palette(0.3)
    assert p.shape == (256, 3) and p.dtype == np.uint8
