import os
import sys

sys.path.append(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'lib'))

import yaml_config as yc

import unittest


class SetDefaultTest(unittest.TestCase):
    def test_set_default1(self):
        class DessertConfig(yc.YamlConfigLoader):
            ELEMENTS = [
                yc.KeyedElem('pie', elements=[
                    yc.StrElem('fruit')
                ])
            ]

        config = DessertConfig()

        # Set the 'fruit' element of the 'pie' element to have a default of 'apple'.
        config.set_default('pie.fruit', 'apple')

    def test_set_default2(self):
        class Config2(yc.YamlConfigLoader):
            ELEMENTS = [
                yc.ListElem('cars', sub_elem=yc.KeyedElem(elements=[
                    yc.StrElem('color'),
                    yc.StrElem('make'),
                    yc.ListElem('extras', sub_elem=yc.StrElem())
                ]))
            ]

            def __init__(self, default_color):
                super(Config2, self).__init__()

                # The Config init is a good place to do this.
                # Set all the default color for all cars in the 'cars' list to red.
                self.set_default('cars.*.color', default_color)
                self.set_default('cars.*.extras', ['rhoomba', 'heated sunshades'])

        raw = {
            'cars': [
                {'color': 'green',
                 'make': 'Dodge'
                 },
                {'make': 'Honda',
                 'extras': ['flaming wheels']}
            ]
        }

        config = Config2('red')

        data = config.validate(raw)

        expected_result = {'cars': [{'make': 'Dodge', 'color': 'green',
                                     'extras': ['rhoomba', 'heated sunshades', 'flaming wheels']},
                                    {'make': 'Honda', 'color': 'red',
                                     'extras': ['rhoomba', 'heated sunshades', 'flaming wheels']}]}

        self.assertEqual(data, expected_result)


if __name__ == '__main__':
    unittest.main()
