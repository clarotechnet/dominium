(() => {
  'use strict';
  // Login button automation only for Claro's initial screen.
  if (location.hostname !== 'cap.claro.com.br' ||
      !/^\/loginapp2fa\/?$/i.test(location.pathname)) return;
  const SESSION_KEY = 'dominium.claro-login.last-submit';
  const MIN_RETRY_MS = 60 * 1000;
  let stopped = false, timer;
  const stop = () => { stopped = true; if (timer) clearInterval(timer); };
  const hasChallenge = () => !!document.querySelector(
    'iframe[src*="recaptcha" i],iframe[src*="hcaptcha" i],' +
    '[id*="captcha" i],[class*="captcha" i],' +
    'input[name*="otp" i],input[autocomplete="one-time-code"]');
  function setInput(input, value) {
    const nativeSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    nativeSetter.call(input, '');
    input.dispatchEvent(new Event('input', {bubbles:true}));
    nativeSetter.call(input, value);
    input.dispatchEvent(new Event('input', {bubbles:true}));
    input.dispatchEvent(new Event('change', {bubbles:true}));
  }
  function scan() {
    if (stopped) return;
    if (hasChallenge()) { stop(); return; }
    const forms = document.querySelectorAll('form');
    if (forms.length !== 1) return;
    const form = forms[0];
    const username = form.querySelector('input[name="username"]');
    const password = form.querySelector('input[name="password"][type="password"]');
    const buttons = [...form.querySelectorAll('button,input[type="submit"]')].filter(b =>
      !b.disabled && String(b.tagName === 'INPUT' ? b.value : b.textContent).trim().toUpperCase() === 'ENVIAR');
    if (!username || !password || !username.value.trim() || !password.value || buttons.length !== 1) return;
    let last = 0;
    try { last = Number(sessionStorage.getItem(SESSION_KEY) || 0); } catch {}
    if (last && Date.now() - last < MIN_RETRY_MS) { stop(); return; }
    // Never copy, persist, send, or log any credentials. Use current Chrome autofill.
    const savedUser = username.value, savedPassword = password.value;
    try {
      setInput(username, savedUser);
      setInput(password, savedPassword);
      if (username.value !== savedUser || password.value !== savedPassword || hasChallenge()) { stop(); return; }
      try { sessionStorage.setItem(SESSION_KEY, String(Date.now())); } catch {}
      stop();
      buttons[0].click();
    } catch { stop(); }
  }
  timer = setInterval(scan, 350);
  scan();
})();