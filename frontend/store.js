import { api } from "/ui.js";

const queryEndpoints = {
  map: "/segments",
  trials: "/trials",
  moves: "/moves",
  blindBatches: "/blind-batches",
};
const state = new Map();

export async function load(...keys) {
  const results = await Promise.all(keys.map(key =>
    state.get(key) || api(queryEndpoints[key]).then(result => {
      state.set(key, result);
      return result;
    })
  ));
  return Object.fromEntries(keys.map((key, i) => [key, results[i]]));
}

export function invalidate(...keys) {
  keys.forEach(key => state.delete(key));
}
