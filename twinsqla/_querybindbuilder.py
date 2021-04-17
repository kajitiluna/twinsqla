from typing import Any, Optional, Union, List, Tuple
from abc import ABCMeta, abstractmethod

import sqlalchemy

from ._support import description
from ._dynamic_parser import DynamicQuery
from ._sqlbuilder import SqlBuilder
from . import exceptions


class PreparedQuery:

    def __init__(self, prepared_sql: Union[str, DynamicQuery],
                 parameters: Union[dict, List[dict]]):

        if (isinstance(parameters, list)
                and isinstance(prepared_sql, DynamicQuery)):
            raise ValueError("Unexpected arguments pair.")

        self.prepared_sql: str = self._init_prepared_sql(
            prepared_sql, parameters)
        self.parameters: Union[dict, List[dict]] = self._init_bind_param(
            prepared_sql, parameters)

    @classmethod
    def _init_prepared_sql(cls, prepared: Union[str, DynamicQuery],
                           parameters: Union[dict, List[dict]]) -> str:

        if isinstance(prepared, str):
            return prepared

        # When prepared object is not instance of string,
        # then parameters object must be instance of dict not list.
        return prepared.query_func(**parameters)

    @classmethod
    def _init_bind_param(cls, prepared: Union[str, DynamicQuery],
                         parameters: Union[dict, List[dict]]
                         ) -> Union[dict, List[dict]]:

        if isinstance(prepared, str):
            return parameters

        # When prepared object is not instance of string,
        # then parameters object must be instance of dict not list.
        dynamic_params: dict = {
            key: param(**parameters)
            for key, param in prepared.pydynamic_params.items()
        }

        return dict(parameters, **dynamic_params)

    def statement(self) -> sqlalchemy.sql.text:
        return sqlalchemy.sql.text(self.prepared_sql)

    def bind_params(self) -> Union[dict, List[dict]]:
        return self.parameters


@description(("query", "sql_path", "table_name", "bind_params",
              "triggered_function", "function_args"))
class QueryContext():

    def __init__(self, *, query: Optional[str], sql_path: Optional[str],
                 table_name: Optional[str], bind_params: dict,
                 triggered_function: callable, function_args: tuple,
                 function_kwargs: dict, condition_columns: Tuple[str, ...]):

        self.query: Optional[str] = query
        self.sql_path: Optional[str] = sql_path
        self.table_name: Optional[str] = table_name
        self.bind_params: dict = bind_params
        self.triggered_function: callable = triggered_function
        self.function_args: tuple = function_args
        self.function_kwargs: dict = function_kwargs
        self.conditions: Tuple[str, ...] = condition_columns

    def init_structure(self, operation: str) -> Tuple[str, List[dict]]:
        entities: List[Any] = self.find_entities()
        table_name: str = self.find_table_name(entities[0], operation)
        bind_parameters: List[dict] = [
            {
                key: value for key, value in vars(entity).items()
                if (value is not None) and (
                    key not in ("__twinsqla_table_name",
                                "__twinsqla_primary_keys",
                                "__twinsqla_auto_keys")
                )
            } for entity in entities
        ]

        return (table_name, bind_parameters)

    def condition_columns(self) -> Tuple[str, ...]:
        if self.conditions:
            return self.conditions

        entities: List[Any] = self.find_entities()
        return getattr(entities[0], "__twinsqla_primary_keys", ())

    def auto_keys(self) -> Tuple[str, ...]:
        entities: List[Any] = self.find_entities()
        return getattr(entities[0], "__twinsqla_auto_keys", ())

    def find_entities(self) -> List[Any]:
        target: Optional[Any] = (
            self.bind_params.get("entities")
            or self.bind_params.get("entity")
            or list(self.bind_params)[0]
        ) if self.bind_params else None

        if target is None:
            raise exceptions.NoSpecifiedEntityException(
                self.triggered_function)

        if isinstance(target, (list, tuple)):
            return target

        return [target]

    def find_table_name(self, entity: Any, operation: str) -> str:
        target_table_name: Optional[str] = self.table_name \
            if self.table_name \
            else getattr(entity, "__twinsqla_table_name", None)

        if target_table_name is None:
            raise exceptions.NotFoundTableNameException(
                entity, operation, "__twinsqla_table_name")

        return target_table_name

    def arg_keys(self) -> Tuple[str]:
        return tuple(self.bind_params.keys())


