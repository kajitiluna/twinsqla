from typing import List
from inspect import signature


class NoQueryArgumentException(Exception):
    def __init__(self):
        super().__init__("No 'query' nor 'sql_path' are specified. One param needs to be specified.")


class DuplicatedQueryArgumentException(Exception):
    def __init__(self):
        super().__init__("Both 'query' and 'sql_path' are specified. Only one param can be specified.")


class InvalidStructureException(Exception):
    pass


class NoSpecifiedInstanceException(Exception):
    def __init__(self, func: callable):
        arguments: List[str] = [
            f"'{param}'" for param in signature(func).parameters.keys() if param != 'self'
        ]
        message: str = (
            f"Not found TWinSQLA object in owner of function '{func.__name__}' "
            f"nor arguments {', '.join(arguments)}."
        )
        super().__init__(message)
