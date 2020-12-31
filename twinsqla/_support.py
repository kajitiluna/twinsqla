from typing import Callable, Type, Any, List, Optional
from collections import OrderedDict
from inspect import signature

from .exceptions import NoSpecifiedInstanceException


def _find_instance(obj_type: Type[Any], obj_names: List[str],
                   func: Callable, args: tuple, kwargs: dict) -> Any:

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


def _merge_arguments_to_dict(func: Callable, args: tuple, kwargs: dict,
                             except_values: list = []) -> OrderedDict:

    func_signature: signature = signature(func)
    key_values: OrderedDict = OrderedDict()

    param_names: List[str] = list(func_signature.parameters.keys())
    target_args: tuple = args
    if param_names[0] == "self":
        param_names = param_names[1:]
        target_args = target_args[1:]

    for index, param_name in enumerate(param_names):
        if index < len(target_args):
            param_value: Any = target_args[index]
            if param_value not in except_values:
                key_values[param_name] = param_value
            continue

        if not kwargs:
            break

        param_value: Optional[Any] = kwargs.get(param_name)
        if (param_value is not None) and (param_names not in except_values):
            key_values[param_name] = param_value

    return key_values
