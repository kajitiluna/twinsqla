from pathlib import Path

target = """
SELECT DISTINCT
    test_column1,
    CASE
        WHEN target_column >= /* :threathold */ 100 THEN dummy
        WHEN TRIM(dummy_column, 5) = 'aaaa' THEN dummy
    END AS hoge,
    COUNT(DISTINCT 1) AS summary
FROM some_table aaa
ORDER BY CASE
    WHEN aaa THEN aaa
    ELSE bbb
END DESC
"""


def main():
    from lark import Lark

    parser = Lark.open(Path(__file__).parent / "sql.two_way.lark",
                       start="query_statement", propagate_positions=True)
    result = parser.parse(target)
    print(result)
    print(result.pretty())


if __name__ == "__main__":
    main()
