// Contact reveal: load the site key, render the reCAPTCHA checkbox, then ask the server for the address.
(() => {
  const box = document.getElementById('contact-captcha');
  const status = document.getElementById('contact-status');
  const result = document.getElementById('contact-result');
  if (!box) return;
  const say = (text) => { status.textContent = text; };

  window.openhraCaptchaReady = async () => {
    try {
      const config = await fetch('/api/contact').then((r) => r.ok ? r.json() : Promise.reject());
      window.grecaptcha.render(box, { sitekey: config.siteKey, callback: reveal, 'expired-callback': () => say('The check expired. Tick the box again.') });
      say('Tick the box to show the address.');
    } catch { say('Contact is not available right now. Please try again later.'); }
  };

  async function reveal(token) {
    say('Checking…');
    try {
      const response = await fetch('/api/contact', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token }) });
      if (!response.ok) throw new Error();
      const { email } = await response.json();
      const link = document.createElement('a');
      link.href = 'mailto:' + email;
      link.textContent = email;
      result.replaceChildren(link);
      result.hidden = false;
      box.hidden = true;
      say('');
    } catch {
      say('The check did not pass. Reload the page and try again.');
      window.grecaptcha.reset();
    }
  }
})();
