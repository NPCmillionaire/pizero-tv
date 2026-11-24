"""Find modules: every package under modules/ exporting MODULE."""
import importlib, os, sys, traceback


class Registry:
    def __init__(self):
        self._by_name, self._classes, self.errors = {}, [], {}

    def add(self, cls):
        self._classes.append(cls)
        self._classes.sort(key=lambda c: (c.order, c.name))
        for n in (cls.name, *cls.aliases):
            self._by_name[n] = cls

    def get(self, name):
        return self._by_name.get(name)

    def names(self):
        return [c.name for c in self._classes]

    def classes(self):
        return list(self._classes)

    def channels(self):
        """Modules in channel order: channel N is channels()[N]."""
        return list(self._classes)

    def number(self, name):
        cls = self.get(name)
        return self._classes.index(cls) if cls in self._classes else None


def discover(root=None, package="modules"):
    root = root or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "modules")
    reg = Registry()
    for d in sorted(os.listdir(root)):
        if not os.path.isfile(os.path.join(root, d, "__init__.py")):
            continue
        try:
            m = importlib.import_module(f"{package}.{d}")
            for cls in getattr(m, "MODULES", None) or [m.MODULE]:
                reg.add(cls)
        except Exception:
            reg.errors[d] = traceback.format_exc()
            print(f"registry: skipping {d}:\n{reg.errors[d]}", file=sys.stderr)
    return reg
