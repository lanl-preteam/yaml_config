"""Provides a customized test case for unittests and colorized results."""

from pathlib import Path
import inspect
import types
import unittest
import fnmatch


class YCTestCase(unittest.TestCase):
    """A test case class that allows for dynamically skippable tests."""

    # Skip any tests that match these globs.
    SKIP = []
    # Only run tests that match these globs.
    ONLY = []

    DATA_DIR = Path(__file__).parent/'tests'/'data'
    ROOT_DIR = Path(__file__).parents[1]

    def __getattribute__(self, item):
        """When the unittest framework wants a test, check if the test
    is in the SKIP or ONLY lists, and skip it as appropriate. Only
    test methods are effected by this.
    A test is in the SKIP or ONLY list if the filename (minus extension),
    class name, or test name (minus the test_ prefix) match one of the
    SKIP or ONLY globs (provided via ``./runtests`` ``-s`` or ``-o``
    options.
    """

        attr = super().__getattribute__(item)

        cls = super().__getattribute__('__class__')
        cname = cls.__name__.lower()
        fname = Path(inspect.getfile(cls)).with_suffix('').name.lower()

        # Wrap our test functions in a function that dynamically wraps
        # them so they only execute under certain conditions.
        if (isinstance(attr, types.MethodType) and
                attr.__name__.startswith('test_')):

            name = attr.__name__[len('test_'):].lower()

            if self.SKIP:
                for skip_glob in self.SKIP:
                    skip_glob = skip_glob.lower()
                    if (fnmatch.fnmatch(name, skip_glob) or
                            fnmatch.fnmatch(cname, skip_glob) or
                            fnmatch.fnmatch(fname, skip_glob)):
                        return unittest.skip("via cmdline")(attr)
                return attr

            if self.ONLY:
                for only_glob in self.ONLY:
                    only_glob = only_glob.lower()
                    if (fnmatch.fnmatch(name, only_glob) or
                            fnmatch.fnmatch(cname, only_glob) or
                            fnmatch.fnmatch(fname, only_glob)):
                        return attr
                return unittest.skip("via cmdline")(attr)

        # If it isn't altered or explicitly returned above, just return the
        # attribute.
        return attr

    @classmethod
    def set_skip(cls, globs):
        """Skip tests whose names match the given globs."""

        cls.SKIP = globs

    @classmethod
    def set_only(cls, globs):
        """Only run tests whos names match the given globs."""
        cls.ONLY = globs

class ColorResult(unittest.TextTestResult):
    """Provides colorized results for the python unittest library."""

    COLOR_BASE = '\x1b[{}m'
    COLOR_RESET = '\x1b[0m'
    BLACK = COLOR_BASE.format(30)
    RED = COLOR_BASE.format(31)
    GREEN = COLOR_BASE.format(32)
    YELLOW = COLOR_BASE.format(33)
    BLUE = COLOR_BASE.format(34)
    MAGENTA = COLOR_BASE.format(35)
    CYAN = COLOR_BASE.format(36)
    GREY = COLOR_BASE.format(2)
    BOLD = COLOR_BASE.format(1)

    def __init__(self, *args, **kwargs):
        self.stream = None
        super().__init__(*args, **kwargs)

    def startTest(self, test):
        super().startTest(test)
        if self.showAll:
            self.stream.write(self.GREY)
            self.stream.write(self.getDescription(test))
            self.stream.write(self.COLOR_RESET)
            self.stream.write(" ... ")
            self.stream.flush()

    def addSuccess(self, test):
        self.stream.write(self.GREEN)
        super().addSuccess(test)
        self.stream.write(self.COLOR_RESET)

    def addFailure(self, test, err):
        self.stream.write(self.MAGENTA)
        super().addFailure(test, err)
        self.stream.write(self.COLOR_RESET)

    def addError(self, test, err):
        self.stream.write(self.RED)
        super().addError(test, err)
        self.stream.write(self.COLOR_RESET)

    def addSkip(self, test, reason):
        self.stream.write(self.CYAN)
        super().addSkip(test, reason)
        self.stream.write(self.COLOR_RESET)

class ColorResult(unittest.TextTestResult):
    """Provides colorized results for the python unittest library."""

    COLOR_BASE = '\x1b[{}m'
    COLOR_RESET = '\x1b[0m'
    BLACK = COLOR_BASE.format(30)
    RED = COLOR_BASE.format(31)
    GREEN = COLOR_BASE.format(32)
    YELLOW = COLOR_BASE.format(33)
    BLUE = COLOR_BASE.format(34)
    MAGENTA = COLOR_BASE.format(35)
    CYAN = COLOR_BASE.format(36)
    GREY = COLOR_BASE.format(2)
    BOLD = COLOR_BASE.format(1)

    def __init__(self, *args, **kwargs):
        self.stream = None
        super().__init__(*args, **kwargs)

    def startTest(self, test):
        super().startTest(test)
        if self.showAll:
            self.stream.write(self.GREY)
            self.stream.write(self.getDescription(test))
            self.stream.write(self.COLOR_RESET)
            self.stream.write(" ... ")
            self.stream.flush()

    def addSuccess(self, test):
        self.stream.write(self.GREEN)
        super().addSuccess(test)
        self.stream.write(self.COLOR_RESET)

    def addFailure(self, test, err):
        self.stream.write(self.MAGENTA)
        super().addFailure(test, err)
        self.stream.write(self.COLOR_RESET)

    def addError(self, test, err):
        self.stream.write(self.RED)
        super().addError(test, err)
        self.stream.write(self.COLOR_RESET)

    def addSkip(self, test, reason):
        self.stream.write(self.CYAN)
        super().addSkip(test, reason)
        self.stream.write(self.COLOR_RESET)
