"""GUIDE — channel 00: what's on every channel, and where this all comes from."""
import time

import pygame

from tvkit import text, theme
from tvkit.module import Module

X0, X1 = 190, 1250
REPO = "github.com/NPCmillionaire/pizero-tv"


class Guide(Module):
    name, title, key = "guide", "GUIDE", theme.BONE
    blurb = "Every channel and what's on it"
    order = 0

    def start(self, ctx):
        super().start(ctx)
        self.reg = ctx.registry
        if self.reg is None:
            from tvkit import registry
            self.reg = registry.discover()
        self._minute = None

    def update(self, now):
        changed = super().update(now)
        m = time.strftime("%H:%M")
        if m != self._minute:
            self._minute, changed = m, True
        return changed

    def draw_static(self, surf):
        text.draw(surf, "What's on", (X0 - 4, 22), "display", 96, theme.BONE)
        chans = [c for c in self.reg.channels() if c.name != self.name]
        per_col = (len(chans) + 1) // 2
        colw = (X1 - X0) // 2
        for i, c in enumerate(chans):
            col, row = divmod(i, per_col)
            x, y = X0 + col * colw, 150 + row * 62
            n = self.reg.number(c.name)
            text.draw(surf, f"{n:02d}", (x, y), "display-600", 40, c.key if c.key else theme.BONE)
            text.draw(surf, c.title, (x + 64, y + 2), "display-600", 28, theme.BONE, max_w=colw - 84)
            text.draw(surf, c.blurb, (x + 64, y + 32), "sans", 16, theme.LICHEN, max_w=colw - 84)
        y = 150 + per_col * 62 + 10
        pygame.draw.line(surf, theme.TIDE, (X0, y), (X1, y), 1)
        text.draw(surf, "Change channel: tv up, tv down, or tv and a number. Arrow and number keys work too.",
                  (X0, y + 16), "sans", 18, theme.LICHEN, max_w=X1 - X0)
        text.draw(surf, REPO, (X0, y + 46), "mono-500", 20, theme.BONE)
        text.draw(surf, time.strftime("%A, %-I:%M %p").replace("AM", "am").replace("PM", "pm"), (X1, y + 48),
                  "sans", 20, theme.LICHEN, anchor="topright")


MODULE = Guide
