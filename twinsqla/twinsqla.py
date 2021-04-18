import logging
from typing import Callable, Any, List, Tuple, NamedTuple, Optional, Union
from typing import Type, TypeVar, Generic
from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path
from enum import Enum
import functools
import re
import threading

import sqlalchemy
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session

from ._sqlbuilder import SqlBuilder
from ._querybindbuilder import (
    QueryBindBuilder, SelectBindBuilder, ExecuteBindBuilder,
    InsertBindBuilder, UpdateBindBuilder, DeleteBindBuilder,
    QueryContext, PreparedQuery
)
from ._resultbuilder import ResultTypeBuilder, ResultType
from ._support import description, _find_instance, _merge_arguments_to_dict
from . import exceptions


@description(
    (("engine", "_engine"), ("sql_builder", "_sql_builder"),
     ("type_builder", "_type_builder"))
)
class TWinSQLA:
    """
    TWinSQLA is a light framework for mapping SQL statements to python
    functions or methods.
    TWinSQLA instance handles SQL statements and transactions.

    Args:
        engine (sqlalchemy.engine.base.Engine): SQLAlchemy engine instance.
        available_dynamic_query (bool, optional):
            If True, then two-ways SQL is available.
            If False, sql statements are not converted in executing
            but executed as it is specified. Defaults to True.
        sql_file_root (Optional[Union[Path, str]], optional):
            Specify the root directory of sql files. Defaults to None.
        cache_size (Optional[int], optional):
            Cache size of loaded query function. Defaults to 128.
    """

    def __init__(self, engine: sqlalchemy.engine.base.Engine, *,
                 available_dynamic_query: bool = True,
                 sql_file_root: Optional[Union[Path, str]] = None,
                 cache_size: Optional[int] = 128):

        self._engine: Engine = engine
        self._sessionmaker: sessionmaker = sessionmaker(bind=engine)
        self._sql_builder: SqlBuilder = SqlBuilder(
            available_dynamic_query=available_dynamic_query,
            sql_file_root=sql_file_root, cache_size=cache_size)
        self._type_builder: ResultTypeBuilder = ResultTypeBuilder(cache_size)
        self._locals: threading.local = threading.local()
        self._logger = logging.getLogger(__name__)

    @contextmanager
    def transaction(self):
        """
        Start transaction with session.
        When any exceptions are occurred, transaction will be rollback.
        On the other case, transaction will be commited.

        Yields:
            sqlalchemy.orm.session.Session: session object
        """

        return (self._transaction_first()
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
               result_type: Type[Any] = Tuple[OrderedDict, ...],
               iteratable: bool = False):
        """
        Function decorator of select operation.
        Only one argument `query` or `sql_path` must be specified.

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
                return type. Defaults to Tuple[OrderedDict, ...].
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
        one of the arguments `query` or `sql_path`.

        In neither `query` nor `sql_path` are specified, this decorator creates
        insert query with arguments of decorated method.
        In this case, you need to specify inserted table name by decorator
        argument 'table_name' or decorating '@twinsqla.table' to entity class.

        Args:
            query (Optional[str], optional):
                insert query (available TwoWay SQL). Defaults to None.
            sql_path (Optional[str], optional):
                file path with sql (available TwoWay SQL). Defaults to None.
            table_name (Optional[str], optional):
                table name for inserting. Defaults to None.
            result_type (Type[Any], optional):
                When constructing "INSERT RETURNING" query, it is useful to
                specify return type. Defaults to None.
            iteratable (bool, optional):
                In almost cases, this argument need not to specified.
                The only useful case is in using "INSERT RETURNING" query.
                Defaults to False.

        Returns:
            Callable: Function decorator for insert query
        """

        return _do_insert(query, sql_path, table_name, result_type, iteratable,
                          sqla=self)

    def update(self, query: Optional[str] = None, *,
               sql_path: Optional[str] = None,
               table_name: Optional[str] = None,
               condition_columns: Optional[Union[str, Tuple[str, ...]]] = None,
               result_type: Type[Any] = None, iteratable: bool = False):
        """
        Function decorator of update operation.
        In constructing update query by yourself, you need to specify either
        one of the arguments `query` or `sql_path`.

        In neither `query` nor `sql_path` are specified, this decorator creates
        update query with arguments of decorated method.
        In this case, you need follows.
            1. To specify updated table name
                by decorating '@twinsqla.table' to entity class.
                or by decorator argument 'table_name'
            2. To specifry the column names for using WHERE conditions
                by decorating '@twinsqla.table' with `pk` parameter
                or by decorator argument 'condition_columns'.

        Args:
            query (Optional[str], optional):
                update query (available TwoWay SQL). Defaults to None.
            sql_path (Optional[str], optional):
                file path with sql (available TwoWay SQL). Defaults to None.
            table_name (Optional[str], optional):
                table name for updating. Defaults to None.
            condition_columns (
                Optional[Union[str, Tuple[str, ...]]], optional
            ):
                column names in WHERE condition. In almost cases, you are
                recommended to specify primary key names of the table.
                Defaults to None.
            result_type (Type[Any], optional):
                When constructing "UPDATE RETURNING" query, it is useful to
                specify return type. Defaults to None.
            iteratable (bool, optional):
                In almost cases, this argument need not to specified.
                The only useful case is in using "UPDATE RETURNING" query.
                Defaults to False.

        Returns:
            Callable: Function decorator for update query
        """

        return _do_update(query, sql_path, table_name, condition_columns,
                          result_type, iteratable, sqla=self)

    def delete(self, query: Optional[str] = None, *,
               sql_path: Optional[str] = None,
               table_name: Optional[str] = None,
               condition_columns: Optional[Union[str, Tuple[str, ...]]] = None,
               result_type: Type[Any] = None, iteratable: bool = False):
        """
        Function decorator of delete operation.
        In constructing delete query by yourself, you need to specify either
        one of the arguments `query` or `sql_path`.

        In neither `query` nor `sql_path` are specified, this decorator creates
        delete query with arguments of decorated method.
        In this case, you need follows.
            1. To specify updated table name
                by decorating '@twinsqla.table' to entity class.
                or by decorator argument 'table_name'
            2. To specifry the column names for using WHERE conditions
                by decorating '@twinsqla.table' with `pk` parameter
                or by decorator argument 'condition_columns'.

        Args:
            query (Optional[str], optional):
                delete query (available TwoWay SQL). Defaults to None.
            sql_path (Optional[str], optional):
                file path with sql (available TwoWay SQL). Defaults to None.
            table_name (Optional[str], optional):
                table name for deleting. Defaults to None.
            condition_columns (
                Optional[Union[str, Tuple[str, ...]]], optional
            ):
                column names in WHERE condition. In almost cases, you are
                recommended to specify primary key names of the table.
                Defaults to ().
            result_type (Type[Any], optional):
                When constructing "DELETE RETURNING" query, it is useful to
                specify return type. Defaults to None.
            iteratable (bool, optional):
                In almost cases, this argument need not to specified.
                The only useful case is in using "DELETE RETURNING" query.
                Defaults to False.

        Returns:
            Callable: Function decorator for delete query
        """

        return _do_delete(query, sql_path, table_name, condition_columns,
                          result_type, iteratable, sqla=self)

    def execute(self, query: Optional[str] = None, *,
                sql_path: Optional[str] = None,
                result_type: Type[Any] = Tuple[OrderedDict, ...],
                iteratable: bool = False):
        """
        Function decorator of any operation.
        Only one argument `query` or `sql_path` must be specified.

        In called decorated method, the processing implemented by the method
        is not executed, but arguments of method are used for bind parameters.

        Args:
            query (Optional[str], optional):
                any query (available TwoWay SQL). Defaults to None.
            sql_path (Optional[str], optional):
                file path with sql (available TwoWay SQL). Defaults to None.
            result_type (Type[Any], optional):
                return type. Defaults to Tuple[OrderedDict, ...].
            iteratable (bool, optional):
                When you want to fetching iterataly result,
                then True specified and returned ResultIterator object.
                Defaults to False.

        Returns:
            Callable: Function decorator for select query
        """

        return _do_execute(query, sql_path, result_type, iteratable, sqla=self)

    def _execute_query(self, prepared: PreparedQuery) -> any:
        query: sqlalchemy.sql.text = prepared.statement()
        bind_params: Union[dict, List[dict]] = prepared.bind_params()

        self._logger.info(f"Execute query : {query.text}")

        session = getattr(self._locals, 'session', None)
        return session.execute(query, bind_params) if session \
            else self._engine.execute(query, bind_params)


