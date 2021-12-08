from os.path import dirname

from bot.exts.filtering._filters.filter import Filter
from bot.exts.filtering._utils import subclasses_in_package

filters = subclasses_in_package(dirname(__file__), f"{__name__}.", Filter)
filters = {filter_.name: filter_ for filter_ in filters}

del dirname
del Filter
del subclasses_in_package
