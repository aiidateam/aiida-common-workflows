# -*- coding: utf-8 -*-
"""
Collects the override functions
"""


def add_or_replace_dict_item(builder, port, key, value):
    """
    Insert a key-value pare in a node
    """
    builder[port][key] = value


def replace_node(builder, port, new_node):
    """
    Replace an entire node
    """
    builder[port] = new_node
