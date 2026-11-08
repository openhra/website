# Implementation

Created model.py (contract), inputs.py (selected public ZIP/CSV and finalized report adapters), scan.py (deterministic publication), check.py (strict schema and semantic checker), schema.json, safe selection example, independent fixture tests, operational README and generated table.

Decisions: public archive/member hashes and all-cell physical-row digests bind denominators; explicit missing issuer declarations detect withheld report rows. No registry-only denominators, reference-edge metrics or NPPES counts. TX source validation is corroborated by the recovered audit and matching manifest snapshots; FL/NC use explicit active tables. Failed refreshes retain a valid current ACTIVE pointer with warnings. Manifest partial status alone never establishes ACTIVE.

Missing federal catalog pointers are an evidence limitation: preserve verified public denominator and null numerator/percent. The selected reports establish 49 comparable 2026 source scopes, but only 19 have an explicit reviewed serving declaration. NY/VT remain supplemental; Oregon SBE SHOP excluded. No 2027 borrowing.

A changed selected federal report was rejected on its pinned hash. The replacement aggregate was inspected: 30 scopes passed with equal source/stored counts and zero mismatches, preserving the reviewed figures. Selection was explicitly repinned; no input file was modified.

Atomic directory exchange uses the standard-library ctypes interface to platform rename primitives. Unsupported replacement platforms fail closed. Tooling table replacement is separate from static data publication.

TODO: implementation, two full-input reproductions, semantic validation and simplification complete. Full site gate passed; static data is included in the local handoff commit. The external federal serving-pointer evidence target remains open.
