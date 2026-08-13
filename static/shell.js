(() => {
  const dock = document.querySelector('[data-rico-dock]');
  if (dock) {
    const toggle = dock.querySelector('.rico-chat-identity');
    const close = dock.querySelector('[data-rico-close]');
    const input = dock.querySelector('textarea');
    const thread = dock.querySelector('[data-rico-thread]');
    const setOpen = (open) => {
      dock.dataset.state = open ? 'expanded' : 'collapsed';
      toggle.setAttribute('aria-expanded', String(open));
      if (open) input.focus(); else toggle.focus();
    };
    toggle.addEventListener('click', () => setOpen(dock.dataset.state !== 'expanded'));
    close.addEventListener('click', () => setOpen(false));
    document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && dock.dataset.state === 'expanded') setOpen(false); });
    dock.querySelectorAll('[data-rico-prompt]').forEach((button) => button.addEventListener('click', () => { input.value = button.dataset.ricoPrompt; input.focus(); }));
    input.addEventListener('input', () => { input.style.height = 'auto'; input.style.height = `${Math.min(input.scrollHeight, 112)}px`; });
    dock.querySelector('[data-rico-form]').addEventListener('submit', async (event) => {
      event.preventDefault(); const question = input.value.trim(); if (!question) return;
      const user = document.createElement('div'); user.className = 'rico-message rico-message-user'; user.innerHTML = '<p></p>'; user.querySelector('p').textContent = question; thread.append(user); input.value = ''; input.style.height = 'auto';
      const pending = document.createElement('div'); pending.className = 'rico-message rico-message-coach'; pending.innerHTML = '<img src="/static/coqui-coach.svg" alt=""><p>Rico is thinking…</p>'; thread.append(pending); thread.scrollTop = thread.scrollHeight;
      try { const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''; const response = await fetch('/agent', {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':csrf}, body:JSON.stringify({question,agent:'rico'})}); const data = await response.json(); pending.querySelector('p').textContent = data.answer || 'I could not answer just now. Try again in a moment.'; }
      catch (_) { pending.querySelector('p').textContent = 'Connection slipped. Please try once more.'; }
      thread.scrollTop = thread.scrollHeight;
    });
  }
  const password = document.querySelector('[data-password-input]');
  const reveal = document.querySelector('[data-password-toggle]');
  if (password && reveal) reveal.addEventListener('click', () => { const showing = password.type === 'text'; password.type = showing ? 'password' : 'text'; reveal.setAttribute('aria-pressed', String(!showing)); reveal.textContent = showing ? 'Show' : 'Hide'; });
})();
