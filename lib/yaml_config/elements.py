from __future__ import print_function, division, unicode_literals

import re
from abc import ABCMeta
from collections import OrderedDict, defaultdict

# A modified pyyaml library
import myyaml as yaml
from myyaml import representer


# This module defines a set of constructs for strictly defining configuration objects that get
# their data from Yaml files. It allows for the general (though not complete) flexibility of
# Yaml/Json, while giving the program using it assurance that the types and structure of the
# configuration parameters brought in are what is to be expected. Configuration objects generated
# by this library can be merged in a predictable way. Example configurations can automatically
# be generated, as can configurations already filled out with the given values.


class RequiredError(ValueError):
    pass


class ConfigDict(dict):
    """Since we enforce field names that are also valid python names, we can build this
    dict that allows for getting and setting keys like attributes.

    The following marks this class as having dynamic attributes for IDE typechecking.
    @DynamicAttrs
    """
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


# This is a dummy for type analyzers
def _post_validator(siblings, value):
    # Just using the variables to clear analyzer complaints
    return siblings[value]


class ConfigElement:
    """The base class for all other element types.

    :cvar type: The type object used to type-check, and convert if needed, the values loaded by
        YAML. This must be defined.
    :cvar type_converter: A function that, given a generic value of unknown type, will convert it
        into the type expected by this ConfigElement. If this is None, the type object itself is
        used instead.
    :cvar _type_name: The name of the type, if different from type.__name__.
    """

    __metaclass__ = ABCMeta

    type = None
    type_converter = None
    _type_name = None

    # The regular expression that all element names are matched against.
    _NAME_RE = re.compile(r'^[a-z][a-z0-9_]+$')

    # We use the representer functions in this to consistently represent certain types.
    _representer = yaml.representer.SafeRepresenter()

    def __init__(self, name=None, default=None, required=False, choices=None,
                 post_validator=None, help_text=""):
        """
        :param str name: The name of this configuration element. Required if this is a key in a
            KeyedElem. Will receive a descriptive default otherwise.
        :param default: The default value if no value is retrieved from a config file.
        :param bool required: When validating a config file, a RequiredError will be thrown if
            there is no value for this element. *NULL does not count as a value.*
        :param list choices: A optional sequence of values that this type will accept.
        :param _post_validator post_validator: A optional post validation function for
            this element. See the Post-Validation section in the online documentation for more info.
        :raises ValueError: May raise a value error from an invalid default.
        """

        if name is not None:
            self._validate_name(name)

        self.name = name

        # A value for this item is required
        self.required = required
        # What values this configuration item may take. None means unlimited.
        self._choices = choices
        # Help text for internal and example configuration files.
        self.help_text = help_text

        # Run this validator on the field data (and all data at this level and lower) when
        # validating
        if not hasattr(self, 'post_validator'):
            self.post_validator = post_validator

        # The type name is usually pulled straight from the type's __name__ attribute
        # This overrides that, when not None
        if self._type_name is None:
            self._type_name = self.type.__name__

        # The default value gets validated through a setter function.
        self._default = None
        if default is not None:
            self.default = default


    def _check_range(self, value):
        """Make sure the value is in the given list of choices. Throws a ValueError if not.

        The value of *self.choices* doesn't matter outside of this method.

        :returns: None
        :raises ValueError: When out of range."""

        if self._choices and value not in self._choices:
            raise ValueError("Value '{}' not in the given choices {} for {} called '{}'.".format(
                value, self._choices, self.__class__.__name__, self.name
            ))

    @property
    def default(self):
        return self._default

    @default.setter
    def default(self, value):
        self.validate(value)
        self._default = value

    def validate(self, value):
        """Validate the given value, and return the validated form.

        :returns: The value, converted to this type if needed.
        :raises TypeError: if type conversion can't occur.
        :raises ValueError: if the value is out of range.
        :raises RequiredError: if the value is required, but missing.
        """

        if type(value) is not self.type:
            if value is None:
                if self._default is not None:
                    value = self._default
                elif self.required:
                    raise RequiredError("Config missing required value for {} named {}."
                                        .format(self.__class__.__name__, self.name))

            try:
                converter = self.type if self.type_converter is None else self.type_converter
                value = converter(value)
            except TypeError:
                raise TypeError("Incorrect type for {} field {}: {}"
                                .format(self.__class__.__name__, self.name, value))

        self._check_range(value)

        return value

    def make_comment(self, show_choices=True, show_name=True):
        """Create a comment for this configuration element.

        :param show_name: Whether to show the name of this element.
        :param show_choices: Whether to include the valid choices for this item in the help
                             comments.
        :returns: A comment string."""

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
        if show_choices and self._choices:
            choices_doc = self._choices_doc()
            if choices_doc is not None:
                comment.append(choices_doc)
        return '\n'.join(comment)

    def find(self, dotted_key):
        """Find the element matching the given dotted key. This is useful for retrieving
        elements to use their help_text or defaults.

        Dotted keys look like normal property references, except that the
        names of the sub-element for Lists or Collections are given as a '*', since they
        don't have an explicit name. An empty string always returns this element.

        Examples: ::

            class Config2(yc.YamlConfig):
                ELEMENTS = [
                    yc.ListElem('cars', sub_elem=yc.KeyedElem(elements=[
                        yc.StrElem('color'),
                        yc.StrElem('make'),
                        yc.IntElem('year'),
                        yc.CollectionElem('accessories', sub_elem=yc.KeyedElem(elements=[
                            yc.StrElem('floor_mats')
                        ])
                    ]
                ]

            config = Config2()
            config.find('cars.*.color')

        :param str dotted_key: The path to the sought for element.
        :returns ConfigElement: The found Element.
        :raises KeyError: If the element cannot be found.
        """

        raise NotImplementedError("Implemented by individual elements.")

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

        return 'Choices: ' + ', '.join(map(str, self._choices))

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

    def _run_post_validator(self, elem, siblings, value):
        """Finds and runs the post validator for the given element.

        :param ConfigElement elem: The config element to run post_validation on.
        :param siblings: The siblings
        """

        # Don't run post-validation on non-required fields that don't have a value.
        if not elem.required and value is None:
            return None

        try:
            if elem.post_validator is not None:
                return elem.post_validator(siblings, value)

            local_pv_name = 'post_validate_{}'.format(elem.name)
            if hasattr(self, local_pv_name):
                getattr(self, local_pv_name)(siblings, value)
            else:
                # Just return the value if there was no post-validation.
                return value
        except ValueError as err:
            # Reformat any ValueErrors to point to where this happened.
            raise ValueError("Error in post-validation of {} called '{}' with value '{}': {}"
                             .format(elem.__class__.__name__, elem.name, value, err))

    def merge(self, old, new):
        """Merge the new values of this entry into the existing one. For most types,
        the old values are simply replaced. For complex types (lists, dicts), the
        behaviour varies."""

        return new


