"""Module with Spinx extension to facilitate the automatic documentation of common workflows."""


def setup(app):
    """Setup function to add the extension classes / nodes to Sphinx."""
    import aiida_common_workflows

    from . import input_generator

    app.setup_extension('sphinxcontrib.details.directive')
    input_generator.setup_extension(app)

    return {'version': aiida_common_workflows.__version__, 'parallel_read_safe': True}
