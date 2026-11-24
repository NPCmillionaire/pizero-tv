"""MOST WANTED — the newest entries in CISA's Known Exploited Vulnerabilities catalog, as wanted posters."""
import random

import pygame
import requests

from tvkit import text, theme
from tvkit.module import Module

from . import data

URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
PAGE_S = 15
PER_PAGE, PAGES = 3, 3
# a corkboard in the squad room, sepia posters, red pins, a red rubber stamp
CORK, CORK_DARK, PAPER, PAPER_EDGE = (92, 62, 38), (64, 42, 26), (236, 224, 196), (196, 178, 140)
INKC, FADED, RED, PIN = (34, 28, 22), (110, 96, 78), (190, 30, 30), (210, 40, 40)
PW, PH = 372, 520


def _date(d):
    return d.strftime("%-d %b %Y") if d else "none set"


class MostWanted(Module):
    name, title, key = "kev", "WANTED", theme.CORAL
    blurb = "Most wanted: vulnerabilities attackers are using right now, from CISA"
    aliases = ("mostwanted", "wanted", "cisa")
    order = 42
    fps = 4
    footer_color = (230, 214, 186)

    def start(self, ctx):
        super().start(ctx)
        self.src = self.source("kev", lambda: requests.get(URL, timeout=30).json(), 6 * 3600, parse=data.parse)
        self.page = 0
        self._cork = None

    def update(self, now):
        changed = super().update(now)
        p = int(now // PAGE_S) % PAGES
        if p != self.page:
            self.page, changed = p, True
        return changed

    def draw_frame(self, surf):
        if self._cork is None:
            self._cork = pygame.Surface((theme.W, theme.H))
            self._cork.fill(CORK)
            rng = random.Random(7)
            for _ in range(9000):                          # cork grain
                x, y = rng.randrange(theme.W), rng.randrange(theme.H)
                c = theme.mix(CORK, CORK_DARK if rng.random() < 0.6 else (130, 92, 58), rng.random())
                pygame.draw.circle(self._cork, c, (x, y), rng.choice((1, 1, 2)))
        surf.blit(self._cork, (0, 0))
        pygame.draw.rect(surf, (48, 30, 18), (0, 0, theme.W, theme.H), 14)       # the frame
        text.draw(surf, "Most wanted", (40, 26), "display", 60, PAPER)

    def draw_static(self, surf):
        c = self.src.value
        if c is None:
            msg = {"offline": "CISA's catalog isn't answering.", "waiting": "Fetching CISA's catalog."}.get(
                self.src.status, "")
            text.draw(surf, msg, (44, 110), "mono-500", 24, PAPER)
            return
        text.draw(surf, f"{c.total:,} vulnerabilities on CISA's list of ones being exploited. "
                        f"{c.added_30d} added in the last 30 days.", (44, 96), "mono", 18, PAPER, max_w=1190)
        posts = c.recent[self.page * PER_PAGE:(self.page + 1) * PER_PAGE] or c.recent[:PER_PAGE]
        rng = random.Random(self.page)
        for i, v in enumerate(posts):
            poster = self._poster(v, self.page * PER_PAGE + i + 1)
            tilt = rng.uniform(-2.2, 2.2)
            img = pygame.transform.rotozoom(poster, tilt, 1.0)
            cx = 40 + PW // 2 + i * (PW + 37)
            r = img.get_rect(center=(cx, 150 + PH // 2))
            shadow = pygame.Surface(img.get_size(), pygame.SRCALPHA)
            shadow.fill((0, 0, 0, 70))
            shadow.blit(img, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            surf.blit(shadow, r.move(6, 8))
            surf.blit(img, r)
            pygame.draw.circle(surf, (90, 10, 10), (cx + 1, r.top + 16), 9)
            pygame.draw.circle(surf, PIN, (cx, r.top + 14), 9)
            pygame.draw.circle(surf, (255, 150, 150), (cx - 3, r.top + 11), 3)

    def _poster(self, v, n):
        p = pygame.Surface((PW, PH), pygame.SRCALPHA)
        p.fill(PAPER)
        pygame.draw.rect(p, PAPER_EDGE, p.get_rect(), 3)
        text.draw(p, "Wanted", (PW // 2, 30), "display", 66, INKC, anchor="midtop")
        crime = data.crime(v)
        for j, line in enumerate(text.wrap("for " + crime[0].lower() + crime[1:], "mono-500", 15, PW - 30)[:2]):
            text.draw(p, line, (PW // 2, 98 + j * 17), "mono-500", 15, INKC, anchor="midtop", max_w=PW - 30)
        # the mugshot: the product against a lineup height chart
        mug = pygame.Rect(24, 138, PW - 48, 126)
        pygame.draw.rect(p, (60, 56, 50), mug)
        for k in range(1, 6):
            y = mug.top + k * mug.height // 6
            pygame.draw.line(p, (110, 104, 94), (mug.left, y), (mug.right, y), 1)
        text.draw(p, v.vendor, (mug.centerx, mug.top + 28), "display-600", 36, PAPER, anchor="midtop",
                  max_w=mug.width - 20)
        text.draw(p, v.product, (mug.centerx, mug.top + 78), "sans-500", 20, (220, 210, 190), anchor="midtop",
                  max_w=mug.width - 20)
        text.draw(p, v.cve, (PW // 2, 276), "display", 40, INKC, anchor="midtop", max_w=PW - 30)
        lines = text.wrap(v.desc, "mono", 14, PW - 40)
        if len(lines) > 6:
            lines = lines[:5] + [text.fit(text.font("mono", 14), lines[5] + " " + lines[6] + "…", PW - 40)]
            if not lines[-1].endswith("…"):
                lines[-1] = lines[-1].rstrip(".,; ") + "…"
        for j, line in enumerate(lines):
            text.draw(p, line, (20, 330 + j * 18), "mono", 14, INKC, max_w=PW - 40)
        pygame.draw.line(p, PAPER_EDGE, (20, 448), (PW - 20, 448), 1)
        text.draw(p, f"Added {_date(v.added)}", (20, 458), "mono-500", 14, INKC)
        text.draw(p, f"Patch by {_date(v.due)}", (20, 478), "mono-500", 14, RED if v.due else INKC)
        text.draw(p, f"No. {n}", (PW - 20, 458), "mono", 14, FADED, anchor="topright")
        if v.ransomware:
            stamp = pygame.Surface((210, 52), pygame.SRCALPHA)
            pygame.draw.rect(stamp, (*RED, 210), stamp.get_rect(), 4, border_radius=6)
            text.draw(stamp, "Ransomware", (105, 26), "display", 34, (*RED,), anchor="center")
            p.blit(pygame.transform.rotate(stamp, 14), (PW - 230, 228))
        return p


MODULE = MostWanted
