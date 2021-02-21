from typing import List
from inspect import signature


class NoQueryArgumentException(Exception):
    def __init__(self):
        super().__init__(
            "No 'query' nor 'sql_path' are specified."
            " One param needs to be specified."
        )


class DuplicatedQueryArgumentException(Exception):
    def __init__(self):
        super().__init__(
            "Both 'query' and 'sql_path' are specified."
            " Only one param can be specified."
        )


class InvalidStructureException(Exception):
    pass


class InvalidTableNameException(Exception):
    def __init__(self, table_name: str, pattern):
        super().__init__(
            f"The specified table name '{table_name}' is"
            " contained invalid charactors."
            f" Table name must be matched pattern '{pattern.name}'"
        )
        self.table_name: str = table_name


class NotFoundTableNameException(Exception):
    def __init__(self, entity: any, operation: str, param_name: str):
        super().__init__(
            f"The table name is not found in the object '{entity}'."
            " You need to choice one of implementation : "
            " to decorate '@TWinSQLA.Table' to an object's class,"
            f" to decorate '@twinsqla.{operation}(table_name)' to a method,"
            f" or to set attribute '{param_name}' to an object."
        )


class NoSpecifiedInstanceException(Exception):
    def __init__(self, func: callable):
        arguments: List[str] = [
            f"'{param}'" for param
            in signature(func).parameters.keys() if param != 'self'
        ]
        message: str = (
            f"Not found TWinSQLA object in owner of function '{func.__name__}'"
            f" nor arguments {', '.join(arguments)}."
        )
        super().__init__(message)


class NoSpecifiedEntityException(Exception):
    def __init__(self, func: callable):
        arguments: List[str] = [
            f"'{param}'" for param in signature(func).parameters.keys()
        ]
        super().__init__(
            "Not found entity to operating in function"
            f" '{func.__name__}({', '.join(arguments)})'"
        )
