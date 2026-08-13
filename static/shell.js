(() => {
  const dock = document.querySelector('[data-rico-dock]');
  if (!dock) return;
  const toggle = dock.querySelector('.rico-dock-toggle');
  const panel = dock.querySelector('.rico-dock-panel');
  const close = dock.querySelector('[data-rico-close]');
  const input = dock.querySelector('textarea');
  const thread = dock.querySelector('[data-rico-thread]');
  const setOpen = (open) => { panel.hidden = !open; toggle.hidden = open; toggle.setAttribute('aria-expanded', String(open)); if (open) input.focus(); };
  toggle.addEventListener('click', () => setOpen(true)); close.addEventListener('click', () => setOpen(false));
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && !panel.hidden) setOpen(false); });
  dock.querySelectorAll('[data-rico-prompt]').forEach((button) => button.addEventListener('click', () => { input.value = button.dataset.ricoPrompt; input.focus(); }));
  dock.querySelector('[data-rico-form]').addEventListener('submit', async (event) => {
    event.preventDefault(); const question = input.value.trim(); if (!question) return;
    const user = document.createElement('div'); user.className = 'rico-dock-message is-user'; user.textContent = question; thread.append(user); input.value = '';
    const pending = document.createElement('div'); pending.className = 'rico-dock-message'; pending.textContent = 'Rico is thinking…'; thread.append(pending);
    try { const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''; const response = await fetch('/agent', {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':csrf}, body:JSON.stringify({question,agent:'rico'})}); const data = await response.json(); pending.textContent = data.answer || data.response || 'I could not answer just now. Try again in a moment.'; }
    catch (_) { pending.textContent = 'Connection slipped. Your message was not lost—please try once more.'; }
    thread.scrollTop = thread.scrollHeight;
  });
})();
