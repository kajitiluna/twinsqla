from typing import Any, Optional
from abc import ABCMeta, abstractmethod

import sqlalchemy

from . import exceptions
from ._sqlbuilder import SqlBuilder


class SqlBinder:
    def __init__(self, prepared_sql: str, parameters: dict):
        self.prepared_sql: str = prepared_sql
        self.parameters: dict = parameters

    def prepared_query(self) -> sqlalchemy.sql.text:
        return sqlalchemy.sql.text(self.prepared_sql)

    def bind_params(self) -> dict:
        return self.parameters.copy()


class QueryBindBuilder(metaclass=ABCMeta):
    @abstractmethod
    def bind(self, builder: SqlBuilder, query: Optional[str],
             sql_path: Optional[str], table_name: Optional[str],
             bind_params: dict) -> SqlBinder:
        pass


class SelectBindBuilder(QueryBindBuilder):
    def bind(self, builder: SqlBuilder, query: Optional[str],
             sql_path: Optional[str], table_name: Optional[str],
             bind_params: dict) -> SqlBinder:

        prepared_sql: Optional[str] = builder.build(
            query=query, sql_path=sql_path)
        if prepared_sql is None:
            raise exceptions.NoQueryArgumentException()

        return SqlBinder(prepared_sql, bind_params)


class InsertBindBuilder(QueryBindBuilder):
    def bind(self, builder: SqlBuilder, query: Optional[str],
             sql_path: Optional[str], table_name: Optional[str],
             bind_params: dict) -> SqlBinder:

        prepared_sql: Optional[str] = builder.build(
            query=query, sql_path=sql_path)
        if prepared_sql is not None:
            return SqlBinder(prepared_sql, bind_params)

        # TODO 挿入対象がListで複数指定された場合
        entity: Optional[Any] = (
            bind_params.get("entity") or list(bind_params)[0]
        ) if bind_params else None
        if entity is None:
            # TODO
            pass

        target_table_name: Optional[str] = table_name if table_name \
            else getattr(entity, "_table_name", None)
        if target_table_name is None:
            raise exceptions.NotFoundTableNameException(
                entity, "insert", "_table_name")

        entity_params: dict = {
            key: value for key, value in vars(entity).items()
            if (value is not None) and (key != "_table_name")
        }
        prepared_sql: str = (
            f"INSERT INTO {target_table_name}"
            f"({', '.join([f'{param}' for param in entity_params.keys()])})"
            f" VALUES "
            f"({', '.join([f':{param}' for param in entity_params.keys()])})"
        )

        return SqlBinder(prepared_sql, entity_params)
