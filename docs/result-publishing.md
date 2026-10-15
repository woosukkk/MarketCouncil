# Local analysis publishing

The Supabase project is `snembdnkylggbxtxfqyz` (marketcouncil). Use the public `analysis-results` bucket for reviewed, publishable analysis results only. Public read does not grant upload rights; do not add anonymous write policies.

## Local setup

Save these variables in the ignored root `.env.result-upload` file:

```
RESULTS_SUPABASE_URL=https://snembdnkylggbxtxfqyz.supabase.co
RESULTS_STORAGE_BUCKET=analysis-results
RESULTS_SUPABASE_SECRET_KEY=<server-side secret key>
RESULTS_AUTO_UPLOAD=false
```

Never place the secret in a VITE variable or commit it. The project secret has broad privileges: keep this project dedicated to result publishing.

`python -m app.debate_main` attempts legacy publishing after successful analysis only when auto-upload is enabled. Publishing now requires an explicit approved manifest; it never discovers all local results. Upload errors do not discard local analysis results. Other entry points do not automatically publish.

Automatic public publishing is disabled in the current local setup. Use the desktop account upload for new private discussions and explicitly select share/community/official publication. The legacy public-archive publisher remains available only for intentionally public example results.

## Explicit public selection (required for the legacy publisher)

The exporter and publisher stop without changing the current index if the manifest is missing, empty or invalid. No manifest is generated automatically from existing results. The current Supabase discussions workflow and existing published assets are unchanged by this source change.

1. Review each analysis and its cited excerpts for public release. New private analyses should use the desktop account upload instead of this legacy publisher.
2. Create a local `public-results.json` in the repository root. List only reviewed result files, with paths relative to `results/analysis_debate` and forward slashes. Include the SHA256 of the exact original file bytes:

```json
{
  "results": [
    {
      "path": "Example/analysis_debate_20261015_090000.json",
      "sha256": "<64 lowercase hexadecimal characters>"
    }
  ]
}
```

Obtain the hash of one deliberately selected file in PowerShell:

```powershell
(Get-FileHash -Algorithm SHA256 -LiteralPath 'C:\MarketCouncil\results\analysis_debate\Example\analysis_debate_20261015_090000.json').Hash.ToLowerInvariant()
```

3. To export the selected public snapshot locally, run `python -m frontend.export_results`. To publish it to the public bucket, run `python publish_results.py`. Both commands also accept `--manifest <path>` for an explicitly prepared manifest elsewhere. Existing no-argument callers use only the repository-root manifest.

The manifest is the complete desired **legacy public index**, not a list of additions. Include every reviewed example that should remain listed before deliberately publishing. Removing an entry on a future successful publication removes it from the index, but does not delete previously public files or make their known URLs private. This change does not unpublish or delete any existing object.

A result changed after review fails its hash check. Review the new contents before updating the hash. Absolute paths, parent traversal, wildcard selection, duplicate files and links resolving outside the archive are rejected. Validation completes before export starts, and a selection error preserves the previous local/remote index. If `RESULTS_AUTO_UPLOAD=true` was used with the old all-files behavior, it now fails closed until a complete explicit manifest exists; keep it disabled for personal analyses.

## Frontend

Set the public, non-secret build variable once:

```
VITE_RESULTS_BASE_URL=https://snembdnkylggbxtxfqyz.supabase.co/storage/v1/object/public/analysis-results
```

Redeploy the frontend once to activate this endpoint. Later result uploads require no frontend deployment: refresh the website to load the current index. Without the variable the UI uses its bundled snapshot.

The publisher sends content-versioned result files before overwriting index.json. Interrupted uploads retain the previous index. Old versions are retained intentionally; review storage usage before cleanup. Run publishing from one local machine at a time; concurrent publishers can replace each other's index. The explicitly reviewed manifest is authoritative for the legacy index; unrelated local files are never added automatically.

The evidence tab groups sources actually cited in saved debate rounds and shows their usage and original quotes. Legacy unstructured results display a notice instead of inventing sources.

Supabase Free includes 1 GB of file storage and low-activity projects may pause. Check availability before a demo.

## Storage boundary

Cloud storage contains analysis JSON and cited excerpts with source title, URL, publication date and page number. Full PDFs, collected article bodies, uncited source catalogs, retrieval context, internal document/chunk/quote IDs, embeddings and Chroma files stay local. The exporter limits evidence fields before publishing without modifying the saved local analysis.

Repeated publishing of unchanged results uses the same content-addressed filenames, so it does not create duplicate objects. Different analyses retain their own quoted evidence for reproducibility. Older changed versions are retained; no automatic deletion is performed.
