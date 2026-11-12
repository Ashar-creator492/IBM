import { test } from 'node:test';
import assert from 'node:assert/strict';
import { PlaybackClock } from '../frontend/src/playback.ts';
test('play, pause, resume and speed preserve computed progress',()=>{
 const c=new PlaybackClock();c.begin(100,1);
 assert.equal(c.tick(10),10);c.paused=true;assert.equal(c.tick(30),10);
 c.paused=false;c.speed=2;assert.equal(c.tick(10),30);
});
test('reset/replay invalidate the previous animation and begin at depot',()=>{
 const c=new PlaybackClock();const first=c.begin(100,1);c.tick(30);
 const replay=c.begin(100,1);assert.notEqual(first,replay);assert.equal(c.value,0);
 assert.equal(c.tick(500),100);
});
test('drone stops at each target even at high playback speed',()=>{
 const c=new PlaybackClock();c.speed=4;c.begin(100,1,[20,50,100]);
 assert.equal(c.tick(100),20);assert.equal(c.tick(300),20);assert.equal(c.tick(350),20);
 assert.equal(c.tick(100),50);c.tick(650);assert.equal(c.tick(100),100);
});

import { searchFrame } from '../frontend/src/playback.ts';
test('search replay reconstructs the recorded live frontier separately from explored cells',()=>{
 const pairs=[{explored:[[0,0],[1,0],[2,0]],frontier_steps:[[[1,0]],[[2,0]],[]]}];
 assert.deepEqual(searchFrame(pairs,0),{explored:[],frontier:[[0,0]]});
 assert.deepEqual(searchFrame(pairs,1),{explored:[[0,0]],frontier:[[1,0]]});
 assert.deepEqual(searchFrame(pairs,3),{explored:[[0,0],[1,0],[2,0]],frontier:[]});
 assert.deepEqual(searchFrame(pairs,1),{explored:[[0,0]],frontier:[[1,0]]});
});