class ScalarElem(ConfigElement):
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

    def find(self, dotted_key):
        if dotted_key != '':
            raise KeyError("Scalars don't have sub-elements, so the only valid find "
                           "string is '' for them.")

        return self

    def set_default(self, dotted_key, value):
        # We call this just to throw the error for an invalid key.
        self.find(dotted_key)
        self.validate(value)
        self._default = value


class IntElem(ScalarElem):
    """An integer configuration element."""
    type = int


class FloatElem(ScalarElem):
    """A float configuration element."""
    type = float


class RangeElem(ScalarElem):

    def __init__(self, name=None, default=None, required=True, vmin=None, vmax=None,
                 post_validator=None, help_text=""):
        """
        :param vmin: The minimum value for this element, inclusive.
        :param vmax: The max value, inclusive.
        """
        super(RangeElem, self).__init__(name=name,
                                        default=default,
                                        required=required,
                                        choices=[vmin, vmax],
                                        post_validator=post_validator,
                                        help_text=help_text)

    def _choices_doc(self):
        if self._choices == (None, None):
            return None
        elif self._choices[0] is None:
            return 'Valid Range: < {}'.format(self._choices[1])
        elif self._choices[1] is None:
            return 'Valid Range: > {}'.format(self._choices[0])
        else:
            return 'Valid Range: {} - {}'.format(*self._choices)

    def _check_range(self, value):
        if self._choices[0] is not None and value <= self._choices[0]:
            raise ValueError("Value {} in {} below minimum ({}).".format(
                value,
                self.name,
                self._choices[0]
            ))
        if self._choices[1] is not None and value >= self._choices[1]:
            raise ValueError("Value {} in {} above maximum ({}).".format(
                value,
                self.name,
                self._choices[1]
            ))


