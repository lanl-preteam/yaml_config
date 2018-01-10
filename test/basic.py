from __future__ import division, unicode_literals, print_function

import os
import sys
sys.path.append(os.path.join(os.path.dirname(os.getcwd()), 'lib'))

import yaml_config as yc
from io import StringIO


class TestConfig(yc.YamlConfig):

    ELEMENTS = [
        yc.StrElem("pet", default="squirrel", required=True, choices=["squirrel", "cat", "dog"],
                   help_text="The kind of pet."),
        yc.IntElem("quantity", required=True, choices=[1, 2, 3]),
        yc.FloatRangeElem("quality", min=0, max=1.0),
        yc.ListElem("potential_names", help_text="What you could name this pet.",
                    subtype=yc.StrElem(help_text="Such as Fido.")),
        yc.KeyedElem("properties", help_text="Pet properties", elements=[
            yc.StrElem("description", help_text="General pet description."),
            yc.RegexElem("greeting", regex=r'hello \w+$',
                         help_text="A regex of some sort."),
            yc.IntRangeElem("legs", min=0)
        ]),
        yc.CodeElem("behavior_code", help_text="Program for pet behavior.")
    ]


test = TestConfig()

f = open('data/test1.yaml', 'r')
data = test.load(f)
print(data)
test.dump(sys.stdout, values=data)
