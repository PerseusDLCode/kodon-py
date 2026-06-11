# Two-Pass TEI Parser with `citeStructure` + `cRefPattern` Fallback

## Background

The parser currently does a single SAX pass over a TEI XML `<body>`, managing a
`textpart_stack` manually to track citation structure. It uses
`get_citable_elements()` to parse `cRefPattern` XPath replacement patterns via
regex to find non-`<div>` elements that carry citation `@n` values (e.g. `<l>`).

The goal is to replace this with a two-pass architecture driven by
`refsDecl[@n='cite-structure']` / `citeStructure` elements when present, falling
back to the existing `cRefPattern` path when not. Both paths must produce
identical output shapes.

### Why two passes?

- **Pass 1 (structure):** `citeStructure` XPath expressions already describe the
  navigation structure precisely. Evaluating them with lxml replaces the ad-hoc
  textpart stack.
- **Pass 2 (content):** NLP tokenization still requires walking each leaf
  element's subtree with paratext filtering. XPath selects the entry points; the
  walk extracts the content.
- **Rendering:** Consumers get the same enriched dict; HTML serialization can be
  done from either the dict or the lxml tree — that is a consumer concern, not a
  parser concern.

### `citeStructure` attributes

```xml
<refsDecl n="cite-structure">
  <citeStructure use="@n" match="//body/div/div[@subtype='book']" unit="book">
    <citeStructure use="@n" match="div[@subtype='chapter']" unit="chapter" delim=".">
      <citeStructure use="@n" match="div[@subtype='section']" unit="section" delim=".">
      </citeStructure>
    </citeStructure>
  </citeStructure>
</refsDecl>
```

| Attribute | Values | Meaning |
|-----------|--------|---------|
| `match`   | XPath fragment | Root level: absolute (starts with `//body/…`). Nested: relative to parent match context. |
| `use`     | `@n` or `position()` | How to derive the citation value for this level. |
| `unit`    | string | Human-readable level name, e.g. `"book"`. Used for TOC labels. |
| `delim`   | string | Separator between citation components, e.g. `"."`. |

---

## New Data Structures

### `CiteStructureLevel` dataclass

Add near the top of `tei_parser.py`, after module-level constants. Requires
`from dataclasses import dataclass, field`.

```python
@dataclass
class CiteStructureLevel:
    unit: str                            # e.g. "book", "chapter", "section"
    match: str                           # raw XPath fragment from the attribute
    use: str                             # "@n" or "position()"
    delim: str                           # separator, e.g. "."
    children: list["CiteStructureLevel"] # nested levels
    absolute_xpath: str                  # computed during parse; empty until then
```

---

## New Standalone Functions

### 1. `parse_cite_structure(tree)` → `list[CiteStructureLevel]`

Reads `refsDecl[@n='cite-structure']` and returns a list of top-level
`CiteStructureLevel` objects with fully resolved `absolute_xpath` fields.
Returns `[]` if no `citeStructure` is present — this triggers the fallback.

**XPath building rules:**

- Root-level `match` (e.g. `//body/div/div[@subtype='book']`) is used directly
  as the absolute XPath.
- Nested `match` values (e.g. `div[@subtype='chapter']`, or bare `p`) are
  concatenated onto the parent's absolute XPath:
  `//body/div/div[@subtype='book']` + `div[@subtype='chapter']`
  → `//body/div/div[@subtype='book']/div[@subtype='chapter']`
- All XPath evaluation uses `namespaces=NAMESPACES` so `tei:` prefixes work.

**Signature:**
```python
def parse_cite_structure(tree: etree._ElementTree) -> list[CiteStructureLevel]:
```

---

### 2. `resolve_cite_structure(tree, levels, base_urn)` → flat list of tuples

Pass 1. Evaluates each level's absolute XPath against the lxml tree and
recursively builds the flat list of addressable nodes.

**Returns:** `list[tuple[str, etree._Element, int, list[str], CiteStructureLevel]]`
i.e. `(urn, element, depth, location, level)` — one tuple per leaf node, in
document order (lxml preserves document order automatically).

**Citation value derivation:**

- `use="@n"` → `element.get("n", "")`
- `use="position()"` → 1-based sibling position among elements with the same
  tag under the same parent. Use a `defaultdict(int)` keyed by
  `(id(parent_element), tag)`. The counter resets per parent because it is local
  to each recursive call frame.

**Signature:**
```python
def resolve_cite_structure(
    tree: etree._ElementTree,
    levels: list[CiteStructureLevel],
    base_urn: str,
) -> list[tuple[str, etree._Element, int, list[str], CiteStructureLevel]]:
```

---

### 3. `build_textpart_from_element(element, urn, index, depth, level, location)` → `dict`

Constructs a textpart dict matching the current output shape. Replaces
`add_textpart_to_stack()` for the new code path.

Key mapping from new → old:

