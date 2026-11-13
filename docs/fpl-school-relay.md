# FPL School relay: one-time setup (about 5 minutes)

The **FPL School** tab rates any team you type in. FPL's API doesn't answer requests from other websites' pages, so the
tab gets the team through a tiny relay: a free Cloudflare Worker that fetches a team and its picks from FPL and passes
them on. It only passes on those two things, stores nothing and needs no keys. The code is
`workers/fpl-school-relay.mjs` (about 30 lines).

## 1. Create the Worker
1. Sign up or log in at https://dash.cloudflare.com (the free plan is enough).
2. Go to **Workers & Pages** → **Create** → **Create Worker**. Name it `fpl-school-relay` and click **Deploy**.
3. Click **Edit code**, delete what's there, paste the whole of `workers/fpl-school-relay.mjs`, and click **Deploy**.
4. Copy the Worker's address, shown at the top, e.g. `https://fpl-school-relay.<your-name>.workers.dev`.

Check it: open `https://fpl-school-relay.<your-name>.workers.dev/entry/8122679/` in a browser. You should see your
team's details as text. Any other address on it says "This relay only passes on a team and its picks".

## 2. Tell the site where it is
Edit `fpl_school.json` in the repo on GitHub and put the address in:

```json
{"relay": "https://fpl-school-relay.<your-name>.workers.dev"}
```

The next data refresh (or **Refresh data** on the site) picks it up, and the FPL School tab starts working. Until then
the tab says the relay isn't set up.

## If it stops working
- The tab says "The relay didn't answer": the Worker is down or the address in `fpl_school.json` is wrong. Open the
  check address above; if it fails, redeploy the Worker in Cloudflare.
- The free plan allows 100,000 requests a day; a review uses two.
- If the site moves to another address, add it to `ORIGINS` in the Worker code and redeploy.
