#!/usr/bin/env python
"""Script to validate the optional dependencies in the `pyproject.toml`."""


def main():
    """Validate the optional dependencies."""
    import pathlib
    import sys

    import tomllib

    filepath_pyproject_toml = pathlib.Path(__file__).parent.parent / 'pyproject.toml'

    with filepath_pyproject_toml.open('rb') as handle:
        pyproject = tomllib.load(handle)

    exclude = ['all_plugins', 'docs', 'pre-commit', 'tests']
    dependencies_all_plugins = pyproject['project']['optional-dependencies']['all_plugins']
    dependencies_separate = []

    for key, dependencies in pyproject['project']['optional-dependencies'].items():
        if key in exclude:
            continue
        dependencies_separate.extend(dependencies)

    missing_all_plugins = set(dependencies_separate).difference(set(dependencies_all_plugins))
    excess_all_plugins = set(dependencies_all_plugins).difference(set(dependencies_separate))

    if missing_all_plugins:
        print(
            'ERROR: the `all_plugins` extras are inconsistent. The following plugin dependencies are missing: '
            f'{", ".join(missing_all_plugins)}',
            file=sys.stderr,
        )
        sys.exit(1)

    if excess_all_plugins:
        print(
            'ERROR: the `all_plugins` extras are inconsistent. The following dependencies are not declared by any '
            f'plugin extras: {", ".join(excess_all_plugins)}',
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == '__main__':
    main()
