from tvkit.module import Module


class Alpha(Module):
    name, title, blurb, aliases = "alpha", "ALPHA", "First test module", ("a",)
    order = 1


MODULE = Alpha
