// Exercises the real NativeMenu._rebuild path with stubbed shell actors.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = process.argv[2];
if (!root) throw new Error('Pass a global-menu extension directory');
const src = fs.readFileSync(path.join(root, 'nativeMenu.js'), 'utf8')
  .replace(/^import .*;\r?\n/gm, '')
  .replace(/^export /gm, '');

class Button {
  constructor(label) { this.label = label; this.menu = {isOpen: false, close() {}}; }
  setLabel(label) { this.label = label; }
  getLabel() { return this.label; }
  setItems(fn) { this.items = fn; }
  destroy() { this.destroyed = true; }
}
const added = [];
const GLib = {idle_add: () => 0, source_remove: () => {}, PRIORITY_DEFAULT: 0, SOURCE_REMOVE: false};
const PopupMenu = {Ornament: {NONE: 0, CHECK: 1, DOT: 2}};
const factory = new Function('GLib', 'PopupMenu', 'MenuBarButton', 'addBarButton',
  src + '\nreturn {NativeMenu, splitBarMenus};');
const {NativeMenu} = factory(GLib, PopupMenu, Button, (role, btn) => added.push(btn));

function makeMenu(nodes, appName, appMenuSource) {
  added.length = 0;
  const proxy = {RequestMenuTree() {}, ActivateMenuItem() {}};
  const menu = new NativeMenu(proxy, 'uuid', source => { appMenuSource.source = source; });
  menu.setItems(nodes, appName);
  return {menu, buttons: added.slice()};
}

let checks = 0;
function check(name, fn) { fn(); checks++; console.log('PASS ' + name); }

check('same-named app menu is folded into the app-name button', () => {
  const appMenuSource = {};
  const {buttons} = makeMenu([
    {label: 'Menutest', children: [{label: '关于 Menutest'}, {label: '退出'}]},
    {label: '窗口', children: [{label: '最小化'}]},
  ], 'Menutest', appMenuSource);
  assert.deepEqual(buttons.map(b => b.label), ['窗口']);
  assert.equal(typeof appMenuSource.source, 'function');
  assert.deepEqual(appMenuSource.source().map(s => s.label), ['关于 Menutest', '退出']);
});

check('a normal app bar keeps every menu', () => {
  const appMenuSource = {};
  const {buttons} = makeMenu([{label: 'File'}, {label: 'Edit'}, {label: 'View'}], 'Google Chrome', appMenuSource);
  assert.deepEqual(buttons.map(b => b.label), ['File', 'Edit', 'View']);
  assert.ok(!appMenuSource.source, 'no app menu source for a normal app');
});

check('switching back to a normal app restores its bar', () => {
  const appMenuSource = {};
  makeMenu([{label: 'Menutest'}, {label: '窗口'}], 'Menutest', appMenuSource);
  const {buttons} = makeMenu([{label: 'File'}, {label: 'Edit'}], 'Chrome', appMenuSource);
  assert.deepEqual(buttons.map(b => b.label), ['File', 'Edit']);
});

check('explicit appMenu nodes are still used and not drawn in the bar', () => {
  const appMenuSource = {};
  const {buttons} = makeMenu([
    {label: 'File'}, {label: '', appMenu: true, children: [{label: 'Quit'}]},
  ], 'Gedit', appMenuSource);
  assert.deepEqual(buttons.map(b => b.label), ['File']);
  assert.deepEqual(appMenuSource.source().map(s => s.label), ['Quit']);
});

console.log(`OK ${checks} checks`);
