from services.formula_checker import compare

def test_equivalent_and_different():
    assert compare('Re=rho*v*L/mu','Re=v*L*rho/mu')=='equivalent'
    assert compare('Re=rho*v*L/mu','Re=2*rho*v*L/mu')=='different'

def test_different_symbols_cannot_be_judged():
    assert compare('Re=rho*v*L/mu','Re=v*L/nu')=='unknown'

def test_no_code_or_expensive_exponents():
    assert compare('x=__import__("os")','x=1')=='unknown'
    assert compare('x=a**99999999','x=a')=='unknown'