_PATTERN_TABLE_NAME = re.compile(r"\A[a-zA-Z_][a-zA-Z0-9_]*\Z")


class autopk(NamedTuple):
    """
    Column name for specifying auto-generating column.

    Attributes:
        column (str): column name of auto-generating
    """

    column: str


def table(name: str, *,
          pk: Union[Union[str, autopk], Tuple[Union[str, autopk], ...]] = ()
          ):
    """
    Class decorator to specify table name and primary keys.
    It is useful in the case using `@insert`, `@update` or `@delete` without
    your query. By decorating `@table` to entity class,
    those function decorators can specify the table name and primary keys
    in constructing queries.

    Args:
        name (str): table name
        pk (Union[Union[str, autopk], Tuple[Union[str, autopk], ...]]):
            column names of primary keys

    Raises:
        exceptions.InvalidTableNameException:
            if `name` contained invalid charactors for table name.

    Returns:
        Callable: class decorator
    """

    matcher: Optional[re.Match] = _PATTERN_TABLE_NAME.fullmatch(name)
    if matcher is None:
        raise exceptions.InvalidTableNameException(name, _PATTERN_TABLE_NAME)

    primary_keys: Tuple[str, ...] = (pk, ) if isinstance(pk, str) else (
        (pk.column, ) if isinstance(pk, autopk) else tuple(
            [target.column if isinstance(
                target, autopk) else target for target in pk]
        )
    )
    auto_keys: Tuple[str, ...] = () if isinstance(pk, str) else (
        (pk.column, ) if isinstance(pk, autopk) else tuple(
            [target.column for target in pk if isinstance(target, autopk)]
        )
    )

    def _table(cls):
        setattr(cls, "__twinsqla_table_name", name)
        setattr(cls, "__twinsqla_primary_keys", primary_keys)
        setattr(cls, "__twinsqla_auto_keys", auto_keys)
        return cls

    return _table


