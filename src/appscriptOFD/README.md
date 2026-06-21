# appscriptOFD

Google Apps Script web apps managed with [clasp](https://github.com/google/clasp). Each folder is a separate script project.

## Prerequisites

- [clasp](https://github.com/google/clasp) logged in (`clasp login`)
- Deploy each script as a **Web app** (Execute as: deploying user, access as needed for your client)

## `otp/` — SMS OTP logger

Receives POSTed JSON and appends rows to sheet `SMS_OTP` (creates the sheet and headers on first use).

## `omzet/` — Trial baseline row updater

Finds a row where column A matches `username`, then updates revenue and order columns on that row.



---
Last Updated: Tue May 12 12:50:02 PM WIB 2026
Added master-report deployment workflow.
 
