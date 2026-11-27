export function startAction(button, notice, task) {
  if (button.disabled) return;
  button.disabled = true;
  notice.hidden = false;
  notice.className = "sand-notice";
  notice.textContent = "正在保存…";
  return Promise.resolve().then(task).catch(error => {
    notice.textContent = error.message || "操作未完成，请再次试试。";
    notice.className = "sand-notice failed";
  }).finally(() => {
    button.disabled = false;
    if (notice.textContent === "正在保存…") notice.hidden = true;
  });
}
