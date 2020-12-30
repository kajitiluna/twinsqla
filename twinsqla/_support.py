from typing import Callable, Type, Any, List, Optional
from inspect import signature

from .exceptions import NoSpecifiedEntityException
from .exceptions import NoSpecifiedInstanceException


def _find_instance(obj_type: Type[Any], obj_names: List[str],
                   func: Callable, *args, **kwargs) -> Any:

    own_obj = getattr(func, "__self__", None) or (
        args[0] if signature(func).parameters.get("self") and len(args) > 0
        else None
    )

    if own_obj:
        for obj_name in obj_names:
            twinsqla_obj: Optional[obj_type] = _find_instance_specified(
                obj_type, own_obj, obj_name)
            if twinsqla_obj:
                return twinsqla_obj

        for param in vars(own_obj).values():
            if isinstance(param, obj_type):
                return param

    result: Optional[obj_type] = (
        _find_instance_fullscan(obj_type, args)
        or _find_instance_fullscan(obj_type, kwargs.values())
    )
    if result:
        return result

    raise NoSpecifiedInstanceException(func)


def _find_instance_specified(
    obj_type: Type[Any], target_obj: Any, param_name
) -> Optional[Any]:

    target = getattr(target_obj, param_name, None)
    return target if target and isinstance(target, obj_type) else None


def _find_instance_fullscan(obj_type: Type[Any], values) -> Optional[Any]:
    if not values:
        return None
    for value in values:
        if isinstance(value, obj_type):
            return value
    return None


def _find_entity(func: Callable, except_list: list, *args, **kwargs) -> Any:
    if "entity" in kwargs:
        return kwargs["entity"]

    index_start: int = 1 if signature(func).parameters.get("self") else 0
    for target in args[index_start:]:
        if target not in except_list:
            return target

    raise NoSpecifiedEntityException(func)


def _merge_arguments_to_dict(func: Callable, *args, **kwargs) -> dict:
    if not args:
        return kwargs

    key_values: dict = kwargs
    func_signature: signature = signature(func)

    positional_args_dict: dict = {
        name: value for name, value in zip(
            func_signature.parameters.keys(), args
        ) if name != "self"
    }
    key_values.update(positional_args_dict)
    return key_values
