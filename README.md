# TWinSQLA

TWinSQLA is a light framework for mapping SQL statements to python functions and methods.

## Features
- Available in Python 3.6+
    - We recommends Python 3.7+ since available to use `@dataclasses.dataclass` decorator in entity classes.
- This framework concept is avoid ORM features!
    Coding with almost-raw SQL query (with prepared parameters) simply.
    - If you can use SQL query with coding simply, it make you to skipping the times of converting python coding
        with ORM features and checking result.
    - TWinSQLA support you to checking only SQL query without coding with ORM features.
- Support "two-way SQL" template.
    - "Two-way SQL" templates can be executed SQL statements with dynamic parameter written by python expression.
    - In "two-way SQL", dynamic parameters and conditional expressions are surrounded by '/\*' and '\*/'.
        So, "two-way SQL" templates are available to execute in SQL tools as they are.
    - TWinSQLa is inspired by [Doma](https://github.com/domaframework/doma),
        which is Java framework for accessing databases.
- Since [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy) core is used for accessing databases,
    SQLAlchemy core features can be utilized. (such as connection pool)


## How to install
You can install from PyPI by the follow command.
```bash
pip install twinsqla
```

## Usage

### First step (In case that TWinSQLA object is available in global scope)

```python
from typing import Optional
from collections import OrderedDict
import sqlalchemy
from twinsqla import TWinSQLA

engine: sqlalchemy.engine.base.Engine = sqlalchemy.create_engine(...)
sqla: TWinSQLA = TWinSQLA(engine)

class StaffDao():
    @sqla.select("SELECT * FROM staff WHERE staff_id = /* :staff_id */1")
    def find_by_id(self, staff_id: int) -> Tuple[OrderDict, ...]:
        pass
```

At first, create instance of sqlalchemy engine, and create TWinSQLA instance with sqlalchemy engine.
```python
engine: sqlalchemy.engine.base.Engine = sqlalchemy.create_engine(...)
sqla: TWinSQLA = TWinSQLA(engine)
```

To execute select query, use `sqla.select` decorator. In this case, `sqla` is TWinSQLA instance.
```python
@sqla.select("SELECT * FROM staff WHERE staff_id = /* :staff_id */1")
def find_by_id(self, staff_id: int) -> Tuple[OrderDict, ...]:
    pass
```

The above example, select query in decorator's argument is written as "two-way SQL."
When called `dao.find_by_id(staff_id=10)`, then the like following code will be executed.
```python
> query = sqlalchemy.sql.text("SELECT * FROM staff WHERE staff_id = :staff_id")
> engine.execute(query, {staff_id:10})
```
The execution results will be converted to sequence of OrderedDict, and returned from the above method.

The `sqla.select` decorator can return object for your custom class, or return the results iterable.  For more details, see the other section.

### In production usage

For about production usage, you may separate source codes as dao classes, entity classes, and handling transaction classes.

```python
from dataclasses import dataclass, field
import twinsqla
from twinsqla import TWinSQLA, table, autopk

# Entity class
@dataclass(frozen=True)
@table("staff", pk=autopk("staff_id"))
class Staff:
    staff_id: int = field(default=None)
    staff_name: str = field(default=None)
    age: int = field(default=None)


# Dao class
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


# Service class (Handling database transaction)
class StaffService:
    def __init__(self, sqla: TWinSQLA):
        self.sqla: TWinSQLA = sqla
        self.staff_dao: StaffDao = StaffDao(sqla)

    def find_staff(self, more_than_id: int) -> List[Staff]:
        return self.staff_dao.fetch(more_than_id)

    def register(self, staff_name: str, age: int):
        new_staff: Staff = Staff(staff_name=staff_name, age=age)

        # DB transaction scope
        with self.sqla.transaction():
            self.staff_dao.insert(new_staff)
```

#### Dao class

##### Initializing

In this cases, the TWinSQLA object is not existed in global scope but only in dao instance scope. So, you cannot use TWinSQLA instance decorators (for example : `@sqla.select()`) at the dao methods.
Instead of using instance decorators, you can use TWinSQLA function decorators. (for example : `@twinsqla.select()`)

When executing, the TWinSQLA function decorators search TWinSQLA object. By this search, TWinSQLA instance can be found specified by one of the follow ways.

- By configured with instance parameter with named 'sqla'. (above the sample code)
    ```python
    def __init__(self, sqla: TWinSQLA):
        self.sqla: TWinSQLA = sqla
    ```

- Or, the other way, by specified with method arguments with named 'sqla'.
    ```python
    @twinsqla.select(...)
    def fetch(self, sqla: TWinSQLA, more_than_id: int) -> List[Staff]:
        pass
    ```

##### Select

To executing select query, you need to use `twinsqla.select()` function decorator instead of `sqla.select()` instance decorator.
```python
@twinsqla.select(
    "SELECT * FROM staff WHERE staff_id >= /* :more_than_id */2", ...
)
def fetch(self, more_than_id: int) -> ... :
    pass
```

You can customise the results of select query by the decorator's argument `result_type`.
The argument `result_type` needs to be specified a class or sequence of a class.
In the case that results of select query is more than one object, you need specify the `result_type` as sequence of a class. (for example, `List[...]`)
```python
@twinsqla.select(
    ... , result_type=List[Staff]
)
def fetch(...) -> List[Staff]:
    pass
```
In the above code, each one result of select query is convert to Staff instance, and `fetch()` method returns list of Staff.

##### Insert

Other examples, to insert a record, you can use `twinsqla.insert()` function decorator.
```python
@twinsqla.insert()
def insert(self, staff: Staff):
    pass
```
The `insert()` decorator automatically build insert query with `Staff` instance which class decorated by `@table()` with table_name.
```python
> query = sqlalchemy.sql.text("INSERT INTO staff(staff_name, age) VALUES (:staff_name, :age)")
> engine.execute(query, {staff_name: staff.staff_name, age: staff.age})
```

By other way, you can build insert query by your hand as following.
```python
@twinsqla.insert("INSERT INTO staff(staff_name, age) VALUES (:staff_name, :age)")
def insert(self, staff_name: str, age: int):
    pass
```

#### Entity class

##### Result of select

Entity class of select query needs to have the constructor with arguments of listed column names
```python
class Staff:
    def __init__(self, staff_id: int, staff_name: str, age: int):
        self.staff_id: int = staff_id
        self.staff_name: str = staff_name
        self.age: int = age
```

The above code can be replaced to the following with decorated by `@dataclass()`.
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Staff:
    staff_id: int
    staff_name: str
    age: int
```

##### Insert

Entity class of insert query with automatically building needs to be decorated by `@table()` with argument of the table name and have attributes for inserting.

```python
@dataclass(frozen=True)
@table("staff", pk=autopk("staff_id"))
class Staff:
    staff_id: int = field(default=None)
    staff_name: str = field(default=None)
    age: int = field(default=None)
```

In the above code, use the `Staff` instance can insert into 'staff' table with columns 'staff_name' and 'age'. The column 'staff_id' is removed in insert query by specified `autopk('staff_id')` in `@table()`'s `pk` argument.

### Transaction
In using TWinSQLA, `TWinSQLA.transaction()` can handle database transaction by context manager via sqlalchemy api.
```python
with sqla.transaction():
    # execute query
```
When any exceptions are not occured in context block, then database transaction are commited. Otherwise, if any exceptions are occured, database transaction will be rollbacked and sqlalchemy exception are raised over context bock.

### Exceptions
In using TWinSQLA, two type base exceptions may be occured.
- `twinsqla.exceptions.TWinSQLAException`
- `sqlalchemy.exc.SQLAlchemyError`

`TWinSQLAException` is occured when your queries or implementation are invalid.
The other hand, `SQLAlchemyError` is raised by sqlalchemy.

In implementation, you need to consider about handling [sqlalchemy.exc.DBAPIError](https://docs.sqlalchemy.org/en/13/core/exceptions.html#sqlalchemy.exc.DBAPIError), which raised in database operation failed.

## API Reference

### `twinsqla.TWinSQLA`
```python
    def __init__(self, engine: sqlalchemy.engine.base.Engine, *,
                 available_dynamic_query: bool = True,
                 sql_file_root: Optional[Union[Path, str]] = None,
                 cache_size: Optional[int] = 128):
        ...
    """
    Args:
        engine (sqlalchemy.engine.base.Engine): SQLAlchemy engine instance.
        available_dynamic_query (bool, optional):
            If True, then two-ways SQL is available.
            If False, sql statements are not converted in executing
            but executed as it is specified. Defaults to True.
        sql_file_root (Optional[Union[Path, str]], optional):
            Specify the root directory of sql files. Defaults to None.
        cache_size (Optional[int], optional):
            Cache size of loaded query function. Defaults to 128.
    """
```

### `TWinSQLA.transaction()`

### `twinsqla.select()`, `TWinSQLA.select()`
```python
def select(query: Optional[str] = None, *, sql_path: Optional[str] = None,
           result_type: Type[Any] = Tuple[OrderedDict, ...],
           iteratable: bool = False):
    """
    Function decorator of select operation.
    Only one argument `query` or `sql_path` must be specified.

    In called decorated method, the processing implemented by the method
    is not executed, but arguments of method are used for bind parameters.

    Args:
        query (Optional[str], optional):
            select query (available TwoWay SQL). Defaults to None.
        sql_path (Optional[str], optional):
            file path with sql (available TwoWay SQL). Defaults to None.
        result_type (Type[Any], optional):
            return type. Defaults to Tuple[OrderedDict, ...].
        iteratable (bool, optional):
            When you want to fetching iterataly result, then True specified
            and returned ResultIterator object. Defaults to False.

    Returns:
        Callable: Function decorator
    """
```

### `twinsqla.insert()`, `TWinSQLA.insert()`
```python
def insert(query: Optional[str] = None, *, sql_path: Optional[str] = None,
           table_name: Optional[str] = None, result_type: Type[Any] = None,
           iteratable: bool = False):
    """
    Function decorator of insert operation.
    In constructing insert query by yourself, you need to specify either
    one of the arguments `query` or `sql_path`.

    In neither `query` nor `sql_path` are specified, this decorator creates
    insert query with arguments of decorated method.
    In this case, you need to specify inserted table name by decorator
    argument 'table_name' or decorating '@twinsqla.table' to entity class.

    Args:
        query (Optional[str], optional):
            insert query (available TwoWay SQL). Defaults to None.
        sql_path (Optional[str], optional):
            file path with sql (available TwoWay SQL). Defaults to None.
        table_name (Optional[str], optional):
            table name for inserting. Defaults to None.
        result_type (Type[Any], optional):
            When constructing "INSERT RETURNING" query, it is useful to
            specify return type. Defaults to None.
        iteratable (bool, optional):
            In almost cases, this argument need not to specified.
            The only useful case is in using "INSERT RETURNING" query.
            Defaults to False.

    Returns:
        Callable: Function decorator for insert query
    """
```

### `twinsqla.update()`, `TWinSQLA.update()`
```python
def update(query: Optional[str] = None, *, sql_path: Optional[str] = None,
           table_name: Optional[str] = None,
           condition_columns: Optional[Union[str, Tuple[str, ...]]] = None,
           result_type: Type[Any] = None, iteratable: bool = False):
    """
    Function decorator of update operation.
    In constructing update query by yourself, you need to specify either
    one of the arguments `query` or `sql_path`.

    In neither `query` nor `sql_path` are specified, this decorator creates
    update query with arguments of decorated method.
    In this case, you need follows.
        1. To specify updated table name
            by decorating '@twinsqla.table' to entity class.
            or by decorator argument 'table_name'
        2. To specifry the column names for using WHERE conditions
            by decorating '@twinsqla.table' with `pk` parameter
            or by decorator argument 'condition_columns'.

    Args:
        query (Optional[str], optional):
            update query (available TwoWay SQL). Defaults to None.
        sql_path (Optional[str], optional):
            file path with sql (available TwoWay SQL). Defaults to None.
        table_name (Optional[str], optional):
            table name for updating. Defaults to None.
        condition_columns (Optional[Union[str, Tuple[str, ...]]], optional):
            column names in WHERE condition. In almost cases, you are
            recommended to specify primary key names of the table.
            Defaults to None.
        result_type (Type[Any], optional):
            When constructing "UPDATE RETURNING" query, it is useful to
            specify return type. Defaults to None.
        iteratable (bool, optional):
            In almost cases, this argument need not to specified.
            The only useful case is in using "UPDATE RETURNING" query.
            Defaults to False.

    Returns:
        Callable: Function decorator for update query
    """
```

### `twinsqla.delete()`, `TWinSQLA.delete()`
```python
def delete(query: Optional[str] = None, *, sql_path: Optional[str] = None,
           table_name: Optional[str] = None,
           condition_columns: Optional[Union[str, Tuple[str, ...]]] = None,
           result_type: Type[Any] = None, iteratable: bool = False):
    """
    Function decorator of delete operation.
    In constructing delete query by yourself, you need to specify either
    one of the arguments `query` or `sql_path`.

    In neither `query` nor `sql_path` are specified, this decorator creates
    delete query with arguments of decorated method.
    In this case, you need follows.
        1. To specify updated table name
            by decorating '@twinsqla.table' to entity class.
            or by decorator argument 'table_name'
        2. To specifry the column names for using WHERE conditions
            by decorating '@twinsqla.table' with `pk` parameter
            or by decorator argument 'condition_columns'.

    Args:
        query (Optional[str], optional):
            delete query (available TwoWay SQL). Defaults to None.
        sql_path (Optional[str], optional):
            file path with sql (available TwoWay SQL). Defaults to None.
        table_name (Optional[str], optional):
            table name for deleting. Defaults to None.
        condition_columns (Optional[Union[str, Tuple[str, ...]]], optional):
            column names in WHERE condition. In almost cases, you are
            recommended to specify primary key names of the table.
            Defaults to None.
        result_type (Type[Any], optional):
            When constructing "DELETE RETURNING" query, it is useful to
            specify return type. Defaults to None.
        iteratable (bool, optional):
            In almost cases, this argument need not to specified.
            The only useful case is in using "DELETE RETURNING" query.
            Defaults to False.

    Returns:
        Callable: Function decorator for delete query
    """
```

### `twinsqla.execute()`, `TWinSQLA.execute()`
```python
def execute(query: Optional[str] = None, *, sql_path: Optional[str] = None,
            result_type: Type[Any] = Tuple[OrderedDict, ...],
            iteratable: bool = False):
    """
    Function decorator of any operation.
    Only one argument `query` or `sql_path` must be specified.

    In called decorated method, the processing implemented by the method
    is not executed, but arguments of method are used for bind parameters.

    Args:
        query (Optional[str], optional):
            any query (available TwoWay SQL). Defaults to None.
        sql_path (Optional[str], optional):
            file path with sql (available TwoWay SQL). Defaults to None.
        result_type (Type[Any], optional):
            return type. Defaults to Tuple[OrderedDict, ...].
        iteratable (bool, optional):
            When you want to fetching iterataly result, then True specified
            and returned ResultIterator object. Defaults to False.

    Returns:
        Callable: Function decorator
    """
```

## SQL Template
### Bind variable

TWinSQLA's two-way SQL can handle the bind parameter named *some_parameter* as follow.
```sql
/* :some_parameter */_dummy_value_
```
Where, *_dummy_value_* is ignored in TWinSQLA dynamic query.

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


### ~~Bind variable with iterator~~ (Not yet implemented)

(Not yet implemented handling iterable binding parameter)
```sql
SELECT * FROM table_name
WHERE keys IN /* :some_values */(300, 305, 317)
```


### Python expression variable

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


### IF block (Basic usage)

Definition of dynamic if-block
```sql
/*%if _python_expression_ */ sql_expression
[ /*%elif _python_expression_ */ dummy_op sql_expression [...] ]
[ /*%else*/ dummy_op sql_expression ]
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


### IF block (Advanced usage)

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


### ~~FOR block~~ (Not yet implemented)

sample
```sql
SELECT * FROM table_name
WHERE
    /*%for item in iterator */
    some_column = /* item */'dummy'
    /*%or*/
    /*%end*/
```
