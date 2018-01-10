from __future__ import print_function, division, unicode_literals

import re

# This module defines a set of constructs for strictly defining configuration objects that get
# their data from Yaml files. It allows for the general (though not complete) flexibility of
# Yaml/Json, while giving the program using it assurance that the types and structure of the
# configuration parameters brought in are what is to be expected. Configuration objects generated
# by this library can be merged in a predictable way. Example configurations can automatically
# be generated, as can configurations already filled out with the given values.


# A modified pyyaml library
import myyaml as yaml
from myyaml import representer

from collections import OrderedDict


class RequiredError(ValueError):
    pass


class ConfigDict(dict):
    """Since we enforce field names that are also valid python names, we can build this
    dict that allows for getting and setting keys like attributes."""
    def __getattr__(self, key):
        if key in self:
            return super(ConfigDict, self).__getitem__(key)
        else:
            return super(ConfigDict, self).__getattribute__(key)

    def __setattr__(self, key, value):
        if key in self:
            super(ConfigDict, self).__setitem__(key, value)
        else:
            super(ConfigDict, self).__setattr__(key, value)


# Tell yaml how to represent a ConfigDict (as a dictionary).
representer.SafeRepresenter.add_representer(ConfigDict,
                                            representer.SafeRepresenter.represent_dict)


class ConfigElem:
    """Describes the type of yaml config value. Type must be overridden with a standard python
    type object valid for YAML, such as str, int, float, list or dict."""
    # The type object for this type. Assumes YAML loading does the conversion, this just
    # validates that we got what we expected.
    type = None
    # The type name is usually pulled straight from the type's __name__ attribute
    # This overrides that, when not None
    _type_name = None

    # The regular expression that all element names are matched against.
    _NAME_RE = re.compile(r'^[a-z][a-z0-9_]+$')

    # We use the representer functions in this to consistently represent certain types.
    _representer = yaml.representer.SafeRepresenter()

    def __init__(self, name=None, default=None, required=False, choices=None, help_text=""):
        """
        :param default: The default value if the given value is None.
        :param choices: A sequence of values that this type will accept.
        """

        if name is not None:
            self._validate_name(name)

        self.name = name
        # Default value, if one wasn't provided
        self.default = default
        # A value for this item is required
        self.required = required
        # What values this configuration item may take. None means unlimited.
        self.choices = choices
        # Help text for internal and example configuration files.
        self.help_text = help_text

        # The type name is usually pulled straight from the type's __name__ attribute
        # This overrides that, when not None
        if self._type_name is None:
            self._type_name = self.type.__name__

    def _check_range(self, value):
        """Make sure the value is in the given list of choices. If you need another type
        of range check, such any positive integer, override this method.
        :returns None
        :raises ValueError: When out of range."""

        if value not in self.choices:
            raise ValueError("Value '{}' not in the given choices {} for {} called '{}'.".format(
                value, self.choices, self.__class__.__name__, self.name
            ))

        if self.choices:
            return value in self.choices
        else:
            return True

    def validate(self, value):
        """Validate the given value.
        :returns The value, converted to this type if needed.
        :raises TypeError if type conversion can't occur.
        :raises ValueError if the value is out of range.
        """

        if type(value) is not self.type:
            if value is None:
                if self.default is not None:
                    value = self.default
                elif self.required:
                    raise RequiredError("Config missing required value for {} named {}."
                                        .format(self.__class__.__name__, self.name))

            try:
                value = type(value)
            except TypeError:
                raise TypeError("Incorrect type for {} field {}: {}"
                                .format(self.__class__.__name__, self.name, value))
        if self.choices:
            self._check_range(value)

        return value

    def make_comment(self, show_choices=True, show_name=True):
        """Create a comment for this configuration element.
        :param show_choices: Whether to include the valid choices for this item in the help
                             comments."""

        if self.name is None:
            name = ''
        else:
            name = self.name.upper()
        comment = ['{name}({required}{type}){colon} {help}'.format(
            name=name if show_name else '',
            required='required ' if self.required else '',
            type=self._type_name,
            colon=':' if self.help_text else '',
            help=self.help_text,
        )]
        if show_choices and self.choices:
            choices_doc = self._choices_doc()
            if choices_doc is not None:
                comment.append(choices_doc)
        return yaml.CommentEvent(value='\n'.join(comment))

    def yaml_events(self, value, show_choices):
        """Returns the yaml events to represent this config item.
            :param value: The value of this config element. May be None.
            :param show_choices: Whether or not to show the choices string in the comments.
        """

        raise NotImplementedError("When defining a new element type, you must define "
                                  "how to turn it (and any sub elements) into a list of "
                                  "yaml events.")

    def _choices_doc(self):
        """Returns a list of strings documenting the available choices and type for this item.
        This may also return None, in which cases choices will never be given."""

        return 'Choices: ' + ', '.join(map(str, self.choices))

    def _validate_name(self, name):
        if name != name.lower():
            raise ValueError("Invalid name for config field {} called {}. Names must "
                             "be lowercase".format(self.__class__.__name__, name))

        if self._NAME_RE.match(name) is None:
            raise ValueError("Invalid name for config field {} called {}. Names must "
                             "start with a letter, and be composed of only letters, "
                             "numbers, and underscores."
                             .format(self.__class__.__name__, name))

    def _represent(self, value):
        """Give the yaml representation for this type. Since we're not representing generic
        python objects, we only need to do this for scalars."""
        return value

    def merge(self, old, new):
        """Merge the new values of this entry into the existing one. For most types,
        the old values are simply replaced. For complex types (lists, dicts), the
        behaviour varies."""

        return new


