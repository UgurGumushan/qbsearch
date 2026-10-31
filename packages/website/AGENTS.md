# Static website

`public/` contains the complete download page: hand-maintained HTML, CSS, and SVG.
There is no package, JavaScript runtime, dependency installation, or build step.
Keep download links usable with JavaScript disabled. Preserve `/download/latest`
as an HTTP 307 redirect in `vercel.json` to the stable GitHub ZIP asset.
The root formatter and deterministic download-contract tests cover this site.