def select(query: Optional[str] = None, *, sql_path: Optional[str] = None,
           result_type: Type[Any] = Tuple[OrderedDict, ...],
           iteratable: bool = False):
    """
    Function decorator of select operation.
    Only one argument `query` or `sql_path` must be specified.

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
            return type. Defaults to Tuple[OrderedDict, ...].
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
        sqla=sqla, query=query, sql_path=sql_path,
        result_type=result_type, iteratable=iteratable
    )


def insert(query: Optional[str] = None, *, sql_path: Optional[str] = None,
           table_name: Optional[str] = None, result_type: Type[Any] = None,
           iteratable: bool = False):
    """
    Function decorator of insert operation.
    In constructing insert query by yourself, you need to specify either
    one of the arguments `query` or `sql_path`.

    In neither `query` nor `sql_path` are specified, this decorator creates
    insert query with arguments of decorated method.
    In this case, you need to specify inserted table name by decorator
    argument 'table_name' or decorating '@twinsqla.table' to entity class.

    Args:
        query (Optional[str], optional):
            insert query (available TwoWay SQL). Defaults to None.
        sql_path (Optional[str], optional):
            file path with sql (available TwoWay SQL). Defaults to None.
        table_name (Optional[str], optional):
            table name for inserting. Defaults to None.
        result_type (Type[Any], optional):
            When constructing "INSERT RETURNING" query, it is useful to
            specify return type. Defaults to None.
        iteratable (bool, optional):
            In almost cases, this argument need not to specified.
            The only useful case is in using "INSERT RETURNING" query.
            Defaults to False.

    Returns:
        Callable: Function decorator for insert query
    """

    return _do_insert(query, sql_path, table_name, result_type, iteratable)


def _do_insert(query: Optional[str], sql_path: Optional[str],
               table_name: Optional[str], result_type: Type[Any],
               iteratable: bool, sqla: Optional[TWinSQLA] = None):

    return QueryType.INSERT.query_decorator(
        sqla=sqla, query=query, sql_path=sql_path, table_name=table_name,
        result_type=result_type, iteratable=iteratable
    )


def update(query: Optional[str] = None, *, sql_path: Optional[str] = None,
           table_name: Optional[str] = None,
           condition_columns: Optional[Union[str, Tuple[str, ...]]] = None,
           result_type: Type[Any] = None, iteratable: bool = False):
    """
    Function decorator of update operation.
    In constructing update query by yourself, you need to specify either
    one of the arguments `query` or `sql_path`.

    In neither `query` nor `sql_path` are specified, this decorator creates
    update query with arguments of decorated method.
    In this case, you need follows.
        1. To specify updated table name
            by decorating '@twinsqla.table' to entity class.
            or by decorator argument 'table_name'
        2. To specifry the column names for using WHERE conditions
            by decorating '@twinsqla.table' with `pk` parameter
            or by decorator argument 'condition_columns'.

    Args:
        query (Optional[str], optional):
            update query (available TwoWay SQL). Defaults to None.
        sql_path (Optional[str], optional):
            file path with sql (available TwoWay SQL). Defaults to None.
        table_name (Optional[str], optional):
            table name for updating. Defaults to None.
        condition_columns (Optional[Union[str, Tuple[str, ...]]], optional):
            column names in WHERE condition. In almost cases, you are
            recommended to specify primary key names of the table.
            Defaults to None.
        result_type (Type[Any], optional):
            When constructing "UPDATE RETURNING" query, it is useful to
            specify return type. Defaults to None.
        iteratable (bool, optional):
            In almost cases, this argument need not to specified.
            The only useful case is in using "UPDATE RETURNING" query.
            Defaults to False.

    Returns:
        Callable: Function decorator for update query
    """

    return _do_update(query, sql_path, table_name, condition_columns,
                      result_type, iteratable)


def _do_update(query: Optional[str], sql_path: Optional[str],
               table_name: Optional[str],
               condition_columns: Optional[Union[str, Tuple[str, ...]]],
               result_type: Type[Any], iteratable: bool,
               sqla: Optional[TWinSQLA] = None):

    target_condition_columns: Tuple[str, ...] = _to_tuple(condition_columns)

    return QueryType.UPDATE.query_decorator(
        sqla=sqla, query=query, sql_path=sql_path,
        table_name=table_name, condition_columns=target_condition_columns,
        result_type=result_type, iteratable=iteratable
    )


def delete(query: Optional[str] = None, *, sql_path: Optional[str] = None,
           table_name: Optional[str] = None,
           condition_columns: Optional[Union[str, Tuple[str, ...]]] = None,
           result_type: Type[Any] = None, iteratable: bool = False):
    """
    Function decorator of delete operation.
    In constructing delete query by yourself, you need to specify either
    one of the arguments `query` or `sql_path`.

    In neither `query` nor `sql_path` are specified, this decorator creates
    delete query with arguments of decorated method.
    In this case, you need follows.
        1. To specify updated table name
            by decorating '@twinsqla.table' to entity class.
            or by decorator argument 'table_name'
        2. To specifry the column names for using WHERE conditions
            by decorating '@twinsqla.table' with `pk` parameter
            or by decorator argument 'condition_columns'.

    Args:
        query (Optional[str], optional):
            delete query (available TwoWay SQL). Defaults to None.
        sql_path (Optional[str], optional):
            file path with sql (available TwoWay SQL). Defaults to None.
        table_name (Optional[str], optional):
            table name for deleting. Defaults to None.
        condition_columns (Optional[Union[str, Tuple[str, ...]]], optional):
            column names in WHERE condition. In almost cases, you are
            recommended to specify primary key names of the table.
            Defaults to None.
        result_type (Type[Any], optional):
            When constructing "DELETE RETURNING" query, it is useful to
            specify return type. Defaults to None.
        iteratable (bool, optional):
            In almost cases, this argument need not to specified.
            The only useful case is in using "DELETE RETURNING" query.
            Defaults to False.

    Returns:
        Callable: Function decorator for delete query
    """

    return _do_delete(query, sql_path, table_name, condition_columns,
                      result_type, iteratable)


def _do_delete(query: Optional[str], sql_path: Optional[str],
               table_name: Optional[str],
               condition_columns: Union[str, Tuple[str, ...]],
               result_type: Type[Any], iteratable: bool,
               sqla: Optional[TWinSQLA] = None):

    target_condition_columns: Tuple[str, ...] = _to_tuple(condition_columns)

    return QueryType.DELETE.query_decorator(
        sqla=sqla, query=query, sql_path=sql_path,
        table_name=table_name, condition_columns=target_condition_columns,
        result_type=result_type, iteratable=iteratable
    )


def execute(query: Optional[str] = None, *, sql_path: Optional[str] = None,
            result_type: Type[Any] = Tuple[OrderedDict, ...],
            iteratable: bool = False):
    """
    Function decorator of any operation.
    Only one argument `query` or `sql_path` must be specified.

    In called decorated method, the processing implemented by the method
    is not executed, but arguments of method are used for bind parameters.

    Args:
        query (Optional[str], optional):
            any query (available TwoWay SQL). Defaults to None.
        sql_path (Optional[str], optional):
            file path with sql (available TwoWay SQL). Defaults to None.
        result_type (Type[Any], optional):
            return type. Defaults to Tuple[OrderedDict, ...].
        iteratable (bool, optional):
            When you want to fetching iterataly result, then True specified
            and returned ResultIterator object. Defaults to False.

    Returns:
        Callable: Function decorator
    """

    return _do_execute(query, sql_path, result_type, iteratable)


def _do_execute(query: Optional[str], sql_path: Optional[str],
                result_type: Type[Any], iteratable: bool,
                sqla: Optional[TWinSQLA] = None):

    return QueryType.EXECUTE.query_decorator(
        sqla=sqla, query=query, sql_path=sql_path,
        result_type=result_type, iteratable=iteratable
    )


def _to_tuple(
    condition_columns: Optional[Union[str, Tuple[str, ...]]]
) -> Tuple[str, ...]:

    return () if not condition_columns else (
        (condition_columns, ) if isinstance(
            condition_columns, str) else condition_columns
    )


@description("bind_builder")
class QueryExecutor():
    def __init__(self, binder: QueryBindBuilder):
        self.bind_builder: QueryBindBuilder = binder

    def query_decorator(self, sqla: Optional[TWinSQLA] = None,
                        query: Optional[str] = None,
                        sql_path: Optional[str] = None,
                        table_name: Optional[str] = None,
                        condition_columns: Tuple[str, ...] = (),
                        result_type: Type[Any] = None,
                        iteratable: bool = False):

        def _execute(func: Callable):

            @functools.wraps(func)
            def wrapper(*args, **kwargs) -> Union[
                Optional[Any], Tuple[Any], ResultIterator[Any]
            ]:

                sqla_obj: TWinSQLA = sqla if sqla \
                    else _find_twinsqla(func, args, kwargs)
                bind_params: dict = _merge_arguments_to_dict(
                    func, args, kwargs, [sqla_obj])

                context: QueryContext = QueryContext(
                    query=query, sql_path=sql_path, table_name=table_name,
                    condition_columns=condition_columns,
                    bind_params=bind_params, triggered_function=func,
                    function_args=args, function_kwargs=kwargs
                )
                prepared: PreparedQuery = self.bind_builder.bind(
                    builder=sqla_obj._sql_builder, context=context
                )

                results = sqla_obj._execute_query(prepared)

                if result_type is None:
                    return None
                return_type: ResultType[Any] = \
                    sqla_obj._type_builder.build(result_type)

                return return_type.to_values(results) if iteratable is False \
                    else ResultIterator[Any](results, return_type)

            return wrapper

        return _execute


def _find_twinsqla(func: Callable, args: tuple, kwargs: dict) -> TWinSQLA:
    return _find_instance(
        TWinSQLA, ["sqla", "twinsqla"], func, args, kwargs
    )


class QueryType(Enum):
    SELECT = QueryExecutor(SelectBindBuilder())
    INSERT = QueryExecutor(InsertBindBuilder())
    UPDATE = QueryExecutor(UpdateBindBuilder())
    DELETE = QueryExecutor(DeleteBindBuilder())
    EXECUTE = QueryExecutor(ExecuteBindBuilder())

    def query_decorator(self, *args, **kwargs):
        return self.value.query_decorator(*args, **kwargs)


RESULT_TYPE = TypeVar("RESULT_TYPE")


@description("result_proxy")
class ResultIterator(Generic[RESULT_TYPE]):
    """
    Iterator of query result.
    This object has `result` attribute,
    which is `sqlalchemy.engine.Result` object.
    (In sqlalchemy < 1.4, this is
    `sqlalchemy.engine.result.ResultProxy` object.)
    You can use this attribute if necessary.

    This object's iteration is equivalent to `iter(result)` iteration.
    If you stop iteration before exhausting all rows,
    you need to call `close()` method.

    Args:
        Generic (result_type): type of each object
    """

    def __init__(self, result, result_type: ResultType):
        # type of resutls is ...
        #     ResultProxy in sqlalcheny < 1.4
        #     CursorResult in sqlalchemy >= 1.4
        self.result = result
        self._result_iter = iter(result)
        self._result_type: ResultType = result_type

    def __iter__(self):
        return self

    def __next__(self) -> RESULT_TYPE:
        next_value = next(self._result_iter)
        return self._result_type.to_value(next_value)

    def close(self) -> None:
        self.result.close()
