from typing import Callable, List, Optional, Union, Tuple
import os
from pathlib import Path
from functools import lru_cache
import re

import sqlalchemy

from . import exceptions


class SqlStructure:
    def __init__(self, prepared_sql: str):
        self.prepared_sql: str = prepared_sql

    def prepared_query(self) -> sqlalchemy.sql.text:
        return sqlalchemy.sql.text(self.prepared_sql)


class SqlBuilder:

    def __init__(self, sql_file_root: Optional[Union[Path, str]] = None,
                 cache_size: Optional[int] = None):

        sql_root: Path = Path(os.getcwd()) if sql_file_root is None \
            else Path(sql_file_root)

        @lru_cache(maxsize=cache_size)
        def _build(query: Optional[str] = None, *,
                   sql_path: Optional[str] = None) -> SqlStructure:

            if (query is None) and (sql_path is None):
                raise exceptions.NoQueryArgumentException()
            if (query is not None) and (sql_path is not None):
                raise exceptions.DuplicatedQueryArgumentException()

            import textwrap

            base_query: str = textwrap.dedent(query) if query is not None \
                else _read_file(sql_path, sql_root)

            return self._do_build(base_query)

        def _read_file(sql_path: str, sql_root: Path) -> str:
            file_path: Path = sql_root.joinpath(sql_path).resolve()
            with open(file_path, 'r') as sql_file:
                return sql_file.read()

        self.build: Callable[[Optional[str], Optional[str]], SqlStructure] \
            = _build

    def _do_build(self, base_query: str) -> SqlStructure:
        prepared_query: List[str] = []
        index: int = 0
        max_index: int = len(base_query)
        while index < max_index:
            target_charactor: str = base_query[index]
            index += 1
            if target_charactor != "/" or index >= max_index:
                prepared_query.append(target_charactor)
                continue

            next_charactor: str = base_query[index]
            index += 1
            if next_charactor != "*" or index >= max_index:
                prepared_query.append(next_charactor)
                continue

            # このタイミングで「/*」が確定している
            seek_spaces, index, param_charactor = self._peer_whitespace(
                index, base_query, max_index)

            if param_charactor != ":":
                # この時点で通常のコメントとみなす。
                seek_comment, index = self._peer_multiline_comment_end(
                    index, base_query, max_index)
                prepared_query.append("/*")
                prepared_query.append(seek_spaces)
                prepared_query.append(param_charactor)
                prepared_query.append(seek_comment)
                continue

            parameter_name, index = self._peer_prepared_param(
                index, base_query, max_index)
            prepared_query.append(seek_spaces[1:])
            prepared_query.append(parameter_name)
            prepared_query.append(" ")

        return SqlStructure("".join(prepared_query))

    def _peer_whitespace(
        self, base_index: int, base_query: str, max_index: int
    ) -> Tuple[str, int, str]:

        index = base_index
        seek_spaces: List[str] = []
        while index < max_index:
            next_charactor: str = base_query[index]
            index += 1
            if next_charactor not in (' ', r'\t', r'\n', r'\r'):
                break
            seek_spaces.append(next_charactor)

        return ("".join(seek_spaces), index, next_charactor)

    def _peer_multiline_comment_end(
        self, base_index: int, base_query: str, max_index: int
    ):

        index = base_index
        while index < max_index:
            next_charactors: str = base_query[index:(index + 2)]
            index += 1
            if next_charactors == "*/":
                break

        return (base_query[base_index: index + 1], index + 1)

    _PATTERN_PARAM_NAME: re.Pattern = re.compile(
        r"\A([a-zA-Z_][a-zA-Z0-9_]*) *\*/")

    def _peer_prepared_param(
        self, base_index: int, base_query: str, max_index: int
    ):

        index: int = base_index
        matcher: Optional[re.Match] = self._PATTERN_PARAM_NAME.match(
            base_query[index:])
        if matcher is None:
            raise exceptions.InvalidStructureException(
                "Block commnet is not closed.")
        parameter_name: str = ":" + matcher.group(1)
        scaned_block: str = matcher.group(0)

        index += len(scaned_block)

        # ダミー値の置き換え
        dummy_charactor = base_query[index]
        index += 1
        if dummy_charactor == "'":
            dummy_value, index = self._peer_text(index, base_query, max_index)
            return (parameter_name, index)

        # TODO 「/* :param */( ...)」 のパターンの処理

        while index < max_index:
            next_charactor: str = base_query[index]
            index += 1
            if next_charactor in (
                " ", r"\t", r"\n", r"\r", "+", "-", "*", "/", "%"
            ):
                break

        return (parameter_name, index - 1)

    def _peer_text(self, base_index: int, base_query: str, max_index: int):
        index = base_index
        seek_charactors: List[str] = ["'"]
        while index < max_index:
            next_charactor: str = base_query[index]
            seek_charactors.append(next_charactor)
            index += 1
            if next_charactor == "'" and (
                (index == max_index) or (base_query[index] != "'")
            ):
                break

        return ("".join(seek_charactors), index)
