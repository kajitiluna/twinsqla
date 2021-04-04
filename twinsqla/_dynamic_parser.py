from typing import Optional, Union, Tuple, List, Dict
from abc import ABCMeta, abstractmethod

from lark import Lark, Transformer, Tree, v_args, LarkError

from ._support import description
from .exceptions import QueryParseFailedException


class TwinQuery():
    pass


@description("query")
class StaticQuery(TwinQuery):
    def __init__(self, query: str):
        self.query: str = query


@description("python_expr")
class PythonExprQuery(TwinQuery):
    def __init__(self, python_expr: str):
        self.python_expr: str = python_expr


@description("alternatives")
class AlternativeQuery(TwinQuery):
    def __init__(self, alternatives: List[Tuple[str, List[TwinQuery]]]):
        self.alternatives: List[Tuple[str, List[TwinQuery]]] = alternatives


@description(("start_pos", "end_pos"))
class QueryRange():

    def __init__(self, start_pos: int, end_pos: int):
        self.start_pos: int = start_pos
        self.end_pos: int = end_pos

    def sort_key(self) -> Tuple[int, int]:
        return (self.start_pos, (-1) * self.end_pos)

    def extract(self, text: str) -> str:
        return text[self.start_pos:self.end_pos]


@description("bind_param")
class BindParameter():

    def __init__(self, bind_param: str):
        self.bind_param: str = bind_param

    def build_param(self, query: str) -> StaticQuery:
        return StaticQuery(self.bind_param)


@description("python_expr_range")
class PythonEvaluatedValue():

    def __init__(self, python_expr_range: QueryRange):
        self.python_expr_range: QueryRange = python_expr_range

    def expr(self, text: str) -> str:
        return self.python_expr_range.extract(text)

    def build_param(self, query: str) -> PythonExprQuery:
        return PythonExprQuery(self.expr(query))


class TwinFactor(metaclass=ABCMeta):

    @abstractmethod
    def build_query(self, query: str, dynamic_params: list) -> TwinQuery:
        pass


@description(("original_range", "dynamic_factor"))
class DynamicFactor(TwinFactor):

    def __init__(self, original_range: QueryRange,
                 dynamic_factor: Union[BindParameter, PythonEvaluatedValue]):

        self.original_range: QueryRange = original_range
        self.dynamic_factor: Union[BindParameter,
                                   PythonEvaluatedValue] = dynamic_factor

    def build_query(self, query: str, dynamic_params: list) -> TwinQuery:
        return self.dynamic_factor.build_param(query)


@description(("python_condition", "query_expr_tree"))
class ConditionalExpression():

    def __init__(self, python_condition: PythonEvaluatedValue,
                 query_expr_tree: Tree):

        self.python_condition: PythonEvaluatedValue = python_condition
        self.query_expr_tree: Tree = query_expr_tree

    def condition_expr(self, query: str) -> str:
        return self.python_condition.expr(query)


@description(("original_range", "conditional_exprs", "else_expr"))
class AlternativeFactor(TwinFactor):

    def __init__(self, original_range: QueryRange,
                 conditional_exprs: List[ConditionalExpression],
                 else_expr: Optional[Tree]):

        self.original_range: QueryRange = original_range
        self.conditional_exprs: List[ConditionalExpression] = conditional_exprs
        self.else_expr: Optional[Tree] = else_expr

    def build_query(self, query: str, dynamic_params: list) -> TwinQuery:
        alternatives: List[Tuple[str, List[TwinQuery]]] = []

        for conditional in self.conditional_exprs:
            condition: str = conditional.condition_expr(query)
            subqueries: List[TwinQuery] = _parse_query(
                conditional.query_expr_tree, query, dynamic_params)

            alternatives.append((condition, subqueries))

        if self.else_expr is not None:
            subqueries: List[TwinQuery] = _parse_query(
                self.else_expr, query, dynamic_params)
            alternatives.append(("True", subqueries))

        return AlternativeQuery(alternatives)


