<p align="right"><a href="README.md">한국어</a> | <strong>English</strong></p>

<div align="center">

# MarketCouncil

### Compare competing investment hypotheses against shared evidence.

Bull and Bear debate from the same sources. The Moderator records open issues and the evidence needed to resolve them.

[Website](https://frontend-six-pi-h5i7tztups.vercel.app/?lang=en) · [Research library](https://frontend-six-pi-h5i7tztups.vercel.app/app?lang=en) · [Windows download](https://frontend-six-pi-h5i7tztups.vercel.app/download?lang=en)

`React` · `Python` · `LangGraph` · `ChromaDB / BGE-M3` · `Supabase` · `Vercel`

</div>

[![MarketCouncil landing page](docs/images/readme/landing.en.jpg)](https://frontend-six-pi-h5i7tztups.vercel.app/?lang=en)

## What you can do

- Browse published research on Samsung Electronics, SK hynix, Hyundai Motor, NAVER, Apple and Microsoft.
- Compare the Bull and Bear arguments and follow each citation back to its source.
- Sign in to save companies and analyses. Personal debates start private and can be shared by link or published to the community.
- Create analyses in the Windows app and read saved results on the web. The website supports Korean and English interfaces.

| Research library | Debate detail |
| --- | --- |
| ![Published research list](docs/images/readme/library.jpg) | ![Debate topics and rounds](docs/images/readme/debate.jpg) |

<details>
<summary>See how a debate links to its citations and sources</summary>

![Expanded evidence with the source and quotation](docs/images/readme/evidence.jpg)

</details>

## How it works

1. **Prepare evidence.** Select the company and cutoff date, then gather filings, earnings material and retrieved documents. Analysis waits if required original material is missing.
2. **Debate.** Bull proposes an upside case, Bear develops the downside case, and the Moderator records where their evidence and assumptions differ.
3. **Trace evidence.** Claims link to source records and quotations. The result preserves the scope of support, counterevidence and open questions.
4. **Store and share.** Analysis and source storage run on the user’s PC. Selected results can be stored in the cloud for private access or publication.

Retrieval quality uses questions with reference evidence. Answer grounding uses citation checks and separate evaluation. Facts, hypotheses and evidence gaps stay distinct so readers can revisit the reasoning. [Architecture and principles](docs/how-it-works.md#architecture-and-principles)

The application source is maintained on the [`debate_focus` branch](https://github.com/woosukkk/MarketCouncil/tree/debate_focus).
