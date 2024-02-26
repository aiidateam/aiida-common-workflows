"""Tests for the :mod:`aiida_common_workflows.generators.generator` module."""
import pytest
from aiida import orm
from aiida.plugins import WorkflowFactory
from aiida_common_workflows.generators import InputGenerator


class InputGeneratorA(InputGenerator):
    """Dummy implementation of ``InputGenerator``."""

    @classmethod
    def define(cls, spec):
        super().define(spec)
        spec.input('a')

    def _construct_builder(self, **kwargs):
        """Not implemented."""


class InputGeneratorB(InputGeneratorA):
    """Dummy subclass of ``InputGeneratorA``."""

    @classmethod
    def define(cls, spec):
        super().define(spec)
        spec.input('b')

    def _construct_builder(self, **kwargs):
        """Not implemented."""


def test_inputgen_constructor(generate_input_generator_cls):
    """Test the constructor of a subclass of ``InputGenerator``."""

    cls = generate_input_generator_cls()

    with pytest.raises(RuntimeError):
        cls()

    cls(process_class=WorkflowFactory('common_workflows.relax.siesta'))


def test_spec():
    """Test that ``spec`` classmethod creates new instance of generator spec and calls ``define``."""
    InputGeneratorA.spec()
    assert hasattr(InputGeneratorA, '_spec')
    assert tuple(InputGeneratorA.spec().inputs.keys()) == ('a',)

    InputGeneratorB.spec()
    assert hasattr(InputGeneratorB, '_spec')
    assert tuple(InputGeneratorB.spec().inputs.keys()) == ('a', 'b')


def test_get_builder_immutable_kwargs(generate_input_generator_cls, generate_structure):
    """Test that calling ``get_builder`` does not mutate the ``kwargs`` when they are nodes.

    In this case a deepcopy would mute the node and therefore return a node with different uuid.
    """

    cls = generate_input_generator_cls(inputs_dict={'structure': orm.StructureData})
    generator = cls(process_class=WorkflowFactory('common_workflows.relax.siesta'))

    structure = generate_structure(symbols=('Si',))
    kwargs = {'structure': structure}
    generator.get_builder(**kwargs)
    # The structure is now stored and so should be the same.
    assert kwargs['structure'].uuid == structure.uuid


def test_get_builder_mutable_kwargs(generate_input_generator_cls, monkeypatch):
    """Test that calling ``get_builder`` does mutate the ``kwargs`` when they are not nodes.

    In this case, the implementation of ``get_builder`` ensure to deepcopy the ``kwargs`` before they will be available
    for use by any subclass of ``InputGenerator``. In this specific case, we test a particulat input (``mutable``) that
    is modified inside the ``get_builder`` of a ``generate_input_generator_cls`` implementation. Even if this input is
    modified inside the implementation (see ``construct_builder`` here), this does not affect the original ``kwargs``
    that was passed in input of ``get_builder``. It would not have been the case if the deepcopy was not in place.
    """

    def construct_builder(self, **kwargs):
        kwargs['mutable']['test'] = 'whatever'
        return self.process_class.get_builder()

    cls = generate_input_generator_cls(inputs_dict={'mutable': dict})
    monkeypatch.setattr(cls, '_construct_builder', construct_builder)
    generator = cls(process_class=WorkflowFactory('common_workflows.relax.siesta'))
    kwargs = {'mutable': {'test': 333}}
    generator.get_builder(**kwargs)
    assert kwargs['mutable'] == {'test': 333}


def test_get_builder_immutable_kwargs_nested(generate_input_generator_cls, generate_structure):
    """Test that calling ``get_builder`` does not mutate the ``kwargs`` when they are nodes, even if nested."""
    cls = generate_input_generator_cls(inputs_dict={'space.structure': orm.StructureData})
    generator = cls(process_class=WorkflowFactory('common_workflows.relax.siesta'))

    structure = generate_structure(symbols=('Si',))
    kwargs = {'space': {'structure': structure}}
    generator.get_builder(**kwargs)
    assert kwargs['space']['structure'].uuid == structure.uuid
