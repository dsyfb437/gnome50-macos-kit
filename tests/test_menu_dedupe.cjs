// Pure-function test for the app-menu dedupe patch; does not run inside GNOME.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = process.argv[2];
if (!root) throw new Error('Pass a global-menu extension directory');
const src = fs.readFileSync(path.join(root, 'nativeMenu.js'), 'utf8')
  .replace(/^import .*;\r?\n/gm, '')
  .replace(/^export /gm, '');
// The top level imports GLib and the Shell popup module; splitBarMenus needs neither.
const code = src.match(/const stripMnemonic[\s\S]*?\n}\n[\s\S]*?export function splitBarMenus[\s\S]*?\n}\n/) ??
  src.match(/function stripMnemonic[\s\S]*?function splitBarMenus[\s\S]*?\n}\n/);
assert.ok(code, 'splitBarMenus and its helpers must be present');
const factory = new Function('GLib', 'PopupMenu', code[0] + '\nreturn {splitBarMenus};');
const {splitBarMenus} = factory({}, {});
let checks = 0;
function check(name, fn) { fn(); checks++; console.log('PASS ' + name); }

const qqMenu = {label: 'QQ', children: [{label: '设置'}, {label: '退出'}]};
const windowMenu = {label: '窗口', children: []};

check('QQ-like bar folds the same-named menu into the app menu', () => {
  const nodes = [qqMenu, windowMenu];
  const {bar, appMenu} = splitBarMenus(nodes, 'QQ');
  assert.deepEqual(bar.map(n => n.label), ['窗口']);
  assert.equal(appMenu, qqMenu);
  assert.equal(appMenu.children.length, 2);
});
check('Chrome-like bar keeps every menu', () => {
  const nodes = [{label: 'File'}, {label: 'Edit'}, {label: 'View'}];
  const {bar, appMenu} = splitBarMenus(nodes, 'Google Chrome');
  assert.deepEqual(bar.map(n => n.label), ['File', 'Edit', 'View']);
  assert.equal(appMenu, null);
});
check('An explicit appMenu node wins over label matching', () => {
  const app = {label: '', appMenu: true};
  const {bar, appMenu} = splitBarMenus([qqMenu, windowMenu, app], 'QQ');
  assert.deepEqual(bar.map(n => n.label), ['QQ', '窗口']);
  assert.equal(appMenu, app);
});
check('Separators and mnemonic underscores are ignored', () => {
  const nodes = [{separator: true}, {label: '_QQ'}, {label: '窗口'}];
  const {bar, appMenu} = splitBarMenus(nodes, 'QQ');
  assert.deepEqual(bar.map(n => n.label), ['窗口']);
  assert.equal(appMenu.label, '_QQ');
});
check('No app name leaves the bar untouched', () => {
  const nodes = [qqMenu, windowMenu];
  const {bar, appMenu} = splitBarMenus(nodes, null);
  assert.deepEqual(bar.map(n => n.label), ['QQ', '窗口']);
  assert.equal(appMenu, null);
});
console.log(`OK ${checks} checks`);
