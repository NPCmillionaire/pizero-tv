from tvkit.module import Module


def make(n, o):
    return type(n.title(), (Module,), dict(name=n, title=n.upper(), blurb=n, order=o))


MODULES = [make("gamma", 3), make("delta", 4)]
