# Perseus 6 Planning – 2026-04-01

## Start with P4

- Sources: https://www.perseus.tufts.edu/hopper/opensource/download

### Unsupportable technical debt

- EpiDoc (can't change it, but we can stop using it for new things)

### TEI XML and XSLT

#### Cliff

- [ ] Convert TEI XML to canonical schema for rendering using XSLT (still TEI XML, but "normalized")
- [ ] Convert normalized TEI XML to HTML

#### Charles

- [ ] Map out P4 (just high-level understanding)
- [ ] Enable token-level annotations of normalized TEI XML
- [ ] Convert milestones to divs in drama so that they are addressable via refsDecl (for chunking)

#### Both

- [ ] Discuss chunking methods

### TODO

- [ ] Itemize P4 features
- [ ] Parity with P4 (no fixes planned for bugs in P4 at this stage)
- [ ] Fix badly encoded texts as we encounter them


### Test cases

- [ ] Galen, _Quod qualitates incorporeae sint_ ([../test_tei/tlg0057.tlg111.verbatim-grc1.xml](../test_tei/tlg0057.tlg111.verbatim-grc1.xml) in this repository)
- [ ] Sophocles, [_Trachiniae_](https://github.com/PerseusDL/canonical-greekLit/blob/master/data/tlg0011/tlg001/tlg0011.tlg001.perseus-grc2.xml)
- [ ] Seneca, [_Agamemnon_](https://github.com/PerseusDL/canonical-latinLit/blob/81cbbe22b100a58efdefffee787265075876fc3c/data/phi1017/phi007/phi1017.phi007.perseus-lat2.xml)
