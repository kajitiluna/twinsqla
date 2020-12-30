from typing import Callable, Any, List, Optional, Union
from typing import Type, TypeVar, Generic
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
from inspect import signature
from pathlib import Path
import functools
import threading

import sqlalchemy
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session
from sqlalchemy.engine.result import ResultProxy, RowProxy

from ._sqlbuilder import SqlBuilder, SqlStructure
from .exceptions import NoSpecifiedInstanceException


class TWinSQLA:

    def __init__(self, engine: sqlalchemy.engine.base.Engine, *,
                 sql_file_root: Optional[Union[Path, str]] = None,
                 cache_size: Optional[int] = 128):

        self._engine: Engine = engine
        self._sessionmaker: sessionmaker = sessionmaker(bind=engine)
        self._sql_builder: SqlBuilder = SqlBuilder(
            sql_file_root=sql_file_root, cache_size=cache_size)
        self._locals: threading.local = threading.local()

    @contextmanager
    def transaction(self):
        """
        Start transaction with session.
        When any exceptions are occurred, transaction will be rollback.
        On the other case, transaction will be commited.

        Yields:
            sqlalchemy.orm.session.Session: session object
        """

        yield (self._transaction_first()
               if not getattr(self._locals, 'session', None)
               else self._transaction_nested())

    def _transaction_first(self):
        session: Session = self._sessionmaker()
        self._locals.session = session
        try:
            yield session
            session.commit()
        except Exception as exc:
            session.rollback()
            raise exc
        finally:
            session.close()
            self._locals.session = None

    def _transaction_nested(self):
        session: Session = self._locals.session.begin_nested()
        try:
            yield session
        except Exception as exc:
            session.rollback()
            raise exc

    def select(self, query: Optional[str] = None, *,
               sql_path: Optional[str] = None,
               result_type: Type[Any] = OrderedDict,
               iteratable: bool = False):
        """
        Function decorator of query for sql selecting.
        Either argument 'query' or 'sql_path' must be specified.

        Args:
            query (Optional[str], optional):
                sql query for selecting. Defaults to None.
            sql_path (Optional[str], optional):
                file path with sql. Defaults to None.
            result_type (Type[Any], optional):
                return type. Defaults to OrderedDict.
            iteratable (bool, optional):
                When you want to iterating result, then True specified.
                Defaults to False.

        Returns:
            Callable: Function decorator
        """

        return _do_select(query, sql_path, result_type, iteratable, sqla=self)

    def _execute_query(
        self, query: sqlalchemy.sql.text, **key_values
    ) -> ResultProxy:

        return self._locals.session.execute(query, key_values) \
            if getattr(self._locals, 'session', None) \
            else self._engine.execute(query, **key_values)


def select(query: Optional[str] = None, *, sql_path: Optional[str] = None,
           result_type: Type[Any] = OrderedDict, iteratable: bool = False):

    return _do_select(query, sql_path, result_type, iteratable)


def _do_select(
    query: Optional[str], sql_path: Optional[str], result_type: Type[Any],
    iteratable: bool, sqla: Optional[TWinSQLA] = None
):

    target_query: Optional[str] = query

    def _select(func: Callable):
        target_func: Callable = func

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Union[
            List[result_type], ResultIterator[result_type]
        ]:

            sqla_obj: TWinSQLA = sqla if sqla \
                else _find_instance(target_func, *args, **kwargs)

            sql_structure: SqlStructure = sqla_obj._sql_builder.build(
                query=target_query, sql_path=sql_path)
            key_values: dict = _merge_arguments_to_dict(
                target_func, *args, **kwargs)

            query: sqlalchemy.sql.text = sql_structure.prepared_query()
            results: ResultProxy = sqla_obj._execute_query(query, **key_values)

            if iteratable is True:
                return ResultIterator[result_type](results)

            return [result_type(**dict(result)) for result in results]

        return wrapper

    return _select


def _find_instance(func: Callable, *args, **kwargs) -> TWinSQLA:
    own_obj = getattr(func, "__self__", None) or (
        args[0] if signature(func).parameters.get("self") and len(args) > 0
        else None
    )

    if own_obj:
        twinsqla_obj: Optional[TWinSQLA] = (
            _find_instance_specified(own_obj, "sqla")
            or _find_instance_specified(own_obj, "twinsqla")
        )
        if twinsqla_obj:
            return twinsqla_obj

        for param in vars(own_obj).values():
            if isinstance(param, TWinSQLA):
                return param

    result: Optional[TWinSQLA] = (
        _find_instance_fullscan(args)
        or _find_instance_fullscan(kwargs.values())
    )
    if result:
        return result

    raise NoSpecifiedInstanceException(func)


def _find_instance_specified(
    target_obj: Any, param_name
) -> Optional[TWinSQLA]:

    target = getattr(target_obj, param_name, None)
    return target if target and isinstance(target, TWinSQLA) else None


def _find_instance_fullscan(values) -> Optional[TWinSQLA]:
    if not values:
        return None
    for value in values:
        if isinstance(value, TWinSQLA):
            return value
    return None


def _merge_arguments_to_dict(func: Callable, *args, **kwargs) -> dict:
    if not args:
        return kwargs

    key_values: dict = kwargs
    func_signature: signature = signature(func)

    positional_args_dict: dict = {
        name: value for name, value in zip(
            func_signature.parameters.keys(), args
        ) if name != "self"
    }
    key_values.update(positional_args_dict)
    return key_values


RESULT_TYPE = TypeVar("RESULT_TYPE")


@dataclass(frozen=True)
class ResultIterator(Generic[RESULT_TYPE]):

    result_proxy: ResultProxy

    def __iter__(self):
        return self

    def __next__(self) -> RESULT_TYPE:
        next_value: RowProxy = self.result_proxy.next()
        return RESULT_TYPE(**dict(next_value))