class ScalarElem(ConfigElem):
    def _represent(self, value):
        """ We use the built in yaml representation system to 'serialize' scalars.
        :returns (value, tag)"""
        # Use the representer from yaml to handle this properly.
        node = self._representer.represent_data(value)
        return node.value, node.tag

    def yaml_events(self, value, show_choices):
        # Get our serialized representation of value, and return it as a ScalarEvent.
        tag = None
        if value is not None:
            value, tag = self._represent(value)
        return [yaml.ScalarEvent(value=value, anchor=None, tag=tag, implicit=(True, True))]


class IntElem(ScalarElem):
    type = int


class FloatElem(ScalarElem):
    type = float


class RangeElem(ScalarElem):

    def __init__(self, name=None, default=None, required=True, min=None, max=None, help_text=""):
        super(RangeElem, self).__init__(name=name,
                                        default=default,
                                        required=required,
                                        choices=[min, max],
                                        help_text=help_text)

    def _choices_doc(self):
        if self.choices == (None, None):
            return None
        elif self.choices[0] is None:
            return 'Valid Range: < {}'.format(self.choices[1])
        elif self.choices[1] is None:
            return 'Valid Range: > {}'.format(self.choices[0])
        else:
            return 'Valid Range: {} - {}'.format(*self.choices)

    def _check_range(self, value):
        if self.choices[0] is not None and value < self.choices[0]:
            raise ValueError("Value {} in {} below minimum ({}).".format(
                value,
                self.name,
                self.choices[0]
            ))
        if self.choices[1] is not None and value > self.choices[1]:
            raise ValueError("Value {} in {} above maximum ({}).".format(
                value,
                self.name,
                self.choices[1]
            ))


class IntRangeElem(IntElem, RangeElem):
    pass


class FloatRangeElem(FloatElem, RangeElem):
    pass


class StrElem(ScalarElem):
    type = str


class RegexElem(StrElem):
    """Just like a string item, but validates against a regex."""

    def __init__(self, name=None, default=None, regex='', help_text=""):
        """
        :param name: The name and key value of config item.
        :param default: The default value if the given value is None.
        :param regex: A regular expression to match against.
        """

        super(RegexElem, self).__init__(name, default=default,
                                        help_text=help_text)
        self.regex = re.compile(regex)
        self.choices = [regex]

    def _check_range(self, value):
        if self.regex.match(value) is None:
            raise ValueError("Value {} does not match regex '{}' for {} called '{}'".format(
                value, self.choices[0], self.__class__.__name__, self.name
            ))

    def _choices_doc(self):
        return "Values must match: r'{regex}'".format(regex=self.choices[0])


