from typing import Any, Optional, Union, List, Tuple
from dataclasses import dataclass
from abc import ABCMeta, abstractmethod

import sqlalchemy

from ._support import description
from ._sqlbuilder import SqlBuilder
from . import exceptions


class PreparedQuery:
    def __init__(self, prepared_sql: str, parameters: Union[dict, List[dict]]):
        self.prepared_sql: str = prepared_sql
        self.parameters: dict = parameters

    def statement(self) -> sqlalchemy.sql.text:
        return sqlalchemy.sql.text(self.prepared_sql)

    def bind_params(self) -> Union[dict, List[dict]]:
        return self.parameters.copy()


@dataclass(frozen=True)
class QueryContext():
    query: Optional[str]
    sql_path: Optional[str]
    table_name: Optional[str]
    bind_params: dict
    condition_columns: Tuple[str, ...]

    triggered_function: callable
    function_args: tuple
    function_kwargs: dict

    def init_structure(self, operation: str) -> Tuple[str, List[dict]]:
        entities: List[Any] = self.find_entities()
        table_name: str = self.find_table_name(entities[0], operation)
        bind_parameters: List[dict] = [
            {
                key: value for key, value in vars(entity).items()
                if (value is not None) and (key != "_table_name")
            } for entity in entities
        ]

        return (table_name, bind_parameters)

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
            else getattr(entity, "_table_name", None)

        if target_table_name is None:
            raise exceptions.NotFoundTableNameException(
                entity, operation, "_table_name")

        return target_table_name


@description()
class QueryBindBuilder(metaclass=ABCMeta):
    @abstractmethod
    def bind(self, builder: SqlBuilder, context: QueryContext
             ) -> PreparedQuery:
        pass


@description()
class SelectBindBuilder(QueryBindBuilder):
    def bind(self, builder: SqlBuilder, context: QueryContext
             ) -> PreparedQuery:

        prepared_sql: Optional[str] = builder.build(
            query=context.query, sql_path=context.sql_path)
        if prepared_sql is None:
            raise exceptions.NoQueryArgumentException()

        return PreparedQuery(prepared_sql, context.bind_params)


@description()
class InsertBindBuilder(QueryBindBuilder):
    def bind(self, builder: SqlBuilder, context: QueryContext
             ) -> PreparedQuery:

        prepared_sql: Optional[str] = builder.build(
            query=context.query, sql_path=context.sql_path)
        if prepared_sql is not None:
            return PreparedQuery(prepared_sql, context.bind_params)

        structure: Tuple[str, List[dict]] = context.init_structure("insert")
        table_name: str = structure[0]
        bind_parameters: List[dict] = structure[1]

        prepared_sql: str = (
            f"INSERT INTO {table_name}"
            f"({', '.join([f'{key}' for key in bind_parameters[0].keys()])})"
            f" VALUES "
            f"({', '.join([f':{key}' for key in bind_parameters[0].keys()])})"
        )

        return PreparedQuery(prepared_sql, bind_parameters)


@description()
class UpdateBindBuilder(QueryBindBuilder):
    def bind(self, builder: SqlBuilder, context: QueryContext
             ) -> PreparedQuery:

        prepared_sql: Optional[str] = builder.build(
            query=context.query, sql_path=context.sql_path)
        if prepared_sql is not None:
            return PreparedQuery(prepared_sql, context.bind_params)

        structure: Tuple[str, List[dict]] = context.init_structure("update")
        table_name: str = structure[0]
        bind_parameters: List[dict] = structure[1]

        updating_columns: List[str] = [
            f'{key} = :{key}' for key in bind_parameters[0].keys()
            if key not in context.condition_columns
        ]
        filter_conditions: List[str] = [
            f"{column} = :{column}" for column in context.condition_columns
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

        prepared_sql: Optional[str] = builder.build(
            query=context.query, sql_path=context.sql_path)
        if prepared_sql is not None:
            return PreparedQuery(prepared_sql, context.bind_params)

        structure: Tuple[str, List[dict]] = context.init_structure("delete")
        table_name: str = structure[0]
        bind_parameters: List[dict] = structure[1]

        filter_conditions: List[str] = [
            f"{column} = :{column}" for column in context.condition_columns
        ]
        # TODO 削除対象のPKをまとめて1クエリで記載する
        prepared_sql: str = \
            f"DELETE FROM {table_name}" + (
                f" WHERE {' AND '.join(filter_conditions)}"
                if filter_conditions else ""
            )

        return PreparedQuery(prepared_sql, bind_parameters)
