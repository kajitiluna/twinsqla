from typing import Any, Optional, Union, List
from dataclasses import dataclass
from abc import ABCMeta, abstractmethod

import sqlalchemy

from . import exceptions
from ._sqlbuilder import SqlBuilder


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

    triggered_function: callable
    function_args: tuple
    function_kwargs: dict

    def find_entities(self) -> List[Any]:
        target: Optional[Any] = (
            self.bind_params.get("entities")
            or self.bind_params.get("entity")
            or list(self.bind_params)[0]
        ) if self.bind_params else None

        if target is None:
            return []

        if isinstance(target, (dict, tuple)):
            return target

        return [target]


class QueryBindBuilder(metaclass=ABCMeta):
    @abstractmethod
    def bind(self, builder: SqlBuilder, context: QueryContext
             ) -> PreparedQuery:
        pass


class SelectBindBuilder(QueryBindBuilder):
    def bind(self, builder: SqlBuilder, context: QueryContext
             ) -> PreparedQuery:

        prepared_sql: Optional[str] = builder.build(
            query=context.query, sql_path=context.sql_path)
        if prepared_sql is None:
            raise exceptions.NoQueryArgumentException()

        return PreparedQuery(prepared_sql, context.bind_params)


class InsertBindBuilder(QueryBindBuilder):
    def bind(self, builder: SqlBuilder, context: QueryContext
             ) -> PreparedQuery:

        prepared_sql: Optional[str] = builder.build(
            query=context.query, sql_path=context.sql_path)
        if prepared_sql is not None:
            return PreparedQuery(prepared_sql, context.bind_params)

        entities: List[Any] = context.find_entities()
        if len(entities) == 0:
            raise exceptions.NoSpecifiedEntityException(
                context.triggered_function)

        target_table_name: Optional[str] = context.table_name \
            if context.table_name \
            else getattr(entities[0], "_table_name", None)
        if target_table_name is None:
            raise exceptions.NotFoundTableNameException(
                entities[0], "insert", "_table_name")

        bind_parameters: List[dict] = [
            {
                key: value for key, value in vars(entity).items()
                if (value is not None) and (key != "_table_name")
            } for entity in entities
        ]

        prepared_sql: str = (
            f"INSERT INTO {target_table_name}"
            f"({', '.join([f'{key}' for key in bind_parameters[0].keys()])})"
            f" VALUES "
            f"({', '.join([f':{key}' for key in bind_parameters[0].keys()])})"
        )

        return PreparedQuery(prepared_sql, bind_parameters)
