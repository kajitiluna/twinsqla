from typing import Callable, Type, TypeVar, Generic
from typing import Any, Tuple, List, Optional, Union
from collections import OrderedDict
from collections.abc import Sequence
from functools import lru_cache

from ._support import description


RESULT_TYPE = TypeVar("RESULT_TYPE")


@description("entity_type")
class ResultType(Generic[RESULT_TYPE]):

    def __init__(self, entity_type: Type[RESULT_TYPE], sequencial: bool):
        self.entity_type: Type[RESULT_TYPE] = entity_type
        self.sequencial: bool = sequencial

    def to_values(self, results) -> Union[
            Optional[RESULT_TYPE], Tuple[RESULT_TYPE, ...]]:
        # type of resutls is ...
        #     ResultProxy in sqlalcheny < 1.4
        #     CursorResult in sqlalchemy >= 1.4

        if results.returns_rows is False:
            return () if self.sequencial is True else None

        if self.sequencial is False:
            return_value: RESULT_TYPE = self.to_value(results.fetchone())
            results.close()

            return return_value

        return tuple(self.to_value(result) for result in results)

    def to_value(self, result) -> RESULT_TYPE:
        return self.entity_type(**OrderedDict(result))


@description("cache_size")
class ResultTypeBuilder:
    def __init__(self, cache_size: Optional[int] = None):

        def _is_generic_sequencial(
            result_type: Type[Any], meta_param: str
        ) -> bool:

            orign_class: Optional[type] = getattr(
                result_type, meta_param, None)

            if not orign_class:
                return False

            try:
                if issubclass(orign_class, str):
                    return False
                if issubclass(orign_class, Sequence):
                    return True
            except Exception:
                pass

            return False

        def _is_sequencial(result_type: Type[Any]) -> bool:
            if result_type in (list, tuple, List, Tuple):
                return True

            # python_version >= 3.7
            if _is_generic_sequencial(result_type, "__origin__"):
                return True
            # python_version < 3.7
            if _is_generic_sequencial(result_type, "__extra__"):
                return True

            try:
                if issubclass(result_type, str):
                    return False
                if issubclass(result_type, Sequence):
                    return True
            except Exception:
                pass

            return False

        @lru_cache(maxsize=cache_size)
        def _build(result_type: Type[Any]) -> ResultType:
            if _is_sequencial(result_type) is False:
                return ResultType(entity_type=result_type, sequencial=False)

            entity_type: Type[Any] = result_type.__args__[0]
            return ResultType(entity_type=entity_type, sequencial=True)

        self.build: Callable[[Type[Any]], ResultType] = _build
        self.cache_size: Optional[int] = cache_size