class ListElem(ConfigElem):
    """A list of configuration items. All items in the list must be the same configitem type.
    Configuration inheritance appends new, unique items to these lists."""

    type = list
    type_name = 'list of items'

    def __init__(self, name=None, subtype=None,
                 min_length=0, max_length=None, help_text=""):
        """
        :param name: The name and key value of config item.
        :param subtype: A ConfigItem that each item in the list must conform to.
        :param min_length: The minimum number of items allowed, inclusive. Default: 0
        :param max_length: The maximum number of items allowed, inclusive. None denotes unlimited.
        """

        super(ListElem, self).__init__(name, help_text=help_text)

        if not isinstance(subtype, ConfigElem):
            raise ValueError("Subtype must be a config element of some kind. Got: {}"
                             .format(subtype))
        self.subtype = subtype

        # Set the name of the subtype if we know the name of this element.
        if self.name is not None:
            self._set_names()

        if min_length < 0:
            raise ValueError("min_length must be a positive integer.")
        self.min_length = min_length
        self.max_length = max_length

    def _set_names(self):
        """List elements generally don't have names, but we force them for easier debugging.
        Unfortunately, the name of a list won't be known until we get to a containing
        mapping/dict, so we use this function to walk back up."""

        if self.subtype.name is None:
            self.subtype.name = '{}.list_item'.format(self.name)

        # Make sure names get set on the sublist, if the subtype is a ListElem
        if isinstance(self.subtype, ListElem):
            self.subtype._set_names()

    def _check_range(self, value: list):
        """Make sure our list is within the appropriate length range."""
        vlen = len(value)
        if vlen < self.min_length:
            return False

        if self.max_length is None or vlen <= self.max_length:
            return True
        else:
            return False

    def validate(self, values):
        """Just like the parent function, except converts None to an empty list,
        and single values of other types into the subtype for this list.  Subvalues are
        recursively validated against the subitem type (whose name is ignored)."""

        if type(values) is not self.type:
            if values is None:
                values = []
            else:
                values = [self.subtype.validate(values)]
        else:
            values = [self.subtype.validate(v) for v in values]

        if not self._check_range(values):
            raise ValueError("Expected [{}-{}] list items for {} field {}, got {}.".format(
                self.min_length,
                self.max_length if self.max_length is not None else 'inf',
                self.__class__.__name__,
                self.name,
                len(values)
            ))

        return values

    def _choices_doc(self):
        return "May contain {min} - {max} items.".format(
            min=self.min_length,
            max=self.max_length if self.max_length is not None else 'inf'
        )

    def yaml_events(self, value, show_choices):
        events = list()
        events.append(yaml.SequenceStartEvent(
            anchor=None,
            tag=None,
            implicit=True,
            flow_style=False,
        ))

        events.append(self.subtype.make_comment(show_choices, show_name=False))

        if value is not None:
            # Value is expected to be a list of items at this point.
            for v in value:
                events.extend(self.subtype.yaml_events(v, show_choices=show_choices))
        else:
            events.extend(self.subtype.yaml_events(None, show_choices))

        events.append(yaml.SequenceEndEvent())
        return events

    def merge(self, old: list, new: list):
        """Add any unique, new items to the list."""
        merged = old.copy()

        for item in new:
            if item not in merged:
                merged.append(item)


class CodeElem(ListElem):
    """Like a list config item, except the subtype is always string, and the
    subitems are considered to be a single group. Useful for config sections that are
    really lines of code or documentation."""
    type = list
    type_name = 'code block'

    def __init__(self, name=None, help_text=""):
        subtype = StrElem('code_line')
        super(CodeElem, self).__init__(name, subtype=subtype, help_text=help_text)

    def validate(self, lines: list):
        lines = [self.subtype.validate(line) for line in lines]

        code_block = '\n'.join(lines)
        self._analyze(code_block)

        return code_block

    def _analyze(self, code):
        """This to be overridden to run a syntax validator for the given code.
        By default, it does nothing.
        :raises ValueError: Any errors raised in validation should be converted to ValueErrors.
        """
        pass
        # try:
        #   analyzer.analyze(code_block)
        # except Exception as err:
        #   raise ValueError(err)

    def yaml_events(self, value, show_choices):
        """Treat each line a separate list element."""

        if value is not None:
            lines = value.split('\n')
        else:
            lines = None
        return super(CodeElem, self).yaml_events(lines, show_choices)


