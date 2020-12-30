from typing import Callable, Any, List, Optional, Union
from typing import Type, TypeVar, Generic
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import functools
import re
import threading

import sqlalchemy
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session
from sqlalchemy.engine.result import ResultProxy, RowProxy

from ._sqlbuilder import SqlBuilder, SqlStructure
from ._support import _find_instance, _find_entity, _merge_arguments_to_dict
from .exceptions import InvalidTableNameException, NotFoundTableNameException


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

    def insert(self, *, table_name: Optional[str] = None,
               result_type: Type[Any] = None,
               iteratable: bool = False):

        return _do_insert(table_name, result_type, iteratable, sqla=self)

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
            List[result_type], ResultIterator[result_type], None
        ]:

            sqla_obj: TWinSQLA = sqla if sqla \
                else _find_twinsqla(target_func, *args, **kwargs)

            sql_structure: SqlStructure = sqla_obj._sql_builder.build(
                query=target_query, sql_path=sql_path)
            key_values: dict = _merge_arguments_to_dict(
                target_func, *args, **kwargs)

            query: sqlalchemy.sql.text = sql_structure.prepared_query()
            results: ResultProxy = sqla_obj._execute_query(query, **key_values)

            if result_type is None:
                return None

            if iteratable is True:
                return ResultIterator[result_type](results)

            return [result_type(**OrderedDict(result)) for result in results]

        return wrapper

    return _select


_PATTERN_TABLE_NAME = re.compile(r"\A[a-zA-Z_][a-zA-Z0-9_]*\Z")


def Table(name: str):
    matcher: Optional[re.Match] = _PATTERN_TABLE_NAME.fullmatch(name)
    if matcher is None:
        raise InvalidTableNameException(name, _PATTERN_TABLE_NAME)

    def _table(cls):
        cls._table_name = name
        return cls

    return _table


def insert(*, table_name: Optional[str] = None, result_type: Type[Any] = None,
           iteratable: bool = False):

    return _do_insert(table_name, result_type, iteratable)


def _do_insert(table_name: Optional[str], result_type: Type[Any],
               iteratable: bool, sqla: Optional[TWinSQLA] = None):

    def _insert(func: Callable):
        target_func: Callable = func

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Union[
            List[result_type], ResultIterator[result_type], None
        ]:

            sqla_obj: TWinSQLA = sqla if sqla \
                else _find_twinsqla(target_func, *args, **kwargs)

            entity: Optional[Any] = _find_entity(
                target_func, [sqla_obj], *args, **kwargs)
            target_table_name: Optional[str] = table_name if table_name \
                else getattr(entity, "_table_name", None)
            if target_table_name is None:
                raise NotFoundTableNameException(
                    entity, "insert", "_table_name")

            bind_params: dict = {
                key: value for key, value in vars(entity).items()
                if (value is not None) and (key != "_table_name")
            }
            query: sqlalchemy.sql.text = sqlalchemy.sql.text(
                f"INSERT INTO {target_table_name}"
                f"({', '.join([f'{param}' for param in bind_params.keys()])})"
                f" VALUES "
                f"({', '.join([f':{param}' for param in bind_params.keys()])})"
            )
            results: ResultProxy = sqla_obj._execute_query(
                query, **bind_params)

            if result_type is None:
                return None

            if iteratable is True:
                return ResultIterator[result_type](results)

            return [result_type(**OrderedDict(result)) for result in results]

        return wrapper

    return _insert


def _find_twinsqla(func: Callable, *args, **kwargs) -> TWinSQLA:
    return _find_instance(
        TWinSQLA, ["sqla", "twinsqla"], func, *args, **kwargs
    )


RESULT_TYPE = TypeVar("RESULT_TYPE")


@dataclass(frozen=True)
class ResultIterator(Generic[RESULT_TYPE]):

    result_proxy: ResultProxy

    def __iter__(self):
        return self

    def __next__(self) -> RESULT_TYPE:
        next_value: RowProxy = self.result_proxy.next()
        return RESULT_TYPE(**dict(next_value))
