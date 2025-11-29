from enum import Enum
from typing import FrozenSet, Iterable


class OptionalFeature(str, Enum):
    """Enumeration of optional features that an input generator can support."""


class OptionalFeatureMixin:
    """Mixin class for input generators that support optional features."""

    _optional_features: FrozenSet[OptionalFeature] = frozenset()
    _supported_optional_features: FrozenSet[OptionalFeature] = frozenset()

    @classmethod
    def get_optional_features(cls) -> set[OptionalFeature]:
        """Return the set of optional features for this common workflow."""
        return set(cls._optional_features)

    @classmethod
    def get_supported_optional_features(cls) -> set[OptionalFeature]:
        """Return the set of optional features supported by this implementation."""
        return set(cls._supported_optional_features)

    @classmethod
    def supports_feature(cls, feature: OptionalFeature) -> bool:
        """Return whether the given feature is supported by this implementation."""
        return feature in cls._supported_optional_features

    @classmethod
    def validate_optional_features(
        cls,
        requested_features: Iterable[str],
    ) -> None:
        """Validate that all requested features are supported by this implementation.

        :param requested_features: an iterable of requested features.
        :raises InputValidationError: if any of the requested features is not supported.
        """
        unsupported_features = set(requested_features) - {
            feature.value for feature in cls.get_supported_optional_features()
        }
        if unsupported_features:
            return (
                f'the following optional features are not supported by `{cls.__name__}`: '
                f'{", ".join(unsupported_features)}'
            )
