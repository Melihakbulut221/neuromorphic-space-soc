# Evidence: the GR801 product page, as fetched

`docs/01` section 2.2 cites <https://www.gaisler.com/products/gr801> for
one figure that is **not** in the archived product brief PDF. An
independent review raised that as finding R-2, `docs/07` rejected it on
the grounds that the figure was in the cited material, and the rejection
named no artefact. This file is the artefact.

It is not a copy of the page. It is what is needed to check the claim
without one: the URL, when it was read, what the server returned, a
digest of the exact bytes, and the one sentence the citation rests on.

| | |
|---|---|
| URL | <https://www.gaisler.com/products/gr801> |
| Fetched | 2026-09-09 |
| HTTP status | 200 |
| Body length | 96,997 bytes |
| SHA-256 of the response body | `0c52561cebae14de30a21edcc197edd706ba2ba85f811a127b3e937cdf60bc10` |

The sentence, quoted verbatim from the page's Akida feature list:

> Each node supports 128 4x4 MACs, for total of 1024 MACs/clock

Three things a reader should know about it.

**It is on the page and not in the brief.** `pdftotext` over
`Product_Brief_GR801.pdf` (368,237 bytes, 2 pages, CreationDate
2026-04-23) returns zero occurrences of `MAC`, `1024`, `128` or `4x4`,
including after decompressing every content stream. So the reviewer's
observation was correct about the brief, and `docs/07` R-2's rejection
was correct about the cited material; what was wrong was `docs/01`
section 2.2's heading, which called the whole list "Facts from the GR801
brief" while citing the product page. **That is a source-attribution
defect, not a fabricated citation**, and it is fixed where it occurred.

**The vendor's arithmetic is the vendor's.** 128 units per node times 8
nodes is 1,024 units per clock, which is the sentence's own reading. If
"4x4 MAC" means sixteen multiply-accumulates, the same sentence supports
16,384 MACs per clock. This project quotes the vendor and does not
resolve the ambiguity, because nothing public resolves it, and no figure
in this repository depends on which reading is right.

**A live URL is not evidence.** This file exists so that the claim
survives the page changing. If the page changes, this record still says
what it said on 2026-09-09 and the digest says which bytes.

Reproduce:

```bash
curl -sS -A 'Mozilla/5.0' https://www.gaisler.com/products/gr801 | sha256sum
```
