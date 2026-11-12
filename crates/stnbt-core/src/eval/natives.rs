//! Math builtins (port of `starlark_runtime.MATH_FUNCTIONS` and `PI`).
//!
//! `round`, `floor`, and `ceil` return ints, like their Python versions,
//! so their results can be used as coordinates. Inputs where Python's `math`
//! raises (`sqrt(-1)`, `sin(inf)`) raise here too instead of returning NaN.
//! libm may differ in the last bit across platforms, so scripts round
//! float results before using them as coordinates.

use starlark::environment::GlobalsBuilder;
use starlark::starlark_module;
use starlark::values::float::{StarlarkFloat, UnpackFloat};
use starlark::values::{UnpackValue, Value};

fn domain_error() -> anyhow::Error {
    anyhow::anyhow!("math domain error")
}

fn to_int(f: f64) -> anyhow::Result<i64> {
    if !f.is_finite() || f < i64::MIN as f64 || f > i64::MAX as f64 {
        return Err(anyhow::anyhow!("cannot convert float {f} to integer"));
    }
    Ok(f as i64)
}

/// An int argument as i64, or a float as f64. Anything else is a type error.
enum Number {
    Int(i64),
    Float(f64),
}

fn number(x: Value<'_>, function: &str) -> anyhow::Result<Number> {
    if x.get_type() == "int" {
        return i64::unpack_value(x)
            .ok()
            .flatten()
            .map(Number::Int)
            .ok_or_else(|| anyhow::anyhow!("{function}() argument is too large"));
    }
    if let Ok(Some(f)) = StarlarkFloat::unpack_value(x) {
        return Ok(Number::Float(f.0));
    }
    Err(anyhow::anyhow!("{function}() needs an int or float, got {}", x.get_type()))
}

#[starlark_module]
pub fn math_builtins(builder: &mut GlobalsBuilder) {
    /// Exact integer square root; prefer it over sqrt() for geometry.
    fn isqrt(#[starlark(require = pos)] n: Value<'_>) -> anyhow::Result<i64> {
        match number(n, "isqrt") {
            Ok(Number::Int(i)) if i >= 0 => {
                // Float estimate, then exact correction.
                let mut r = (i as f64).sqrt() as i64;
                while r > 0 && r.checked_mul(r).is_none_or(|sq| sq > i) {
                    r -= 1;
                }
                while (r + 1).checked_mul(r + 1).is_some_and(|sq| sq <= i) {
                    r += 1;
                }
                Ok(r)
            }
            _ => Err(anyhow::anyhow!("isqrt() needs a non-negative int, got {}", n)),
        }
    }

    fn sqrt(#[starlark(require = pos)] x: UnpackFloat) -> anyhow::Result<f64> {
        let x = x.0;
        if x < 0.0 {
            return Err(domain_error());
        }
        Ok(x.sqrt())
    }

    fn sin(#[starlark(require = pos)] x: UnpackFloat) -> anyhow::Result<f64> {
        let x = x.0;
        if x.is_infinite() {
            return Err(domain_error());
        }
        Ok(x.sin())
    }

    fn cos(#[starlark(require = pos)] x: UnpackFloat) -> anyhow::Result<f64> {
        let x = x.0;
        if x.is_infinite() {
            return Err(domain_error());
        }
        Ok(x.cos())
    }

    fn atan2(#[starlark(require = pos)] y: UnpackFloat, #[starlark(require = pos)] x: UnpackFloat) -> anyhow::Result<f64> {
        Ok(y.0.atan2(x.0))
    }

    /// Round half away from zero to an int, unlike Python's banker's rounding.
    fn round(#[starlark(require = pos)] x: Value<'_>) -> anyhow::Result<i64> {
        match number(x, "round")? {
            Number::Int(i) => Ok(i),
            Number::Float(f) => Ok(to_int((f.abs() + 0.5).floor())? * if f >= 0.0 { 1 } else { -1 }),
        }
    }

    fn floor(#[starlark(require = pos)] x: Value<'_>) -> anyhow::Result<i64> {
        match number(x, "floor")? {
            Number::Int(i) => Ok(i),
            Number::Float(f) => to_int(f.floor()),
        }
    }

    fn ceil(#[starlark(require = pos)] x: Value<'_>) -> anyhow::Result<i64> {
        match number(x, "ceil")? {
            Number::Int(i) => Ok(i),
            Number::Float(f) => to_int(f.ceil()),
        }
    }

    const PI: f64 = std::f64::consts::PI;
}
