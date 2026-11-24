from modules.matrix import Rain, GLYPHS


def test_columns_fill_width():
    r = Rain(1130, 720, cell=18, seed=1)
    assert len(r.columns) == 1130 // 18
    assert all(0 <= c.x < 1130 for c in r.columns)


def test_glyphs_include_katakana_and_digits():
    assert any("ｦ" <= g <= "ﾝ" for g in GLYPHS) and "7" in GLYPHS


def test_step_moves_heads_and_wraps():
    r = Rain(180, 200, cell=18, seed=2)
    ys = [c.y for c in r.columns]
    for _ in range(200):
        r.step(0.1)
    assert [c.y for c in r.columns] != ys and all(c.y < 200 + 18 * 40 for c in r.columns)
