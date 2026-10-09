# User service

Supabase Auth uses email login links and creates an account on first sign-in. Configure Site URL to the production /app URL. Vercel uses VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY; never use a server secret in frontend configuration.

Apply supabase/user-lists.sql once. watchlist and saved_analyses use user_id ownership and row level security for all operations, with anonymous access revoked. Saved analysis IDs omit content versions so bookmarks follow the current published result. Account deletion cascades the personal lists.

Public research stays public. Personal lists contain references and company metadata, not copied analyses or PDFs. Watchlist entries are manual; adding one does not execute a new analysis.

Supabase default mail delivery is for project team addresses only. A custom SMTP provider is required before opening email sign-in to general users. Email delivery and login-link completion require a real mailbox test.
