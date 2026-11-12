//! `Val`: the JSON-compatible tree that Starlark constructors produce.
//!
//! This is the boundary type between evaluation and validation. Both the
//! Python shim (Python dicts) and, later, the Rust Starlark runtime convert
//! into `Val`, and `schema` parses only from `Val`.
//!
//! Equality and `repr` follow Python semantics, because the Python pipeline
//! is the spec: `1 == 1.0 == True` and dict equality ignores order.

use indexmap::IndexMap;
use std::fmt::Write;

pub type Dict = IndexMap<String, Val>;

#[derive(Clone, Debug)]
pub enum Val {
    Null,
    Bool(bool),
    Int(i64),
    Float(f64),
    Str(String),
    List(Vec<Val>),
    Dict(Dict),
}

impl Val {
    /// Python truthiness (`if value:`).
    pub fn truthy(&self) -> bool {
        match self {
            Val::Null => false,
            Val::Bool(b) => *b,
            Val::Int(i) => *i != 0,
            Val::Float(f) => *f != 0.0,
            Val::Str(s) => !s.is_empty(),
            Val::List(l) => !l.is_empty(),
            Val::Dict(d) => !d.is_empty(),
        }
    }

    pub fn as_str(&self) -> Option<&str> {
        match self {
            Val::Str(s) => Some(s),
            _ => None,
        }
    }

    pub fn is_null(&self) -> bool {
        matches!(self, Val::Null)
    }

    /// Python `repr()` of the equivalent Python value.
    pub fn py_repr(&self) -> String {
        let mut out = String::new();
        self.write_repr(&mut out);
        out
    }

    fn write_repr(&self, out: &mut String) {
        match self {
            Val::Null => out.push_str("None"),
            Val::Bool(true) => out.push_str("True"),
            Val::Bool(false) => out.push_str("False"),
            Val::Int(i) => {
                let _ = write!(out, "{i}");
            }
            Val::Float(f) => out.push_str(&py_float_repr(*f)),
            Val::Str(s) => out.push_str(&py_str_repr(s)),
            Val::List(items) => {
                out.push('[');
                for (i, item) in items.iter().enumerate() {
                    if i > 0 {
                        out.push_str(", ");
                    }
                    item.write_repr(out);
                }
                out.push(']');
            }
            Val::Dict(map) => {
                out.push('{');
                for (i, (key, value)) in map.iter().enumerate() {
                    if i > 0 {
                        out.push_str(", ");
                    }
                    out.push_str(&py_str_repr(key));
                    out.push_str(": ");
                    value.write_repr(out);
                }
                out.push('}');
            }
        }
    }
}

/// Numeric view for Python-style cross-type comparison.
enum Num {
    Int(i64),
    Float(f64),
}

fn num(v: &Val) -> Option<Num> {
    match v {
        Val::Bool(b) => Some(Num::Int(*b as i64)),
        Val::Int(i) => Some(Num::Int(*i)),
        Val::Float(f) => Some(Num::Float(*f)),
        _ => None,
    }
}

/// Exact int/float comparison, as Python does it (no lossy cast of the int).
/// An integral f64 below 2^127 converts to i128 exactly; larger ones
/// saturate to a value no i64 can equal, so the comparison stays exact.
fn int_eq_float(i: i64, f: f64) -> bool {
    f.is_finite() && f.fract() == 0.0 && (f as i128) == i as i128
}

impl PartialEq for Val {
    fn eq(&self, other: &Val) -> bool {
        if let (Some(a), Some(b)) = (num(self), num(other)) {
            return match (a, b) {
                (Num::Int(a), Num::Int(b)) => a == b,
                (Num::Float(a), Num::Float(b)) => a == b,
                (Num::Int(i), Num::Float(f)) | (Num::Float(f), Num::Int(i)) => int_eq_float(i, f),
            };
        }
        match (self, other) {
            (Val::Null, Val::Null) => true,
            (Val::Str(a), Val::Str(b)) => a == b,
            (Val::List(a), Val::List(b)) => a == b,
            // IndexMap equality is order-insensitive, like Python dicts.
            (Val::Dict(a), Val::Dict(b)) => a == b,
            _ => false,
        }
    }
}

