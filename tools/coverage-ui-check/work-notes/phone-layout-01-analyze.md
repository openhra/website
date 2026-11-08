# Analyze — phone layout and keyboard

Scope: leased plans CSS/markup/runtime and coverage UI checker only. No public checkout changes.

Existing `.verification .table` is a focusable labelled horizontal scroll region. Its cells retain nowrap numbers. The contact grid has a fixed 304px verification placeholder inside 20px gutters. At 320px with a scrollbar the page client width is 305px but scroll width is 324px.

Reuse the existing browser CDP checker, responsive assertions, negative controls, and static protected-file parity. Its historical baseline branch no longer exists after incubation; remove this allowance rather than carrying baseline overflow forward. Native select closed-control type-ahead works through real keyboard events; popup arrow events alone do not.

No open questions. Owner authorizes sensible unattended choices.

TODO: [x] Analyze; [x] Design; [x] Implement; [x] Test; [x] Simplify.
