"""Matematik dvigatel (EduTech.docx: "Photomath uslubi") — SymPy asosida.

Formula matnini qabul qilib:
  - tenglamani yechadi (chiziqli/kvadrat uchun qadam-baqadam),
  - ifodani soddalashtiradi / ko'paytuvchilarga ajratadi,
  - natijani doskaga qo'yiladigan chiroyli (unicode) ko'rinishda qaytaradi.
"""
from sympy import Eq, Poly, Rational, diff, expand, factor, integrate, pretty, simplify, solve, sqrt, symbols  # noqa: F401
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

_TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)

MAX_LEN = 300


class MathError(ValueError):
    pass


def _parse(text: str):
    try:
        return parse_expr(text, transformations=_TRANSFORMS, evaluate=True)
    except Exception as exc:  # sympy har xil xato turini otadi
        raise MathError(f"Ifodani tushunolmadim: {exc}") from exc


def _pretty(obj) -> str:
    return pretty(obj, use_unicode=True)


def _quadratic_steps(poly: Poly, var) -> list[str]:
    """ax^2+bx+c=0 uchun diskriminant qadamlari — Photomath uslubidagi tushuntirish."""
    a, b, c = (poly.all_coeffs() + [0, 0, 0])[:3]
    d = b * b - 4 * a * c
    steps = [
        f'Kvadrat tenglama: a={a}, b={b}, c={c}',
        f'Diskriminant: D = b² − 4ac = ({b})² − 4·({a})·({c}) = {d}',
    ]
    if d > 0:
        x1 = simplify((-b + sqrt(d)) / (2 * a))
        x2 = simplify((-b - sqrt(d)) / (2 * a))
        steps.append('D > 0 — ikkita ildiz bor:')
        steps.append(f'x₁ = (−b + √D) / 2a = {x1}')
        steps.append(f'x₂ = (−b − √D) / 2a = {x2}')
    elif d == 0:
        x1 = simplify(Rational(-b, 2 * a))
        steps.append(f'D = 0 — bitta ildiz: x = −b / 2a = {x1}')
    else:
        steps.append('D < 0 — haqiqiy ildiz yo‘q (kompleks ildizlar).')
    return steps


def solve_math(text: str) -> dict:
    """Kirish: '2x^2 - 5x + 3 = 0' yoki 'x^2 - 9' kabi matn. Chiqish: natija + qadamlar."""
    text = (text or '').strip()
    if not text:
        raise MathError('Formula kiriting.')
    if len(text) > MAX_LEN:
        raise MathError('Formula juda uzun.')

    steps: list[str] = []
    if '=' in text:
        lhs_s, rhs_s = text.split('=', 1)
        lhs, rhs = _parse(lhs_s), _parse(rhs_s)
        expr = simplify(lhs - rhs)
        free = sorted(expr.free_symbols, key=lambda s: s.name)
        if not free:
            ok = simplify(lhs - rhs) == 0
            return {
                'input': text,
                'pretty': _pretty(Eq(lhs, rhs)),
                'result': "To'g'ri tenglik ✓" if ok else "Noto'g'ri tenglik ✗",
                'steps': [],
            }
        var = free[0]
        try:
            poly = Poly(expr, var)
            if poly.degree() == 2 and len(free) == 1:
                steps = _quadratic_steps(poly, var)
            elif poly.degree() == 1 and len(free) == 1:
                a, b = (poly.all_coeffs() + [0, 0])[:2]
                steps = [
                    f'Chiziqli tenglama: {a}·{var} + ({b}) = 0',
                    f'{var} = {simplify(Rational(-1) * b / a) if a else "—"}',
                ]
        except Exception:  # noqa: BLE001 — polinom bo'lmasa qadamlar shart emas
            pass
        roots = solve(Eq(lhs, rhs), var)
        result = ', '.join(f'{var} = {r}' for r in roots) if roots else 'Yechim topilmadi'
        return {
            'input': text,
            'pretty': _pretty(Eq(lhs, rhs)),
            'result': result,
            'steps': steps,
        }

    # tenglik yo'q — soddalashtirish / ko'paytuvchilarga ajratish
    expr = _parse(text)
    simplified = simplify(expr)
    factored = factor(expr)
    steps = []
    if simplified != expr:
        steps.append(f'Soddalashtirilgan: {simplified}')
    if factored not in (expr, simplified):
        steps.append(f"Ko'paytuvchilar: {factored}")
    return {
        'input': text,
        'pretty': _pretty(expr),
        'result': str(simplified if simplified != expr else factored),
        'steps': steps,
    }
