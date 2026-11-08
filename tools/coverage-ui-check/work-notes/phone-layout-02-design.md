# Design — phone layout and keyboard

CSS only: wrap verification cells and constrain their existing scroll region. Set the contact grid min width to zero and its track to minmax(0, 1fr). Below 360px, allow contact gutters to contract while keeping the widget at its original 304px width. No clipping, transforms, content changes or page-level overflow hiding.

Extend browser.mjs directly: require page scrollWidth <= clientWidth at 320, 360, 390, 768, 1280 and retain 1440; plant a wide element and require the same assertion to throw. Test Tab/Shift+Tab order, Space/Enter layer buttons, native year/state type-ahead (AK/DC/HI), focus-visible and live status accessibility semantics and updates. Keep all prior selection/data failure tests.

README and phase notes document reproducible local runs and remaining limits. No new dependency or runtime abstraction. No open questions.
