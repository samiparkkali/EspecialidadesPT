// Drives a live example inside Rank My Preferences during the tour by dispatching real events at
// real DOM nodes. Module-level state tracks what the demo added so undoRankDemo can remove exactly
// that and nothing the user typed.

const setNativeValue = (input, value) => {
  const proto = input.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
  setter.call(input, value);
  input.dispatchEvent(new Event('input', { bubbles: true }));
};

const state = {
  searchFilled: false,
  numberFilled: false,
  preferenceAdded: false,
  pendingClickTimer: null,
};

export const DEMO_SPECIALTY = 'Cirurgia Geral';
export const DEMO_NUMBER = '1500';

export const demoFillSearch = () => {
  const input = document.querySelector('[data-tour="rank-filters"] input[type="text"]');
  if (!input || input.value === DEMO_SPECIALTY) return;
  setNativeValue(input, DEMO_SPECIALTY);
  state.searchFilled = true;
};

export const demoAddPreference = () => {
  demoFillSearch();
  window.clearTimeout(state.pendingClickTimer);
  state.pendingClickTimer = window.setTimeout(() => {
    state.pendingClickTimer = null;
    const buttons = document.querySelectorAll('[data-tour="rank-browse"] button');
    const target = DEMO_SPECIALTY.toLowerCase();
    const match = Array.from(buttons).find((b) => b.textContent.toLowerCase().includes(target));
    if (match && !match.disabled) {
      match.click();
      state.preferenceAdded = true;
    }
  }, 120);
};

export const demoFillNumber = () => {
  const input = document.querySelector('[data-tour="rank-number"] input[type="number"]');
  if (!input || input.value === DEMO_NUMBER) return;
  setNativeValue(input, DEMO_NUMBER);
  state.numberFilled = true;
};

// Reverts everything the demo changed, leaving any real ranking the user built untouched.
export const undoRankDemo = () => {
  window.clearTimeout(state.pendingClickTimer);
  state.pendingClickTimer = null;
  if (state.preferenceAdded) {
    // Selects by a stable data attribute rather than the button's aria-label,
    // which is localized (e.g. "Remover" in Portuguese, the default language)
    // and would silently never match once translated.
    const removeButtons = document.querySelectorAll(
      '[data-tour="rank-list"] button[data-tour-action="remove-preference"]'
    );
    const last = removeButtons[removeButtons.length - 1];
    last?.click();
    state.preferenceAdded = false;
  }
  if (state.numberFilled) {
    const input = document.querySelector('[data-tour="rank-number"] input[type="number"]');
    if (input) setNativeValue(input, '');
    state.numberFilled = false;
  }
  if (state.searchFilled) {
    const input = document.querySelector('[data-tour="rank-filters"] input[type="text"]');
    if (input) setNativeValue(input, '');
    state.searchFilled = false;
  }
};
