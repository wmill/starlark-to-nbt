//! `json.dumps(value, indent=2, sort_keys=True) + "\n"`, byte for byte.
//!
//! That is the format of `.meta.json` and the `--debug-dir` stage files.
//! Python's defaults apply: `ensure_ascii` (non-ASCII becomes `\uXXXX`,
//! astral characters become surrogate pairs), floats use `float.__repr__`,
//! and non-finite floats are `NaN` / `Infinity` / `-Infinity`.

use std::fmt::Write;

use crate::val::{py_float_repr, Val};

pub fn dumps(value: &Val) -> String {
    let mut out = String::new();
    write_value(&mut out, value, 0);
    out.push('\n');
    out
}

fn indent(out: &mut String, level: usize) {
    out.push('\n');
    out.extend(std::iter::repeat_n(' ', level * 2));
}

fn write_value(out: &mut String, value: &Val, level: usize) {
    match value {
        Val::Null => out.push_str("null"),
        Val::Bool(true) => out.push_str("true"),
        Val::Bool(false) => out.push_str("false"),
        Val::Int(i) => {
            let _ = write!(out, "{i}");
        }
        Val::Float(f) if f.is_nan() => out.push_str("NaN"),
        Val::Float(f) if f.is_infinite() => out.push_str(if *f > 0.0 { "Infinity" } else { "-Infinity" }),
        Val::Float(f) => out.push_str(&py_float_repr(*f)),
        Val::Str(s) => write_string(out, s),
        Val::List(items) if items.is_empty() => out.push_str("[]"),
        Val::List(items) => {
            out.push('[');
            for (i, item) in items.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                indent(out, level + 1);
                write_value(out, item, level + 1);
            }
            indent(out, level);
            out.push(']');
        }
        Val::Dict(map) if map.is_empty() => out.push_str("{}"),
        Val::Dict(map) => {
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort_unstable();
            out.push('{');
            for (i, key) in keys.into_iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                indent(out, level + 1);
                write_string(out, key);
                out.push_str(": ");
                write_value(out, &map[key], level + 1);
            }
            indent(out, level);
            out.push('}');
        }
    }
}

fn write_string(out: &mut String, s: &str) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            // Control characters and all non-ASCII; DEL (0x7f) stays raw.
            c if (c as u32) < 0x20 || (c as u32) >= 0x80 => {
                let mut units = [0u16; 2];
                for unit in c.encode_utf16(&mut units) {
                    let _ = write!(out, "\\u{unit:04x}");
                }
            }
            c => out.push(c),
        }
    }
    out.push('"');
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::val::from_json;

    #[test]
    fn matches_python_json_dumps() {
        let v = from_json(r#"{"b": [1, 2.5, {}], "a": {"z": null, "y": []}, "c": true}"#);
        assert_eq!(dumps(&v), "{\n  \"a\": {\n    \"y\": [],\n    \"z\": null\n  },\n  \"b\": [\n    1,\n    2.5,\n    {}\n  ],\n  \"c\": true\n}\n");
        assert_eq!(dumps(&Val::List(vec![])), "[]\n");
    }

    #[test]
    fn escapes_like_ensure_ascii() {
        // json.dumps("é\"\\\x01\x7f🙂 ") ==
        assert_eq!(dumps(&Val::Str("é\"\\\u{1}\u{7f}🙂\u{2028}".into())), "\"\\u00e9\\\"\\\\\\u0001\u{7f}\\ud83d\\ude42\\u2028\"\n");
        assert_eq!(dumps(&Val::Float(f64::NAN)), "NaN\n");
        assert_eq!(dumps(&Val::Float(1e16)), "1e+16\n");
    }
}
