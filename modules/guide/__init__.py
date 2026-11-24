"""GUIDE — channel 00: the cable listings channel. Every channel, scrolling past, with a promo up top."""
import time

import pygame

from tvkit import text, theme
from tvkit.module import Module

REPO = "github.com/NPCmillionaire/pizero-tv"
PROMO_S = 7                     # the promo box features each channel in turn
SCROLL = 22                     # listings scroll up at 22 px a second
# listings-channel blues, white type, yellow time bar
NAVY, CELL, CHAN, EDGE = (6, 10, 70), (22, 40, 128), (10, 70, 170), (60, 96, 196)
WHITE, PALE, YELLOW = (255, 255, 255), (180, 200, 255), (255, 222, 60)
GRID = pygame.Rect(30, 352, 1220, 300)
ROW_H, CHAN_W = 60, 280


def _half_hours(now):
    t = time.localtime(now)
    start = now - (t.tm_min % 30) * 60 - t.tm_sec
    return [start + k * 1800 for k in range(3)]


def _clock(ts):
    t = time.localtime(ts)
    return f"{t.tm_hour % 12 or 12}:{t.tm_min:02d} {'am' if t.tm_hour < 12 else 'pm'}"


class Guide(Module):
    name, title, key = "guide", "GUIDE", theme.BONE
    blurb = "Every channel and what's on it"
    order = 0
    fps = 15
    footer_color = PALE

    def start(self, ctx):
        super().start(ctx)
        self.reg = ctx.registry
        if self.reg is None:
            from tvkit import registry
            self.reg = registry.discover()
        self._minute, self.promo, self._rows = None, 0, None

    def channels(self):
        return [c for c in self.reg.channels() if c.name != self.name]

    def update(self, now):
        changed = super().update(now)
        m = time.strftime("%H:%M")
        if m != self._minute:
            self._minute, changed, self._rows = m, True, None
        p = int(now // PROMO_S)
        if p != self.promo:
            self.promo, changed = p, True
        return changed

    def draw_frame(self, surf):
        surf.fill(NAVY)

    def draw_static(self, surf):
        now = time.time()
        text.draw(surf, "Channel guide", (30, 24), "list-700", 64, WHITE)
        text.draw(surf, time.strftime("%A %-d %B"), (34, 100), "list", 30, PALE)
        text.draw(surf, _clock(now), (34, 140), "list-700", 84, YELLOW)
        text.draw(surf, "Change channel: tv up, tv down, or tv and a number.", (34, 246), "list", 26, PALE,
                  max_w=520)
        text.draw(surf, REPO, (34, 282), "mono-500", 20, WHITE)
        self._promo(surf)
        # the time bar over the listings
        bar = pygame.Rect(GRID.left, GRID.top - 40, GRID.width, 36)
        pygame.draw.rect(surf, YELLOW, bar)
        text.draw(surf, time.strftime("%a %-d %b"), (bar.left + 14, bar.centery), "list-700", 24, NAVY,
                  anchor="midleft")
        slot_w = (GRID.width - CHAN_W) // 3
        for k, ts in enumerate(_half_hours(now)):
            text.draw(surf, _clock(ts), (GRID.left + CHAN_W + k * slot_w + 12, bar.centery), "list-700", 24, NAVY,
                      anchor="midleft")

    def _promo(self, surf):
        chans = self.channels()
        r = pygame.Rect(600, 24, 650, 270)
        pygame.draw.rect(surf, CELL, r)
        pygame.draw.rect(surf, EDGE, r, 2)
        if not chans:
            return
        c = chans[self.promo % len(chans)]
        n = self.reg.number(c.name)
        text.draw(surf, "Coming up", (r.left + 24, r.top + 18), "list", 26, PALE)
        text.draw(surf, f"Channel {n}", (r.right - 24, r.top + 18), "list-700", 26, YELLOW, anchor="topright")
        text.draw(surf, c.title, (r.left + 22, r.top + 52), "list-700", 96, WHITE, max_w=r.width - 44)
        for j, line in enumerate(text.wrap(c.blurb, "list", 32, r.width - 48)[:2]):
            text.draw(surf, line, (r.left + 24, r.top + 164 + j * 36), "list", 32, PALE)
        text.draw(surf, f"tv {n}", (r.right - 24, r.bottom - 16), "mono-500", 20, YELLOW, anchor="bottomright")

    def _listing(self):
        """All rows rendered once onto a tall strip (twice over, so the scroll can loop)."""
        chans = self.channels()
        h = max(1, len(chans)) * ROW_H
        strip = pygame.Surface((GRID.width, h * 2))
        strip.fill(NAVY)
        for rep in range(2):
            for i, c in enumerate(chans):
                y = rep * h + i * ROW_H
                pygame.draw.rect(strip, CHAN, (0, y + 2, CHAN_W - 4, ROW_H - 4))
                n = self.reg.number(c.name)
                text.draw(strip, f"{n:02d}", (14, y + ROW_H // 2), "list-700", 34, YELLOW, anchor="midleft")
                text.draw(strip, c.title, (70, y + ROW_H // 2), "list-700", 30, WHITE, anchor="midleft",
                          max_w=CHAN_W - 90)
                cell = pygame.Rect(CHAN_W, y + 2, GRID.width - CHAN_W, ROW_H - 4)
                pygame.draw.rect(strip, CELL, cell)
                text.draw(strip, c.blurb, (cell.left + 14, cell.centery), "list", 28, WHITE, anchor="midleft",
                          max_w=cell.width - 160)
                text.draw(strip, "On all day", (cell.right - 14, cell.centery), "list", 24, PALE,
                          anchor="midright")
        return strip, h

    def draw_live(self, surf, t):
        if self._rows is None:
            self._rows = self._listing()
        strip, h = self._rows
        off = int(t * SCROLL) % h if h > GRID.height else 0
        surf.blit(strip, GRID.topleft, pygame.Rect(0, off, GRID.width, GRID.height))
        return h > GRID.height


MODULE = Guide