- `subtype = level.unit` (e.g. `"book"`) — replaces inferring from XML
  `@subtype`. Because well-formed files set `@subtype` to the same value as
  `unit`, `create_table_of_contents()` needs no changes.
- `type = "textpart"`
- `depth`, `index`, `location`, `urn` as before
- Does **not** set `tokens` — that is Pass 2's responsibility

**Signature:**
```python
def build_textpart_from_element(
    element: etree._Element,
    urn: str,
    index: int,
    depth: int,
    level: CiteStructureLevel,
    location: list[str],
) -> dict:
```

---

### 4. `walk_element_subtree(...)` → `(elements, tokens, updated_global_index)`

Pass 2. Iterative DFS over the lxml subtree rooted at a single leaf textpart
element. Replaces the SAX `startElementNS` / `endElementNS` / `characters` loop
for the new code path.

**Paratext handling:** Maintain a suppressed-subtree depth counter. When a node's
local name is in `PARATEXTUAL_ELEMENTS`, increment the counter; decrement on
exit. While the counter is > 0, do not emit tokens. This fixes a latent bug in
the SAX path where entering any non-paratext child of a `<note>` incorrectly
clears `inside_paratext` via `toggle_inside_paratext`.

**`element.tail` text:** In lxml, tail text belongs to the parent element's
context. The walk must attribute tail text to the *parent* element's `children`
list, mirroring SAX `characters` behaviour.

**`citable_elements` handling:** When a node's local name is in
`citable_elements` and it has an `@n` attribute, update the local
`current_textpart_urn` for this node and its descendants (matching
`handle_element` logic).

**`speaker` / `l` backfill:** Track a local `pending_speaker` variable. When a
`citable_element` with `@n` is encountered and `pending_speaker` is set, call
the existing `_rewrite_element_urn(pending_speaker, current_textpart_urn)`.

**Signature:**
```python
def walk_element_subtree(
    element: etree._Element,
    textpart_urn: str,
    textpart_index: int,
    base_urn: str,
    tokenize_fn: Callable[[str], list],
    global_element_index: int,
    citable_elements: frozenset[str],
) -> tuple[list[dict], list[dict], int]:
    # returns (elements, tokens_for_textpart, updated_global_element_index)
```

---

### 5. `process_tokens_standalone(...)` → `(text_run | None, updated_index)`

Decouples token processing from SAX state. `TEIParser.process_tokens()` becomes
a thin wrapper around this, so both code paths share the logic.

**Signature:**
```python
def process_tokens_standalone(
    tokens: list,
    current_textpart_urn: str,
    textpart_tokens: list[dict],
    inside_paratext: bool,
    global_element_index: int,
) -> tuple[dict | None, int]:
```

---

## Changes to `TEIParser`

### `__init__`

After building metadata (`author`, `editionStmt`, etc.) but before parsing the
body:

1. Call `_extract_urn_and_language()` to set `self.urn` and `self.language`
   (currently set inside `handle_div` during SAX — must happen earlier for the
   new path).
2. Call `parse_cite_structure(self.tree)`.
3. Branch:

```python
cite_structure_levels = parse_cite_structure(self.tree)

if cite_structure_levels:
    self.citable_elements = self._get_citable_elements_from_cite_structure(cite_structure_levels)
    self._run_cite_structure_pass(cite_structure_levels)
else:
    self.citable_elements = self._get_citable_elements_from_cref()
    for body in self.tree.iterfind(".//tei:body", namespaces=NAMESPACES):
        lxml.sax.saxify(body, self)
```

---

### `_extract_urn_and_language()` — new

Finds the work-level `<div>` and sets `self.urn` and `self.language` from it.
Currently this happens inside `handle_div` during SAX traversal.

```python
def _extract_urn_and_language(self) -> None:
    XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
    for work_type in WORK_TYPES:
        div = self.tree.find(
            f".//tei:body/tei:div[@type='{work_type}']",
            namespaces=NAMESPACES,
        )
        if div is not None:
            self.language = div.get(XML_LANG)
            self.urn = div.get("n")
            return
```

---

### `_run_cite_structure_pass(levels)` — new

Orchestrates Pass 1 and Pass 2.

1. **Populate `textpart_labels`:** Walk `levels` depth-first, collect
   `level.unit` in order, assign to `self.textpart_labels`.
2. **Pass 1:** Call `resolve_cite_structure(self.tree, levels, self.urn)`.
3. **Pass 2:** For each `(urn, element, depth, location, level)` tuple:
   - Build the textpart dict via `build_textpart_from_element(...)` and append
     to `self.textparts`.
   - Call `walk_element_subtree(element, urn, textpart_index, self.urn,
     self.tokenize, self.global_element_index, self.citable_elements)`.
   - Extend `self.elements` with the returned elements list.
   - Set `self.textparts[i]["tokens"]` to the returned token list.
   - Update `self.global_element_index`.

