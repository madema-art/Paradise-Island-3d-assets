# Paradise Island 3D asset workshop: standing instructions

This repository is an independent asset workshop. Never modify or integrate anything into the main Paradise Island game.

## After every new creature, asset or revision: publish a private preview

The owner inspects results in the browser from Claude Cloud, without downloading anything. After every creation or revision:

1. Build and validate the assets as usual (`tools/monkey/build_all.sh`, or the equivalent for the new asset).
2. Stage the viewer with the REAL packaged GLBs: `python3 tools/stage_artifact_viewer.py` (writes `build/artifact/`; extend the script
   when a new creature is added). Never use screenshots or approximations, and never modify models just to preview them.
3. Publish `build/artifact/index.html` with the Artifact tool plus the files listed in `build/artifact/files.json`. The host serves no
   `.glb` extension, so the script publishes the identical bytes as `*.glb.wasm` with `contentType: application/wasm`.
   To update the existing preview, publish again with `url` = the artifact below (same URL), not a new artifact.
4. Artifacts are private by default. Never share or publish publicly without the owner's explicit permission.
5. Give the owner the link in the final message.

Current monkey preview: https://claude.ai/artifact/9PwuB2sqeuQfCUuDooKsDF (private).

The castaway has its own viewer and its own private artifact: stage with `python3 tools/stage_castaway_viewer.py` (writes `build/artifact_castaway/`, GLBs published as
`*.glb.wasm`), publish `build/artifact_castaway/index.html` plus the files in `build/artifact_castaway/files.json` (contentType `application/wasm` for `*.wasm`), and update
the same URL on later revisions: https://claude.ai/artifact/HZPAouJkxq8bbxT8CYE7cK (private).

The broadleaf tree canopy comparison (current game style against the new leaf-clump canopy) has its own private artifact: stage with `python3 tools/stage_canopy_viewer.py` (writes `build/artifact_canopy/`), publish `build/artifact_canopy/index.html` plus the files in `build/artifact_canopy/files.json` (contentType `text/plain` for extension-less files), and update the same URL on later revisions: https://claude.ai/artifact/5Fdk3N3E9WyaPnyX2JJhnu (private).

The redesigned points of interest (Sunken Temple and Glimmer Ring) have their own private artifact: stage with `python3 tools/stage_poi_viewer.py` (writes `build/artifact_poi/`), publish `build/artifact_poi/index.html` plus the files in `build/artifact_poi/files.json` (contentType `text/plain` for extension-less files), and update the same URL on later revisions: https://claude.ai/artifact/3hAsQBpFrtb6Lfd5fpQHYk (private).

The lagoon coral comparison (the game's coral against the redesign) has its own private artifact: stage with `python3 tools/stage_lagoon_viewer.py` (writes `build/artifact_lagoon/`), publish `build/artifact_lagoon/index.html` plus the files in `build/artifact_lagoon/files.json` (contentType `text/plain` for extension-less files), and update the same URL on later revisions: https://claude.ai/artifact/NQtVbK86ozevgzeBDmD2sx (private).

The giant manta ray has its own viewer and private artifact: stage with `python3 tools/stage_manta_viewer.py` (writes `build/artifact_manta/`, GLB published as `*.glb.wasm`), publish `build/artifact_manta/index.html` plus the files in `build/artifact_manta/files.json` (contentType `application/wasm` for `*.wasm`), and update the same URL on later revisions: https://claude.ai/artifact/SkuLE4corUxLQ1qRcA6Y37 (private).
