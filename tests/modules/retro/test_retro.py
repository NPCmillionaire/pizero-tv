import numpy as np

from modules.retro import Life, MODES, Retro


def test_modes_cycle():
    r = Retro()
    names = [r.mode]
    for _ in range(len(MODES)):
        r.next_mode()
        names.append(r.mode)
    assert names[0] == names[-1] and len(set(names)) == len(MODES)


def test_life_blinker_oscillates():
    g = Life(5, 5, seed=0)
    g.grid[:] = 0
    g.grid[2, 1:4] = 1
    g.step()
    assert g.grid[1:4, 2].tolist() == [1, 1, 1] and g.grid[2].sum() == 1
    g.step()
    assert g.grid[2, 1:4].tolist() == [1, 1, 1]


def test_life_reseeds_when_still():
    g = Life(8, 8, seed=0)
    g.grid[:] = 0
    g.step()
    assert g.grid.sum() > 0
