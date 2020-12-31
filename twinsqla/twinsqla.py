from typing import Callable, Any, List, Optional, Union
from typing import Type, TypeVar, Generic
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from enum import Enum
import functools
import re
import threading

import sqlalchemy
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session
from sqlalchemy.engine.result import ResultProxy, RowProxy

from ._sqlbuilder import SqlBuilder
from ._querybindbuilder import (
    QueryBindBuilder, SelectBindBuilder, InsertBindBuilder, SqlBinder
)
from ._support import _find_instance, _merge_arguments_to_dict
from . import exceptions


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
        Function decorator of select operation.
        Only one argument 'query' or 'sql_path' must be specified.

        In called decorated method, the processing implemented by the method
        is not executed, but arguments of method are used for bind parameters.

        For example:
            - Implementation
            @twinsqla_obj.select(
                "SELECT * FROM staff WHERE staff_id >= /* :more_than_id */10",
                result_type=Staff
            )
            def filter_staff(more_than_id: int) -> List[Staff]:
                pass

            - In executing
            staff: List[Staff] = filter_staff(73)
        staff object contains the result of
         "SELECT * FROM staff WHERE staff_id >= 73"

        Args:
            query (Optional[str], optional):
                select query (available TwoWay SQL). Defaults to None.
            sql_path (Optional[str], optional):
                file path with sql (available TwoWay SQL). Defaults to None.
            result_type (Type[Any], optional):
                return type. Defaults to OrderedDict.
            iteratable (bool, optional):
                When you want to fetching iterataly result,
                then True specified and returned ResultIterator object.
                Defaults to False.

        Returns:
            Callable: Function decorator for select query
        """

        return _do_select(query, sql_path, result_type, iteratable, sqla=self)

    def insert(self, query: Optional[str] = None, *,
               sql_path: Optional[str] = None,
               table_name: Optional[str] = None,
               result_type: Type[Any] = None,
               iteratable: bool = False):
        """
        Function decorator of insert operation.
        In constructing insert query by yourself, you need to specify either
        one of the arguments 'query' or 'sql_path'.

        In neither 'query' nor 'sql_path' are specified, this decorator creates
        insert query with arguments of decorated method.
        In this case, you need to specify inserted table name by decorator
        argument 'table_name' or decorating '@twinsqla.Table' to entity class.

        Args:
            query (Optional[str], optional):
                insert query (available TwoWay SQL). Defaults to None.
            sql_path (Optional[str], optional):
                file path with sql (available TwoWay SQL). Defaults to None.
            table_name (Optional[str], optional):
                table name for inserting. Defaults to None.
            result_type (Type[Any], optional):
                When constructing "INSERT RETURN" query, it is useful to
                specify return type. Defaults to None.
            iteratable (bool, optional):
                In almost cases, this argument need not to specified.
                The only useful case is in using "INSERT RETURN" query.
                Defaults to False.

        Returns:
            Callable: Function decorator for insert query
        """

        return _do_insert(query, sql_path, table_name, result_type, iteratable,
                          sqla=self)

    def _execute_query(self, sql_binder: SqlBinder) -> ResultProxy:
        query: sqlalchemy.sql.text = sql_binder.prepared_query()
        bind_params: dict = sql_binder.bind_params()

        return self._locals.session.execute(query, bind_params) \
            if getattr(self._locals, 'session', None) \
            else self._engine.execute(query, **bind_params)


_PATTERN_TABLE_NAME = re.compile(r"\A[a-zA-Z_][a-zA-Z0-9_]*\Z")


def Table(name: str):
    matcher: Optional[re.Match] = _PATTERN_TABLE_NAME.fullmatch(name)
    if matcher is None:
        raise exceptions.InvalidTableNameException(name, _PATTERN_TABLE_NAME)

    def _table(cls):
        cls._table_name = name
        return cls

    return _table


def select(query: Optional[str] = None, *, sql_path: Optional[str] = None,
           result_type: Type[Any] = OrderedDict, iteratable: bool = False):
    """
    Function decorator of select operation.
    Only one argument 'query' or 'sql_path' must be specified.

    In called decorated method, the processing implemented by the method
    is not executed, but arguments of method are used for bind parameters.

    For example:
        - Implementation
        @twinsqla.select(
            "SELECT * FROM staff WHERE staff_id >= /* :more_than_id */10",
            result_type=Staff
        )
        def filter_staff(self, more_than_id: int) -> List[Staff]:
            pass

        - In executing
        staff: List[Staff] = filter_staff(73)
    staff object contains the result of
        "SELECT * FROM staff WHERE staff_id >= 73"

    Args:
        query (Optional[str], optional):
            select query (available TwoWay SQL). Defaults to None.
        sql_path (Optional[str], optional):
            file path with sql (available TwoWay SQL). Defaults to None.
        result_type (Type[Any], optional):
            return type. Defaults to OrderedDict.
        iteratable (bool, optional):
            When you want to fetching iterataly result, then True specified
            and returned ResultIterator object. Defaults to False.

    Returns:
        Callable: Function decorator
    """

    return _do_select(query, sql_path, result_type, iteratable)


def _do_select(query: Optional[str], sql_path: Optional[str],
               result_type: Type[Any], iteratable: bool,
               sqla: Optional[TWinSQLA] = None):

    return QueryType.SELECT.query_decorator(
        sqla=sqla,
        query=query, sql_path=sql_path,
        result_type=result_type,
        iteratable=iteratable
    )


def insert(query: Optional[str] = None, *, sql_path: Optional[str] = None,
           table_name: Optional[str] = None, result_type: Type[Any] = None,
           iteratable: bool = False):
    """
    Function decorator of insert operation.
    In constructing insert query by yourself, you need to specify either
    one of the arguments 'query' or 'sql_path'.

    In neither 'query' nor 'sql_path' are specified, this decorator creates
    insert query with arguments of decorated method.
    In this case, you need to specify inserted table name by decorator
    argument 'table_name' or decorating '@twinsqla.Table' to entity class.

    Args:
        query (Optional[str], optional):
            insert query (available TwoWay SQL). Defaults to None.
        sql_path (Optional[str], optional):
            file path with sql (available TwoWay SQL). Defaults to None.
        table_name (Optional[str], optional):
            table name for inserting. Defaults to None.
        result_type (Type[Any], optional):
            When constructing "INSERT RETURN" query, it is useful to
            specify return type. Defaults to None.
        iteratable (bool, optional):
            In almost cases, this argument need not to specified.
            The only useful case is in using "INSERT RETURN" query.
            Defaults to False.

    Returns:
        Callable: Function decorator for insert query
    """

    return _do_insert(query, sql_path, table_name, result_type, iteratable)


def _do_insert(query: Optional[str], sql_path: Optional[str],
               table_name: Optional[str], result_type: Type[Any],
               iteratable: bool, sqla: Optional[TWinSQLA] = None):

    return QueryType.INSERT.query_decorator(
        sqla=sqla,
        query=query, sql_path=sql_path, table_name=table_name,
        result_type=result_type, iteratable=iteratable
    )


class QueryExecutor():
    def __init__(self, binder: QueryBindBuilder):
        self.bind_builder = binder

    def query_decorator(self, sqla: Optional[TWinSQLA] = None,
                        query: Optional[str] = None,
                        sql_path: Optional[str] = None,
                        table_name: Optional[str] = None,
                        result_type: Type[Any] = None,
                        iteratable: bool = False):

        def _execute(func: Callable):

            @functools.wraps(func)
            def wrapper(*args, **kwargs) -> Union[
                List[result_type], ResultIterator[result_type], None
            ]:

                sqla_obj: TWinSQLA = sqla if sqla \
                    else _find_twinsqla(func, args, kwargs)
                bind_params: dict = _merge_arguments_to_dict(
                    func, args, kwargs, [sqla_obj])
                sql_binder: SqlBinder = self.bind_builder.bind(
                    sqla_obj._sql_builder, query, sql_path, table_name,
                    bind_params
                )

                results: ResultProxy = sqla_obj._execute_query(sql_binder)

                if result_type is None:
                    return None
                if iteratable is True:
                    return ResultIterator[result_type](results)
                return [result_type(**OrderedDict(result))
                        for result in results]

            return wrapper

        return _execute


def _find_twinsqla(func: Callable, args: tuple, kwargs: dict) -> TWinSQLA:
    return _find_instance(
        TWinSQLA, ["sqla", "twinsqla"], func, args, kwargs
    )


class QueryType(Enum):
    SELECT = QueryExecutor(SelectBindBuilder())
    INSERT = QueryExecutor(InsertBindBuilder())

    def query_decorator(self, *args, **kwargs):
        return self.value.query_decorator(*args, **kwargs)


RESULT_TYPE = TypeVar("RESULT_TYPE")


@dataclass(frozen=True)
class ResultIterator(Generic[RESULT_TYPE]):

    result_proxy: ResultProxy

    def __iter__(self):
        return self

    def __next__(self) -> RESULT_TYPE:
        next_value: RowProxy = self.result_proxy.next()
        return RESULT_TYPE(**dict(next_value))
