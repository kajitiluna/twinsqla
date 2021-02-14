from pathlib import Path

from lark import Lark

target = r"""
SELECT DISTINCT
    test_column1
FROM some_table aaa
WHERE
    /*%if some_colume == 'aaa' */
        /* some_colume */TRUE
    /*%elif some_colume == 'bbb' */
        OR some_value = '10'
    /*%else*/
        OR FALSE
    /*%end*/
"""


def main():

    parser = Lark.open(Path(__file__).parent / "sql.two_way.lark",
                       start="query_statement",
                       propagate_positions=True,
                       maybe_placeholders=True)
    result = parser.parse(target)
    print(result)
    print(result.pretty())


if __name__ == "__main__":
    main()
