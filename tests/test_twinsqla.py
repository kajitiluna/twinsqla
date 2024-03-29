"""
HOW TO TEST

$ export PYTHON_VERSION=3.9
$ docker-compose up --biuld

...testing
# press ctrl + C to stop docker containers.

$ docker-compose down
"""

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


@twinsqla.table("staff", pk="staff_id")
class StaffWithTablePk(Staff):
    pass


@twinsqla.table("auto_staff", pk=twinsqla.autopk("staff_id"))
class StaffWithTableAutoPk(Staff):
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
            with self.subTest(
                "select one function with object's annotation",
                db_type=db_type
            ):
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
            with self.subTest(
                "select one function with static annotation.", db_type=db_type
            ):
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
            with self.subTest(
                """select one function with static annotation
                and named 'twinsqla'.""",
                db_type=db_type
            ):
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
            with self.subTest(
                """select one function with static annotation
                and type searching""", db_type=db_type
            ):
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
            with self.subTest(
                "select one function with sqla argument.", db_type=db_type
            ):
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
            with self.subTest(
                "select one function except sqla object.", db_type=db_type
            ):
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
            with self.subTest(
                "select one function not matched argument name.",
                db_type=db_type
            ):
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
            with self.subTest(
                "select one function with duplicated param", db_type=db_type
            ):
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
            with self.subTest(
                "select one function without query.", db_type=db_type
            ):
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
            with self.subTest("returning a few values.", db_type=db_type):
                sqla: TWinSQLA = db_type.sqla

                @sqla.select(self.query_select_many,
                             result_type=Tuple[Staff, ...])
                def find_for_function(id: int) -> Staff:
                    pass

                results: Tuple[Staff, ...] = find_for_function(5)
                self.assertIsInstance(results, tuple)
                self.assertEqual(len(results), 5)

    def test_select_function_returned_one_with_tuple(self):
        """
        A function returns only one value with tuple type.
        """

        for db_type in self.db_types:
            with self.subTest(
                "returning a few values wtih one tuple.", db_type=db_type
            ):
                sqla: TWinSQLA = db_type.sqla

                @sqla.select(self.query_select_one,
                             result_type=Tuple[Staff, ...])
                def find_for_function(id: int) -> Staff:
                    pass

                results: Tuple[Staff, ...] = find_for_function(5)
                self.assertIsInstance(results, tuple)
                self.assertEqual(len(results), 1)

    def test_select_function_returned_one_unexpected_query_result(self):
        """
        A function returns only one value against query returning a few values.
        """

        for db_type in self.db_types:
            with self.subTest(
                "returning a few values but only one handled.", db_type=db_type
            ):
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
            with self.subTest("insert a value with query.", db_type=db_type):
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
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]["staff_id"], 100)
                self.assertEqual(results[0]["username"], "Zoo")
                self.assertEqual(results[0]["age"], 88)

    def test_insert_function_and_rollback(self):
        for db_type in self.db_types:
            with self.subTest("rollback for inserting.", db_type=db_type):
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
                self.assertEqual(len(results), 0)

    def test_insert_with_table_function__without_query(self):
        for db_type in self.db_types:
            with self.subTest(
                "insert a value with auto query and table name.",
                db_type=db_type
            ):
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
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]["staff_id"], 100)
                self.assertEqual(results[0]["username"], "Zoo")
                self.assertEqual(results[0]["age"], 88)

    def test_insert_function__without_query_table(self):
        for db_type in self.db_types:
            with self.subTest(
                "insert a value with auto query and no table name.",
                db_type=db_type
            ):
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
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]["staff_id"], 100)
                self.assertEqual(results[0]["username"], "Zoo")
                self.assertEqual(results[0]["age"], 88)

    def test_insert_function__without_query_table_pk(self):
        for db_type in self.db_types:
            with self.subTest(
                "insert a value with auto query and auto pk.", db_type=db_type
            ):
                sqla: TWinSQLA = db_type.sqla

                @sqla.insert()
                def insert(entity: Staff):
                    pass

                with sqla.transaction():
                    insert(StaffWithTableAutoPk(
                        staff_id=9999999, username='AUTO PK INSERT 1', age=3))

                results = [dict(value) for value
                           in db_type.engine.execute(
                    """
                    SELECT * FROM auto_staff
                    WHERE username = 'AUTO PK INSERT 1'
                    """
                )]
                self.assertEqual(len(results), 1)
                self.assertNotEqual(results[0]["staff_id"], 9999999)
                self.assertEqual(results[0]["username"], "AUTO PK INSERT 1")
                self.assertEqual(results[0]["age"], 3)

    def test_insert_function__without_query_no_tablename(self):
        for db_type in self.db_types:
            with self.subTest(
                "insert a value without table name.", db_type=db_type
            ):
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

    def test_insert_many_with_table__function_without_query(self):
        for db_type in self.db_types:
            with self.subTest("insert values.", db_type=db_type):
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
                self.assertEqual(len(results), 3)

    def test_insert_many__function_without_query_table(self):
        for db_type in self.db_types:
            with self.subTest("insert values", db_type=db_type):
                sqla: TWinSQLA = db_type.sqla

                @sqla.insert()
                def insert(entities: List[Staff]):
                    pass

                entities: List[Staff] = [
                    StaffWithTable(staff_id=100, username='Zoo', age=88),
                    StaffWithTable(staff_id=101, username='Xaming', age=17),
                    StaffWithTable(staff_id=102, username='Yorga', age=45),
                ]
                with sqla.transaction():
                    insert(entities)

                results = [dict(value) for value
                           in db_type.engine.execute(
                    "SELECT * FROM staff WHERE staff_id >= 100"
                )]
                self.assertEqual(len(results), 3)

    def test_insert_many__function_without_query_table_pk(self):
        for db_type in self.db_types:
            with self.subTest("insert values", db_type=db_type):
                sqla: TWinSQLA = db_type.sqla

                @sqla.insert()
                def insert(entities: List[Staff]):
                    pass

                entities: List[Staff] = [
                    StaffWithTableAutoPk(
                        staff_id=10001, username='AUTO PK INSERT 2', age=88),
                    StaffWithTableAutoPk(
                        staff_id=10002, username='AUTO PK INSERT 2', age=17),
                    StaffWithTableAutoPk(
                        staff_id=10003, username='AUTO PK INSERT 2', age=45),
                ]
                with sqla.transaction():
                    insert(entities)

                results = [dict(value) for value
                           in db_type.engine.execute(
                    """
                    SELECT * FROM auto_staff
                    WHERE username = 'AUTO PK INSERT 2'
                    """
                )]
                self.assertEqual(len(results), 3)
                for result in results:
                    self.assertTrue(result["staff_id"] < 10000)

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
                self.assertEqual(len(results), 1)
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
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]["staff_id"], 6)
                self.assertNotEqual(results[0]["username"], "UPDATED NAME")
                self.assertIsNotNone(results[0]["age"])

    def test_update_with_table_pk_function__without_query(self):
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
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]["staff_id"], 6)
                self.assertEqual(results[0]["username"], "UPDATED NAME")
                self.assertEqual(results[0]["age"], 100)

    def test_update_with_pk_function___without_query_table(self):
        for db_type in self.db_types:
            with self.subTest("update a value with table named entity",
                              db_type=db_type):

                sqla: TWinSQLA = db_type.sqla

                @sqla.update(condition_columns="staff_id")
                def update(entity: Staff):
                    pass

                with sqla.transaction():
                    update(StaffWithTable(
                        staff_id=6, username='UPDATED NAME', age=100))

                results = [dict(value) for value
                           in db_type.engine.execute(
                    "SELECT * FROM staff WHERE username = 'UPDATED NAME'"
                )]
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]["staff_id"], 6)
                self.assertEqual(results[0]["username"], "UPDATED NAME")
                self.assertEqual(results[0]["age"], 100)

    def test_update_function___without_query_table_pk(self):
        for db_type in self.db_types:
            with self.subTest("update a value with table named entity",
                              db_type=db_type):

                sqla: TWinSQLA = db_type.sqla

                @sqla.update()
                def update(entity: Staff):
                    pass

                with sqla.transaction():
                    update(StaffWithTablePk(
                        staff_id=6, username='UPDATED NAME', age=100))

                results = [dict(value) for value
                           in db_type.engine.execute(
                    "SELECT * FROM staff WHERE username = 'UPDATED NAME'"
                )]
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]["staff_id"], 6)
                self.assertEqual(results[0]["username"], "UPDATED NAME")
                self.assertEqual(results[0]["age"], 100)

    def test_update_many_with_table_pk_function___without_query(self):
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
                self.assertEqual(len(results), 3)

    def test_update_many_with_pk_function__without_query_table(self):
        for db_type in self.db_types:
            with self.subTest("update a value", db_type=db_type):
                sqla: TWinSQLA = db_type.sqla

                @sqla.update(condition_columns="staff_id")
                def update(entities: List[Staff]):
                    pass

                entities: List[Staff] = [
                    StaffWithTable(
                        staff_id=6, username='UPDATED NAME', age=100),
                    StaffWithTable(
                        staff_id=7, username='UPDATED NAME', age=10),
                    StaffWithTable(staff_id=8, username='UPDATED NAME', age=30)
                ]
                with sqla.transaction():
                    update(entities)

                results = [dict(value) for value
                           in db_type.engine.execute(
                    "SELECT * FROM staff WHERE username = 'UPDATED NAME'"
                )]
                self.assertEqual(len(results), 3)

    def test_update_many_function__without_query_table_pk(self):
        for db_type in self.db_types:
            with self.subTest("update a value", db_type=db_type):
                sqla: TWinSQLA = db_type.sqla

                @sqla.update(condition_columns="staff_id")
                def update(entities: List[Staff]):
                    pass

                entities: List[Staff] = [
                    StaffWithTablePk(
                        staff_id=6, username='UPDATED NAME', age=100),
                    StaffWithTablePk(
                        staff_id=7, username='UPDATED NAME', age=10),
                    StaffWithTablePk(
                        staff_id=8, username='UPDATED NAME', age=30)
                ]
                with sqla.transaction():
                    update(entities)

                results = [dict(value) for value
                           in db_type.engine.execute(
                    "SELECT * FROM staff WHERE username = 'UPDATED NAME'"
                )]
                self.assertEqual(len(results), 3)


if __name__ == "__main__":
    unittest.main()
