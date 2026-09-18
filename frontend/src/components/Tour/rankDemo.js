// Drives a live example inside Rank My Preferences during the tour, by
// dispatching real events at real DOM nodes -- the same nodes the user would
// click/type into -- so the tour shows the actual feature reacting instead
// of just describing it. Module-level state tracks what the demo itself
// added so undoRankDemo can remove exactly that and nothing the user typed.

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
};

export const DEMO_SPECIALTY = 'Cirurgia Geral';
export const DEMO_NUMBER = '1500';

// Types the example specialty into the browse search box.
export const demoFillSearch = () => {
  const input = document.querySelector('[data-tour="rank-filters"] input[type="text"]');
  if (!input || input.value === DEMO_SPECIALTY) return;
  setNativeValue(input, DEMO_SPECIALTY);
  state.searchFilled = true;
};

// Clicks the first filtered combo to add it to the ranking, demonstrating
// what "appears in the scratchpad" without the user having to click anything.
export const demoAddPreference = () => {
  demoFillSearch();
  window.setTimeout(() => {
    const buttons = document.querySelectorAll('[data-tour="rank-browse"] button');
    const match = Array.from(buttons).find((b) => b.textContent.includes(DEMO_SPECIALTY));
    if (match && !match.disabled) {
      match.click();
      state.preferenceAdded = true;
    }
  }, 120);
};

// Fills in an example Golden Ticket Number so the likelihood panel populates live.
export const demoFillNumber = () => {
  const input = document.querySelector('[data-tour="rank-number"] input[type="number"]');
  if (!input || input.value === DEMO_NUMBER) return;
  setNativeValue(input, DEMO_NUMBER);
  state.numberFilled = true;
};

// Reverts everything the demo itself changed, leaving any real ranking the
// user had built (or started building) untouched.
export const undoRankDemo = () => {
  if (state.preferenceAdded) {
    const removeButtons = document.querySelectorAll('[data-tour="rank-list"] button[aria-label="Remove"]');
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
