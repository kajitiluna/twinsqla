from typing import Callable, Optional, Union, Tuple
import os
from pathlib import Path
from functools import lru_cache
import textwrap

from ._support import description
from ._dynamic_parser import DynamicParser, DynamicQuery
from . import exceptions


@description(("sql_file_root", "cache_size"))
class SqlBuilder:

    def __init__(self, available_dynamic_query: bool,
                 sql_file_root: Optional[Union[Path, str]] = None,
                 cache_size: Optional[int] = None):

        sql_root: Path = Path(os.getcwd()) if sql_file_root is None \
            else Path(sql_file_root)
        dynamic_parser: Optional[DynamicParser] = DynamicParser() \
            if available_dynamic_query else None

        @lru_cache(maxsize=cache_size)
        def load_query(
            query: Optional[str], sql_path: Optional[str], arg_keys: Tuple[str]
        ) -> Union[str, DynamicQuery]:

            base_query: str = textwrap.dedent(query) if query is not None \
                else _read_file(sql_path, sql_root)

            return dynamic_parser.parse(base_query, arg_keys) \
                if dynamic_parser else base_query

        def _read_file(sql_path: str, sql_root: Path) -> str:
            file_path: Path = sql_root.joinpath(sql_path).resolve()
            with open(file_path, 'r') as sql_file:
                return sql_file.read()

        self._load_query: Callable[[Optional[str], Optional[str], Tuple[str]],
                                   Union[str, DynamicQuery]] = load_query
        self.available_dynamic_query: bool = available_dynamic_query
        self.sql_file_root: Path = sql_root.resolve()
        self.cache_size: Optional[int] = cache_size

    def build(self, *, query: Optional[str], sql_path: Optional[str],
              arg_keys: Tuple[str]) -> Optional[str]:

        if (query is None) and (sql_path is None):
            return None
        if (query is not None) and (sql_path is not None):
            raise exceptions.DuplicatedQueryArgumentException()

        return self._load_query(query, sql_path, arg_keys)
