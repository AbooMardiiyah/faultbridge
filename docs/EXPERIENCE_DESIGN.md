# Experience Design

FaultBridge presents two connected views. The caller interface at `/` keeps one
task prominent: describe a service problem by voice. The operations workspace at
`/operations` turns completed calls into an auditable decision ledger, delivery
queue, and early-warning view. Both use the same typography, color, spacing, and
status language so the submission reads as one product.

## Interaction principles

- Explain voice processing before requesting microphone permission. Consent is
  required, the microphone has a visible listening state, and recording stops as
  soon as the caller presses Stop.
- Pair spoken output with an on-screen transcript and written answer. Response
  audio plays only after the caller presses **Play response**.
- Show progress in plain language: Ready, Listening, Processing, Awaiting test,
  and Complete. Tool activity is translated into customer-facing evidence such
  as “Checked network status.”
- Keep operational data behind the internal API key and render provider data with
  DOM text nodes. The interface does not inject API content as HTML.
- Use responsive layouts, visible keyboard focus, reduced-motion support,
  44-pixel primary controls, and text colors with at least 4.5:1 contrast.

These choices follow [WCAG 2.2](https://www.w3.org/TR/WCAG22/), W3C guidance for
[target size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum),
and Apple guidance for [feedback](https://developer.apple.com/design/human-interface-guidelines/feedback),
[privacy](https://developer.apple.com/design/human-interface-guidelines/privacy),
and [accessible alternatives to audio](https://developer.apple.com/design/human-interface-guidelines/accessibility/).

## Manual review checklist

Test both pages at 320, 768, and 1440 pixels. Navigate every control by keyboard,
deny and grant microphone access, record a short and a 90-second message, complete
both resolution turns, replay generated audio, and verify empty, populated, error,
and invalid-key states. Repeat with reduced motion and 200% browser zoom.
