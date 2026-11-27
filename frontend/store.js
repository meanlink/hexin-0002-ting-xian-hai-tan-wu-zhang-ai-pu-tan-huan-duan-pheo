import { api } from "/ui.js";

const queryEndpoints = { map: "/segments", trials: "/trials", moves: "/moves" };
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
