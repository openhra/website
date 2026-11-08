# Design — coverage reader

Static fetch → validate index/hash/dataset → selection record → one synchronous DOM commit. Keep requested selection separate from displayed selection; newest request wins. On failure restore controls to the visible dataset without moving focus.

Edit only section 06 plus deferred coverage.js reference, append scoped styles. Create coverage.js because neither the preview reader nor contact flow supports validated switching. Reuse A's fragment verbatim in both fallback tables. Derive us-states.svg from the documented Census artifact and embed the same geographic content so fallback map requires no fetch. New tools/coverage-ui-check owns independent static and browser checks; no dependency or gate edits.

Default: Providers/2026, Texas detail. Advertised years derive from the index. Share links restore year/layer; state stays local. Do not invent market-wide claims or a coherent serving snapshot. Label 2027 premium scopes with no published source in this snapshot as not published yet in this snapshot, without changing Unknown or importing a prior-year denominator. This is a publication statement about this static release, not a claim about CMS beyond the evidence.

No open questions. Implementation: derive markup, implement validation/rendering and races, add checks, inspect captures and simplify.
