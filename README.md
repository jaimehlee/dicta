# Dicta

What leaders said, straight from the source.

A public website that shows short, word-for-word quotes from company leaders, each linked to the original release, filing or transcript. A free daily check on SEC EDGAR finds new earnings releases from the companies you follow, and your team approves every quote before it goes up.

## What's in this folder

| File | What it does |
| --- | --- |
| `index.html` | The public site |
| `review.html` | The team's review desk (not linked from the site) |
| `assets/style.css` | Styles for both pages |
| `data/quotes.json` | The quotes on the site |
| `data/corrections.json` | Your public corrections log |
| `data/config.json` | Contact email, sign-up form link, error-report link, trading rule |
| `data/watchlist.json` | Companies the daily check follows |
| `data/pending.json` | Releases waiting for review (the daily check fills this) |
| `data/seen.json` | Releases already listed, so nothing shows up twice |
| `scripts/fetch_filings.py` | The daily SEC check |
| `scripts/validate.py` | Checks the data files before every update |
| `.github/workflows/site.yml` | Runs the check every weekday and publishes the site |

## Set it up (about 15 minutes, free)

1. **Make a GitHub account** at github.com if you don't have one.
2. **Create a new repository.** Name it `dicta` and set it to **Public**. Free Pages and free Actions need a public repository.
3. **Upload the files.** In the new repository, choose *Add file › Upload files* and drag in everything from this folder.
   - The `.github` folder starts with a dot, so your computer may hide it and the uploader may skip it. Check that `.github/workflows/site.yml` shows up in the repository. If it doesn't, choose *Add file › Create new file*, type `.github/workflows/site.yml` as the name, and paste in that file's contents.
4. **Turn on Pages.** *Settings › Pages › Build and deployment › Source:* choose **GitHub Actions**.
5. **Add your contact for the SEC.** *Settings › Secrets and variables › Actions › Variables › New repository variable.* Name: `SEC_USER_AGENT`. Value: `Dicta research yourname@example.com`, with your real email. The SEC asks every automated visitor for this.
6. **Run it once.** Open the *Actions* tab. If GitHub asks, enable workflows. Click **Dicta site › Run workflow**. It takes a minute or two.
7. **Find your address.** *Settings › Pages* shows it. It will look like `https://your-username.github.io/dicta/`.
8. **Fill in `data/config.json`.** Open the file on GitHub, click the pencil, and add:
   - `contactEmail`: the team's email
   - `signupUrl`: a link to your digest sign-up form (a Google Form works)
   - `reportUrl`: optional, a form for readers to report errors
   - `tradingRule`: your team's rule, shown on the How we verify page

   Commit the change. The site updates in a few minutes.

## Your daily routine

1. On weekday mornings the check looks for new earnings releases from the companies in `data/watchlist.json`.
2. If it finds any, it opens a GitHub issue listing them. Click *Watch* on the repository so GitHub emails you.
3. Open `review.html` on your site, for example `https://your-username.github.io/dicta/review.html`.
4. For each release: open the source, pick a line, fill the form, tick the checklist and add it. Tick *Done* on every release you've looked at.
5. Copy the two outputs into `data/quotes.json` and `data/pending.json` on GitHub (pencil, select all, paste, commit).
6. Close the issue. The site updates in a few minutes.

If a file has a mistake, the update stops, the old site stays up, and GitHub emails you what to fix.

## Fix a mistake in the open

1. Fix the quote in `data/quotes.json` and add `"correctedAt": "2026-10-23"` (today's date) to it.
2. Add an entry to `data/corrections.json`:

```json
{
  "corrections": [
    {
      "date": "2026-10-23",
      "label": "JPMorgan Chase · Jamie Dimon · Oct 13, 2026",
      "note": "We listed the wrong source link. It now points to the earnings release."
    }
  ]
}
```

## Add or remove companies

Edit `data/watchlist.json`. Use the US ticker the company trades under. Foreign companies work if they file with the SEC, like TSMC and ASML. Canadian companies that file only on SEDAR+ aren't covered by the check, so add their quotes by hand.

## What it costs

Nothing, on GitHub's free plan with a public repository. A few limits to know:

- The site can be up to 1 GB, with a soft limit of 100 GB of traffic a month.
- GitHub says Pages isn't meant for running an online business. If Dicta becomes one, move to another host.
- X posts aren't included. X's API charges for every post you read.
- A custom domain is optional. Buy one from any registrar, then add it under *Settings › Pages › Custom domain*.

## Good to know

- The check never copies quotes. It only lists where they are, and a person picks and checks every quote.
- Keep each quote to 14 words or fewer. The update check stops anything longer.
- The repository is public, so never put private information in it. Keep sign-up emails in your form or newsletter tool, not here.
- If GitHub pauses the scheduled check after a long quiet stretch, turn it back on in the *Actions* tab.
- Context, not investment advice. Everyone sees the same content.
