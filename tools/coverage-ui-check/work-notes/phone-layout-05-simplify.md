# Simplification — phone layout and keyboard

Reused the existing labelled, focusable verification scroll region and the existing CDP checker. No markup, runtime JS, dependency or page overflow-hiding rule needed. Removed the obsolete historical baseline branch/file lifecycle and tolerance for existing page overflow.

Visual review at 320px caught cramped numeric cells and edge-aligned contact text in the first iteration. A readable table minimum inside the scroll region and expanded widget grid keep the normal text gutters. Final screenshots reviewed: <scratch>/openplans-w5-ui/phone320-verification.png and phone320-contact.png.

Browser checker PASS after simplification: 306 selections, strict overflow at 320/360/390/768/1280/1440, native keyboard changes, keyboard table scroll, focus/live accessibility, fallbacks and negative controls. Final gates recorded in phone-layout-04-tests.md.
