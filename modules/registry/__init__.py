"""REGISTRY — who owns the aircraft overhead: AIRSPACE's planes looked up in the FAA registry, as case files."""
import os

import pygame
import requests

from tvkit import text, theme
from tvkit.module import Module
from modules.flights import data as flights

from . import data

CASE_S = 12
RANGE_NM = 60
# a detective's desk: dark wood, a manila folder, a typed sheet, a polaroid, a rubber stamp
DESK, FOLDER, FOLDER_DARK, SHEET = (38, 30, 26), (214, 184, 124), (178, 150, 96), (246, 242, 230)
TYPE, FADED, RED, CARD = (30, 30, 34), (120, 112, 100), (178, 34, 34), (236, 230, 210)


def _download(to):
    with requests.get(data.RELEASE, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(to, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)


class Registry(Module):
    name, title, key = "registry", "REGISTRY", theme.SODIUM
    blurb = "Who owns the aircraft overhead, from the FAA registry"
    aliases = ("faa", "owners", "casefile")
    order = 52
    fps = 2
    footer_color = (170, 150, 120)

    def start(self, ctx):
        super().start(ctx)
        self.place = ctx.config.place
        self.case_i, self._case_t, self._found = 0, None, {}
        dest = os.path.join(ctx.cache_dir or os.path.expanduser("~/.cache/pizero-tv/registry"), "registry.sqlite")
        self.reg = self.source("registry", lambda: data.ensure(dest, _download), 6 * 3600, cache=False)
        if self.place:
            lat, lon = self.place.lat, self.place.lon
            url = f"https://api.adsb.lol/v2/point/{lat}/{lon}/{RANGE_NM}"
            self.air = self.source("aircraft", lambda: requests.get(url, timeout=15).json(), 60,
                                   parse=lambda p: flights.parse(p, lat, lon), cache=False)

    def _records(self, planes):
        meta = self.reg.value
        if not meta or not planes:
            return {}
        if "records" in meta:                                   # test fixtures carry the rows themselves
            return {r["hex"]: data.Record(**r) for r in meta["records"]}
        return data.lookup(meta["path"], [p.hex for p in planes])

    def update(self, now):
        changed = super().update(now)
        if changed:
            planes = self.air.value if self.place else None
            try:
                self._found = self._records([p for p in (planes or []) if not p.on_ground] or planes or [])
            except Exception as ex:                             # a half-written file never takes the channel down
                print(f"[registry] lookup failed: {ex}")
                self._found = {}
        if self._case_t is None:
            self._case_t = now
        elif now - self._case_t >= CASE_S:
            self.case_i, self._case_t, changed = self.case_i + 1, now, True
        return changed

    def on_key(self, event):
        if event.key in (pygame.K_SPACE, pygame.K_RIGHT):
            self.case_i += 1
            self.dirty = True

    # -- the desk -------------------------------------------------------------------------
    def draw_frame(self, surf):
        surf.fill(DESK)
        for y in range(0, 720, 9):                               # wood grain
            pygame.draw.line(surf, theme.mix(DESK, (60, 46, 38), (y * 37 % 11) / 11), (0, y), (1280, y + 3), 1)
        folder = pygame.Rect(30, 70, 860, 620)
        pygame.draw.rect(surf, FOLDER_DARK, folder.move(0, -8), border_radius=6)
        pygame.draw.rect(surf, FOLDER_DARK, (folder.left + 30, folder.top - 40, 270, 46), border_top_left_radius=10,
                         border_top_right_radius=10)
        pygame.draw.rect(surf, FOLDER, folder, border_radius=6)
        text.draw(surf, "Case file", (76, 52), "display-600", 26, (90, 70, 40), anchor="midleft")

    def draw_static(self, surf):
        planes = [p for p in (self.air.value or []) if not p.on_ground] if self.place else []
        found = [(p, self._found[p.hex.upper()]) for p in planes if p.hex.upper() in self._found]
        sheet = pygame.Rect(56, 92, 700, 576)
        pygame.draw.rect(surf, (0, 0, 0), sheet.move(5, 6))
        pygame.draw.rect(surf, SHEET, sheet)
        x, y = sheet.left + 30, sheet.top + 26
        meta = self.reg.value
        if not self.place:
            self._typed(surf, ["No place set.", "", "Add a [place] to config.toml so the", "registry knows which sky to watch."], x, y)
            return
        if meta is None:
            msg = {"offline": "Couldn't fetch the FAA registry from the govint-data release.",
                   "waiting": "Fetching the FAA registry (about 34 MB, once a week)."}.get(self.reg.status, "")
            self._typed(surf, text.wrap(msg, "mono", 20, sheet.width - 60), x, y)
            return
        if not found:
            lines = ["No registered aircraft overhead right now." if planes is not None else "Listening for aircraft."]
            if planes:
                lines += ["", f"{len(planes)} aircraft in the air, none in the", "US registry (foreign or military)."]
            self._typed(surf, lines, x, y)
            self._cards(surf, planes, {})
            return
        p, r = found[self.case_i % len(found)]
        text.draw(surf, r.n, (176, 52), "mono-500", 22, TYPE, anchor="midleft")
        text.draw(surf, f"Case {self.case_i % len(found) + 1} of {len(found)}", (sheet.right - 30, y), "mono", 16,
                  FADED, anchor="topright")
        text.draw(surf, "Federal Aviation Administration aircraft registry", (x, y), "mono", 16, FADED)
        text.draw(surf, r.n, (x, y + 30), "display", 74, TYPE)
        text.draw(surf, f"{r.make} {r.model}".strip(), (x, y + 112), "mono-500", 22, TYPE, max_w=sheet.width - 60)
        rows = [("Registered to", r.owner or "name not on file"), ("Owner type", r.owner_kind),
                ("Based in", ", ".join(v for v in (r.city, r.state) if v) or "not on file"),
                ("Aircraft", r.kind + (f", {r.seats} seats" if r.seats else "")),
                ("Built", r.year or "unknown"), ("Certificate", r.since or "unknown")]
        yy = y + 160
        for k, v in rows:
            text.draw(surf, k, (x, yy), "mono", 18, FADED)
            for j, line in enumerate(text.wrap(v, "mono-500", 20, sheet.width - 250)[:2]):
                text.draw(surf, line, (x + 190, yy + j * 24), "mono-500", 20, TYPE)
            yy += 30 + 24 * (len(text.wrap(v, "mono-500", 20, sheet.width - 250)[:2]) - 1)
        pygame.draw.line(surf, FADED, (x, yy + 6), (sheet.right - 30, yy + 6), 1)
        now = [f"Last seen {p.dist_nm:.0f} nm {['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'][round(p.bearing / 45) % 8]}"
               f" of {self.place.name}",
               f"at {p.alt:,} ft" + (f", {p.speed:.0f} knots" if p.speed else "") + (f", flying as {p.callsign}"
                                                                                     if p.callsign != r.n else "")]
        for j, line in enumerate(now):
            text.draw(surf, line, (x, yy + 18 + j * 24), "mono", 18, TYPE, max_w=sheet.width - 60)
        stamp = pygame.Surface((250, 56), pygame.SRCALPHA)
        pygame.draw.rect(stamp, (*RED, 200), stamp.get_rect(), 4, border_radius=6)
        text.draw(stamp, "Public record", (125, 28), "display", 34, RED, anchor="center")
        surf.blit(pygame.transform.rotate(stamp, 10), (sheet.right - 290, sheet.bottom - 110))
        text.draw(surf, f"FAA data as of {meta.get('date', '?')}", (x, sheet.bottom - 30), "mono", 14, FADED)
        self._cards(surf, planes, self._found, current=p)

    def _typed(self, surf, lines, x, y):
        for j, line in enumerate(lines):
            text.draw(surf, line, (x, y + j * 28), "mono-500", 20, TYPE, max_w=640)

    def _cards(self, surf, planes, found, current=None):
        """Index cards for the other aircraft in view."""
        x, y = 920, 70
        text.draw(surf, "Also overhead", (x, y - 46), "display-600", 30, (230, 214, 180))
        for p in planes[:7]:
            if p is current:
                continue
            r = found.get(p.hex.upper())
            card = pygame.Rect(x, y, 330, 78)
            if card.bottom > 690:
                break
            pygame.draw.rect(surf, CARD, card)
            pygame.draw.line(surf, (200, 120, 120), (card.left, card.top + 24), (card.right, card.top + 24), 1)
            text.draw(surf, r.n if r else p.callsign, (card.left + 10, card.top + 3), "mono-500", 17, TYPE)
            text.draw(surf, f"{p.dist_nm:.0f} nm", (card.right - 10, card.top + 3), "mono", 15, FADED,
                      anchor="topright")
            owner = (r.owner or r.owner_kind) if r else "not in the US registry"
            text.draw(surf, owner, (card.left + 10, card.top + 30), "mono", 15, TYPE if r else FADED,
                      max_w=card.width - 20)
            what = f"{r.make} {r.model}".strip() if r else (p.type or "")
            text.draw(surf, what, (card.left + 10, card.top + 52), "mono", 14, FADED, max_w=card.width - 20)
            y += 88


MODULE = Registry
