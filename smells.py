# smells.py
# Author: Cody
"""
Static analysis for 5 AI code smells.

Input:  Python source code as text
Output: SmellScores with counts of each smell type:

  1) duplicate_blocks
  2) api_hallucinations
  3) over_engineering
  4) unnecessary_abstractions
  5) silent_failures
"""

from __future__ import annotations

import ast
import builtins
from collections import Counter
from typing import List, Set, Tuple

from models import SmellScores


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _safe_parse(source: str) -> ast.AST | None:
    """Parse Python source into an AST. Return None on syntax error."""
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def _canonicalize_node(node: ast.AST) -> str:
    """
    Canonicalize an AST node into a structural string representation.

    We:
      - normalize identifier names
      - normalize literals
      - hide attribute names

    This helps us detect duplicated *structure* even when names differ,
    which is common in AI-generated copy-paste.
    """

    class Canonicalizer(ast.NodeTransformer):
        def visit_Name(self, n: ast.Name) -> ast.AST:
            return ast.copy_location(ast.Name(id="__ID__", ctx=n.ctx), n)

        def visit_Attribute(self, n: ast.Attribute) -> ast.AST:
            self.generic_visit(n)
            return ast.copy_location(
                ast.Attribute(value=n.value, attr="__ATTR__", ctx=n.ctx),
                n,
            )

        def visit_arg(self, n: ast.arg) -> ast.AST:
            return ast.copy_location(ast.arg(arg="__ARG__", annotation=None), n)

        def visit_Constant(self, n: ast.Constant) -> ast.AST:
            return ast.copy_location(ast.Constant(value="__CONST__"), n)

    try:
        src = ast.unparse(node)
        normalized_tree = Canonicalizer().visit(ast.parse(src))
        ast.fix_missing_locations(normalized_tree)
        return ast.dump(normalized_tree, include_attributes=False)
    except Exception:
        return ast.dump(node, include_attributes=False)


