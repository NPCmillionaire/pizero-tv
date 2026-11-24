"""Four psychedelic channels: LIQUID, MANDALA, FRACTAL, DREAM. Full screen, computed small and scaled up."""
import math

import numpy as np
import pygame

from tvkit.module import Module

SW, SH, SCALE = 320, 180, 4                      # 1280 × 720 on screen
_x = np.linspace(-1.6, 1.6, SW, dtype=np.float32)[:, None]
_y = np.linspace(-0.9, 0.9, SH, dtype=np.float32)[None, :]
X, Y = np.broadcast_to(_x, (SW, SH)), np.broadcast_to(_y, (SW, SH))
VIGNETTE = np.clip(1.25 - np.sqrt(X * X + Y * Y) * 0.55, 0, 1).astype(np.float32)[..., None]
ACID = [[(10, 0, 20), (255, 0, 140), (255, 140, 0), (255, 255, 60), (0, 255, 180), (40, 80, 255)],
        [(0, 0, 0), (120, 0, 255), (0, 200, 255), (180, 255, 0), (255, 0, 90), (255, 220, 0)],
        [(5, 0, 10), (255, 40, 0), (255, 0, 200), (0, 120, 255), (0, 255, 120), (255, 255, 255)]]


def gradient(stops, n=256, shift=0.0):
    s = np.array(stops, np.float32)
    x = (np.linspace(0, 1, n, dtype=np.float32) + np.float32(shift)) % 1.0
    tri = 1 - np.abs(2 * x - 1)
    pos = tri * (len(s) - 1)
    i = np.clip(pos.astype(int), 0, len(s) - 2)
    f = (pos - i)[:, None]
    return (s[i] * (1 - f) + s[i + 1] * f).astype(np.uint8)


def _show(surf, rgb):
    small = pygame.surfarray.make_surface(rgb)
    surf.blit(pygame.transform.scale(small, (SW * SCALE, SH * SCALE)), (0, 0))


class Art(Module):
    order = 131
    fps = 10
    footer_color = (120, 120, 140)

    def draw_frame(self, surf):
        surf.fill((0, 0, 0))

    def draw_static(self, surf):
        pass

    def status(self):
        return None, None


# -- LIQUID: a 1960s oil-wheel light show ---------------------------------------------------
def liquid_field(t):
    # domain-warped metaballs: big dye blobs that stretch, merge and split like oil on a wheel
    xw = X + 0.18 * np.sin(Y * 3.1 + t * 0.5) + 0.07 * np.sin(Y * 7 - t * 0.9)
    yw = Y + 0.14 * np.sin(X * 2.7 - t * 0.4) + 0.06 * np.sin(X * 6 + t * 0.7)
    v = np.zeros((SW, SH), np.float32)
    for i in range(7):
        bx = 1.2 * math.sin(t * (0.11 + i * 0.023) + i * 1.9)
        by = 0.65 * math.cos(t * (0.09 + i * 0.019) + i * 2.6)
        r2 = 0.16 + 0.06 * math.sin(t * 0.21 + i)
        v += r2 / ((xw - bx) ** 2 + (yw - by) ** 2 + 0.02)
    return v


class Liquid(Art):
    name, title, key = "liquid", "LIQUID", (255, 0, 140)
    blurb = "An oil-wheel light show, the 1967 kind"
    order = 131
    fps = 6

    def draw_live(self, surf, t):
        v = liquid_field(t)
        idx = ((np.log1p(v) * 130 + t * 6) % 256).astype(np.uint8)
        rgb = gradient(ACID[0], 256, shift=t * 0.004)[idx].astype(np.float32)
        _show(surf, np.clip(rgb * VIGNETTE, 0, 255).astype(np.uint8))
        return True


