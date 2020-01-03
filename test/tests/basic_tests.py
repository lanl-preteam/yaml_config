import os
from io import StringIO

import yaml_config as yc
import yaml_config.scalars
import yaml_config.structures
from testlib import YCTestCase


class BasicTest(YCTestCase):
    def setUp(self):
        class TestConfig(yc.YamlConfigLoader):

            ELEMENTS = [
                yaml_config.scalars.StrElem("pet", default="squirrel", required=True, choices=["squirrel",
                                                                              "cat", "dog"],
                                            help_text="The kind of pet."),
                yaml_config.scalars.IntElem("quantity", required=True, choices=[1, 2, 3]),
                yaml_config.scalars.FloatRangeElem("quality", vmin=0, vmax=1.0),
                yaml_config.structures.ListElem("potential_names", help_text="What you could name this pet.",
                                                sub_elem=yaml_config.scalars.StrElem(help_text="Such as Fido.")),
                yaml_config.structures.KeyedElem("properties", help_text="Pet properties", elements=[
                    yaml_config.scalars.StrElem("description", help_text="General pet description."),
                    yaml_config.scalars.RegexElem("greeting", regex=r'hello \w+$',
                                                  help_text="A regex of some sort."),
                    yaml_config.scalars.IntRangeElem("legs", vmin=0)
                ]),
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
