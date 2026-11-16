# Render the ProofFlow film on the Mac mini

The Mac only renders the picture. The Windows machine then adds the final mix and captions (`tools/finish.mjs`).

Requirements: Node 22 or newer, Google Chrome, and ffmpeg (`brew install ffmpeg`).

```sh
mkdir -p ~/proofflow-film && cd ~/proofflow-film
unzip -o ~/Downloads/proofflow-film-render.zip     # or wherever the zip landed

# 1. Dry run: checks the environment and the composition, about 1 minute
npx --yes hyperframes@0.8.157 check
npx --yes hyperframes@0.8.157 snapshot --at 30,120,200 --no-end --describe false -o out/snaps

# 2. Final 4K picture (pinned CLI version, delivery quality)
time npx --yes hyperframes@0.8.157 render --resolution 4k --fps 30 --quality delivery --crf 12 --browser-gpu \
  -o out/proofflow-film-picture.mp4
```

The second line of the render summary should say `beginframe` or `fast capture` and `hardware gpu`. If it says `software gpu`, Chrome isn't using the GPU, so tell the lead.

Send `out/proofflow-film-picture.mp4` back to the Windows machine at `Z:\Projects\Proofflow\film\out\`. Then run `node tools/finish.mjs --name proofflow-film` there.
