import { api, pollJob } from "/ui.js";
import { invalidate } from "./store.js";

async function change(path, data, ...keys) {
  const result = await api(path, { method: "POST", body: data });
  invalidate(...keys);
  return result;
}

export const createTrial = form => change("/trials", form, "trials");
export const confirmTrial = (code, outcome) => change(`/trials/${code}/confirm`, {outcome}, "trials");
export const proposeMove = form => change("/moves", form, "moves");
export const approveMove = code => change(`/moves/${code}/approve`, {}, "moves", "map");
export const handoverMove = (code, recipient) => change(`/moves/${code}/handover`, {recipient}, "moves");
export const moveDetails = code => api(`/moves/${code}`);

export async function runTrial(code) {
  const { id } = await change(`/trials/${code}/predict`, {}, "trials");
  const result = await pollJob(id);
  invalidate("trials");
  return result;
}

export const openBlindBatch = form => change("/blind-batches", form, "blindBatches");
export const blindBatch = code => api(`/blind-batches/${encodeURIComponent(code)}`);
export const recordBlindTrial = (code, form) =>
  change(`/blind-batches/${encodeURIComponent(code)}/trials`, form, "blindBatches");
export const assessBlindTrial = (code, trialCode, outcome) =>
  change(`/blind-batches/${encodeURIComponent(code)}/trials/${encodeURIComponent(trialCode)}/assess`,
    {outcome}, "blindBatches");
export const revealBlindBatch = code =>
  change(`/blind-batches/${encodeURIComponent(code)}/reveal`, {}, "blindBatches");

export async function runBlindTrial(code, trialCode, observedResult) {
  const body = observedResult ? {observed_result: observedResult} : {};
  const { id } = await change(
    `/blind-batches/${encodeURIComponent(code)}/trials/${encodeURIComponent(trialCode)}/predict`,
    body, "blindBatches");
  const result = await pollJob(id);
  invalidate("blindBatches");
  return result;
}
