# -*- coding: utf8 -*-
    
"""
Converts expressions from SymPy and Sage to Mathics expressions.
Conversion to SympPy and Sage is handled directly in BaseExpression descendants.
"""

u"""
    Mathics: a general-purpose computer algebra system
    Copyright (C) 2011 Jan Pöschko

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import sympy

from UserList import UserList
    
sage_symbol_prefix = '_Mathics_User_'
sympy_symbol_prefix = sage_symbol_prefix

def create_symbol(self, name):
    from mathics.core import expression
    
    if name.startswith(sage_symbol_prefix):
        name = name[len(sage_symbol_prefix):]
    return expression.Symbol(name)
        
class ConvertSubstitutions(object):
    head_name = '___SageSubst___'
    
    def __init__(self):
        self.subs = []
        
    def substitute(self, expr):
        from mathics.core import expression
        
        index = len(self.subs)
        self.subs.append(expr)
        return expression.Expression(self.head_name, expression.Integer(index), *expr.get_atoms())
    
class SympyExpression(sympy.basic.Basic):
    is_Function = True
    nargs = None
    
    def __new__(cls, expr):
        obj = sympy.basic.Basic.__new__(cls)
        obj.expr = expr
        obj._args = (expr.head.to_sympy(),) + tuple(leaf.to_sympy() for leaf in expr.leaves)
        return obj
    
    def new(self, *args):
        from mathics.core import expression
        
        expr = expression.Expression(from_sympy(args[0]), *(from_sympy(arg) for arg in args[1:]))
        return SympyExpression(expr)
        
    @property
    def func(self):
        from mathics.core import expression
        
        class SympyExpressionFunc(object):
            def __new__(cls, *args):
                return SympyExpression(expression.Expression(self.expr.head, *(from_sympy(arg) for arg in args[1:])))
        return SympyExpressionFunc
        
    def has_any_symbols(self, *syms):
        result = any(arg.has_any_symbols(*syms) for arg in self.args)
        return result
    
    def _eval_subs(self, old, new):
        if self == old:
            return new
        old, new = from_sympy(old), from_sympy(new)
        old_name = old.get_name()
        if old_name:
            new_expr = self.expr.replace_vars({old_name: new})
            return SympyExpression(new_expr)
        return self
        
    def _eval_rewrite(self, pattern, rule, **hints):
        return self
       
def from_sympy(expr):
    from mathics.builtin import sympy_to_mathics
    from mathics.core.expression import Symbol, Integer, Rational, Real, Expression
    
    if isinstance(expr, (tuple, list)):
        return Expression('List', *[from_sympy(item) for item in expr])
    if expr is None:
        return Symbol('Null')
    if isinstance(expr, sympy.Matrix):
        return Expression('List', *[Expression('List', *[from_sympy(item) for item in row]) for row in expr.tolist()])
    if expr.is_Atom:
        name = None
        if expr.is_Symbol:
            name = unicode(expr)
            if isinstance(expr, sympy.core.symbol.Dummy):
                name = name + ('__Dummy_%d' % expr.dummy_index)
                return Symbol(name, sympy_dummy=expr)
            if name.startswith(sage_symbol_prefix):
                name = name[len(sage_symbol_prefix):]
        elif expr.is_NumberSymbol:
            name = unicode(expr)
        if name is not None:
            builtin = sympy_to_mathics.get(name)
            if builtin is not None:
                name = builtin.get_name()
            return Symbol(name)
        elif isinstance(expr, (sympy.core.numbers.Infinity, sympy.core.numbers.ComplexInfinity)):
            return Symbol(expr.__class__.__name__)
        elif isinstance(expr, sympy.core.numbers.NegativeInfinity):
            return Expression('Times', Integer(-1), Symbol('Infinity'))
        elif isinstance(expr, sympy.core.numbers.ImaginaryUnit):
            return Symbol('I')
        elif isinstance(expr, sympy.core.numbers.Integer):
            return Integer(expr.p)
        elif isinstance(expr, sympy.core.numbers.Rational):
            return Rational(expr.p, expr.q)
        elif isinstance(expr, sympy.core.numbers.Real):
            return Real(expr.num)
        elif isinstance(expr, sympy.core.function.FunctionClass):
            return Symbol(unicode(expr))
    elif expr.is_Add:
        return Expression('Plus', *(from_sympy(arg) for arg in expr.args))
    elif expr.is_Mul:
        return Expression('Times', *(from_sympy(arg) for arg in expr.args))
    elif expr.is_Pow:
        return Expression('Power', *(from_sympy(arg) for arg in expr.args))
    
    elif isinstance(expr, SympyExpression):
        return expr.expr
    
    elif expr.is_Function or isinstance(expr, (sympy.Integral, sympy.Derivative)):
        if isinstance(expr, sympy.Integral):
            name = 'Integral'
        elif isinstance(expr, sympy.Derivative):
            name = 'Derivative'
        else:
            name = expr.func.__name__
        args = [from_sympy(arg) for arg in expr.args]
        builtin = sympy_to_mathics.get(name)
        if builtin is not None:
            name = builtin.get_name()
            args = builtin.from_sympy(args)
        else:
            if name.startswith(sage_symbol_prefix):
                name = name[len(sage_symbol_prefix):]
        return Expression(Symbol(name), *args)
    
    else:
        raise ValueError("Unknown SymPy expression: %s" % expr)
    
try:
    # sage converter (if sage is present)
    
    import operator
    
    from sage.symbolic.expression_conversions import Converter
    from sage.rings.number_field.number_field_element_quadratic import NumberFieldElement_quadratic
    from sage.symbolic.constants import Constant
    from sage.rings.integer import is_Integer
    from sage.rings.complex_number import is_ComplexNumber
    from sage.rings.real_mpfr import is_RealNumber
    from sage.structure.element import is_Vector
    from sage import all as sage
    
    class MathicsConverter(Converter):
        def __init__(self, subs=None):
            super(MathicsConverter, self).__init__(use_fake_div=False)
            self.subs = subs
            
        def __call__(self, ex=None):
            if hasattr(ex, 'pyobject'):
                return super(MathicsConverter, self).__call__(ex)
            else:
                return self.pyobject(ex, ex)
            
        def create_symbol(self, name):
            from mathics.core import expression
            
            if name.startswith(sage_symbol_prefix):
                name = name[len(sage_symbol_prefix):]
            return expression.Symbol(name)
            
        def symbol(self, ex):
            return self.create_symbol(unicode(ex))
        
        def arithmetic(self, ex, op):
            from mathics.core import expression
            
            if op == operator.add:
                head = 'Plus'
            elif op == operator.mul:
                head = 'Times'
            elif op == operator.pow:
                head = 'Power'
            else:
                head = 'UNKNOWN'
                
            operands = map(self, ex.operands())
            if head in ['Plus', 'Times']:
                # normalize arguments so that expressions don't change
                # when Sage does not change them
                operands.sort()
            
            return expression.Expression(head, *operands)
        
        def pyobject(self, ex, obj):
            from mathics.core import expression
            from mathics.core.expression import Number
            
            if obj is None:
                return expression.Symbol('Null')
            elif isinstance(obj, (list, tuple)) or is_Vector(obj):
                return expression.Expression('List', *(from_sage(item, self.subs) for item in obj))
            elif isinstance(obj, Constant):
                return expression.Symbol(obj._conversions.get('mathematica', obj._name))
            elif is_Integer(obj):
                return expression.Integer(str(obj))
            elif isinstance(obj, sage.Rational):
                rational = expression.Rational(str(obj))
                if rational.value.denom() == 1:
                    return expression.Integer(rational.value.numer())
                else:
                    return rational
            elif isinstance(obj, sage.RealDoubleElement) or is_RealNumber(obj):
                return expression.Real(str(obj))
            elif is_ComplexNumber(obj):
                real = Number.from_string(str(obj.real())).value
                imag = Number.from_string(str(obj.imag())).value
                return expression.Complex(real, imag)
            elif isinstance(obj, NumberFieldElement_quadratic):
                # TODO: this need not be a complex number, but we assume so!
                real = Number.from_string(str(obj.real())).value
                imag = Number.from_string(str(obj.imag())).value
                return expression.Complex(real, imag)
            else:
                return expression.from_python(obj)
            
        def derivative(self, ex, operator):
            params = operator.parameter_set()
            counts = {}
            for param in params:
                if param in counts:
                    counts[param] += 1
                else:
                    counts[param] = 1
            new_params = []
            for index, count in counts.items():
                if len(new_params) <= index:
                    new_params.extend([0] * (index - len(new_params) + 1))
                new_params[index] = count
            f = self.create_symbol(repr(operator.function()))
            return expression.Expression(expression.Expression('Derivative',
                *(expression.Integer(count) for count in new_params)), f)
            
        def composition(self, ex, operator):
            from mathics.core import expression
            from mathics.builtin import sage_to_mathics
        
            func_name = repr(operator)
            builtin = sage_to_mathics.get(func_name)
            leaves = map(self, ex.operands())
            if builtin is not None:
                head = expression.Symbol(builtin.get_name())
                leaves = builtin.from_sage(leaves)
            else:
                head = self.create_symbol(func_name)
            
            result = expression.Expression(head, *leaves)
            
            if self.subs is not None and result.has_form(ConvertSubstitutions.head_name, 1, None):
                index = result.leaves[0]
                return self.subs.subs[index.value]
            else:
                return result
    
    def from_sage(expr, subs=None):
        from mathics.builtin import sage_to_mathics
        
        converter = MathicsConverter(subs)
        return converter(expr)
    
    def to_sage(expressions, evaluation):
        subs = ConvertSubstitutions()
        
        def convert_item(item):
            " Recursively convert lists/tuples of Mathics expressions "
            
            if isinstance(item, (list, tuple)):
                return [convert_item(expr) for expr in item]
            else:
                return item.to_sage(evaluation.definitions, subs)
            
        result = convert_item(expressions)
        return result, subs
    
except (ImportError, RuntimeError):
    def from_sage(expr, subs=None):
        return None
    
    def to_sage(expressions, definitions):
        return [], None
