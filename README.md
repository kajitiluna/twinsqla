# TWinSQLA

TWinSQLA is a database access framework for Python3.

## Features
- Tow Way SQL template.
    - Inspired by [Doma](https://github.com/domaframework/doma)
- Type hint support.
- Depending on SQLAlchemy for connection to databases, connection pooling, transaction management, and so on.

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
        def select(self, staff_id: int) -> Optional[Staff]:
            pass
    ```

- In production usage

    - staff.py
    ```python
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
            result_type=Staff
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