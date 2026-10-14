// Runs the official Khronos glTF validator on a .glb and prints a JSON report.
// Usage: node tools/blender/validate_glb_khronos.js path/to/model.glb
// Exit code 0 = no spec errors, 1 = errors found, 2 = validator crashed.
const fs = require('fs');
const validator = require('gltf-validator');

const file = process.argv[2];
if (!file) {
  console.error('usage: node validate_glb_khronos.js <model.glb>');
  process.exit(2);
}

validator.validateBytes(new Uint8Array(fs.readFileSync(file)))
  .then((r) => {
    const i = r.info;
    console.log(JSON.stringify({
      file,
      version: i.version,
      generator: i.generator,
      meshes: i.meshCount,
      materials: i.materialCount,
      triangles: i.totalTriangleCount,
      vertices: i.totalVertexCount,
      textures: i.textureCount,
      imageBytes: i.totalImageByteLength,
      bounds: i.bounds,
      errors: r.issues.numErrors,
      warnings: r.issues.numWarnings,
      infos: r.issues.numInfos,
      messages: r.issues.messages.map((m) => `${m.severity} ${m.code}: ${m.message} @ ${m.pointer}`),
    }, null, 2));
    process.exit(r.issues.numErrors ? 1 : 0);
  })
  .catch((e) => {
    console.error('validator crashed:', e);
    process.exit(2);
  });
