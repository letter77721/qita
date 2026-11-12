"""Restricted algebra grammar, never eval user formulas or use parse_expr."""
import ast
import re
import sympy as sp


def expression(text):
    if len(text)>180: raise ValueError('formula too long')
    tree=ast.parse(text.replace('^','**'),mode='eval')
    if sum(1 for _ in ast.walk(tree))>80: raise ValueError('formula too complex')
    def visit(node):
        if isinstance(node,ast.Expression): return visit(node.body)
        if isinstance(node,ast.Name) and len(node.id)<=20: return sp.Symbol(node.id)
        if isinstance(node,ast.Constant) and type(node.value) in (int,float) and abs(node.value)<1e6: return sp.Rational(str(node.value))
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.USub,ast.UAdd)):
            return -visit(node.operand) if isinstance(node.op,ast.USub) else visit(node.operand)
        if isinstance(node,ast.BinOp):
            a,b=visit(node.left),visit(node.right)
            if isinstance(node.op,ast.Add): return a+b
            if isinstance(node.op,ast.Sub): return a-b
            if isinstance(node.op,ast.Mult): return a*b
            if isinstance(node.op,ast.Div) and b!=0: return a/b
            if isinstance(node.op,ast.Pow) and b.is_Integer and abs(b)<=4: return a**b
        raise ValueError('unsupported algebra')
    result=visit(tree)
    if result.has(sp.zoo,sp.nan,sp.oo): raise ValueError('undefined algebra')
    return result


def compare(a,b):
    """Return unknown for differing symbols or unsupported notation."""
    try:
        lhs_a,rhs_a=a.split('='); lhs_b,rhs_b=b.split('=')
        if lhs_a.strip()!=lhs_b.strip(): return 'unknown'
        x,y=expression(rhs_a.strip()),expression(rhs_b.strip())
        if x.free_symbols!=y.free_symbols: return 'unknown'
        return 'equivalent' if sp.cancel(x-y)==0 else 'different'
    except (ValueError,SyntaxError,TypeError,RecursionError): return 'unknown'


def extract(quote):
    # Explicit multiplication only: implicit handwriting and LaTeX stay for human review.
    match=re.search(r'(?<![A-Za-z_])([A-Za-z][A-Za-z_0-9]*\s*=\s*[A-Za-z0-9_+*/^(). \-]+)',quote)
    return match.group(1).strip() if match else None
