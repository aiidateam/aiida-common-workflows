"""Define a Restructured Text directive to auto-document :class:`aiida_common_workflows.generators.InputGenerator`."""
import inspect
import typing as t

from aiida.common.utils import get_object_from_string
from aiida.engine import Process
from docutils import nodes
from docutils.parsers.rst import directives
from plumpy.ports import PortNamespace
from sphinx import addnodes
from sphinx.ext.autodoc import ClassDocumenter
from sphinx.util.docutils import SphinxDirective

from aiida_common_workflows.generators.ports import InputGeneratorPort


def setup_extension(app):
    """Setup the Sphinx extension."""
    app.add_directive_to_domain('py', CommonInputGeneratorDocumenter.directivetype, CommonInputGeneratorDirective)


class CommonInputGeneratorDocumenter(ClassDocumenter):
    """Sphinx documenter class for AiiDA Processes."""

    directivetype = 'common-input-generator'
    objtype = 'common-input-generator'
    priority = 10

    @classmethod
    def can_document_member(cls, member, membername, isattr, parent):
        return inspect.isclass(member) and issubclass(member, Process)


class CommonInputGeneratorDirective(SphinxDirective):
    """Directive to auto-document AiiDA processes."""

    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True

    EXPAND_NAMESPACES_FLAG = 'expand-namespaces'
    option_spec: t.ClassVar = {'module': directives.unchanged_required, EXPAND_NAMESPACES_FLAG: directives.flag}
    signature = 'InputGenerator'
    annotation = 'common-input-generator'

    has_content = True

    def run(self):
        """Run the directive by initializing it and, building and returning the node tree."""
        self.initialize()
        return self.build_node_tree()

    def initialize(self):
        """Set internal attributes of the class.

        Includes importing the process class.
        """
        self.class_name = self.arguments[0].split('(')[0]
        self.module_name = self.options['module']
        self.process_name = f'{self.module_name}.{self.class_name}'
        self.process = get_object_from_string(self.process_name)

        try:
            self.process_spec = self.process.spec()
        except Exception as exc:
            raise RuntimeError(f"Error while building the spec for process '{self.process_name}': '{exc!r}.'") from exc

    def build_node_tree(self):
        """Return the docutils node tree."""
        process_node = addnodes.desc(desctype='class', domain='py', noindex=False, objtype='class')
        process_node += self.build_signature()
        process_node += self.build_content()
        return [process_node]

    def build_signature(self):
        """Return the signature of the process."""
        signature = addnodes.desc_signature(first=False, fullname=self.signature)
        # signature += addnodes.desc_annotation(text=self.annotation)
        # signature += addnodes.desc_addname(text=f'{self.module_name}.')
        signature += addnodes.desc_name(text=self.class_name)
        return signature

    def build_content(self):
        """Return the main content (docstring, inputs, outputs) of the documentation."""
        note = """
        If arguments are bold, they are required, otherwise they are optional. The required type is in between square
        brackets []. If the argument only accepts a certain number of values, they are listed in between angular
        brackets <>.
        """
        content = addnodes.desc_content()
        content += nodes.paragraph(text=self.process.__doc__)
        content += nodes.note('', nodes.paragraph(text=note))
        content += self.build_doctree(
            title='Keyword arguments:',
            port_namespace=self.process_spec.inputs,
        )
        return content

    def build_doctree(self, title, port_namespace):
        """Return a doctree for a given port namespace, including a title."""
        paragraph = nodes.paragraph()
        paragraph += nodes.strong(text=title)
        namespace_doctree = self.build_portnamespace_doctree(port_namespace)
        if namespace_doctree:
            paragraph += namespace_doctree
        else:
            paragraph += nodes.paragraph(text='None defined.')

        return paragraph

    def build_portnamespace_doctree(self, port_namespace):
        """Build the doctree for a port namespace."""
        if not port_namespace:
            return None
        result = nodes.bullet_list(bullet='*')
        for name, port in sorted(
            port_namespace.items(), key=lambda item: (item[1].required, not item[1].name), reverse=True
        ):
            item = nodes.list_item()
            if isinstance(port, InputGeneratorPort):
                item.extend(self.build_port_content(name, port))
            elif isinstance(port, PortNamespace):
                if port.required:
                    item += addnodes.literal_strong(text=name)
                else:
                    item.append(nodes.Text(name))
                if port.help:
                    item += nodes.Text(f': {port.help}')
                item += self.build_portnamespace_doctree(port)
            else:
                raise NotImplementedError
            result += item
        return result

    def build_port_content(self, name, port):
        """Build the content that describes an input port."""
        content = []

        if port.required:
            content.append(nodes.strong(text=name))
        else:
            content.append(nodes.Text(name))

        type_string = self.format_valid_types(port.valid_type)

        if port.choices is not None:
            type_string += self.format_choices(port.choices)
        if port.code_entry_point is not None:
            type_string += self.format_code_entry_point(port.code_entry_point)

        content.append(nodes.literal(text=f' [{type_string}]:'))

        if port.help:
            content.append(nodes.emphasis(text=port.help))
        else:
            content.append(nodes.emphasis(text='...'))

        return content

    @staticmethod
    def format_choices(choices):
        """Format the choices of a port with ``ChoiceType`` as valid type."""
        strings = []
        for choice in choices:
            try:
                strings.append(str(choice.value))
            except AttributeError:
                strings.append(str(choice))
        return f'<{", ".join(strings)}>'

    @staticmethod
    def format_code_entry_point(code_entry_point):
        """Format the entry point string of a port with the ``CodeType`` as valid type."""
        return f'<{code_entry_point}>'

    def format_valid_types(self, valid_type):
        """Format a (list or tuple of) valid type(s)."""
        if isinstance(valid_type, (list, str)):
            return [self.format_valid_type(element) for element in valid_type]

        return self.format_valid_type(valid_type)

    @staticmethod
    def format_valid_type(valid_type):
        """Format a valid type."""
        from inspect import isclass

        if isclass(valid_type):
            return valid_type.__name__

        try:
            cls = valid_type.__class__
        except AttributeError:
            cls = valid_type

        try:
            return cls.__name__
        except AttributeError:
            return str(cls)