/// Python `float.__repr__`: shortest round-trip digits, positional for
/// exponents in [-4, 16), scientific (`1e+16`, `1.5e-05`) otherwise.
pub fn py_float_repr(f: f64) -> String {
    if f.is_nan() {
        return "nan".into();
    }
    if f.is_infinite() {
        return if f > 0.0 { "inf".into() } else { "-inf".into() };
    }
    if f == 0.0 {
        return if f.is_sign_negative() { "-0.0".into() } else { "0.0".into() };
    }
    // Rust's LowerExp without precision is also shortest round-trip.
    let formatted = format!("{f:e}");
    let (mantissa, exponent) = formatted.split_once('e').expect("LowerExp has an exponent");
    let exponent: i32 = exponent.parse().expect("integer exponent");
    let negative = mantissa.starts_with('-');
    let digits: String = mantissa.chars().filter(|c| c.is_ascii_digit()).collect();
    let mut out = String::new();
    if negative {
        out.push('-');
    }
    if !(-4..16).contains(&exponent) {
        out.push_str(&digits[..1]);
        if digits.len() > 1 {
            out.push('.');
            out.push_str(&digits[1..]);
        }
        let sign = if exponent < 0 { '-' } else { '+' };
        let _ = write!(out, "e{sign}{:02}", exponent.abs());
    } else if exponent >= 0 {
        let int_len = exponent as usize + 1;
        if digits.len() <= int_len {
            out.push_str(&digits);
            out.extend(std::iter::repeat_n('0', int_len - digits.len()));
            out.push_str(".0");
        } else {
            out.push_str(&digits[..int_len]);
            out.push('.');
            out.push_str(&digits[int_len..]);
        }
    } else {
        out.push_str("0.");
        out.extend(std::iter::repeat_n('0', (-exponent - 1) as usize));
        out.push_str(&digits);
    }
    out
}

/// Approximation of Python's `str.isprintable` for repr escaping: control
/// characters, separators other than space, and a few format characters are
/// escaped. Exact Unicode category tables are not worth carrying here.
fn py_printable(c: char) -> bool {
    let u = c as u32;
    !(u < 0x20
        || (0x7f..=0xa0).contains(&u)
        || u == 0xad
        || u == 0x1680
        || (0x2000..=0x200f).contains(&u)
        || (0x2028..=0x202f).contains(&u)
        || (0x205f..=0x206f).contains(&u)
        || u == 0x3000
        || u == 0xfeff
        || (0xe000..=0xf8ff).contains(&u))
}

/// Python `str.__repr__`.
pub fn py_str_repr(s: &str) -> String {
    let quote = if s.contains('\'') && !s.contains('"') { '"' } else { '\'' };
    let mut out = String::with_capacity(s.len() + 2);
    out.push(quote);
    for c in s.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '\t' => out.push_str("\\t"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            c if c == quote => {
                out.push('\\');
                out.push(c);
            }
            c if py_printable(c) => out.push(c),
            c if (c as u32) < 0x100 => {
                let _ = write!(out, "\\x{:02x}", c as u32);
            }
            c if (c as u32) < 0x10000 => {
                let _ = write!(out, "\\u{:04x}", c as u32);
            }
            c => {
                let _ = write!(out, "\\U{:08x}", c as u32);
            }
        }
    }
    out.push(quote);
    out
}

#[cfg(test)]
pub(crate) fn from_json(text: &str) -> Val {
    fn convert(v: serde_json::Value) -> Val {
        match v {
            serde_json::Value::Null => Val::Null,
            serde_json::Value::Bool(b) => Val::Bool(b),
            serde_json::Value::Number(n) => match n.as_i64() {
                Some(i) => Val::Int(i),
                None => Val::Float(n.as_f64().expect("finite number")),
            },
            serde_json::Value::String(s) => Val::Str(s),
            serde_json::Value::Array(items) => Val::List(items.into_iter().map(convert).collect()),
            serde_json::Value::Object(map) => Val::Dict(map.into_iter().map(|(k, v)| (k, convert(v))).collect()),
        }
    }
    convert(serde_json::from_str(text).expect("valid test JSON"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn float_repr_matches_python() {
        let cases = [
            (1e16, "1e+16"),
            (1.5e-5, "1.5e-05"),
            (0.0001, "0.0001"),
            (123456789012345678.0, "1.2345678901234568e+17"),
            (-0.0, "-0.0"),
            (5.0, "5.0"),
            (0.1, "0.1"),
            (2.5, "2.5"),
            (1234.5, "1234.5"),
            (-90.0, "-90.0"),
            (9999999999999998.0, "9999999999999998.0"),
            (f64::INFINITY, "inf"),
        ];
        for (value, expected) in cases {
            assert_eq!(py_float_repr(value), expected, "{value}");
        }
    }

    #[test]
    fn str_repr_matches_python() {
        assert_eq!(py_str_repr("it's"), "\"it's\"");
        assert_eq!(py_str_repr("a\"b"), "'a\"b'");
        assert_eq!(py_str_repr("x'y\"z"), "'x\\'y\"z'");
        assert_eq!(py_str_repr("tab\tnl\n\x7f\u{a0}é"), "'tab\\tnl\\n\\x7f\\xa0é'");
    }

    #[test]
    fn repr_of_containers() {
        assert_eq!(from_json(r#"[1, "a", null, true, {"k": 2.5}]"#).py_repr(), "[1, 'a', None, True, {'k': 2.5}]");
    }

    #[test]
    fn equality_follows_python_numeric_rules() {
        assert_eq!(Val::Int(1), Val::Float(1.0));
        assert_eq!(Val::Bool(true), Val::Int(1));
        assert_ne!(Val::Float(f64::NAN), Val::Float(f64::NAN));
        assert_ne!(Val::Int(1), Val::Str("1".into()));
        assert_eq!(from_json(r#"{"a": 1, "b": 2}"#), from_json(r#"{"b": 2, "a": 1}"#));
    }
}