class QueryTransformer(Transformer):

    def query_statement(self, children: list):
        return children[0]

    def query_expr(self, children: list):
        return children[0]

    @v_args(tree=True)
    def dynamic_if_bool(self, tree: Tree):
        children: list = tree.children
        first_if_expr = children[0].children[0]
        first_then_expr = children[1]

        alternative_units: List[ConditionalExpression] = [
            ConditionalExpression(
                python_condition=PythonEvaluatedValue(
                    python_expr_range=QueryRange(
                        start_pos=first_if_expr.meta.start_pos,
                        end_pos=first_if_expr.meta.end_pos
                    )
                ),
                query_expr_tree=first_then_expr
            )
        ]

        elseif_tree = children[2]
        if elseif_tree:
            for elseif_node in elseif_tree.children:
                elseif_expr = elseif_node.children[0].children[0]
                else_then_expr = elseif_node.children[2]
                alternative_units.append(
                    ConditionalExpression(
                        python_condition=PythonEvaluatedValue(
                            python_expr_range=QueryRange(
                                start_pos=elseif_expr.meta.start_pos,
                                end_pos=elseif_expr.meta.end_pos
                            )
                        ),
                        query_expr_tree=else_then_expr
                    )
                )

        else_expr = children[3].children[1] if (
            children[3] is not None) else None

        return AlternativeFactor(
            original_range=QueryRange(start_pos=tree.meta.start_pos,
                                      end_pos=tree.meta.end_pos),
            conditional_exprs=alternative_units,
            else_expr=else_expr
        )

    @v_args(tree=True)
    def twoway_bind_text(self, tree: Tree):
        return self._twoway_binding(tree)

    @v_args(tree=True)
    def twoway_bind_bool(self, tree: Tree):
        return self._twoway_binding(tree)

    @v_args(tree=True)
    def twoway_bind_numeric(self, tree: Tree):
        return self._twoway_binding(tree)

    def _twoway_binding(self, tree: Tree):
        return DynamicFactor(
            original_range=QueryRange(start_pos=tree.meta.start_pos,
                                      end_pos=tree.meta.end_pos),
            dynamic_factor=tree.children[0]
        )

    def twoway_bind_param(self, children: list):
        return children[0]

    def bind_param(self, children: list):
        bind_param: str = children[0].value
        return BindParameter(bind_param)

    @v_args(tree=True)
    def dynamic_value(self, tree: Tree):
        return PythonEvaluatedValue(
            python_expr_range=QueryRange(start_pos=tree.meta.start_pos,
                                         end_pos=tree.meta.end_pos)
        )


class DynamicQuery():

    def __init__(self, query_func: callable,
                 pydynamic_params: Dict[str, callable]):

        self.query_func: callable = query_func
        self.pydynamic_params: Dict[str, callable] = pydynamic_params


class DynamicParser():

    def __init__(self):
        from pathlib import Path

        self.parser: Lark = Lark.open(
            Path(__file__).parent / "sql.two_way.lark",
            start="query_statement",
            propagate_positions=True,
            maybe_placeholders=True
        )
        self.transformer: QueryTransformer = QueryTransformer()

    def parse(self, query: str, arg_keys: Tuple[str]) -> DynamicQuery:
        try:
            return self._do_parse(query, arg_keys)
        except LarkError as lark_exc:
            raise QueryParseFailedException(
                f"Failed to parse dynamic query. Detail : {lark_exc}"
            ) from lark_exc

    def _do_parse(self, query: str, arg_keys: Tuple[str]) -> DynamicQuery:

        root_tree: Tree = self.parser.parse(query)
        dynamic_params: List[TwinFactor] = self._seek_dynamic_params(
            root_tree)
        parsed_queries: List[TwinQuery] = _parse_query(
            root_tree, query, dynamic_params)

        dynamic_query, pydynamic_params = _do_build_query(
            parsed_queries, ", ".join(arg_keys))

        return DynamicQuery(eval(dynamic_query), pydynamic_params)

    def _seek_dynamic_params(self, root: Tree) -> List[TwinFactor]:

        dynamic_params: List[TwinFactor] = []
        for target_data in (
            "twoway_bind_text", "twoway_bind_bool", "twoway_bind_numeric",
            "dynamic_if_bool"
        ):

            dynamic_trees: List[Tree] = root.find_data(target_data)
            dynamic_params.extend(
                [self.transformer.transform(dynamic_tree)
                 for dynamic_tree in dynamic_trees]
            )

        dynamic_params.sort(key=lambda param: param.original_range.sort_key())
        return dynamic_params


