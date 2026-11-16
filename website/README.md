# ProofFlow product site

A static product site for judges: what ProofFlow does, an in-browser replay of the guided sample, the audited results with their limits, the architecture and how to try it. It has no backend; it links to the live app, the evidence and the repository.

```sh
npm ci
npm run dev      # http://127.0.0.1:5180
npm run build    # static output in dist/
```

Production serves the built HTML at `/` and its static files under `/showcase/`. Build it with `npm run build -- --base=/showcase/`. The live application is at `/app/`.

- Design plan, judge journey and tokens: [DESIGN.md](DESIGN.md).
- Every figure on the page cites the repository file that states it (`Source` links). Shared verified facts live in `src/content/facts.ts`; section data sits next to each section in `src/sections/<name>/`.
- The demo section (`src/sections/demo/engine.ts`) ports the guided sample's arithmetic and lineage rules from `proofflow/analytics.py`, `proofflow/demo.py` and `proofflow/runtime.py`, and reproduces the README's verified values. It is labeled on the page as a replay; the live app runs the same flow on SQLite and HydraDB.
- Screenshots in `public/shots/` are copied from `evidence/ui/` and `video/poster.jpg`.
