// Creature cycling for the left and right buttons. Pure logic, no three.js, so it can be tested on its own.
//
// Rule (as asked):
//  - Focused on a creature whose species has more than one individual: left and right go to the previous and next individual
//    of that species, in a fixed order, wrapping round.
//  - Otherwise (not focused, or the species has one individual): left and right go through the views of ALL creatures, in one
//    fixed order (category, species name, individual number). From nothing, the first press starts at the creature nearest the camera.
//
// A creature is { id, name (the species), cat (the category), n (the individual number within its species), pos: [x, y, z] }.

const CAT_ORDER = ['People', 'Mammals', 'Birds', 'Reptiles', 'Sea life', 'Shore life'];

function rank(c) {
  const ci = CAT_ORDER.indexOf(c.cat);
  return [ci < 0 ? 99 : ci, c.name, c.n];
}

// all creatures in the one fixed order used for the global cycle
export function viewOrder(creatures) {
  return creatures.slice().sort((a, b) => {
    const ra = rank(a), rb = rank(b);
    if (ra[0] !== rb[0]) return ra[0] - rb[0];
    if (ra[1] !== rb[1]) return ra[1] < rb[1] ? -1 : 1;
    return ra[2] - rb[2];
  });
}

// the individuals of one species, in order
export function speciesOf(creatures, name) {
  return viewOrder(creatures.filter((c) => c.name === name));
}

// the next (dir 1) or previous (dir -1) individual of the focused creature's species, or null if the species has only one
export function nextInSpecies(creatures, focus, dir) {
  if (!focus) return null;
  const group = speciesOf(creatures, focus.name);
  if (group.length < 2) return null;
  const i = group.findIndex((c) => c.id === focus.id);
  return group[(i + dir + group.length) % group.length];
}

// the next (dir 1) or previous (dir -1) creature in the global view order; from nothing, the one nearest the camera first
export function nextView(creatures, focus, dir, cameraPos) {
  const order = viewOrder(creatures);
  if (!order.length) return null;
  if (!focus) {
    let best = order[0], bd = Infinity;
    for (const c of order) {
      const d = Math.hypot(c.pos[0] - cameraPos[0], c.pos[1] - cameraPos[1], c.pos[2] - cameraPos[2]);
      if (d < bd) { bd = d; best = c; }
    }
    return best;
  }
  const i = order.findIndex((c) => c.id === focus.id);
  return order[(i + dir + order.length) % order.length];
}

// what the left and right buttons do when pressed in play mode (menu closed)
export function cycleFocus(creatures, focus, dir, cameraPos) {
  return nextInSpecies(creatures, focus, dir) || nextView(creatures, focus, dir, cameraPos);
}
