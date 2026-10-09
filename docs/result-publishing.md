# Local analysis publishing

The Supabase project is `snembdnkylggbxtxfqyz` (marketcouncil). Use the public `analysis-results` bucket for reviewed, publishable analysis results only. Public read does not grant upload rights; do not add anonymous write policies.

## Local setup

Save these variables in the ignored root `.env.result-upload` file:

```
RESULTS_SUPABASE_URL=https://snembdnkylggbxtxfqyz.supabase.co
RESULTS_STORAGE_BUCKET=analysis-results
RESULTS_SUPABASE_SECRET_KEY=<server-side secret key>
RESULTS_AUTO_UPLOAD=true
```

Never place the secret in a VITE variable or commit it. The project secret has broad privileges: keep this project dedicated to result publishing.

`python -m app.debate_main` publishes the local archive after successful analysis when auto-upload is enabled. Upload errors do not discard local analysis results. Retry with `python publish_results.py`. Other entry points do not automatically publish.

## Frontend

Set the public, non-secret build variable once:

```
VITE_RESULTS_BASE_URL=https://snembdnkylggbxtxfqyz.supabase.co/storage/v1/object/public/analysis-results
```

Redeploy the frontend once to activate this endpoint. Later result uploads require no frontend deployment: refresh the website to load the current index. Without the variable the UI uses its bundled snapshot.

The publisher sends content-versioned result files before overwriting index.json. Interrupted uploads retain the previous index. Old versions are retained intentionally; review storage usage before cleanup. Run publishing from one local machine at a time; concurrent publishers can replace each other's index. The current local archive is authoritative.

The evidence tab groups sources actually cited in saved debate rounds and shows their usage and original quotes. Legacy unstructured results display a notice instead of inventing sources.

Supabase Free includes 1 GB of file storage and low-activity projects may pause. Check availability before a demo.

## Storage boundary

Cloud storage contains analysis JSON and cited excerpts with source title, URL, publication date and page number. Full PDFs, collected article bodies, uncited source catalogs, retrieval context, internal document/chunk/quote IDs, embeddings and Chroma files stay local. The exporter limits evidence fields before publishing without modifying the saved local analysis.

Repeated publishing of unchanged results uses the same content-addressed filenames, so it does not create duplicate objects. Different analyses retain their own quoted evidence for reproducibility. Older changed versions are retained; no automatic deletion is performed.