def _parse_query(
    tree: Tree, query: str, dynamic_params: List[TwinFactor]
) -> List[TwinQuery]:

    target_params = filter(
        lambda param: (
            (param.original_range.start_pos >= tree.meta.start_pos)
            and (param.original_range.end_pos <= tree.meta.end_pos)
        ),
        dynamic_params
    )

    build_queries: List[TwinQuery] = []
    index: int = tree.meta.start_pos
    for param in target_params:
        if index > param.original_range.start_pos:
            continue

        build_queries.append(StaticQuery(
            query[index:param.original_range.start_pos]))
        index = param.original_range.end_pos

        build_queries.append(param.build_query(query, dynamic_params))

    if index < tree.meta.end_pos:
        build_queries.append(StaticQuery(query[index:tree.meta.end_pos]))

    return build_queries


def _do_build_query(
    parsed_queries: List[TwinQuery], func_arguments: str,
    current_params: Optional[Dict[str, callable]] = None,
    current_condition: Optional[str] = None
) -> Tuple[str, Dict[str, callable]]:

    pydynamic_params: Dict[str, callable] = current_params \
        if current_params else {}

    dynamic_queries: List[str] = []
    for index, parsed_query in enumerate(parsed_queries):
        if isinstance(parsed_query, StaticQuery):
            dynamic_queries.append(f"{repr(parsed_queries[index].query)}")
            continue

        if isinstance(parsed_query, PythonExprQuery):
            # append python evaluation to bind_params
            dynamic_param: str = f"pydynamic_param{len(pydynamic_params)}"
            dynamic_queries.append(f'":{dynamic_param}"')
            param_condition: str = f" if ({current_condition}) else None" \
                if current_condition else ""

            pydynamic_params[dynamic_param] = eval(
                f"lambda {func_arguments}:"
                f"(({parsed_query.python_expr}){param_condition})"
            )
            continue

        if isinstance(parsed_query, AlternativeQuery):
            dynamic_sub_query, updated_params = _do_build_for_alternative(
                parsed_query.alternatives, func_arguments, pydynamic_params,
                current_condition)
            dynamic_queries.append(dynamic_sub_query)
            pydynamic_params = updated_params
            continue

        # TODO
        raise Exception("Not implemented.")

    return (
        f"""(lambda {func_arguments}:( {' + '.join(dynamic_queries)} ))""",
        pydynamic_params
    )


def _do_build_for_alternative(
    alternatives: List[Tuple[str, List[TwinQuery]]],
    func_arguments: str, current_params: Dict[str, callable],
    current_condition: Optional[str] = None
) -> Tuple[str, Dict[str, callable]]:

    if len(alternatives) == 0:
        return ("'FALSE'", current_params)

    condition, sub_queries = alternatives[0]

    else_condition: str = \
        f"({current_condition} and (not bool({condition})))" \
        if current_condition else f"(not bool({condition}))"
    later_sub_query, pydynamic_params = _do_build_for_alternative(
        alternatives[1:], func_arguments, current_params, else_condition
    )

    sub_condition: str = f"bool({condition}) and {current_condition}" \
        if current_condition else f"bool({condition})"
    sub_expr, updated_params = _do_build_query(
        sub_queries, func_arguments, pydynamic_params, sub_condition)

    sub_query = (
        "("
        f"{sub_expr}({func_arguments})"
        f" if bool({condition}) else {later_sub_query}"
        ")"
    )
    return (sub_query, updated_params)
