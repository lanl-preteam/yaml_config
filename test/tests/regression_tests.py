import os
from io import StringIO

import yaml_config as yc
import yaml_config.scalars
import yaml_config.structures
import yc_yaml
from testlib import YCTestCase


class BasicTest(YCTestCase):
    def setUp(self):
        class TestConfig(yc.YamlConfigLoader):

            ELEMENTS = [
                yaml_config.scalars.StrElem(
                    "pet", default="squirrel", required=True,
                    choices=["squirrel", "cat", "dog"],
                    help_text="The kind of pet."),
                yaml_config.scalars.IntElem("quantity", required=True,
                                            choices=[1, 2, 3]),
                yaml_config.scalars.FloatRangeElem("quality", vmin=0, vmax=1.0),
                yaml_config.structures.ListElem(
                    "potential_names",
                    help_text="What you could name this pet.",
                    sub_elem=yaml_config.scalars.StrElem(help_text="Such as Fido.")),
                yaml_config.structures.KeyedElem(
                    "properties", help_text="Pet properties", elements=[
                    yaml_config.scalars.StrElem(
                        "description", help_text="General pet description."),
                    yaml_config.scalars.RegexElem(
                        "greeting", regex=r'hello \w+$',
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

    def test_duplicates(self):
        """Duplicates are not allowed in mappings."""

        with self.assertRaises(yc_yaml.YAMLError):
            with open(self._data_path('duplicates.yaml')) as f:
                self.Config().load(f)

    def test_string_conv_limits(self):
        """We should only auto-convert scalars into strings."""

        with self.assertRaises(ValueError):
            with open(self._data_path('string_conv_limits.yaml')) as f:
                print(self.Config().load(f))

    def test_regex_val_type(self):
        """Make sure parsed values end up being the correct type by the
        time we check them. Regex elements will assume this."""

        with self.assertRaises(ValueError):
            with open(self._data_path('regex_val_type.yaml')) as f:
                self.Config().load(f)

    def test_bad_default(self):
        """Defaults should normalize to the appropriate type as well."""

        yaml_config.scalars.RegexElem(
            'num', default=5, regex=r'\d+')

    def test_extra_keyedelem_key(self):
        """KeyedElements should not allow for keys that aren't defined in
        their element list."""

        with self.assertRaises(KeyError):
            self.Config().validate(
                {
                    'not_defined': 'nope',
                }
            )