# -- MANDALA: rotating symmetric line art -----------------------------------------------------
class Mandala(Art):
    name, title, key = "mandala", "MANDALA", (180, 255, 0)
    blurb = "Sacred geometry that never sits still"
    order = 132
    fps = 12

    def start(self, ctx):
        super().start(ctx)
        self.layer = pygame.Surface((SW * 2, SH * 2))
        self.layer.fill((0, 0, 0))
        self.fade = pygame.Surface(self.layer.get_size())
        self.fade.fill((14, 10, 18))

    def draw_live(self, surf, t):
        L = self.layer
        L.blit(self.fade, (0, 0), special_flags=pygame.BLEND_RGB_SUB)
        cx, cy = SW, SH
        n = (6, 8, 12, 5, 10)[int(t // 20) % 5]          # the symmetry changes every twenty seconds
        pal = gradient(ACID[1], 64, shift=t * 0.02)
        for ring in range(4):
            k = 2 + ring
            rad = 70 + ring * 70 + 18 * math.sin(t * 0.7 + ring)
            rot = t * (0.25 if ring % 2 else -0.18) + ring
            col = tuple(int(c) for c in pal[(ring * 13 + int(t * 8)) % 64])
            pts = []
            for j in range(n * k * 6 + 1):
                a = 2 * math.pi * j / (n * k * 6)
                r = rad * (0.55 + 0.45 * abs(math.cos(n * a / 2 + t * 0.3 * (ring + 1))))
                pts.append((cx + r * math.cos(a + rot), cy + r * math.sin(a + rot)))
            pygame.draw.lines(L, col, False, pts, 2)
            for j in range(n):                            # spokes and beads on every axis
                a = rot * 1.3 + 2 * math.pi * j / n
                p = (cx + rad * math.cos(a), cy + rad * math.sin(a))
                pygame.draw.circle(L, col, (int(p[0]), int(p[1])), 3 + ring)
        surf.blit(pygame.transform.scale(L, (1280, 720)), (0, 0))
        return True


# -- FRACTAL: a Julia set that keeps changing shape -----------------------------------------
FW, FH = 256, 144
_fx = np.linspace(-1.75, 1.75, FW, dtype=np.float32)[:, None]
_fy = np.linspace(-0.98, 0.98, FH, dtype=np.float32)[None, :]
Z0 = (_fx + 1j * _fy).astype(np.complex64)


def julia(t, iters=36):
    c = np.complex64(0.7885 * complex(math.cos(t * 0.11), math.sin(t * 0.11)))
    z = Z0.copy()
    count = np.zeros(z.shape, np.float32)
    alive = np.ones(z.shape, bool)
    for _ in range(iters):
        z[alive] = z[alive] * z[alive] + c
        alive &= (z.real * z.real + z.imag * z.imag) < 16
        count += alive
    return count / iters


class Fractal(Art):
    name, title, key = "fractal", "FRACTAL", (0, 200, 255)
    blurb = "A Julia set, morphing in acid colors"
    order = 133
    fps = 5

    def draw_live(self, surf, t):
        v = julia(t)
        pal = gradient(ACID[2], 256, shift=t * 0.03)
        rgb = pal[(v * 255).astype(np.uint8)]
        rgb[v >= 0.999] = (0, 0, 0)                       # the set itself stays black
        small = pygame.surfarray.make_surface(rgb)
        surf.blit(pygame.transform.smoothscale(small, (1280, 720)), (0, 0))
        return True


# -- DREAM: video feedback, a camera pointed at its own screen ---------------------------------
class Dream(Art):
    name, title, key = "dream", "DREAM", (255, 140, 0)
    blurb = "Video feedback: the picture falling into itself"
    order = 134
    fps = 12

    def start(self, ctx):
        super().start(ctx)
        self.buf = pygame.Surface((SW, SH))
        self.buf.fill((0, 0, 0))
        self.dim = pygame.Surface((SW, SH))
        self.dim.fill((3, 3, 4))

    def draw_live(self, surf, t):
        b = self.buf
        z = pygame.transform.rotozoom(b, 1.6 * math.sin(t * 0.13) + 0.8, 1.045)
        b.blit(z, (SW // 2 - z.get_width() // 2, SH // 2 - z.get_height() // 2))
        b.blit(self.dim, (0, 0), special_flags=pygame.BLEND_RGB_SUB)
        pal = gradient(ACID[int(t // 30) % 3], 64, shift=t * 0.05)
        for i in range(3):                                # fresh light keeps falling into the tunnel
            a = t * (0.9 + i * 0.4) + i * 2.1
            p = (SW / 2 + math.cos(a) * (40 + 30 * math.sin(t * 0.3 + i)), SH / 2 + math.sin(a * 1.3) * 34)
            col = tuple(int(c) for c in pal[(i * 21 + int(t * 10)) % 64])
            pygame.draw.circle(b, col, (int(p[0]), int(p[1])), 7)
        if int(t * 10) % 37 == 0:                         # now and then the colors rotate, like a hue knob
            arr = pygame.surfarray.pixels3d(b)
            arr[...] = arr[..., [1, 2, 0]]
            del arr
        surf.blit(pygame.transform.scale(b, (1280, 720)), (0, 0))
        return True


MODULES = [Liquid, Mandala, Fractal, Dream]
