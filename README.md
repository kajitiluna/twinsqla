# TWinSQLA

TWinSQLA is a light framework for mapping SQL statements to python functions and methods.

## Features
- Available in Python 3.6+
    - We recommends Python 3.7+ since available to use `@dataclasses.dataclass` decorator in entity classes.
- This framework concept is avoid ORM features!
    Coding with almost-raw SQL query (with prepared parameters) simply.
    - Let's consider that you coding with ORM features in accessing databases.
        For example, you want to fetch records form a table.
        First, you think SQL query for fetching records (you may be executing query for checking results!),
        and you convert raw sql query to python's functions with ORM features.
        And more, you will check the result of executing program with ORM features.
    - If you can use SQL query with coding simply, it make you to skipping the times of converting python coding
        with ORM features and checking result.python coding with ORM features.
    - TWinSQLA support you to checking only SQL query without coding with ORM features.
- Support "two-way SQL" template.
    - "Two-way SQL" templates can be executed SQL statements with dynamic parameter written by python expression.
    - In "two-way SQL", dynamic parameters and conditional expressions are surrounded by '/\*' and '\*/'.
        So, "two-way SQL" templates are available to execute in SQL tools as they are.
    - TWinSQLa is inspired by [Doma](https://github.com/domaframework/doma),
        which is Java framework for accessing databases.
- Since [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy) core is used for accessing databases,
    SQLAlchemy core features can be utilized. (such as connection pool)
- Type hint support.

## How to install (TODO)
You can install from PyPI by the follow command.
```bash
pip install ...
```

## Usage

- First step (In case that TWinSQLA object is available in global scope)

    ```python
    from typing import Optional
    import sqlalchemy
    from twinsqla import TWinSQLA

    engine: sqlalchemy.engine.base.Engine = sqlalchemy.create_engine(...)
    sqla: TWinSQLA = TWinSQLA(engine)

    class StaffDao():
        @sqla.select("SELECT * FROM staff WHERE staff_id = /* :staff_id */1")
        def find_by_id(self, staff_id: int) -> Optional[Staff]:
            pass
    ```

- In production usage

    - staff_dao.py
        ```python
        import twinsqla
        from twinsqla import TWinSQLA

        class StaffDao:
            def __init__(self, sqla: TWinSQLA):
                self.sqla: TWinSQLA = sqla

            @twinsqla.select(
                "SELECT * FROM staff WHERE staff_id >= /* :more_than_id */2",
                result_type=List[Staff]
            )
            def fetch(self, more_than_id: int) -> List[Staff]:
                pass

            @twinsqla.insert()
            def insert(self, staff: Staff):
                pass
        ```

        You need to specify the TWinSQLA instance by one of the follow way.

        - By configured with instance parameter with named 'sqla'. (See above the sample code)
        - Or, by specified with method arguments with named 'sqla'.

            ```python
            @twinsqla.select(...)
            def fetch(self, sqla: TWinSQLA, more_than_id: int) -> List[Staff]:
                pass
            ```

    - staff.py
        ```python
        from typing import Optional
        from dataclasses import dataclass
        from twinsqla import table

        @dataclass(frozen=True)
        @table("staff")
        class Staff:
            staff_id: Optional[int]
            staff_name: str
        ```

        We recommend using `dataclass` decorator in operations of insert or update.

    - staff_service.py
        ```python
        class StaffService:
            def __init(self, sqla: TWinSQLA):
                self.sqla: TWinSQLA = sqla
                self.staff_dao: StaffDao = StaffDao(sqla)

            def find_staff(self, more_than_id: int) -> List[Staff]:
                return self.staff_dao.fetch(more_than_id)

            def register(self, staff_name: str):
                new_staff: Staff = Staff(staff_id=None, staff_name=staff_name)

                # db transaction scope
                with self.sqla.transaction():
                    self.staff_dao.insert(new_staff)
        ```

## SQL Template
- Bind variable

    TWinSQLA's two-way SQL can handle the bind parameter named *some_parameter* as follow.
    ```sql
    /* :some_parameter */_dummy_value_
    ```
    Where, *_dummy_value_* is ignored in TWinSQLA query.

    Implementation.
    ```python
    @twinsqla.select(
        "SELECT * FROM table_name WHERE key = /* :some_value */300"
    )
    def fetch_by_key(self, some_value: int) -> dict:
        pass
    ```

    Calling methods.
    ```python
    dao.fetch_by_key(10)
    ```

    In this case, the follow statement and codes are executed.
    ```python
    query = sqlalchemy.sql.text("SELECT * FROM table_name WHERE key = :some_value")
    sqlalchemy_engin.execute(query, {"some_value": 10})
    ```


- Bind variable with iterator (Not yet implemented)

    (Not yet implemented handling iterable binding parameter)
    ```sql
    SELECT * FROM table_name
    WHERE keys IN /* :some_values */(300, 305, 317)
    ```


- Python expression variable

    TWinSQLA's two-way SQL can embed a python expressions in sql statements as follow.
    ```sql
    /* python_expression */_dummy_value_
    ```
    Where, *_dummy_value_* is ignored in TWinSQLA query.

    Implementation.
    ```python
    @twinsqla.select(
        "SELECT * FROM table_name WHERE key = /* some_value * 100 */300"
    )
    def fetch_by_key(self, some_value: int) -> dict:
        pass
    ```
    In this case, `some_value * 100` is the python expression, and `some_value` must be specified in this method's arguments.

    Call methods.
    ```python
    dao.fetch_by_key(10)
    ```

    Then the follow statement and codes are executed.
    ```python
    query = sqlalchemy.sql.text("SELECT * FROM table_name WHERE key = :dynamic_param")
    sqlalchemy_engin.execute(query, {"dynamic_param": 10 * 100})
    ```
    This bind parameter `:dynamic_param` is automatically generated by TWinSQLA to assign the python expression `some_value * 100` to this bind parameter.


- IF block (Basic usage)

    Definition of dynamic if-block
    ```sql
    /*%if _python_expression_ */ expression
    [ /*%elif _python_expression_ */ dummy_op expression [...] ]
    [ /*%else*/ dummy_op expression ]
    /*%end*/

    dummy_op := "AND" | "OR"
    ```

    Implementation
    ```python
    @twinsqla.select(r"""
        SELECT * FROM table_name
        WHERE
            /*%if some_value == 'first' */
            some_column1 > 0
            /*%elif some_value == 'second' */
            OR some_column2 > 0
            /*%else*/
            OR some_column1 = 0 AND some_column2 = 0
            /*%end*/
    """)
    def find(self, some_value: str) -> List[dict]:
        pass
    ```

    Call sample1.
    ```python
    dao.find("first")
    ```
    Then query1 is:
    ```sql
        SELECT * FROM table_name
        WHERE
            some_column1 > 0
    ```
    By the first if-condition is satisfied, then the others expressions are ignored.

    Call sample2.
    ```python
    dao.find("second")
    ```
    Then query2 is:
    ```sql
        SELECT * FROM table_name
        WHERE
            some_column2 > 0
    ```
    By the first if-condition is not satisfied and second is, then the excepts for second expression are ignored. And, noticed that `OR` operation ahead of expression `some_column2 > 0` is ignored.

    Call sample3.
    ```python
    dao.find("other")
    ```
    Then query3 is:
    ```sql
        SELECT * FROM table_name
        WHERE
            some_column1 = 0 AND some_column2 = 0
    ```


- IF block (Advanced usage)

    - Nested IF block

        IF block can be nested.

        Example.
        ```python
        @twinsqla.select(r"""
            SELECT * FROM table_name
            WHERE
                /*%if some_value1 == 'first' */
                some_column1 > 0
                /*%elif some_value1 == 'second' */
                OR some_column2 > 0 AND
                    /*%if some_value2 > 0 */
                    some_column3 = some_column4
                    /*%else*/
                    OR some_column3 IS NULL
                    /*%end*/
                /*%else*/
                OR some_column1 = 0 AND some_column2 = 0
                /*%end*/
        """)
        def find(self, some_value1: str, some_value2: int) -> List[dict]:
            pass
        ```

    - About python expression nested in if-blocks evaluation

        Python expression variables nested in if-blocks are evaluated only when if-condition is satisfied.
        Consider the follow example with if-block and python expression variable.

        ```python
        @twinsqla.select(r"""
            SELECT * FROM table_name
            WHERE
                /*%if some_value1 != 0 */
                some_column1 > /* some_value2 / some_value1 */10
                /*%else*/
                OR some_column1 > 0
                /*%end*/
        """)
        def find(self, some_value1: int, some_value2: int) -> List[dict]:
            pass
        ```

        In the first case, the follow calling has no problem.
        ```python
        dao.find(10, 50)
        ```
        The above calling is the almost same the following execution.
        ```python
        query = sqlalchemy.sql.text("""
            SELECT * FROM table_name
            WHERE
                some_column1 > :dynamic_param
        """)
        sqlalchemy_engin.execute(query, {"dynamic_param": (50 / 10)})
        ```

        In the next case, the follow calling.
        ```python
        dao.find(0, 7)
        ```
        In this case.
        ```python
        query = sqlalchemy.sql.text("""
            SELECT * FROM table_name
            WHERE
                some_column1 > 0
        """)
        sqlalchemy_engin.execute(query, {"dynamic_param": None})
        ```

        Because for the first if-condition `some_value1 != 0` is not satisfied, the first python expression variable is not evaluated. (In detail, evaluated as `None` without evaluating dividing by zero `5 / 0`.)


- FOR block (Not yet implemented)

    sample
    ```sql
    SELECT * FROM table_name
    WHERE
        /*%for item in iterator */
        some_column = /* $item */'dummy'
        /*%or*/
        /*%end*/
    ```