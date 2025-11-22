# smells.py
# Author: Cody
import ast
from collections import defaultdict
from typing import Dict, List, Tuple
from models import FileSmells


class DuplicateDetector(ast.NodeVisitor):
    # 通过归一化 function body 文本 + hash 来找重复
    def __init__(self):
        self.func_bodies = defaultdict(list)  # hash -> [node]

    def visit_FunctionDef(self, node: ast.FunctionDef):
        body_src = ast.get_source_segment(self.source, node) or ""
        normalized = "".join(body_src.split())  # 粗暴去空白
        key = hash(normalized)
        self.func_bodies[key].append(node)
        self.generic_visit(node)

    def run(self, tree: ast.AST, source: str) -> int:
        self.source = source
        self.visit(tree)
        # 每个 hash 如果出现 >=2 次算一个重复块
        blocks = 0
        for key, nodes in self.func_bodies.items():
            if len(nodes) >= 2:
                blocks += 1
        return blocks


class APIChecker(ast.NodeVisitor):
    # API 幻觉：访问未定义名字 / 未导入模块中的属性
    def __init__(self):
        self.defined_names = set()
        self.imported_modules = set()
        self.hallucinations = 0

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.defined_names.add(alias.asname or alias.name.split(".")[0])

    def visit_ImportFrom(self, node: ast.ImportFrom):
        for alias in node.names:
            self.defined_names.add(alias.asname or alias.name)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.defined_names.add(node.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        self.defined_names.add(node.name)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name):
                self.defined_names.add(t.id)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        # Load 且没定义，可能是 API 幻觉 / bug
        if isinstance(node.ctx, ast.Load):
            if node.id not in self.defined_names and node.id not in dir(__builtins__):
                self.hallucinations += 1

    def run(self, tree: ast.AST) -> int:
        self.visit(tree)
        return self.hallucinations


class OverEngineeringChecker(ast.NodeVisitor):
    # 过度工程 + 不必要抽象
    def __init__(self):
        self.wrappers = 0
        self.tiny_classes = 0

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # 只有一行：return other_func(...)
        if len(node.body) == 1 and isinstance(node.body[0], ast.Return):
            value = node.body[0].value
            if isinstance(value, ast.Call):
                self.wrappers += 1
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        methods = [b for b in node.body if isinstance(b, ast.FunctionDef)]
        if len(methods) <= 1:
            self.tiny_classes += 1
        self.generic_visit(node)

    def run(self, tree: ast.AST) -> Tuple[int, int]:
        self.visit(tree)
        return self.wrappers, self.tiny_classes


class SilentFailureChecker(ast.NodeVisitor):
    # Silent failure: bare except / except 后只 pass 或 simple log
    def __init__(self):
        self.count = 0

    def visit_Try(self, node: ast.Try):
        for handler in node.handlers:
            # bare except
            if handler.type is None:
                if self._is_silent(handler.body):
                    self.count += 1
            else:
                if self._is_silent(handler.body):
                    self.count += 1
        self.generic_visit(node)

    def _is_silent(self, body: List[ast.stmt]) -> bool:
        if not body:
            return True
        if len(body) == 1:
            stmt = body[0]
            if isinstance(stmt, ast.Pass):
                return True
            # 只 print / logging.info
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                func = stmt.value.func
                if isinstance(func, ast.Attribute) and func.attr in ("info", "warning", "error", "debug"):
                    return True
                if isinstance(func, ast.Name) and func.id in ("print",):
                    return True
        return False

    def run(self, tree: ast.AST) -> int:
        self.visit(tree)
        return self.count


def analyze_smells(tree: ast.AST, source: str) -> FileSmells:
    dup = DuplicateDetector()
    duplicates = dup.run(tree, source)

    api = APIChecker()
    hallucinations = api.run(tree)

    oe = OverEngineeringChecker()
    wrappers, tiny_classes = oe.run(tree)

    sf = SilentFailureChecker()
    silent = sf.run(tree)

    smells = FileSmells(
        duplicate_blocks=duplicates,
        api_hallucinations=hallucinations,
        over_engineering=wrappers,
        unnecessary_abstractions=tiny_classes,
        silent_failures=silent,
    )
    return smells
