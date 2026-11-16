# Render, finish and publish the ProofFlow film on the Mac

Everything the render needs is in git on branch `film/v2`: compositions, fonts, GSAP, product stills, measured narration timing, captions, and every audio file as lossless FLAC under `audio/handoff/`. No zip, nothing to copy from Windows.

Requirements: Node 22 or newer, Google Chrome, ffmpeg (`brew install ffmpeg`), git with push access.

## 1. Get the branch and restore the audio

```sh
cd ~/proofflow            # your clone of saivedant169/proofflow
git fetch origin && git switch film/v2 && git pull
cd film
node tools/handoff-audio.mjs unpack     # FLAC -> audio/narration/s1..s8.wav, music-bed.wav, sfx.wav, mix.wav
node tools/sync.mjs                     # must end with "film-data.js written" and no problems
```

## 2. Dry run (about 1 minute)

```sh
npx --yes hyperframes@0.8.157 check
npx --yes hyperframes@0.8.157 snapshot --at 10,60,110,160,215,245 --no-end --describe false -o out/snaps
```

Look at the snapshots: no blank frames, no clipped text.

## 3. Final 4K picture

```sh
time npx --yes hyperframes@0.8.157 render --resolution 4k --fps 30 --quality delivery --crf 12 --browser-gpu \
  -o out/proofflow-film-v2-picture.mp4
```

The render summary should say `beginframe` or `fast capture` and `hardware gpu`. If it says `software gpu`, Chrome isn't using the GPU.

## 4. Finish: final mix and captions

```sh
node tools/finish.mjs --name proofflow-film-v2
```

This writes, in `out/`:

- `proofflow-film-v2.mp4`: the 4K master with the final mix (AAC 320 kb/s) and an English subtitle track that is off by default.
- `proofflow-film-v2-1080p.mp4`: a 1080p copy.
- `.en.vtt` / `.en.srt` captions.

Check the master's length against `timing.json` → `duration`, and its loudness (about -14 LUFS):

```sh
ffmpeg -i out/proofflow-film-v2.mp4 -af ebur128 -f null - 2>&1 | tail -12
```

## 5. Put it on the live site

The team removed the old walkthrough in commit `50683c5`. That commit took out the hero button, the Try tile, the footer link, the app link, the README link, and the Dockerfile copy to `/walkthrough.mp4`. To publish the new film:

1. Make a web encode under 90 MB (GitHub's limit is 100 MB per file):
   ```sh
   ffmpeg -i out/proofflow-film-v2.mp4 -vf scale=1920:1080 -c:v libx264 -preset slow -crf 21 -pix_fmt yuv420p \
     -c:a aac -b:a 192k -movflags +faststart ../video/proofflow-walkthrough.mp4
   ffmpeg -ss 196 -i out/proofflow-film-v2.mp4 -frames:v 1 -vf scale=1920:1080 -q:v 3 ../video/poster.jpg
   cp out/proofflow-film-v2.en.vtt ../video/captions.vtt
   ```
   Pick the poster time from a frame you like. The default, 196 s, is in the results chart.
2. On a branch from `main`, run `git revert 50683c5` to bring the links and the Dockerfile copy back. Then:
   - copy the new `video/` files over;
   - update the link text that says "Two-minute walkthrough" to match the new length (about four minutes);
   - copy `video/poster.jpg` to `website/public/shots/walkthrough-poster.jpg`.
3. Build and check the site and app, open a PR, merge, then deploy the usual way:
   - rebuild the app image (it copies the video to `/walkthrough.mp4`) and replace only the app container; HydraDB and its volumes stay as they are;
   - copy `website/dist` with `index.html` at the web root and the rest under `/showcase/`, built with `--base=/showcase/`;
   - finally, check that `https://proofflow.arnavbule.in/walkthrough.mp4` plays and seeks.
