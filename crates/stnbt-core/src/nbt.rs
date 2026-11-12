//! Minimal big-endian NBT writer: just the tags structure files use.
//!
//! Output matches nbtlib byte for byte: the root is a compound with an
//! empty name, compounds keep insertion order, and lists carry their element
//! type id (an empty list still needs one; callers choose it). Strings are
//! written as standard UTF-8, as nbtlib does, not Java's modified UTF-8.
//! The difference only shows for NUL and non-BMP characters.

#[derive(Clone, Debug, PartialEq)]
pub enum Tag {
    Byte(i8),
    Int(i32),
    Float(f32),
    Double(f64),
    String(String),
    List(List),
    Compound(Compound),
}

#[derive(Clone, Debug, PartialEq)]
pub struct List {
    pub element: u8,
    pub items: Vec<Tag>,
}

pub type Compound = Vec<(String, Tag)>;

pub const BYTE: u8 = 1;
pub const INT: u8 = 3;
pub const FLOAT: u8 = 5;
pub const DOUBLE: u8 = 6;
pub const STRING: u8 = 8;
pub const LIST: u8 = 9;
pub const COMPOUND: u8 = 10;

impl Tag {
    pub fn id(&self) -> u8 {
        match self {
            Tag::Byte(_) => BYTE,
            Tag::Int(_) => INT,
            Tag::Float(_) => FLOAT,
            Tag::Double(_) => DOUBLE,
            Tag::String(_) => STRING,
            Tag::List(_) => LIST,
            Tag::Compound(_) => COMPOUND,
        }
    }

    /// nbtlib's tag class name, for error messages.
    pub fn type_name(id: u8) -> &'static str {
        match id {
            BYTE => "Byte",
            INT => "Int",
            FLOAT => "Float",
            DOUBLE => "Double",
            STRING => "String",
            LIST => "List",
            COMPOUND => "Compound",
            _ => "End",
        }
    }
}

/// A typed list. Every item must carry the element type.
pub fn list(element: u8, items: Vec<Tag>) -> Result<Tag, String> {
    if let Some(bad) = items.iter().find(|t| t.id() != element) {
        return Err(format!("{} item should be a {} tag", Tag::type_name(bad.id()), Tag::type_name(element)));
    }
    Ok(Tag::List(List { element, items }))
}

pub fn ints(values: &[i32]) -> Tag {
    Tag::List(List { element: INT, items: values.iter().map(|v| Tag::Int(*v)).collect() })
}

pub fn doubles(values: &[f64]) -> Tag {
    Tag::List(List { element: DOUBLE, items: values.iter().map(|v| Tag::Double(*v)).collect() })
}

pub fn floats(values: &[f32]) -> Tag {
    Tag::List(List { element: FLOAT, items: values.iter().map(|v| Tag::Float(*v)).collect() })
}

/// Serialize a root compound (unnamed), as `nbtlib.File(root).write`.
pub fn write_root(root: &Compound) -> Result<Vec<u8>, String> {
    let mut out = Vec::with_capacity(1 << 16);
    out.push(COMPOUND);
    write_string(&mut out, "")?;
    write_compound(&mut out, root)?;
    Ok(out)
}

fn write_string(out: &mut Vec<u8>, s: &str) -> Result<(), String> {
    let len = u16::try_from(s.len()).map_err(|_| format!("string of {} bytes exceeds the NBT limit of 65535", s.len()))?;
    out.extend_from_slice(&len.to_be_bytes());
    out.extend_from_slice(s.as_bytes());
    Ok(())
}

fn write_compound(out: &mut Vec<u8>, items: &Compound) -> Result<(), String> {
    for (name, tag) in items {
        out.push(tag.id());
        write_string(out, name)?;
        write_payload(out, tag)?;
    }
    out.push(0);
    Ok(())
}

fn write_payload(out: &mut Vec<u8>, tag: &Tag) -> Result<(), String> {
    match tag {
        Tag::Byte(v) => out.push(*v as u8),
        Tag::Int(v) => out.extend_from_slice(&v.to_be_bytes()),
        Tag::Float(v) => out.extend_from_slice(&v.to_be_bytes()),
        Tag::Double(v) => out.extend_from_slice(&v.to_be_bytes()),
        Tag::String(s) => write_string(out, s)?,
        Tag::List(list) => {
            out.push(list.element);
            out.extend_from_slice(&(list.items.len() as i32).to_be_bytes());
            for item in &list.items {
                write_payload(out, item)?;
            }
        }
        Tag::Compound(items) => write_compound(out, items)?,
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hex(bytes: &[u8]) -> String {
        use std::fmt::Write;
        bytes.iter().fold(String::new(), |mut out, b| {
            let _ = write!(out, "{b:02x}");
            out
        })
    }

    #[test]
    fn matches_nbtlib_bytes() {
        // nbtlib: File(Compound({"a": List[String]([]), "b": List[Compound]([])}))
        let root = vec![
            ("a".to_owned(), list(STRING, vec![]).unwrap()),
            ("b".to_owned(), list(COMPOUND, vec![]).unwrap()),
        ];
        assert_eq!(hex(&write_root(&root).unwrap()), "0a0000090001610800000000090001620a0000000000");
        // Head of a real structure: DataVersion 4438, size [3, 15, ...].
        let root = vec![("DataVersion".to_owned(), Tag::Int(4438)), ("size".to_owned(), ints(&[3, 15]))];
        assert!(hex(&write_root(&root).unwrap()).starts_with("0a000003000b4461746156657273696f6e0000115609000473697a6503000000020000000300"));
    }

    #[test]
    fn rejects_mixed_lists_and_long_strings() {
        assert_eq!(list(INT, vec![Tag::Int(1), Tag::String("a".into())]).unwrap_err(), "String item should be a Int tag");
        assert!(write_root(&vec![("s".into(), Tag::String("x".repeat(70_000)))]).is_err());
    }
}
