# Microsoft Store packaging inputs

The manifest template is intentionally incomplete until Partner Center provides the exact package identity. Do not
replace its tokens with example values in source control.

Required publisher build inputs:

- Package Identity Name, Publisher and Publisher Display Name copied from Partner Center.
- `Assets/` already contains package logos generated from the existing `my-site` brand mark; see `ASSET-SOURCE.md`.
- `ListingAssets/AppTileIcon-300x300.png` is the recommended 1:1 Store listing icon.
- `makeappx.exe` from the Windows SDK.

`scripts/publish-store-msix.ps1` builds an unsigned Store submission package. Microsoft re-signs a package accepted
through Partner Center. Local installation testing still requires a test certificate trusted by the test machine; the
certificate and private key must never be committed.

The script uses `packaging/store/Assets` by default. Pass `-AssetsPath` only when replacing the complete asset set.
