# Workflow usability review

## Operations workspace redesign

Replaced the prototype shell with a desktop sidebar and compact mobile navigation, current-section indicators, accessible keyboard focus and a skip link. Admin home shortcuts lead to submitted/approved/invoiced queues. Order search and status filters preserve server-side salesman ownership. Sales entry stays prominent for salesmen; the admin queue takes priority. Added removable product rows, unsaved-form warnings, error-summary focus and duplicate-submit suppression without disabling submitted action values.

Production displays the run register before entry forms, state-specific next actions and anchors for receiving/starting runs. Order corrections are secondary disclosures. Stock shows exact kg/L amounts with base units retained in the stock table. Reports use a consistent period/filter/export layout. Shared styling applies to optional feature screens as well.

Validation: the full nine-step browser scenario passes after redesign. `scripts/workspace_check.py` verifies five roles, desktop and 360 px layouts, queue filtering and unsaved-form protection. Human usability timing and complete translation remain pending. Browser warnings depend on browser support and prior user interaction; they do not replace server protections.

The benchmark, stock correctness and explainable service boundaries remain the strongest submission evidence. Added role-aware home shortcuts, an explicit Home link, run breadcrumb and order-state instructions so users can find their next task without learning the document model first. Existing styling is retained.

Hindi and Marathi now cover common production actions and core navigation, alongside English and Tamil. The language chooser is available to every role. This is partial localization: order forms, detailed guidance, validation errors and some production labels remain English. The chooser warns that changing language reloads a form. Native-speaker review is still needed.

Critical follow-up priorities, rather than more feature breadth:

1. Observe a real person placing an order in under a minute and completing a production run without help; automated layout checks cannot establish this.
2. Add unsaved-form protection and field-specific error placement across transaction screens in a focused UX pass.
3. Verify backup and restore before using real operational data. Local Docker persistence alone is not a backup policy.
4. Exercise expired stock, partial dispatch, customer credits and failed/retried requests in the interview rehearsal; explain the limits before promising real-world accounting behavior.

All eight stretch categories already have implementations. Full statutory filing, live government integrations, complex promotion rules and route optimization would increase explanation and validation burden without improving the mandatory benchmark. Existing Tally import, language review and demo-video gaps remain disclosed in README.