@description()
class QueryBindBuilder(metaclass=ABCMeta):

    @abstractmethod
    def bind(self, builder: SqlBuilder, context: QueryContext
             ) -> PreparedQuery:
        pass

    def _bind_from_query(self, builder: SqlBuilder, context: QueryContext
                         ) -> Optional[PreparedQuery]:

        prepared_sql: Optional[Union[str, DynamicQuery]] = builder.build(
            query=context.query, sql_path=context.sql_path,
            arg_keys=context.arg_keys())

        return PreparedQuery(prepared_sql, context.bind_params) \
            if prepared_sql is not None else None


@description()
class SelectBindBuilder(QueryBindBuilder):
    def bind(self, builder: SqlBuilder, context: QueryContext
             ) -> PreparedQuery:

        prepared_query: Optional[PreparedQuery] = self._bind_from_query(
            builder, context)
        if prepared_query is None:
            raise exceptions.NoQueryArgumentException()

        return prepared_query


@description()
class InsertBindBuilder(QueryBindBuilder):
    def bind(self, builder: SqlBuilder, context: QueryContext
             ) -> PreparedQuery:

        prepared_query: Optional[PreparedQuery] = self._bind_from_query(
            builder, context)
        if prepared_query is not None:
            return prepared_query

        structure: Tuple[str, List[dict]] = context.init_structure("insert")
        table_name: str = structure[0]
        bind_parameters: List[dict] = structure[1]

        auto_keys: Tuple[str, ...] = context.auto_keys()
        insert_columns: List[str] = [
            key for key in bind_parameters[0].keys() if key not in auto_keys]

        prepared_sql: str = (
            f"INSERT INTO {table_name}"
            f"({', '.join([f'{key}' for key in insert_columns])})"
            f" VALUES "
            f"({', '.join([f':{key}' for key in insert_columns])})"
        )

        return PreparedQuery(prepared_sql, bind_parameters)


@description()
class UpdateBindBuilder(QueryBindBuilder):
    def bind(self, builder: SqlBuilder, context: QueryContext
             ) -> PreparedQuery:

        prepared_query: Optional[PreparedQuery] = self._bind_from_query(
            builder, context)
        if prepared_query is not None:
            return prepared_query

        structure: Tuple[str, List[dict]] = context.init_structure("update")
        table_name: str = structure[0]
        bind_parameters: List[dict] = structure[1]
        condition_columns: Tuple[str, ...] = context.condition_columns()

        updating_columns: List[str] = [
            f'{key} = :{key}' for key in bind_parameters[0].keys()
            if key not in condition_columns
        ]
        filter_conditions: List[str] = [
            f"{column} = :{column}" for column in condition_columns
        ]
        prepared_sql: str = \
            f"UPDATE {table_name} SET {', '.join(updating_columns)}" + (
                f" WHERE {' AND '.join(filter_conditions)}"
                if filter_conditions else ""
            )

        return PreparedQuery(prepared_sql, bind_parameters)


@description()
class DeleteBindBuilder(QueryBindBuilder):
    def bind(self, builder: SqlBuilder, context: QueryContext
             ) -> PreparedQuery:

        prepared_query: Optional[PreparedQuery] = self._bind_from_query(
            builder, context)
        if prepared_query is not None:
            return prepared_query

        structure: Tuple[str, List[dict]] = context.init_structure("delete")
        table_name: str = structure[0]
        bind_parameters: List[dict] = structure[1]

        filter_conditions: List[str] = [
            f"{column} = :{column}" for column in context.condition_columns()
        ]
        # TODO 削除対象のPKをまとめて1クエリで記載する
        prepared_sql: str = \
            f"DELETE FROM {table_name}" + (
                f" WHERE {' AND '.join(filter_conditions)}"
                if filter_conditions else ""
            )

        return PreparedQuery(prepared_sql, bind_parameters)


@description()
class ExecuteBindBuilder(QueryBindBuilder):
    def bind(self, builder: SqlBuilder, context: QueryContext
             ) -> PreparedQuery:

        prepared_query: Optional[PreparedQuery] = self._bind_from_query(
            builder, context)
        if prepared_query is None:
            raise exceptions.NoQueryArgumentException()

        return prepared_query
