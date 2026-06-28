// The /privacy/request query-param contract (PRIVACY_DESIGN.md 3.9).
//
// Single source of truth for the param names and the removal request-type value
// shared by BOTH the producer (the tree selection-mode CTA href builder in
// components/layout/PrivacyLinks.tsx) and the consumer (the prefill parser in
// pages/legal/PrivacyRequestPage.tsx). Defining them once means the two sides
// agree by construction and the contract cannot silently drift.

/** ?owner= -- the tree owner's username the request is filed against. */
export const PARAM_OWNER = 'owner';

/** ?individual_ids= -- comma-separated GEDCOM-shaped ids (e.g. I1,I2,I3). */
export const PARAM_INDIVIDUAL_IDS = 'individual_ids';

/** ?request_type= -- one of the three privacy-request kinds. */
export const PARAM_REQUEST_TYPE = 'request_type';

// 3.9 only emits removal selections from the tree; the parser still accepts the
// other two values so the contract reads correctly if selection mode is later
// extended to access (see PRIVACY_DESIGN.md 3.9 "Scoped to removal at first").
export const REQUEST_TYPE_REMOVAL = 'removal';
