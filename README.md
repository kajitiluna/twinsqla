# TWinSQLA

TWinSQLA is a light framework for mapping SQL statements to python functions or methods.

## Features
- Available in Python 3.7+
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
    - Inspired by [Doma](https://github.com/domaframework/doma)
- Since [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy) core is used for accessing databases,
    SQLAlchemy core features can be utilized. (such as connection pool)
- Type hint support.

## Usage

- First step (In case that TWinSQLA object is available in global scope)

    ```python
    from typing import Optional
    import sqlalchemy
    engine: sqlalchemy.engine.base.Engine = sqlalchemy.create_engine(...)

    from twinsqla import TWinSQLA
    sqla: TWinSQLA = TWinSQLA(engine)

    class StaffDao():
        @sqla.select("SELECT * FROM staff WHERE staff_id = /* :staff_id */1")
        def find_by_id(self, staff_id: int) -> Optional[Staff]:
            pass
    ```

- In production usage

    - staff.py
    ```python
    from typing import List
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class Staff:
        staff_id: int
        staff_name: str
        ...
    ```

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
    ```

## SQL Template
- Bind variable

    sample
    ```sql
    SELECT * FROM table_name
    WHERE user_id = /* :id */300
    ```

    ```sql
    SELECT * FROM table_name
    WHERE user_id IN /* :ids */(300, 305, 317)
    ```

- IF block

    sample
    ```sql
    SELECT * FROM table_name
    WHERE
        /*%if _bool_expression_ */
        some_column1 = 1
        /*%elseif _bool_expression_ */
        OR some_column2 = 2
        /*%else*/
        OR some_column3 = 3
        /*%end*/
    ```

    definition
    ```sql
    /*%if _bool_expression_ */ query [/*%elseif _bool_expression_ */ query [...]] [/*%else*/ query] /*%end*/
    ```

- FOR block

    sample
    ```sql
    SELECT * FROM table_name
    WHERE
        /*%for item in iterator */
        some_column = /* $item */'dummy'
        /*# or */
        /*%end*/
    ```