# Microsoft Store packaging inputs

The manifest template is intentionally incomplete until Partner Center provides the exact package identity. Do not
replace its tokens with example values in source control.

Required private build inputs:

- Package Identity Name, Publisher and Publisher Display Name copied from Partner Center.
- `StoreLogo.png` (50 × 50), `Square44x44Logo.png` (44 × 44), `Square150x150Logo.png` (150 × 150) and
  `Wide310x150Logo.png` (310 × 150). Supply scale-qualified assets before the final Store submission.
- `makeappx.exe` from the Windows SDK.

`scripts/publish-store-msix.ps1` builds an unsigned Store submission package. Microsoft re-signs a package accepted
through Partner Center. Local installation testing still requires a test certificate trusted by the test machine; the
certificate and private key must never be committed.
