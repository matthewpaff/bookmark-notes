// Optional enhancement: all forms, search, and navigation also work without JS.
document.addEventListener('keydown', (event) => {
  const editing = event.target.closest('input, textarea, select, [contenteditable]');
  if (event.key === '/' && !editing && !event.ctrlKey && !event.metaKey && !event.altKey) {
    const search = document.getElementById('search');
    if (search) {
      event.preventDefault();
      search.focus();
    }
  }
});
