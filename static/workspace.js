// Warn when leaving edited transaction forms, but permit deliberate submission.
const editedForms = new Set();
document.querySelectorAll('form[method="post"]:not([data-no-dirty])').forEach(form => {
  form.addEventListener('input', () => editedForms.add(form));
  form.addEventListener('change', () => editedForms.add(form));
  form.addEventListener('submit', event => {
    if (form.dataset.submitting) { event.preventDefault(); return; }
    if (event.defaultPrevented) return;
    form.dataset.submitting = 'true';
    editedForms.clear();
  });
});
window.addEventListener('beforeunload', event => {
  if (editedForms.size) { event.preventDefault(); event.returnValue = ''; }
});
window.addEventListener('pageshow', () => document.querySelectorAll('form[data-submitting]').forEach(form => delete form.dataset.submitting));
const error = document.querySelector('[role="alert"]');
if (error) error.focus();