class KeyedElem(ConfigElem):
    """A dictionary configuration item with predefined keys that may have non-uniform types. The
    valid keys are are given as ConfigItem objects, with their names being used as the key name."""

    type = dict

    def __init__(self, name=None, elements=list(), help_text=""):
        """
        :param name: The name of this Config Item
        :param elements: The valid keys for this config item.
        """

        super(KeyedElem, self).__init__(name, help_text=help_text)

        self.config_elems = OrderedDict()

        for i in range(len(elements)):
            elem = elements[i]
            if elem.name is None:
                raise ValueError("In KeyedConfig item ({}), subitem {} has name of None."
                                 .format(self.name if self.name is not None else '<unnamed>', i))
            self.config_elems[elem.name] = elem

    def validate(self, value_dict: dict):
        """Value in this case should be a dictionary."""
        out_dict = ConfigDict()

        for key, value in value_dict.items():
            key = key.lower()
            if key not in self.config_elems:
                raise ValueError("Invalid config key '{}' given under {} called '{}'."
                                 .format(key, self.__class__.__name__, self.name))
            # Validate each of the subkeys in this dict.
            out_dict[key] = self.config_elems[key].validate(value)

        return out_dict

    def merge(self, old, new):
        for key, value in new.items():
            elem = self.config_elems[key]
            old[key] = elem.merge(old[key], new[key])
        return old

    def yaml_events(self, values: {}, show_choices: bool):
        if values is None:
            values = dict()

        events = list()
        events.append(yaml.MappingStartEvent(anchor=None, tag=None, implicit=True))
        for key, elem in self.config_elems.items():
            value = values.get(key, None)
            events.append(elem.make_comment(show_choices))
            # Add the mapping key
            events.append(yaml.ScalarEvent(value=key, anchor=None,
                                           tag=None, implicit=(True, True)))
            # Add the mapping value
            events.extend(elem.yaml_events(value, show_choices))
        events.append(yaml.MappingEndEvent())
        return events


class CategoryElem(ConfigElem):
    """A dictionary config item where all the keys must be of the same type, but the key values
    themselves do not have to be predefined. The possible keys may still be restricted with
    the choices argument to init."""

    type = dict

    def __init__(self, name=None, subtype=None, choices=None, help_text=""):
        super(CategoryElem, self).__init__(name, choices=choices, help_text=help_text)
        if not isinstance(subtype, ConfigElem):
            raise ValueError("Subtype must be a config element of some kind. Got: {}"
                             .format(subtype))
        self.subtype = subtype

    def validate(self, value_dict: dict):
        out_dict = ConfigDict()

        for key, value in value_dict.items():
            key = key.lower()
            if self.choices is not None and key not in self.choices:
                raise ValueError("Invalid key for {} called {}. '{}' not in given choices.")
            out_dict[key] = self.subtype.validate(value)

        return out_dict

    def yaml_events(self, values: {}, show_choices: bool):
        """Create a mapping event list, based on the values given."""
        if values is None:
            values = dict()

        events = list()
        events.append(yaml.MappingStartEvent(anchor=None, tag=None, implicit=True))
        events.append(self.subtype.make_comment(show_choices))
        if values:
            for key, value in values.items():
                # Add the mapping key.
                events.append(yaml.ScalarEvent(value=self.name, anchor=None,
                                               tag=None, implicit=(True, True)))
                # Add the mapping value.
                events.extend(self.subtype.yaml_events(value, show_choices))
        events.append(yaml.MappingEndEvent())
        return events


class YamlConfig(KeyedElem):
    """Creates a config object from the given YAML file.  The YAML file data is treated specially,
    according to the description in ELEMENTS, to restrict the structure of the information given.
    The following general rules and properties also apply.
     - The top level of the YAML file must be a strictly keyed map/dict.
     - Only those s/values described in advance in ELEMENTS are allowed
     - The values .
     - The type of all values in a list must be the same.
     - The keys of maps/dicts must match [a-z][a-z0-9_]
     - Dict keys can always be accessed as attributes or dict keys.
    """

    ELEMENTS = []

    def __init__(self):
        """"""
        super(YamlConfig, self).__init__(elements=self.ELEMENTS)
        self.name = '<root>'

    def dump(self, outfile, values=None, show_choices=True):
        """Write the configuration to the given output stream.
        :param outfile:
        :param values: Write the configuration file with the given values inserted. Values
                       should be a dictionary as produced by YamlConfig.load().
        :param show_choices: When dumping the config file, include the choices available for
                             each item. Defaults to True."""
        events = list()
        events.extend([yaml.StreamStartEvent(), yaml.DocumentStartEvent()])
        events.extend(self.yaml_events(values, show_choices))
        events.extend([yaml.DocumentEndEvent(), yaml.StreamEndEvent()])

        yaml.emit(events, outfile)

    def load(self, infile):
        """
        :param infile: The input stream from which to read.
        :return: A ConfigDict of the contents of the configuration file.
        :raises ValueError, RequiredError
        """

        raw_data = yaml.load(infile)

        return self.validate(raw_data)
