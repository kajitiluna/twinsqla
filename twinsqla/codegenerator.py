from typing import List, Optional, NamedTuple
import argparse
import sys
import re
import keyword

import sqlalchemy
from sqlalchemy.engine.base import Engine
from sqlalchemy.schema import MetaData, Table, Column
from sqlalchemy.sql import sqltypes


def main():
    args = init_argument_parser().parse_args()
    execute(url=args.url, schema=args.schema,
            to_file=args.to_file, indent_size=args.indent_size)


def init_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        "Generate TWinSQLA model codes from an existing database.")
    parser.add_argument(
        "url", help="SQLAlchemy uri to connect to the database.")
    parser.add_argument(
        "--schema", default=None,
        help="The schema name from which loading tables if necessary ."
    )
    parser.add_argument("--to_file", default=None,
                        help="file path to wirte output.")
    parser.add_argument("--indent_size", type=int, default=4,
                        help="indent size of python code.")

    return parser


class ModelAttribute:

    def __init__(self, column: Column, indent_count: int = 1):
        self.column: Column = column
        self.indent_count: int = indent_count

    @property
    def primary_key(self) -> bool:
        return self.column.primary_key

    def to_dataclass_code(self, indent_size: int = 4) -> str:
        param_name: str = to_avairable_name(self.column.name)
        param_type: str = to_python_type(self.column.type)

        indent: str = " " * (self.indent_count * indent_size)
        wrapped_type: str = f"Optional[{param_type}]" \
            if self.column.nullable else param_type

        return f"{indent}{param_name}: {wrapped_type} = field(default=None)"


class ModelClass:

    def __init__(self, table: Table, indent_count: int = 0):
        self.table: Table = table
        self.attributes: List[ModelAttribute] = [
            ModelAttribute(column) for column in table.columns
        ]
        self.indent_count: int = indent_count

    def to_dataclass_code(self, indent_size: int = 4) -> str:
        class_name: str = to_class_name(self.table.name)
        attribute_codes: List[str] = [
            attribute.to_dataclass_code(indent_size)
            for attribute in self.attributes
        ]

        class_codes: List[str] = [
            "\n", "@dataclass(frozen=True)",
            f"{self._table_decorator()}", f"class {class_name}:"
        ]
        class_codes.extend(attribute_codes)
        indent: str = ' ' * (self.indent_count * indent_size)

        return f"\n{indent}".join(class_codes)

    def _table_decorator(self) -> str:
        table_name: str = f"{self.table.schema}.{self.table.name}" \
            if self.table.schema else self.table.name

        primary_keys: List[str] = [
            f'twinsqla.autopk("{column.name}")'
            if column.autoincrement else f'"{column.name}"'
            for column in self.table.primary_key
        ]

        pk_args: str = "" if len(primary_keys) == 0 else (
            f', pk={primary_keys[0]}' if len(primary_keys) == 1 else (
                f', pk=({", ".join(primary_keys)})'
            )
        )

        return f'@twinsqla.table("{table_name}"{pk_args})'


def execute(url: str, schema: Optional[str] = None,
            to_file: Optional[str] = None, indent_size: int = 4):

    engine: Engine = sqlalchemy.create_engine(url)
    metadata = MetaData(engine)
    metadata.reflect(engine, schema=schema)

    model_classes: List[ModelClass] = [
        ModelClass(table) for table in metadata.tables.values()
    ]
    if len(model_classes) == 0:
        print((
            "Not found any tables in connected"
            f" '{repr(engine.url)}'' with schema '{schema}'."
        ), file=sys.stderr)
        return

    python_code: str = _to_python_code_with_dataclass(
        model_classes, indent_size)

    if not to_file:
        print(f"\n{python_code}\n")
        return

    with open(to_file, "w", encoding="utf-8") as output_file:
        print(python_code, file=output_file)

    print(f"\n\nSucceed to output TWinSQLA model classes to '{to_file}'."
          f" ({len(model_classes)} classes)")


def _to_python_code_with_dataclass(
    model_classes: List[ModelClass], indent_size: int
) -> str:

    codes: List[str] = [
        "from dataclasses import dataclass, field",
        "from typing import Optional",
        "import datetime",
        "",
        "import twinsqla"
    ]
    codes.extend([
        model_class.to_dataclass_code(indent_size)
        for model_class in model_classes
    ])

    return "\n".join(codes)


def to_class_name(table_name: str) -> str:
    name: str = to_avairable_name(table_name)
    return "".join(part.capitalize() for part in name.split("_"))


_INVALID_CHARACTOR_PATTERN = re.compile(r"[^a-zA-Z0-9_]")


def to_avairable_name(org: str) -> str:
    if not org:
        return org

    avairable_name: str = f"_{org}" if (
        org[0].isdigit() or keyword.iskeyword(org)) else (
            org if org != "metadata" else "metadata_"
    )

    return _INVALID_CHARACTOR_PATTERN.sub("_", avairable_name)


class TypePair(NamedTuple):
    sql_type: any
    python_type: str


# Not support types : SchemaType, Enum, PickleType, NullType
_CONVERT_PAIRS = [
    TypePair(sqltypes.String, "str"),
    TypePair(sqltypes.Integer, "int"),

    TypePair(sqltypes.DateTime, "datetime.datetime"),
    TypePair(sqltypes.Date, "datetime.date"),

    TypePair(sqltypes.Boolean, "bool"),

    TypePair(sqltypes.Numeric, "float"),
    TypePair(sqltypes.Time, "datetime.time"),
    TypePair(sqltypes._Binary, "bytes"),
    TypePair(sqltypes.Interval, "datetime.timedelta"),
    TypePair(sqltypes.JSON, "any"),
    TypePair(sqltypes.ARRAY, "list")
]


def to_python_type(column_type) -> str:
    for type_pair in _CONVERT_PAIRS:
        if isinstance(column_type, type_pair.sql_type):
            return type_pair.python_type

    return "any"


if __name__ == "__main__":
    main()
