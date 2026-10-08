# MarketCouncil web

React + Vite read-only investment debate archive. Deployment is a snapshot of saved analysis results; it does not run new analyses or sync automatically.

## Run and deploy

From this directory:

```powershell
..\venv\Scripts\python.exe export_results.py
npm ci
npm test
npm run build
npm run dev
# After Vercel login, deploy the reviewed frontend and public result snapshot:
npx vercel --prod
```

`export_results.py` exports the selected analysis fields from `../results/analysis_debate`. All generated JSON files are public when deployed. Do not include confidential results. No API keys, vector databases, model files or environment files are needed.

The UI distinguishes quote matching from the accuracy of investment claims and links only HTTP(S) evidence URLs. Results without newer navigation metadata fall back to their original agenda and status records.
