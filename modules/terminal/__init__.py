"""TERMINAL — a shell mirrored from any machine with `tv mirror`, on a public-access cable show."""
import time

import pygame

from tvkit import fx, text, theme
from tvkit.module import Module

# public-access cable: a cheap purple backdrop, a beige CRT on the desk, a yellow chyron, camcorder overlay
BACK_TOP, BACK_BOTTOM = (70, 44, 120), (18, 12, 36)
BEZEL, BEZEL_DARK, GLASS = (204, 198, 180), (150, 144, 126), (8, 12, 10)
CHYRON, CHYRON_INK, TAG, WHITE = (255, 214, 0), (20, 20, 20), (20, 60, 170), (255, 255, 255)
MONITOR = pygame.Rect(70, 26, 1140, 568)
SCREEN = MONITOR.inflate(-60, -56)
ANSI = {"black": (0, 0, 0), "red": (230, 70, 60), "green": (90, 220, 110), "brown": (230, 200, 60),
        "yellow": (240, 220, 80), "blue": (90, 140, 255), "magenta": (210, 100, 220), "cyan": (80, 210, 220),
        "white": (220, 220, 220), "default": (214, 222, 214), "brightblack": (110, 110, 110),
        "brightred": (255, 110, 100), "brightgreen": (130, 255, 150), "brightyellow": (255, 240, 120),
        "brightblue": (130, 170, 255), "brightmagenta": (240, 140, 250), "brightcyan": (120, 240, 250),
        "brightwhite": (255, 255, 255)}


def _color(name, default):
    if name in ANSI:
        return ANSI[name] if name != "default" else default
    if isinstance(name, str) and len(name) == 6:
        try:
            return tuple(int(name[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            pass
    return default


def fit_size(cols, rows, w, h):
    """The biggest mono size that fits cols × rows into w × h."""
    best = 10
    for s in range(10, 34):
        f = text.font("mono", s)
        if f.size("M" * cols)[0] <= w and f.get_linesize() * rows <= h:
            best = s
    return best


class Terminal(Module):
    name, title, key = "terminal", "TERMINAL", (255, 214, 0)
    blurb = "Your terminal, live on TV: run tv mirror -H pizero"
    aliases = ("mirror", "shell")
    order = 95
    fps = 4
    in_cycle = False
    resume = False
    footer_color = (200, 190, 230)

    def start(self, ctx):
        super().start(ctx)
        self.server = ctx.mirror
        self._seen = None

    def _session(self):
        s = self.server.session if self.server and self.server.conn else None
        return s

    def update(self, now):
        changed = super().update(now)
        s = self._session()
        key = (id(s), s.version if s else None)
        if key != self._seen:
            self._seen, changed = key, True
        return changed

    def status(self):
        return ("live", None) if self._session() else (None, None)

    def draw_frame(self, surf):
        surf.blit(fx.gradient((theme.W, theme.H), BACK_TOP, BACK_BOTTOM), (0, 0))
        pygame.draw.rect(surf, BEZEL_DARK, MONITOR.move(0, 6), border_radius=34)
        pygame.draw.rect(surf, BEZEL, MONITOR, border_radius=34)
        pygame.draw.rect(surf, GLASS, SCREEN.inflate(16, 16), border_radius=26)
        pygame.draw.circle(surf, (80, 200, 90), (MONITOR.right - 40, MONITOR.bottom - 16), 5)       # power lamp
        bar = pygame.Rect(0, 612, 1280, 58)
        pygame.draw.rect(surf, CHYRON, bar)
        pygame.draw.rect(surf, TAG, (0, 612, 250, 58))
        text.draw(surf, "Public access", (125, 641), "list-700", 30, WHITE, anchor="center")

    def draw_static(self, surf):
        s = self._session()
        if s is None:
            self._cursor = None
            lines = (["No signal", "", "On your computer, run:", "   tv mirror -H pizero", "",
                      "Whatever happens in that terminal shows up here.", "Exit the shell to stop."]
                     if self.server else
                     ["No signal", "", "Terminal mirroring needs pyte on the Pi:", "   sudo apt install python3-pyte",
                      "then restart the TV (systemctl --user restart pizero-tv)."])
            for i, line in enumerate(lines):
                text.draw(surf, line, (SCREEN.left + 20, SCREEN.top + 20 + i * 40), "mono-500" if i == 0 else "mono",
                          44 if i == 0 else 26, ANSI["brightgreen"] if i == 0 else ANSI["default"])
            text.draw(surf, "Tonight: your terminal, live", (270, 641), "list-700", 32, CHYRON_INK, anchor="midleft")
            return
        size = fit_size(s.cols, s.rows, SCREEN.width - 20, SCREEN.height - 16)
        f = text.font("mono", size)
        cw, lh = f.size("M")[0], f.get_linesize()
        x0 = SCREEN.left + 10 + (SCREEN.width - 20 - cw * s.cols) // 2
        y0 = SCREEN.top + 8
        buf = s.screen.buffer
        for row in range(s.rows):
            line = buf[row]
            col = 0
            while col < s.cols:
                ch = line[col]
                fg, bg, bold = ch.fg, ch.bg, ch.bold
                if ch.reverse:
                    fg, bg = bg, fg
                start = col
                run = []
                while col < s.cols:
                    c = line[col]
                    if (c.fg, c.bg, c.bold, c.reverse) != (ch.fg, ch.bg, ch.bold, ch.reverse):
                        break
                    run.append(c.data or " ")
                    col += 1
                fgc = _color(fg if not ch.reverse else fg, ANSI["default"] if not ch.reverse else GLASS)
                if bg != "default" or ch.reverse:
                    bgc = _color(bg, ANSI["default"] if ch.reverse else GLASS)
                    pygame.draw.rect(surf, bgc, (x0 + start * cw, y0 + row * lh, (col - start) * cw, lh))
                s_run = "".join(run).rstrip() if bg == "default" and not ch.reverse else "".join(run)
                if s_run.strip():
                    img = text.render(s_run, "mono-500" if bold else "mono", size, fgc)
                    surf.blit(img, (x0 + start * cw, y0 + row * lh))
        c = s.screen.cursor
        self._cursor = None if c.hidden else (x0 + c.x * cw, y0 + c.y * lh, cw, lh)
        mins = int(time.time() - s.started) // 60
        text.draw(surf, f"Live from {s.host}", (270, 641), "list-700", 34, CHYRON_INK, anchor="midleft", max_w=640)
        text.draw(surf, f"on the air {mins} min" if mins else "just went on the air", (1240, 641), "list", 26,
                  CHYRON_INK, anchor="midright")

    def draw_live(self, surf, t):
        # camcorder overlay: blinking REC and a running date stamp, plus the terminal's cursor
        if int(t * 1.5) % 2 == 0:
            pygame.draw.circle(surf, (230, 30, 30), (34, 690), 8)
        text.draw(surf, "REC", (50, 690), "vga", 28, WHITE, anchor="midleft")
        pygame.draw.rect(surf, BACK_BOTTOM, (820, 674, 262, 34))
        text.draw(surf, time.strftime("%b %d %Y  %H:%M:%S").upper(), (1078, 690), "vga", 28, WHITE, anchor="midright")
        cur = getattr(self, "_cursor", None)
        if cur and int(t * 2) % 2 == 0:
            pygame.draw.rect(surf, ANSI["default"], cur)
        return True


MODULE = Terminal