class IntRangeElem(IntElem, RangeElem):
    """An int element with range validation."""
    pass


class FloatRangeElem(FloatElem, RangeElem):
    """A float with range validation."""
    pass


class BoolElem(ScalarElem):
    """A boolean element. YAML automatically translates many strings into boolean values."""
    type = bool


class StrElem(ScalarElem):
    type = str


class RegexElem(StrElem):
    """Just like a string item, but validates against a regex."""

    def __init__(self, name=None, default=None, regex='', post_validator=None, help_text=""):
        """
        :param regex: A regular expression string to match against.
        """

        super(RegexElem, self).__init__(name, default=default,
                                        post_validator=post_validator,
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


class ListElem(ConfigElement):
    """A list of configuration items. All items in the list must be the same ConfigElement type.
    Configuration inheritance appends new, unique items to these lists.

    A shortcut is allowed in the interpretation of lists, such that a single value is
    interpreted as a single valued list. Each of the following is valid. ::

        colors: red
        colors: [red, yellow, green]
        colors:
            - red
            - yellow
            - blue

    However, if the sub-element is another list, the lists must always be explicit. ::

        collections:
            - [quarter, dime, nickel]
            - [thing1, thing2, thing3]
        collections: [[quarter, dime, nickel], [thing1, thing2, thing3]

    When dumping configs, the lists are always given explicitly.

    """

    type = list
    type_name = 'list of items'

    def __init__(self, name=None, sub_elem=None, min_length=0, max_length=None,
                 required=False, post_validator=None, defaults=None, help_text=""):
        """
        :param sub_elem: A ConfigItem that each item in the list must conform to.
        :param min_length: The minimum number of items allowed, inclusive. Default: 0
        :param max_length: The maximum number of items allowed, inclusive. None denotes unlimited.
        :param [] defaults: Defaults on a list are items that are prepended to the list
            regardless of what's in a loaded config file. Duplicates are possible (just as they
            are if the config file has duplicates).
        """

        if defaults is None:
            defaults = []

        if not isinstance(sub_elem, ConfigElement):
            raise ValueError("Subtype must be a config element of some kind. Got: {}"
                             .format(sub_elem))
        self.sub_elem = sub_elem

        if min_length < 0:
            raise ValueError("min_length must be a positive integer.")
        self.min_length = min_length
        self.max_length = max_length

        super(ListElem, self).__init__(name,
                                       default=defaults,
                                       required=required,
                                       post_validator=post_validator,
                                       help_text=help_text)

        # Set the name of the subtype if we know the name of this element.
        if self.name is not None:
            self._set_names()

    def _set_names(self):
        """List elements generally don't have names, but we force them for easier debugging.
        Unfortunately, the name of a list won't be known until we get to a containing
        mapping/dict, so we use this function to walk back up."""

        if self.sub_elem.name is None:
            self.sub_elem.name = '{}.list_item'.format(self.name)

        # Make sure names get set on the sublist, if the subtype is a ListElem
        if isinstance(self.sub_elem, ListElem):
            self.sub_elem._set_names()

    def _check_range(self, value):
        """Make sure our list is within the appropriate length range."""
        vlen = len(value)
        if vlen < self.min_length:
            return False

        if self.max_length is None or vlen <= self.max_length:
            return True
        else:
            return False

    def validate(self, raw_values):
        """Just like the parent function, except converts None to an empty list,
        and single values of other types into the subtype for this list.  Subvalues are
        recursively validated against the subitem type (whose name is ignored)."""

        if self.default is None:
            values = []
        else:
            values = self.default

        if type(raw_values) is not self.type:
            if raw_values is not None:
                raw_values = [raw_values]
            else:
                raw_values = []


        for val in raw_values:
            values.append(self.sub_elem.validate(val))

        if not self._check_range(values):
            raise ValueError("Expected [{}-{}] list items for {} field {}, got {}.".format(
                self.min_length,
                self.max_length if self.max_length is not None else 'inf',
                self.__class__.__name__,
                self.name,
                len(values)
            ))

        for i in range(len(values)):
            values[i] = self._run_post_validator(self.sub_elem, values, values[i])

        return values

    def _choices_doc(self):
        return "May contain {min} - {max} items.".format(
            min=self.min_length,
            max=self.max_length if self.max_length is not None else 'inf'
        )

    def find(self, dotted_key):
        if dotted_key == '':
            return self
        else:
            parts = dotted_key.split('.', maxsplit=1)
            key = parts[0]
            next_key = parts[1] if len(parts) == 2 else ''
            if key != '*':
                raise KeyError("Invalid dotted key for {} called '{}'. List elements"
                               "must have their element name given as a *, since it's "
                               "sub-element isn't named. Got '{}' from '{}' instead."
                               .format(self.__class__.__name__, self.name, key, dotted_key))

            return self.sub_elem.find(next_key)

    def yaml_events(self, value, show_choices):
        events = list()
        events.append(yaml.SequenceStartEvent(
            anchor=None,
            tag=None,
            implicit=True,
            flow_style=False,
        ))

        comment = self.sub_elem.make_comment(show_choices, show_name=False)
        events.append(yaml.CommentEvent(value=comment))

        if value is not None:
            # Value is expected to be a list of items at this point.
            for v in value:
                events.extend(self.sub_elem.yaml_events(v, show_choices=show_choices))
        else:
            events.extend(self.sub_elem.yaml_events(None, show_choices))

        events.append(yaml.SequenceEndEvent())
        return events

    def merge(self, old, new):
        """Add any unique, new items to the list."""
        merged = old.copy()

        for item in new:
            if item not in merged:
                merged.append(item)

#TODO: Make this worthwhile
class CodeElem(ListElem):
    """Like a list config item, except the subtype is always string, and the
    subitems are considered to be a single group. Useful for config sections that are
    really lines of code or documentation."""
    type = list
    type_name = 'code block'

    def __init__(self, name=None, help_text=""):
        subtype = StrElem('code_line')
        super(CodeElem, self).__init__(name, sub_elem=subtype, help_text=help_text)

    def validate(self, lines):
        lines = [self.sub_elem.validate(line) for line in lines if line is not None]

        code_block = '\n'.join(lines).strip()
        if not code_block.endswith('\n'):
            code_block += '\n'
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


class DerivedElem(ConfigElement):
    """The value is derived from the values of other elements. This is only valid when used
    as an element in a KeyedElem (or YamlConfig), trying to use it elsewhere will raise an
    exception (It simply doesn't make sense anywhere else).

    Resolution of this element is deferred until after all non-derived elements are resolved. All
    derived elements are then resolved in the order they were listed. This resolution is performed
    by a function, which can be given either:

      - As the 'resolver' argument to __init__
      - The 'resolve' method of this class
      - The 'resolve_<name>' method of the parent KeyedElem or YamlConfig class.

    This function is expected to take one positional argument, which is the dictionary of
    validated values from the KeyedElem so far.
    """

    def __init__(self, name, resolver=None, post_validator=None, help_text=""):
        if name is None:
            raise ValueError("Derived Elements must be named.")

        if resolver is not None:
            self.resolve = resolver
        super(DerivedElem, self).__init__(name=name,
                                          post_validator=post_validator,
                                          help_text=help_text)

    def resolve(self, siblings):
        """A resolver function gets a dictionary of its returned sibling's values, and should return
        the derived value. A resolver passed as an argument to DerivedElem's __init__ should have
        the same signature (without the self).

        :param {} siblings: The dictionary of validated values from the keyed element that this
            is a part of.
        :returns: The derived element value
        """
        return None

    def yaml_events(self, value, show_choices):
        """Derived elements are never written to file."""
        return []

    def set_default(self, dotted_key, value):
        raise RuntimeError("You can't set defaults on derived elements.")


class _DictElem(ConfigElement):
    result_dict_type = ConfigDict

    def __init__(self, *args, **kwargs):
        super(_DictElem, self).__init__(*args, **kwargs)

    def validate(self, value):
        raise NotImplementedError

    def _key_check(self, values_dict):
        """Raises a KeyError if duplicate (case-insensitive) keys are present in values_dict.

        :param {} values_dict: The dictionary to check.
        """

        # Check for duplicate keys.
        lowered_keys = defaultdict(lambda: [])
        for key in values_dict.keys():
            key_l = key.lower()
            lowered_keys[key_l].append(key)

            if self._NAME_RE.match(key_l) is None:
                raise KeyError("Invalid key '{}' in {} called {}. (keys must be valid python "
                               "identifiers.".format(key_l, self.__class__.__name__, self.name))

        for k_list in lowered_keys.values():
            if len(k_list) != 1:
                raise KeyError("Duplicate keys given {} in {} called {} (keys are case "
                               "insensitive)."
                               .format(k_list, self.__class__.__name__, self.name))

    def find(self, dotted_key):
        raise NotImplementedError()


class KeyedElem(_DictElem):
    """A dictionary configuration item with predefined keys that may have non-uniform types. The
    valid keys are are given as ConfigItem objects, with their names being used as the key name."""

    type = dict

    def __init__(self, name=None, elements=list(), post_validator=None,
                 help_text="", required=False):
        """
        :param elements: This list of config elements is also forms the list of accepted keys,
                         with the element.name being the key.
        """

        super(KeyedElem, self).__init__(name,
                                        post_validator=post_validator,
                                        help_text=help_text,
                                        required=required)

        self.config_elems = OrderedDict()

        for i in range(len(elements)):
            elem = elements[i]
            # Make sure each sub-element has a usable name that can be used as a key..
            if elem.name is None:
                raise ValueError("In KeyedConfig item ({}), subitem {} has name of None."
                                 .format(self.name if self.name is not None else '<unnamed>', i))

            # Make sure derived elements have a resolver defined somewhere.
            if isinstance(elem, DerivedElem):
                self._find_resolver(elem)

            self.config_elems[elem.name] = elem

    def _find_resolver(self, elem):
        """Find the resolver function for the given DerivedElem. Try the elem.resolve method
        first, then look for a 'get_<elem.name>' method next. Raises a ValueError on failure."""

        if elem.resolve is not None:
            return elem.resolve
        elif hasattr(self, 'resolve_' + elem.name):
            return getattr(self, 'resolve_' + elem.name)
        else:
            raise ValueError("Could not find resolver for derived element '{}' in {} called {}."
                             .format(elem.name, self.__class__.__name__, self.name))

    def find(self, dotted_key):
        if dotted_key == '':
            return self
        else:
            parts = dotted_key.split('.', maxsplit=1)
            key = parts[0]
            next_key = parts[1] if len(parts) == 2 else ''
            if key not in self.config_elems:
                raise KeyError("Invalid dotted key for {} called '{}'. KeyedElem"
                               "element names must be in the defined keys. "
                               "Got '{}' from '{}', but valid keys are {}"
                               .format(self.__class__.__name__, self.name,
                                       key, dotted_key, self.config_elems.keys()))

            return self.config_elems[key].find(next_key)

    find.__doc__ = ConfigElement.find.__doc__

    def merge(self, old, new):
        for key, value in new.items():
            elem = self.config_elems[key]
            old[key] = elem.merge(old[key], new[key])
        return old

    def validate(self, values):
        """Ensure the given values conform to the config specification. Also adds any
        derived element values.

        :param dict values: The dictionary of values to validate.
        :returns dict: The validated and type converted value dict.
        :raises TypeError: if type conversion can't occur.
        :raises ValueError: When the value is not within range.
        :raises RequiredError: When a required value is missing.
        :raises KeyError: For duplicate or malformed keys.
        """
        out_dict = self.result_dict_type()

        self._key_check(values)

        lowered_keys = [k.lower() for k in values.keys()]
        unknown_keys = set(lowered_keys).difference(self.config_elems.keys())
        if unknown_keys:
            raise KeyError("Invalid config key '{}' given under {} called '{}'."
                           .format(unknown_keys.pop(), self.__class__.__name__, self.name))

        derived_elements = []

        for key, elem in self.config_elems.items():
            if isinstance(elem, DerivedElem):
                derived_elements.append(elem)
            else:
                # Validate each of the subkeys in this dict.
                out_dict[key] = self.config_elems[key].validate(values.get(key))

        # Handle any derived elements
        for elem in derived_elements:
            out_dict[elem.name] = self._find_resolver(elem)(out_dict)

        # Run custom post validation against each key, if given.
        for key, elem in self.config_elems.items():
            out_dict[key] = self._run_post_validator(elem, out_dict, out_dict[key])

        return out_dict

    def yaml_events(self, values, show_choices):
        if values is None:
            values = dict()

        events = list()
        events.append(yaml.MappingStartEvent(anchor=None, tag=None, implicit=True))
        for key, elem in self.config_elems.items():
            # Don't output anything for Derived Elements
            if isinstance(elem, DerivedElem):
                continue

            value = values.get(key, None)
            comment = elem.make_comment(show_choices)
            events.append(yaml.CommentEvent(value=comment))
            # Add the mapping key
            events.append(yaml.ScalarEvent(value=key, anchor=None,
                                           tag=None, implicit=(True, True)))
            # Add the mapping value
            events.extend(elem.yaml_events(value, show_choices))
        events.append(yaml.MappingEndEvent())
        return events


class CategoryElem(_DictElem):
    """A dictionary config item where all the keys must be of the same type, but the key values
    themselves do not have to be predefined. The possible keys may still be restricted with
    the choices argument to init."""

    type = dict

    def __init__(self, name=None, sub_elem=None, choices=None, defaults=None,
                 required=False, help_text=""):
        """
        :param name: The name of this Config Element
        :param sub_elem: The type all keys in this mapping must conform to.
        :param choices: The possible keys for this element. None denotes that any are valid.
        :param required: Whether this element is required.
        :param defaults: An optional dictionary of default key:value pairs.
        :param help_text: Description of the purpose and usage of this element.
        """

        if defaults is None:
            defaults = dict()

        if not isinstance(sub_elem, ConfigElement):
            raise ValueError("Sub-element must be a config element of some kind. Got: {}"
                             .format(sub_elem))
        elif isinstance(sub_elem, DerivedElem):
            raise ValueError("Using a derived element as the sub-element in a CategoryElem "
                             "does not make sense.")

        self.sub_elem = sub_elem

        super(CategoryElem, self).__init__(name, choices=choices, help_text=help_text,
                                           default=defaults, required=required)

    def validate(self, value_dict):
        out_dict = self.result_dict_type()

        self._key_check(value_dict)

        for key, value in value_dict.items():
            key = key.lower()
            if self._choices is not None and key not in self._choices:
                raise ValueError("Invalid key for {} called {}. '{}' not in given choices.")
            out_dict[key] = self.sub_elem.validate(value)

        # Use the default dictionary to
        for key, value in self._default:
            if key not in out_dict:
                out_dict[key] = self.sub_elem.validate(value)

        for key, value in out_dict.items():
            out_dict[key] = self._run_post_validator(self.sub_elem, out_dict, value)

        return out_dict

    def find(self, dotted_key):
        if dotted_key == '':
            return self
        else:
            parts = dotted_key.split('.', maxsplit=1)
            key = parts[0]
            next_key = parts[1] if len(parts) == 2 else ''
            if key != '*':
                raise KeyError("Invalid dotted key for {} called '{}'. CategoryElem"
                               "must have their element name given as a *, since it's "
                               "sub-element isn't named. Got '{}' from '{}' instead."
                               .format(self.__class__.__name__, self.name, key, dotted_key))

            return self.sub_elem.find(next_key)

    def yaml_events(self, values, show_choices):
        """Create a mapping event list, based on the values given."""
        if values is None:
            values = dict()

        events = list()
        events.append(yaml.MappingStartEvent(anchor=None, tag=None, implicit=True))
        comment = self.sub_elem.make_comment(show_choices, show_name=False)
        events.append(yaml.CommentEvent(value=comment))
        if values:
            for key, value in values.items():
                # Add the mapping key.
                events.append(yaml.ScalarEvent(value=self.name, anchor=None,
                                               tag=None, implicit=(True, True)))
                # Add the mapping value.
                events.extend(self.sub_elem.yaml_events(value, show_choices))
        events.append(yaml.MappingEndEvent())
        return events