def _iter_function_bodies(tree: ast.AST) -> List[ast.AST]:
    """Collect body blocks from all function / method definitions."""
    bodies: List[ast.AST] = []

    class BodyCollector(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            bodies.append(ast.Module(body=node.body, type_ignores=[]))
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            bodies.append(ast.Module(body=node.body, type_ignores=[]))
            self.generic_visit(node)

    BodyCollector().visit(tree)
    return bodies


# ---------------------------------------------------------------------
# 1) Duplicate blocks
# ---------------------------------------------------------------------


def _detect_duplicate_blocks(tree: ast.AST, source: str) -> int:
    """
    Detect duplicated code in two ways:

      A) duplicated function bodies (AST-based)
      B) duplicated text windows (line-based)

    Returns a combined count.
    """
    # A) structural duplicates
    bodies = _iter_function_bodies(tree)
    hashes: List[str] = [_canonicalize_node(b) for b in bodies]
    counter = Counter(hashes)

    structural_dups = 0
    for freq in counter.values():
        if freq >= 2:
            structural_dups += (freq - 1)

    # B) text windows
    lines_raw = source.splitlines()
    lines: List[str] = []
    for ln in lines_raw:
        s = ln.strip()
        if not s:
            continue
        if s.startswith("#"):
            continue
        lines.append(s)

    window_size = 5
    if len(lines) < 2 * window_size:
        return structural_dups

    seen: Set[Tuple[str, ...]] = set()
    text_dups = 0
    for i in range(len(lines) - window_size + 1):
        window = tuple(lines[i : i + window_size])
        if window in seen:
            text_dups += 1
        else:
            seen.add(window)

    return structural_dups + text_dups


# ---------------------------------------------------------------------
# 2) API hallucinations
# ---------------------------------------------------------------------

_BUILTIN_NAMES: Set[str] = set(dir(builtins))


def _collect_defined_names(tree: ast.AST) -> Set[str]:
    """
    Collect names that are clearly defined in this module:
      - functions, classes
      - imports
      - assignments
      - with/as targets, exception aliases, comprehension targets
    """
    defined: Set[str] = set()

    def _collect_target(target: ast.AST) -> None:
        if isinstance(target, ast.Name):
            defined.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                _collect_target(elt)

    class DefVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            defined.add(node.name)
            for arg in node.args.args + node.args.kwonlyargs:
                defined.add(arg.arg)
            if node.args.vararg:
                defined.add(node.args.vararg.arg)
            if node.args.kwarg:
                defined.add(node.args.kwarg.arg)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.visit_FunctionDef(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            defined.add(node.name)
            self.generic_visit(node)

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                defined.add(local)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            for alias in node.names:
                local = alias.asname or alias.name
                defined.add(local)

        def visit_Assign(self, node: ast.Assign) -> None:
            for t in node.targets:
                _collect_target(t)
            self.generic_visit(node)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            _collect_target(node.target)
            self.generic_visit(node)

        def visit_With(self, node: ast.With) -> None:
            for item in node.items:
                if item.optional_vars is not None:
                    _collect_target(item.optional_vars)
            self.generic_visit(node)

        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            if isinstance(node.name, str):
                defined.add(node.name)
            self.generic_visit(node)

        def visit_comprehension(self, node: ast.comprehension) -> None:
            _collect_target(node.target)
            self.generic_visit(node)

    DefVisitor().visit(tree)
    return defined


def _collect_used_names(tree: ast.AST) -> Counter:
    """Collect names that are used in Load context."""
    usage: Counter = Counter()

    class UseVisitor(ast.NodeVisitor):
        def visit_Name(self, node: ast.Name) -> None:
            if isinstance(node.ctx, ast.Load):
                usage[node.id] += 1
            self.generic_visit(node)

    UseVisitor().visit(tree)
    return usage


def _detect_api_hallucinations(tree: ast.AST) -> int:
    """
    Heuristic API hallucination detector.

    We count references to names that are:
      - not built-ins
      - not defined locally
      - not imported
      - not obviously private (starts with "_")
    """
    defined = _collect_defined_names(tree)
    used = _collect_used_names(tree)

    total = 0
    for name, count in used.items():
        if name in _BUILTIN_NAMES:
            continue
        if name in defined:
            continue
        if name.startswith("_"):
            continue
        total += count
    return total


# ---------------------------------------------------------------------
# 3) Over-engineering & unnecessary abstractions
# ---------------------------------------------------------------------


def _is_trivial_wrapper_function(node: ast.AST) -> bool:
    """
    Return True if a function is essentially a thin wrapper:

        def foo(...):
            return bar(...)

        def foo(...):
            bar(...)
    """
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False

    body = node.body
    if len(body) != 1:
        return False

    stmt = body[0]
    if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Call):
        return True
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        return True

    return False


def _class_has_state(cls: ast.ClassDef) -> bool:
    """Check whether a class writes to self.<attr> anywhere."""
    has_state = False

    class Visitor(ast.NodeVisitor):
        def visit_Attribute(self, node: ast.Attribute) -> None:
            nonlocal has_state
            if isinstance(node.value, ast.Name) and node.value.id == "self":
                has_state = True

    Visitor().visit(cls)
    return has_state


def _detect_over_engineering_and_abstractions(tree: ast.AST) -> Tuple[int, int]:
    """
    Detect:
      - over_engineering: wrapper functions / wrapper-only classes
      - unnecessary_abstractions: small stateless classes with trivial methods
    """
    over_engineering = 0
    unnecessary_abs = 0

    # module-level wrapper functions
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _is_trivial_wrapper_function(node):
                over_engineering += 1

    # class-level patterns
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        methods = [m for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
        if not methods:
            continue

        trivial_count = 0
        all_pass = True
        for m in methods:
            if _is_trivial_wrapper_function(m):
                trivial_count += 1
            if not (len(m.body) == 1 and isinstance(m.body[0], ast.Pass)):
                all_pass = False

        has_state = _class_has_state(node)

        if trivial_count == len(methods) and len(methods) > 0:
            over_engineering += 1

        if not has_state and len(methods) <= 3 and (trivial_count == len(methods) or all_pass):
            unnecessary_abs += 1

    return over_engineering, unnecessary_abs


# ---------------------------------------------------------------------
# 4) Silent failure pattern
# ---------------------------------------------------------------------


def _detect_silent_failures(tree: ast.AST) -> int:
    """
    Detect try/except blocks that swallow errors without meaningful handling.

    A handler is "silent" if:
      - bare `except:` or catching Exception/BaseException
      - and body has no `raise` or `return`
    """
    silent = 0

    def is_suspicious(exc: ast.expr | None) -> bool:
        if exc is None:
            return True
        if isinstance(exc, ast.Name) and exc.id in {"Exception", "BaseException"}:
            return True
        return False

    def has_action(body: List[ast.stmt]) -> bool:
        for stmt in body:
            if isinstance(stmt, (ast.Raise, ast.Return)):
                return True
        return False

    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if not is_suspicious(handler.type):
                continue
            if has_action(handler.body):
                continue
            silent += 1

    return silent


# ---------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------


def analyze_smells(source: str) -> SmellScores:
    """Main API used by analyzers.py."""
    tree = _safe_parse(source)
    if tree is None:
        return SmellScores(
            duplicate_blocks=0,
            api_hallucinations=0,
            over_engineering=0,
            unnecessary_abstractions=0,
            silent_failures=0,
        )

    dup = _detect_duplicate_blocks(tree, source)
    api = _detect_api_hallucinations(tree)
    over_eng, unnecessary_abs = _detect_over_engineering_and_abstractions(tree)
    silent = _detect_silent_failures(tree)

    return SmellScores(
        duplicate_blocks=dup,
        api_hallucinations=api,
        over_engineering=over_eng,
        unnecessary_abstractions=unnecessary_abs,
        silent_failures=silent,
    )
