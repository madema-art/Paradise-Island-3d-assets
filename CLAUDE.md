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
