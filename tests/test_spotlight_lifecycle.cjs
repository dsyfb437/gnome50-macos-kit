// Tests candidate source with an actor-tree mock. Does not run inside GNOME.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = process.argv[2];
if (!root) throw new Error('Pass the reviewed Spotlight source directory');
class Actor {
  constructor(opts={}) { this.children=[]; this.parent=null; this.visible=opts.visible ?? true; this.destroyed=false; }
  get_parent() { return this.parent; }
  add_child(a) { assert.equal(a.parent,null); this.children.push(a); a.parent=this; }
  remove_child(a) { assert.equal(a.parent,this); this.children.splice(this.children.indexOf(a),1); a.parent=null; }
  hide() { this.visible=false; }
  show() { this.visible=true; }
  destroy() { assert.equal(this.children.length,0,'parking must not destroy native search widgets'); this.parent?.remove_child(this); this.destroyed=true; }
  add_style_class_name() {}
  remove_style_class_name() {}
  grab_key_focus() {}
  remove_all_transitions() { this.transitionsRemoved=true; }
  get_stage() { for (let n=this; n; n=n.parent) if(n.isStage) return n; return null; }
}
const stage=new Actor(); stage.isStage=true;
let connected=0, disconnected=0;
stage.connect=()=>++connected; stage.disconnect=()=>disconnected++;
global.stage=stage;
const uiGroup=new Actor(); stage.add_child(uiGroup);
const controls=new Actor(); uiGroup.add_child(controls);
const entry=new Actor(), search=new Actor(); controls.add_child(entry); controls.add_child(search);
let originalCalls=0;
const activateDefault=()=>originalCalls++, activate=()=>originalCalls++, cancelled=()=>{};
search._searchResults={activateDefault,activate}; search._searchCancelled=cancelled;
search._text={set_text(){},disconnect(){}};
const Main={uiGroup,overview:{searchEntry:entry,searchController:search,visible:false,toggle(){}},layoutManager:{addChrome(a){uiGroup.add_child(a)},removeChrome(a){a.parent.remove_child(a)}}};
const Clutter={Actor,EventType:{KEY_PRESS:1},EVENT_PROPAGATE:0,EVENT_STOP:1,keysym_to_unicode:x=>x};
const clean = file => fs.readFileSync(path.join(root,file),'utf8').replace(/^import .*;\r?\n/gm,'').replace(/^export /gm,'');
const Stealer=new Function('Main','Clutter',clean('lib/overview/searchStealer.js')+'\nreturn OverviewSearchStealer;')(Main,Clutter);
const Popup=new Function('Main','St','Clutter','GLib','GObject','Gio','PopupBackdrop','PopupPositioner','OverviewSearchStealer','ThumbnailEnhancer','installCloseDefense','uninstallCloseDefense','applyTheme','scheduleIdle','cancelIdle','trackTextVisibility','connectGlobalSignals','disconnectGlobalSignals',clean('lib/popup/widget/spotlightPopup.js')+'\nreturn SpotlightPopup;')(
  Main,{Widget:Actor},Clutter,{}, {registerClass:x=>x},{}, class extends Actor {constructor(){super()}}, class {},Stealer,class {},()=>{},()=>{},()=>{},(o,k,fn)=>fn(),()=>{},()=>1,()=>{},()=>{});
let checks=0;
function check(name,fn){ fn(); checks++; console.log('PASS '+name); }
const popup=new Popup(); popup._content=new Actor(); popup.add_child(popup._content);
popup._stealer=new Stealer(popup); popup._positioner={stop(){},getTargetMonitor(){return{}},showCentered(fn){fn()}};
popup._textChangedEventId=0;popup._openIdleId=0;popup._closeIdleId=0;popup._visible=false;popup._opening=false;
let animations=0;popup._animateClose=done=>{animations++;done()};
check('steal parks both native actors under Shell stage',()=>{popup._stealer.steal();assert.equal(entry.get_stage(),stage);assert.equal(search.get_stage(),stage);assert.equal(entry.parent.visible,false)});
check('steal is idempotent',()=>{const p=entry.parent;popup._stealer.steal();assert.equal(entry.parent,p);assert.equal(connected,1)});
check('open transfers parked actors to popup on stage',()=>{popup._doOpen();assert.equal(search.parent,popup._content);assert.equal(search.get_stage(),stage);assert.equal(popup._visible,true)});
check('normal close parks actors before removing popup chrome',()=>{popup._doClose();assert.equal(search.get_stage(),stage);assert.notEqual(search.parent,popup._content);assert.equal(popup.parent,null);assert.equal(animations,1)});
check('repeated open/close does not orphan search',()=>{for(let i=0;i<10;i++){popup._doOpen();popup._doClose();assert.equal(search.get_stage(),stage);assert.equal(entry.get_stage(),stage)}});
check('sync close removes transitions without animation callback',()=>{popup._doOpen();const count=animations;popup._syncClose();assert.equal(animations,count);assert.equal(popup.transitionsRemoved,true);assert.equal(popup.parent,null)});
check('restore returns original parents and callbacks',()=>{popup._stealer.restore();assert.equal(entry.parent,controls);assert.equal(search.parent,controls);assert.equal(search._searchResults.activateDefault,activateDefault);assert.equal(search._searchResults.activate,activate);assert.equal(search._searchCancelled,cancelled);assert.equal(popup._stealer._parkingActor,null)});
check('restore is idempotent and disconnects once',()=>{popup._stealer.restore();assert.equal(disconnected,1)});
check('disable sequence drains popup before restoring native widgets',()=>{const text=clean('extension.js');assert.ok(text.indexOf('this._popup._syncClose();')<text.indexOf('this._popup.returnOverviewSearch();'))});
console.log(`${checks} lifecycle checks passed; real GNOME visual validation still required after login`);
