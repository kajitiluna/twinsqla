from typing import Callable, Type, TypeVar, Generic
from typing import Any, Tuple, Optional, Union
from collections import OrderedDict
from functools import lru_cache

from sqlalchemy.engine.result import ResultProxy, RowProxy

from ._support import description


RESULT_TYPE = TypeVar("RESULT_TYPE")


@description("entity_type")
class ResultType(Generic[RESULT_TYPE]):

    def __init__(self, entity_type: Type[RESULT_TYPE], sequencial: bool):
        self.entity_type: Type[RESULT_TYPE] = entity_type
        self.sequencial: bool = sequencial

    def to_values(self, results: ResultProxy) -> Union[
            Optional[RESULT_TYPE], Tuple[RESULT_TYPE]]:

        if results.returns_rows is False:
            return () if self.sequencial is True else None

        if self.sequencial is False:
            result: RowProxy = results.fetchone()
            return self.to_value(result)

        return tuple(self.to_value(result) for result in results)

    def to_value(self, result: RowProxy) -> RESULT_TYPE:
        return self.entity_type(**OrderedDict(result))


@description("cache_size")
class ResultTypeBuilder:
    def __init__(self, cache_size: Optional[int] = None):

        @lru_cache(maxsize=cache_size)
        def _build(result_type: Type[Any]) -> ResultType:
            full_type: str = str(result_type)

            if (full_type.startswith("typing.Tuple") is False) \
                    and (full_type.startswith("typing.List") is False):
                return ResultType(entity_type=result_type, sequencial=False)

            entity_type: Type[Any] = result_type.__args__[0]
            return ResultType(entity_type=entity_type, sequencial=True)

        self.build: Callable[[Type[Any]], ResultType] = _build
        self.cache_size: Optional[int] = cache_size
