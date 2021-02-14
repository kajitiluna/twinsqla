import unittest

from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from twinsqla._dynamic_parser import DynamicParser, DynamicQuery


class DynamicParserTest(unittest.TestCase):

    def setUp(self):
        self.parser = DynamicParser()

    def test_select_normal(self):
        test_query: str = """
        WITH prepare_query AS (
            SELECT TRUE FROM some_table WHERE TRUE
        ), prepare_query2 AS (
            SELECT DISTINCT
                column1,
                column2 AS column22,
                TRIME('aaaa') AS column3
        )
        SELECT DISTINCT
            base.some_column1,
            prepare.some_column2,
            base.some_column3 / prepare.some_column4,
            'constant' + base.some_column5 AS column5
        FROM some_table base
            INNER JOIN prepare_query prepare
                ON base.key = prepare.key
            LEFT JOIN (
                SELECT some_column
                FROM some_table, UNNEST(some_array) AS some_column
            ) prepare2
                ON base.key = prepare2.key
                    AND prepare.key2 = prepare2.key2
        WHERE base.some_column > 100
            AND NOT EXISTS (
                SELECT 1 FROM some_table some
                WHERE base.key = some.key
            )
        GROUP BY key
        HAVING value > 10
        ORDER BY key ASC, value DESC NULLS LAST
        LIMIT 10
        """

        result: DynamicQuery = self.parser.parse(test_query, tuple([]))

        # print(f"EXPECTED : \n{test_query.strip()}\n----------------\n")
        # print(f"ACTUAL :\n{result.query_func()}\n----------------\n")

        self.assertEqual(result.query_func(), test_query.strip())

    def test_insert_normal1(self):
        test_query: str = """
            INSERT INTO some_table (column1, column2, column3)
            VALUES (1, 'aaaa', NULL, current_timestamp())
        """
        result: DynamicQuery = self.parser.parse(test_query, tuple([]))

        self.assertEqual(result.query_func(), test_query.strip())

    def test_insert_normal2(self):
        test_query: str = """
            insert into some_table values
                (1, 'aaaa', NULL, current_timestamp()),
                (2, '', '2020-01-01', NULL)
        """
        result: DynamicQuery = self.parser.parse(test_query, tuple([]))

        self.assertEqual(result.query_func(), test_query.strip())

    def test_insert_normal3(self):
        test_query: str = """
            insert into some_table
            SELECT DISTINCT
                column1,
                column2,
                'constant' AS column3
            FROM some_table
                INNER JOIN other_table other
                    ON some_table.key = other.key
            WHERE condition > 0
            GROUP BY column1
            ORDER BY key DESC
            LIMIT 100
        """
        result: DynamicQuery = self.parser.parse(test_query, tuple([]))

        self.assertEqual(result.query_func(), test_query.strip())

    def test_select_bind_param(self):
        test_query: str = """
            SELECT
                key,
                /* :some_value1 */'dummy' AS column
            FROM some_table
            WHERE some_column >= /* :some_value2 */100
        """

        expected_query: str = """
            SELECT
                key,
                :some_value1 AS column
            FROM some_table
            WHERE some_column >= :some_value2
        """
        result: DynamicQuery = self.parser.parse(
            test_query, tuple(["some_value1", "some_value2"]))

        self.assertEqual(result.query_func("aaa", 10), expected_query.strip())

    def test_select_dynamic_value(self):
        test_query: str = """
            SELECT
                key,
                /* text.strip() */'dummy' AS column
            FROM some_table
            WHERE some_column1 >= /* :some_value1 */100
                AND some_column2 = /* text */'dummy '
        """

        expected_query: str = """
            SELECT
                key,
                :pydynamic_param0 AS column
            FROM some_table
            WHERE some_column1 >= :some_value1
                AND some_column2 = :pydynamic_param1
        """
        result: DynamicQuery = self.parser.parse(
            test_query, tuple(["text", "some_value1"]))

        input_values: dict = {"text": "dynamic_value ", "some_value1": 10}
        self.assertEqual(result.query_func(
            **input_values), expected_query.strip())
        self.assertEqual(
            result.pydynamic_params["pydynamic_param0"](**input_values),
            input_values["text"].strip())
        self.assertEqual(
            result.pydynamic_params["pydynamic_param1"](**input_values),
            input_values["text"])

    def test_select_dynamic_if(self):
        test_query: str = r"""
            SELECT
                some_column
            FROM some_table
            WHERE other_value = 'target' AND
                /*%if some_value1 != 0 */
                    some_column > /* some_value2 / some_value1 */100
                /*%elif some_value2 >0 */
                    OR some_colmn = /* :some_value2 */20
                /*%else*/
                    OR some_column = 0
                /*%end*/
        """

        test_cases = [
            {
                "input_values": {
                    "some_value1": 10,
                    "some_value2": -100
                },
                "expected_query": r"""
            SELECT
                some_column
            FROM some_table
            WHERE other_value = 'target' AND
                some_column > :pydynamic_param0
        """,
                "expected_values": {
                    "pydynamic_param0": -100 / 10
                }
            },

            {
                "input_values": {
                    "some_value1": 0,
                    "some_value2": 30
                },
                "expected_query": r"""
            SELECT
                some_column
            FROM some_table
            WHERE other_value = 'target' AND
                some_colmn = :some_value2
        """,
                "expected_values": {
                    "pydynamic_param0": None
                }
            },

            {
                "input_values": {
                    "some_value1": 0,
                    "some_value2": -1
                },
                "expected_query": r"""
            SELECT
                some_column
            FROM some_table
            WHERE other_value = 'target' AND
                some_column = 0
        """,
                "expected_values": {
                    "pydynamic_param0": None
                }
            }
        ]

        result: DynamicQuery = self.parser.parse(
            test_query, tuple(["some_value1", "some_value2"]))

        for test_case in test_cases:
            with self.subTest("dynamic_if_tests",
                              test_input=test_case["input_values"]):

                input_values: dict = test_case["input_values"]
                expected_query: str = test_case["expected_query"].strip()
                expected_values: dict = test_case["expected_values"]

                self.assertEqual(result.query_func(
                    **input_values), expected_query)
                self.assertEqual(
                    result.pydynamic_params["pydynamic_param0"](
                        **input_values),
                    expected_values["pydynamic_param0"])

    def test_select_dynamic_if_nested(self):
        test_query: str = r"""
            SELECT
                some_column
            FROM some_table
            WHERE some_column1 = 'target' AND
                /*%if value1 > 0 */
                    some_colum2 > 0 AND
                    /*%if value2 == 'aaa' */
                        some_column3 = /* value1 */0
                    /*%else*/
                        OR some_column3 > 0
                    /*%end*/
                /*%elseif value2 == 'aaa' */
                    AND some_column3 = 0
                /*%end*/
        """

        test_cases = [
            {
                "input_values": {
                    "value1": 10,
                    "value2": 'aaa'
                },
                "expected_query": r"""
            SELECT
                some_column
            FROM some_table
            WHERE some_column1 = 'target' AND
                some_colum2 > 0 AND
                    some_column3 = :pydynamic_param0
        """,
                "expected_values": {
                    "pydynamic_param0": 10
                }
            },

            {
                "input_values": {
                    "value1": 10,
                    "value2": 'other_value'
                },
                "expected_query": r"""
            SELECT
                some_column
            FROM some_table
            WHERE some_column1 = 'target' AND
                some_colum2 > 0 AND
                    some_column3 > 0
        """,
                "expected_values": {
                    "pydynamic_param0": None
                }
            },

            {
                "input_values": {
                    "value1": 0,
                    "value2": 'aaa'
                },
                "expected_query": r"""
            SELECT
                some_column
            FROM some_table
            WHERE some_column1 = 'target' AND
                some_column3 = 0
        """,
                "expected_values": {
                    "pydynamic_param0": None
                }
            }
        ]

        result: DynamicQuery = self.parser.parse(
            test_query, tuple(["value1", "value2"]))

        for test_case in test_cases:
            with self.subTest("dynamic_if_tests",
                              test_input=test_case["input_values"]):

                input_values: dict = test_case["input_values"]
                expected_query: str = test_case["expected_query"].strip()
                expected_values: dict = test_case["expected_values"]

                self.assertEqual(result.query_func(
                    **input_values), expected_query)
                self.assertEqual(
                    result.pydynamic_params["pydynamic_param0"](
                        **input_values),
                    expected_values["pydynamic_param0"])


if __name__ == "__main__":
    unittest.main()
