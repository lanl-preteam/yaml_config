from __future__ import division, unicode_literals, print_function

import os
import sys
sys.path.append(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'lib'))

import yaml_config as yc


if sys.version_info[0] == 3:
    from io import StringIO
else:
    from StringIO import StringIO


import unittest


class BasicTest(unittest.TestCase):
    def setUp(self):
        class TestConfig(yc.YamlConfig):

            ELEMENTS = [
                yc.StrElem("pet", default="squirrel", required=True, choices=["squirrel",
                                                                              "cat", "dog"],
                           help_text="The kind of pet."),
                yc.IntElem("quantity", required=True, choices=[1, 2, 3]),
                yc.FloatRangeElem("quality", vmin=0, vmax=1.0),
                yc.ListElem("potential_names", help_text="What you could name this pet.",
                            sub_elem=yc.StrElem(help_text="Such as Fido.")),
                yc.KeyedElem("properties", help_text="Pet properties", elements=[
                    yc.StrElem("description", help_text="General pet description."),
                    yc.RegexElem("greeting", regex=r'hello \w+$',
                                 help_text="A regex of some sort."),
                    yc.IntRangeElem("legs", vmin=0)
                ]),
                yc.CodeElem("behavior_code", help_text="Program for pet behavior.")
            ]

        self.Config = TestConfig

    def _data_path(self, filename):
        """Return an absolute path to the given test data file."""
        path = os.path.abspath(__file__)
        path = os.path.dirname(path)
        return os.path.join(path, 'data', filename)

    def test_instantiate(self):
        """Verify that we can instantiate the a test config class without errors."""
        self.Config()

    def test_load(self):
        """Verify that we can load data without errors."""
        test = self.Config()
        with open(self._data_path('test1.yaml'), 'r') as f:
            test.load(f)

    def test_dump(self):
        """Verify that the data loaded is equal to the data if dumped and loaded again."""
        test = self.Config()
        with open(self._data_path('test1.yaml'), 'r') as f:
            data = test.load(f)

        dest_stream = StringIO()
        test.dump(dest_stream, values=data)
        dest_stream.seek(0)

        data2 = test.load(dest_stream)

        self.assertEqual(data, data2)

        dest_stream.close()


if __name__ == '__main__':
    unittest.main()
