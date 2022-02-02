# -*- coding: utf-8 -*-
"""
Collects the generic override functions.

Overrides functions receive a `builder` and change it according to some
`**kwargs` passed (dependent on the problem to solve).
In this context, "generic" means that these overrides act
on aiida data type without knowlwdge of the use of the data type.
Each override function must be associated to an entry point under the
group `acwf.overrides`.
"""


def _check_port(func_name, builder, port):
    """
    Check that a port exists in a builder
    """
    if not isinstance(port, str):
        raise ValueError(f'The `port` passed to {func_name} override is not a python `str`')

    try:
        builder[port]
    except KeyError:
        raise ValueError(f'`{port}` passed to {func_name} override is not a valid port of the passed `builder`')


def update_dict(builder, port: str, dictionary: dict, sub_path=None):
    """
    Update the dictionary contained in a orm.Dict instance.

    It supports nested dictionaries through the `sub_path` argument.
    For instance taking a builder[port] = {"original":{"nested":1},"dict":2}
      update_dict(builder, port, {"test":1})
    will return:
      {"original":{"nested":1},"dict":2,"test":1}
    while:
      update_dict(builder, port, {"test":1}, sub_path = ["original"])
    returns:
      {"original":{"nested":1, "test":1},"dict":2}

    :param builder: the builder to modify
    :param port: the builder port that will be changed, must corespond to a port
                 with orm.dict as valid  type.
    :param dictionary: the dictionary to insert in the `builder[port]`
    :param sub_path: a list of keys for nested dictionaries, as explained above
    :return builder: a builder with the updated `port`.
    """

    _check_port(update_dict.__name__, builder, port)

    if not isinstance(dictionary, dict):
        raise ValueError('The `dictionary` passed to `update_dict` override is not a python `dict`')

    if sub_path is not None:
        if isinstance(sub_path, str):
            sub_path = [sub_path]
        if not isinstance(sub_path, list):
            raise ValueError('The `sub_path` passed to `update_dict` override must be a `list` of keys')

    old_dict_node = builder[port]

    if old_dict_node.is_stored:
        new_dict_node = builder[port].clone()
    else:
        new_dict_node = old_dict_node

    #The implementation relys on the python feature that `to_change` is
    #a copy (not a deep copy!) of `new_dict_node.attributes`, therefore
    #any change on `to_change` is reflected in `new_dict_node.attributes`
    to_change = new_dict_node.attributes

    if sub_path is not None:
        for key in sub_path:
            if to_change is None:
                break
            to_change = to_change.get(key, None)
        if not isinstance(to_change, dict):
            raise ValueError('The `sub_path` passed to `update_dict` override contains an invalid key')

    to_change.update(dictionary)

    builder[port] = new_dict_node


def add_or_replace_node(builder, port, new_node):
    """
    Replace an entire node. Since the new_node will be passed
    as component of a orm.List inputs of a WprkChain, it mst be json
    serializable. Foe this we replace the node with its uuid,
    """
    from aiida.common import NotExistent
    from aiida.orm import load_node

    _check_port(add_or_replace_node.__name__, builder, port)

    try:
        new_node = load_node(new_node)
    except NotExistent:
        raise ValueError('The `new_node_uuid` passed to the `add_or_replace_node` override is not a valid uuid')

    #NOTE: need a check on the correspondence of the new_node type
    #respect to the accepted type of port? I believe no.

    builder[port] = new_node


def remove_node(builder, port):
    """
    Remove contento of a port
    """
    _check_port(remove_node.__name__, builder, port)

    builder.pop(port)
