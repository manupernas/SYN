"""Huella de referencia del motor de vídeo de SYN 1.0.2b.

Ambos AST se generan con el mismo Python, evitando hashes incompatibles
entre versiones. La instantánea está en syn_backend_reference.txt.
"""
import ast
import hashlib
from pathlib import Path


def baseline_digest(name):
    text = (Path(__file__).resolve().parent / "syn_backend_reference.txt").read_text("utf-8")
    tree = ast.parse(text)
    found = [node for node in ast.walk(tree)
             if isinstance(node, ast.ClassDef) and node.name == name]
    if len(found) != 1:
        raise AssertionError(f"Referencia ausente o ambigua: {name}")
    return hashlib.sha256(ast.dump(found[0], include_attributes=False).encode()).hexdigest()
