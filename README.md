# Kodon

A Python implementation of a lenient TEI parser for textual enrichment (morphological analysis, commentary linking, etc.)
and HTML rendering.

## Installation

`uv` is the recommended tool for working with Kodon. You can install the library from GitHub:

```sh
uv add git+https://github.com/PerseusDLCode/kodon-py.git
```

## Development

If you're working on `kodon-py` locally, clone this repository and install the library as an editable dependency
with, e.g.,

```sh
uv add --editable ../kodon-py
```

## How Kodon Works

Much of the challenge of working with TEI XML emerges from lack of standardized encodings even within a single
corpus. Further, because the structure of any TEI document is not fully known until after the document has been
parsed and processed, automatic enrichment of TEI-encoded data is a difficult and often intractable task: generally
speaking, so much needs to be known about the minutiae of the document that it has usually made more sense either
to encode the enrichment manually or to enrich a stripped-down or non-TEI version of the document.

Kodon is a minimal computing–inspired library that tries to meet the documents where they are and to make it possible to add token-level annotations
using Canonical Text Services (CTS) Universal Resource Names (URNs). Although Kodon currently performs some
rudimentary chunking and generation of tables of contents, these features are generally outside of Kodon's
focus, which lies squarely in addressing the gap between data encoding and data enrichment.

To achieve this goal, Kodon implements a [Simple API for XML](https://en.wikipedia.org/wiki/Simple_API_for_XML) (SAX)
parser for processing block-level chunks of TEI XML and turning them into a quasi-abstract syntax tree of containers—
TEI elements—and text runs (strings of textual content). The text runs are tokenized with [`stanza`](https://stanfordnlp.github.io/stanza/),
and primary text runs can then be collected and passed to a more complete NLP process, either using `stanza`'s full pipeline
or using another service entirely, such as [spaCy](https://spacy.io).

During tokenization, each token is assigned a CTS URN. These URNs can be used to add further enrichments from, e.g.,
secondary sources. The CTS URNs serve as pointers from the "flat" list of tokens into the nested AST, meaning
that data enrichment can manipulate the AST more or less directly, rather than needing to modify the structure of the TEI-encoded
document.

This intermediate AST, complete with enrichments of the project's choosing, is rendered as HTML for browser-based
reading environments by walking the AST and reassembling its elements according to pre- or user-defined
[templates](./src/kodon_py/templates). This approach to templating allows projects to override Kodon's defaults
declaratively by defining templates named after the original TEI elements. Right now, [Jinja](https://jinja.palletsprojects.com/en/stable/)
templates are supported, but it is conceivable that other approaches to templating will be supported in the future.

An example of a complete workflow using `kodon-py` can be seen in [Mera Galeni Folia](https://galenus-verbatim.github.io/mera-galeni-folia/),
a minimal-computing revision of Galenus Verbatim.

## Funding

Kodon is currently being developed with support from the Perseus Project.

Kodon's development has also been supported by Galenus Verbatim, which in turn
was funded by l'[Institut universitaire de France](https://www.iufrance.fr), as well as
by l'[Initiative humanités biomédicales de l'Alliance Sorbonne Université](https://humanites-biomedicales.sorbonne-universite.fr)
for its Latin component.

Kodon was originally developed under the auspices of the
[_Ajax_ Multi-Commentary](https://multi.ajmch.ch), which was generously by the Swiss
National Science Foundation under an Ambizione grant (no.
[PZ00P1_186033](https://data.snf.ch/grants/grant/186033)).

Kodon parses TEI XML files into a format that renders straightforwardly in the browser,
without the need for XSLTs. Kodon's format also makes further annotation trivial by
identifying each token in the corpus with a unique
[CTS URN](https://cite-architecture.github.io/ctsurn_spec/).

# LICENSE

MIT License

Copyright (c) 2024-2026

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.