**Signature:**
```python
def _run_cite_structure_pass(self, levels: list[CiteStructureLevel]) -> None:
```

---

### `get_citable_elements()` → split into two methods

Rename existing method to `_get_citable_elements_from_cref()`. Add:

```python
def _get_citable_elements_from_cite_structure(
    self, levels: list[CiteStructureLevel]
) -> frozenset[str]:
```

This walks the leaf levels and extracts tagnames from non-`div` `match`
attributes (e.g. `"p"` from `match="p"`, `"l"` from
`match="l[@n='$1']"`). Returns a `frozenset[str]`.

`__init__` assigns `self.citable_elements` from whichever method is appropriate
(see `__init__` section above).

---

### `process_tokens()` — thin wrapper

```python
def process_tokens(self, tokens):
    text_run, self.global_element_index = process_tokens_standalone(
        tokens,
        self.current_textpart_urn,
        self.textpart_stack[-1].get("tokens", []) if self.textpart_stack else [],
        self.inside_paratext,
        self.global_element_index,
    )
    return text_run
```

---

### Everything SAX-related — unchanged

`startElementNS`, `endElementNS`, `characters`, `handle_div`, `handle_element`,
`add_textpart_to_stack`, `determine_location`, `toggle_inside_paratext` are all
kept as-is for the fallback path.

---

## Output Shape Contract

Both paths must produce identical dict structures. Key invariant:

- `textpart["subtype"]` is set to the `unit` value from `citeStructure` in the
  new path, and to the XML `@subtype` attribute in the fallback. For well-formed
  files these coincide (the `@subtype` of the div *is* the unit name).
- `create_table_of_contents()` and `nest_textparts()` require no changes.
- `TextpartDict.subtype` in `document.py` should be documented to note the dual
  source.

---

## Known Scope Boundary

The `toggle_inside_paratext` bug in the SAX path — where entering any
non-paratext child element inside a `<note>` incorrectly clears
`inside_paratext` — is fixed implicitly by the suppressed-subtree counter in
`walk_element_subtree`. Fixing it in the SAX path is out of scope for this
refactor.

---

## Tests to Add

File: `tests/test_cite_structure.py`

| Test | What it checks |
|------|---------------|
| `test_parse_cite_structure_returns_levels` | Dataclass fields, depth, `absolute_xpath` construction |
| `test_resolve_cite_structure_returns_urn_pairs` | Correct URNs, document order, correct elements returned |
| `test_position_based_use` | Synthetic file with `use="position()"` yields ordinal URNs |
| `test_cite_structure_preferred_over_cref` | File with both `refsDecl` blocks uses `citeStructure` path |
| `test_fallback_output_shape_matches` | Same content via both paths; assert identical textpart count, element count, token count, and dict keys |

---

## Method Change Summary

| Method / Function | Action | Notes |
|---|---|---|
| `CiteStructureLevel` | **Add** dataclass | Top of module |
| `parse_cite_structure(tree)` | **Add** | Returns `list[CiteStructureLevel]` or `[]` |
| `resolve_cite_structure(tree, levels, base_urn)` | **Add** | Pass 1; returns flat tuple list |
| `build_textpart_from_element(...)` | **Add** | Replaces `add_textpart_to_stack` for new path |
| `walk_element_subtree(...)` | **Add** | Pass 2; replaces SAX event handling for new path |
| `process_tokens_standalone(...)` | **Add** | Shared token logic; decoupled from SAX state |
| `TEIParser._extract_urn_and_language()` | **Add** | Reads URN/lang before either pass runs |
| `TEIParser._run_cite_structure_pass(levels)` | **Add** | Orchestrates Pass 1 + Pass 2 |
| `TEIParser._get_citable_elements_from_cite_structure(levels)` | **Add** | Derives citable elements from leaf levels |
| `TEIParser._get_citable_elements_from_cref()` | **Rename** | Former `get_citable_elements()`; fallback only |
| `TEIParser.__init__()` | **Change** | Branch on `parse_cite_structure` result |
| `TEIParser.process_tokens()` | **Change** | Thin wrapper around `process_tokens_standalone` |
| `create_table_of_contents()` | **Keep** | Works unchanged; `subtype` is already `unit` in new path |
| `nest_textparts()` | **Keep** | No change |
| `_rewrite_element_urn()` | **Keep** | Used in `walk_element_subtree` for speaker backfill |
| `TEIParser.add_textpart_to_stack()` | **Keep** | Fallback only |
| `TEIParser.determine_location()` | **Keep** | Fallback only |
| `TEIParser.handle_div()` | **Keep** | Fallback only |
| `TEIParser.startElementNS / endElementNS / characters` | **Keep** | Fallback SAX path |
| `TextpartDict.subtype` in `document.py` | **Document** | Note dual source of `subtype` value |
