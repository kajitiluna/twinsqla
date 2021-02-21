import unittest
from typing import List, Tuple, Optional

import sqlalchemy
from sqlalchemy.engine.base import Engine

# import docker

from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))

import twinsqla
from twinsqla import TWinSQLA


class DBType:
    def __init__(self, name: str, uri: str):
        self.name: str = name
        self.engine: Engine = sqlalchemy.create_engine(uri)
        self.sqla: TWinSQLA = TWinSQLA(self.engine)

    def __repr__(self):
        return f"DBType({self.name})"


class Staff:
    def __init__(self, **kwargs):
        self.staff_id: int = kwargs.get("staff_id")
        self.username: str = kwargs.get("username")
        self.age: Optional[int] = kwargs.get("age")


@twinsqla.table("staff")
class StaffWithTable(Staff):
    pass


class TWinSQLATest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # docker_configs: list = [
        #     {
        #         "name": "tiwnsqla_postgres",
        #         "image": "postgres:9.6", "auto_remove": True,
        #         "ports": {"5432/tcp": "5432"},
        #         "volumes": {
        #             str(Path("./tests/db").resolve()): {
        #                 "bind": "/docker-entrypoint-initdb.d",
        #                 "mode": "ro"
        #             }
        #         },
        #         "environment": {
        #             "POSTGRES_USER": "db_user",
        #             "POSTGRES_PASSWORD": "db_password",
        #             "POSTGRES_DB": "test_db"
        #         }
        #     },
        #     {
        #         "name": "tiwnsqla_mysql",
        #         "image": "mysql:5.7", "auto_remove": True,
        #         "ports": {"3306/tcp": "3306"},
        #         "volumes": {
        #             str(Path("./tests/db").resolve()): {
        #                 "bind": "/docker-entrypoint-initdb.d",
        #                 "mode": "ro"
        #             }
        #         },
        #         "environment": {
        #             "MYSQL_RANDOM_ROOT_PASSWORD": "yes",
        #             "MYSQL_USER": "db_user",
        #             "MYSQL_PASSWORD": "db_password",
        #             "MYSQL_DATABASE": "test_db"
        #         }
        #     }
        # ]

        cls.db_types: Tuple[DBType, ...] = (
            DBType(
                "postgres",
                "postgresql://db_user:db_password@postgres_db:5432/test_db"
            ),
            DBType(
                "mysql",
                "mysql+mysqldb://db_user:db_password@mysql_db:3306/test_db"
            )
        )

        # try:
        #     docker_client: docker.DockerClient = docker.from_env()
        #     print("Start docker containers.")
        #     cls.containers: list = [
        #         docker_client.containers.run(detach=True, **config)
        #         for config in docker_configs
        #     ]
        # except Exception as exc:
        #     print("Failed in initializing docker containers."
        #           f" So forcely stopping this unit tests. Detail : {exc}")
        #     sys.exit(1)

        # import time
        # print("Waiting for docker containers starting.", end="", flush=True)
        # wait_seconds: int = 3
        # for index in range(wait_seconds + 1):
        #     try:
        #         for db_type in cls.db_types:
        #             db_type.engine.execute("SELECT 1")

        #         break
        #     except Exception:
        #         if index >= wait_seconds:
        #             print("\nToo many time processed in starting."
        #                   " So forcely stopping this unit tests.")
        #             cls.tearDownClass()
        #             sys.exit(1)

        #         time.sleep(1)
        #         print(".", end="", flush=True)

        # print("\nCompleted starting docker containers.")

    # @classmethod
    # def tearDownClass(cls):
    #     [container.stop() for container in cls.containers]

    def setUp(self):
        try:
            for db_type in self.db_types:
                db_type.engine.execute(
                    "CREATE TABLE staff AS SELECT * FROM base_staff")
        except Exception as exc:
            self.tearDown()
            raise exc

    def tearDown(self):
        for db_type in self.db_types:
            db_type.engine.execute("DROP TABLE IF EXISTS staff")

    query_select_one: str = "SELECT * FROM staff WHERE staff_id = :id"

    def test_select_function_returned_one(self):
        """
        A function returns only one value.
        """

        for db_type in self.db_types:
            with self.subTest("select one function", db_type=db_type):
                sqla: TWinSQLA = db_type.sqla

                @sqla.select(self.query_select_one, result_type=Staff)
                def find_for_function(id: int) -> Staff:
                    pass

                result: Staff = find_for_function(1)
                self.assertIsInstance(result, Staff)
                self.assertEqual(result.staff_id, 1)
                self.assertEqual(result.username, "Alice")
                self.assertEqual(result.age, 20)

    def test_select_method_returned_one_with_named_sqla(self):
        """
        A dao's method returns only one value.
        A dao has TWinSQLA object with named 'sqla.'
        """

        for db_type in self.db_types:
            with self.subTest("select one function", db_type=db_type):
                sqla: TWinSQLA = db_type.sqla

                class StaffDao:
                    def __init__(self, sqla: TWinSQLA):
                        self.sqla = sqla

                    @twinsqla.select(self.query_select_one, result_type=Staff)
                    def find_for_method(self, id: int) -> Staff:
                        pass

                dao: StaffDao = StaffDao(sqla)
                result: Staff = dao.find_for_method(1)
                self.assertIsInstance(result, Staff)
                self.assertEqual(result.staff_id, 1)
                self.assertEqual(result.username, "Alice")
                self.assertEqual(result.age, 20)

    def test_select_method_returned_one_with_named_twinsqla(self):
        """
        A dao's method returns only one value.
        A dao has TWinSQLA object with named 'twinsqla.'
        """

        for db_type in self.db_types:
            with self.subTest("select one function", db_type=db_type):
                sqla: TWinSQLA = db_type.sqla

                class StaffDao:
                    def __init__(self, sqla: TWinSQLA):
                        self.twinsqla = sqla

                    @twinsqla.select(self.query_select_one, result_type=Staff)
                    def find_for_method(self, id: int) -> Staff:
                        pass

                dao: StaffDao = StaffDao(sqla)
                result: Staff = dao.find_for_method(1)
                self.assertIsInstance(result, Staff)
                self.assertEqual(result.staff_id, 1)
                self.assertEqual(result.username, "Alice")
                self.assertEqual(result.age, 20)

    def test_select_method_returned_one_with_unexpected_named(self):
        """
        A dao's method returns only one value.
        A dao has TWinSQLA object without named 'sqla' nor 'twinsqla.'
        """

        for db_type in self.db_types:
            with self.subTest("select one function", db_type=db_type):
                sqla: TWinSQLA = db_type.sqla

                class StaffDao:
                    def __init__(self, sqla: TWinSQLA):
                        self.other_name = sqla

                    @twinsqla.select(self.query_select_one, result_type=Staff)
                    def find_for_method(self, id: int) -> Staff:
                        pass

                dao: StaffDao = StaffDao(sqla)
                result: Staff = dao.find_for_method(1)
                self.assertIsInstance(result, Staff)
                self.assertEqual(result.staff_id, 1)
                self.assertEqual(result.username, "Alice")
                self.assertEqual(result.age, 20)

    def test_select_method_returned_one_with_argument(self):
        """
        A dao's method returns only one value with twinsqla object argument.
        A dao has no TWinSQLA object.
        """

        for db_type in self.db_types:
            with self.subTest("select one function", db_type=db_type):
                sqla: TWinSQLA = db_type.sqla

                class StaffDao:
                    @twinsqla.select(self.query_select_one, result_type=Staff)
                    def find_for_method(self, obj: TWinSQLA, id: int) -> Staff:
                        pass

                dao: StaffDao = StaffDao()
                result: Staff = dao.find_for_method(sqla, 1)
                self.assertIsInstance(result, Staff)
                self.assertEqual(result.staff_id, 1)
                self.assertEqual(result.username, "Alice")
                self.assertEqual(result.age, 20)

    def test_no_twinsqla_object(self):
        """
        A dao's method finds no TWinSQLA object.
        """

        for db_type in self.db_types:
            with self.subTest("select one function", db_type=db_type):
                class StaffDao:
                    @twinsqla.select(self.query_select_one, result_type=Staff)
                    def find_for_method(self, id: int) -> Staff:
                        pass

                dao: StaffDao = StaffDao()
                with self.assertRaises(Exception):
                    dao.find_for_method(1)

    def test_not_matched_argument(self):
        """
        A dao's method argument is not matched name in prepared_statement.
        """

        for db_type in self.db_types:
            with self.subTest("select one function", db_type=db_type):
                class StaffDao:
                    @twinsqla.select(self.query_select_one, result_type=Staff)
                    def find_for_method(self, staff_id: int) -> Staff:
                        pass

                dao: StaffDao = StaffDao()
                with self.assertRaises(Exception):
                    dao.find_for_method(1)

    def test_duplicated_query(self):
        """
        A dao's method can't specify query for duplicated param.
        """

        for db_type in self.db_types:
            with self.subTest("select one function", db_type=db_type):
                class StaffDao:
                    @twinsqla.select(self.query_select_one,
                                     sql_path="dummy.sql", result_type=Staff)
                    def find_for_method(self, staff_id: int) -> Staff:
                        pass

                dao: StaffDao = StaffDao()
                with self.assertRaises(Exception):
                    dao.find_for_method(1)

    def test_no_query(self):
        """
        A dao's method can't specify query for not found
        """

        for db_type in self.db_types:
            with self.subTest("select one function", db_type=db_type):
                class StaffDao:
                    @twinsqla.select(result_type=Staff)
                    def find_for_method(self, staff_id: int) -> Staff:
                        pass

                dao: StaffDao = StaffDao()
                with self.assertRaises(Exception):
                    dao.find_for_method(1)

    query_select_many: str = "SELECT * FROM staff WHERE staff_id <= :id"

    def test_select_function_returned_many(self):
        """
        A function returns a few values.
        """

        for db_type in self.db_types:
            with self.subTest("returning a few values", db_type=db_type):
                sqla: TWinSQLA = db_type.sqla

                @sqla.select(self.query_select_many,
                             result_type=Tuple[Staff, ...])
                def find_for_function(id: int) -> Staff:
                    pass

                results: Tuple[Staff, ...] = find_for_function(5)
                self.assertIsInstance(results, tuple)
                self.assertTrue(len(results) == 5)

    def test_select_function_returned_one_with_tuple(self):
        """
        A function returns only one value with tuple type.
        """

        for db_type in self.db_types:
            with self.subTest("returning a few values", db_type=db_type):
                sqla: TWinSQLA = db_type.sqla

                @sqla.select(self.query_select_one,
                             result_type=Tuple[Staff, ...])
                def find_for_function(id: int) -> Staff:
                    pass

                results: Tuple[Staff, ...] = find_for_function(5)
                self.assertIsInstance(results, tuple)
                self.assertTrue(len(results) == 1)

    def test_select_function_returned_one_unexpected_query_result(self):
        """
        A function returns only one value against query returning a few values.
        """

        for db_type in self.db_types:
            with self.subTest("returning a few values", db_type=db_type):
                sqla: TWinSQLA = db_type.sqla

                @sqla.select(self.query_select_many,
                             result_type=Staff)
                def find_for_function(id: int) -> Staff:
                    pass

                result: Staff = find_for_function(5)
                self.assertIsInstance(result, Staff)

    query_insert: str = """
        INSERT INTO staff(staff_id, username, age)
            VALUES (:staff_id, :username, :age)
    """

    def test_insert_function_with_query(self):
        for db_type in self.db_types:
            with self.subTest("insert a value", db_type=db_type):
                sqla: TWinSQLA = db_type.sqla

                @sqla.insert(self.query_insert)
                def insert(staff_id: int, username: str, age: int):
                    pass

                with sqla.transaction():
                    insert(100, 'Zoo', 88)

                results = [dict(value) for value
                           in db_type.engine.execute(
                    "SELECT * FROM staff WHERE staff_id = 100"
                )]
                self.assertTrue(len(results) == 1)
                self.assertEqual(results[0]["staff_id"], 100)
                self.assertEqual(results[0]["username"], "Zoo")
                self.assertEqual(results[0]["age"], 88)

    def test_insert_function_and_rollback(self):
        for db_type in self.db_types:
            with self.subTest("rollback for inserting", db_type=db_type):
                sqla: TWinSQLA = db_type.sqla

                @sqla.insert(self.query_insert)
                def insert(staff_id: int, username: str, age: int):
                    pass

                try:
                    with sqla.transaction():
                        insert(100, 'DUMMPY', 88)
                        raise Exception()
                except Exception:
                    pass

                results = [dict(value) for value
                           in db_type.engine.execute(
                    "SELECT * FROM staff WHERE staff_id >= 100"
                )]
                self.assertTrue(len(results) == 0)

    def test_insert_function_without_query(self):
        for db_type in self.db_types:
            with self.subTest("insert a value", db_type=db_type):
                sqla: TWinSQLA = db_type.sqla

                @sqla.insert(table_name="staff")
                def insert(entity: Staff):
                    pass

                with sqla.transaction():
                    insert(Staff(staff_id=100, username='Zoo', age=88))

                results = [dict(value) for value
                           in db_type.engine.execute(
                    "SELECT * FROM staff WHERE staff_id >= 100"
                )]
                self.assertTrue(len(results) == 1)
                self.assertEqual(results[0]["staff_id"], 100)
                self.assertEqual(results[0]["username"], "Zoo")
                self.assertEqual(results[0]["age"], 88)

    def test_insert_function_without_query2(self):
        for db_type in self.db_types:
            with self.subTest("insert a value", db_type=db_type):
                sqla: TWinSQLA = db_type.sqla

                @sqla.insert()
                def insert(entity: Staff):
                    pass

                with sqla.transaction():
                    insert(StaffWithTable(
                        staff_id=100, username='Zoo', age=88))

                results = [dict(value) for value
                           in db_type.engine.execute(
                    "SELECT * FROM staff WHERE staff_id >= 100"
                )]
                self.assertTrue(len(results) == 1)
                self.assertEqual(results[0]["staff_id"], 100)
                self.assertEqual(results[0]["username"], "Zoo")
                self.assertEqual(results[0]["age"], 88)

    def test_insert_function_without_query_no_tablename(self):
        for db_type in self.db_types:
            with self.subTest("insert a value", db_type=db_type):
                sqla: TWinSQLA = db_type.sqla

                @sqla.insert()
                def insert(entity: Staff):
                    pass

                with self.assertRaises(Exception):
                    with sqla.transaction():
                        insert(Staff(staff_id=100, username='Zoo', age=88))

                results = [dict(value) for value
                           in db_type.engine.execute(
                    "SELECT * FROM staff WHERE staff_id >= 100"
                )]
                self.assertTrue(len(results) == 0)

    def test_insert_many_function_without_query(self):
        for db_type in self.db_types:
            with self.subTest("insert a value", db_type=db_type):
                sqla: TWinSQLA = db_type.sqla

                @sqla.insert(table_name="staff")
                def insert(entities: List[Staff]):
                    pass

                entities: List[Staff] = [
                    Staff(staff_id=100, username='Zoo', age=88),
                    Staff(staff_id=101, username='Xaming', age=17),
                    Staff(staff_id=102, username='Yorga', age=45),
                ]
                with sqla.transaction():
                    insert(entities)

                results = [dict(value) for value
                           in db_type.engine.execute(
                    "SELECT * FROM staff WHERE staff_id >= 100"
                )]
                self.assertTrue(len(results) == 3)

    query_update: str = """
        UPDATE staff SET username = :username, age = :age
            WHERE staff_id = :staff_id
    """

    def test_update_function_with_query(self):
        for db_type in self.db_types:
            with self.subTest("update a value", db_type=db_type):
                sqla: TWinSQLA = db_type.sqla

                @sqla.update(self.query_update)
                def update(staff_id: int, username: str, age: Optional[int]):
                    pass

                with sqla.transaction():
                    update(6, 'UPDATED NAME', None)

                results = [dict(value) for value
                           in db_type.engine.execute(
                    "SELECT * FROM staff WHERE staff_id = 6"
                )]
                self.assertTrue(len(results) == 1)
                self.assertEqual(results[0]["staff_id"], 6)
                self.assertEqual(results[0]["username"], "UPDATED NAME")
                self.assertEqual(results[0]["age"], None)

    def test_update_function_and_rollback(self):
        for db_type in self.db_types:
            with self.subTest("update a value", db_type=db_type):
                sqla: TWinSQLA = db_type.sqla

                @sqla.update(self.query_update)
                def update(staff_id: int, username: str, age: Optional[int]):
                    pass

                try:
                    with sqla.transaction():
                        update(6, 'UPDATED NAME', None)
                        raise Exception()
                except Exception:
                    pass

                results = [dict(value) for value
                           in db_type.engine.execute(
                    "SELECT * FROM staff WHERE staff_id = 6"
                )]
                self.assertTrue(len(results) == 1)
                self.assertEqual(results[0]["staff_id"], 6)
                self.assertNotEqual(results[0]["username"], "UPDATED NAME")
                self.assertIsNotNone(results[0]["age"])

    def test_update_function_without_query(self):
        for db_type in self.db_types:
            with self.subTest("update a value", db_type=db_type):
                sqla: TWinSQLA = db_type.sqla

                @sqla.update(table_name="staff", condition_columns="staff_id")
                def update(entity: Staff):
                    pass

                with sqla.transaction():
                    update(Staff(staff_id=6, username='UPDATED NAME', age=100))

                results = [dict(value) for value
                           in db_type.engine.execute(
                    "SELECT * FROM staff WHERE username = 'UPDATED NAME'"
                )]
                self.assertTrue(len(results) == 1)
                self.assertEqual(results[0]["staff_id"], 6)
                self.assertEqual(results[0]["username"], "UPDATED NAME")
                self.assertEqual(results[0]["age"], 100)

    def test_update_many_function_without_query(self):
        for db_type in self.db_types:
            with self.subTest("update a value", db_type=db_type):
                sqla: TWinSQLA = db_type.sqla

                @sqla.update(table_name="staff", condition_columns="staff_id")
                def update(entities: List[Staff]):
                    pass

                entities: List[Staff] = [
                    Staff(staff_id=6, username='UPDATED NAME', age=100),
                    Staff(staff_id=7, username='UPDATED NAME', age=10),
                    Staff(staff_id=8, username='UPDATED NAME', age=30)
                ]
                with sqla.transaction():
                    update(entities)

                results = [dict(value) for value
                           in db_type.engine.execute(
                    "SELECT * FROM staff WHERE username = 'UPDATED NAME'"
                )]
                self.assertTrue(len(results) == 3)


if __name__ == "__main__":
    unittest.main()
