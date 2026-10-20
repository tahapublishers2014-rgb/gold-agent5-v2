const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

const html = fs.readFileSync('index.html', 'utf8');
const start = html.indexOf('function calcTradeSize(');
const end = html.indexOf('\nfunction scenCard(', start);
assert(start >= 0 && end > start, 'position answer functions not found');
const source = html.slice(start, end);
const storage = { value: null, getItem() { return this.value; }, setItem(_k, v) { this.value = v; } };
const context = {
  localStorage: storage,
  fmt: (x, n = 2) => Number(x).toFixed(n),
};
vm.runInNewContext(source, context);

const d = {
  updated: new Date().toISOString(),
  demo: false,
  simple: {
    key: 'wait', title: 'الان صبر کن', head: 'تایم‌فریم‌ها متعارض‌اند.',
    why: [['bad', 'تعارض تایم‌فریم‌ها: روزانه و هفتگی خلاف هم‌اند.']],
    conflicts: ['تعارض تایم‌فریم‌ها'], wait_for: ['منتظر هم‌جهت‌شدن بمان.'],
    plan: { side: 'خرید', entry: 2000, sl: 1990, tp1: 2020, tp2: 2030,
      risk: 10, equity: 10000, risk_pct: 1, active: true, note: 'طرح فرضی.' },
  },
};
assert(context.positionAnswer(d, 'بای یا سل؟').includes('الان صبر کن'));
assert(context.positionAnswer(d, 'چرا صبر کنم؟').includes('تعارض تایم‌فریم‌ها'));
assert(context.positionAnswer(d, 'حد ضرر و تارگت چیست؟').includes('حد ضرر 1990'));
assert(context.positionAnswer(d, 'حجم پوزیشن چقدر باشد؟').includes('لات'));
const stale = JSON.parse(JSON.stringify(d));
stale.updated = new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString();
assert(context.positionAnswer(stale, 'بای یا سل؟').includes('قدیمی'));
console.log('position answer tests passed');
