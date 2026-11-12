import {test} from 'node:test';
import assert from 'node:assert/strict';
import {moveCheckpoint,paintCells,cellBlocked,reviseEnvironment,revisionMatches} from '../frontend/src/environment.ts';
import {stitchRoute} from '../frontend/src/playback.ts';
const env=()=>({size:24,revision:1,nodes:[[3,3],[18,3],[18,18],[3,18]],obstacles:[[8,8]],zones:[{center:[12,12],radius:2}],pathfinding:'dijkstra'});
test('checkpoint edits preserve four nodes and reject overlap, obstacles and EW boundary cells',()=>{
 const e=env();const moved=moveCheckpoint(e,1,[16,5]);assert.deepEqual(moved.nodes[1],[16,5]);assert.equal(moved.nodes.length,4);assert.deepEqual(e.nodes[1],[18,3]);
 for(const c of [[3,3],[8,8],[12,12],[14,13],[-1,0],[24,0]])assert.throws(()=>moveCheckpoint(e,1,c));
});
test('paint/erase affect navigation and checkpoint cells cannot be painted',()=>{
 const e=env();const drawn=paintCells(e,[[5,5],[5,6]]);assert.ok(cellBlocked(drawn,[5,5]));
 const erased=paintCells(drawn,[[5,5]],true);assert.ok(!cellBlocked(erased,[5,5]));assert.ok(cellBlocked(erased,[5,6]));
 assert.throws(()=>paintCells(e,[[3,3]]));assert.equal(e.obstacles.length,1);
});
test('new revisions invalidate old computation responses, including undo content',()=>{
 const old=env(),edited=reviseEnvironment(moveCheckpoint(old,1,[16,5]),2),undo=reviseEnvironment(old,3);
 assert.ok(!revisionMatches(old,edited));assert.ok(!revisionMatches(edited,undo));assert.ok(revisionMatches({revision:3},undo));
});
test('flight follows the concatenated computed cells in both directions without modifying cached paths',()=>{
 const pairs=[{source:0,target:1,path:[[0,0],[1,0],[1,1]]},{source:1,target:2,path:[[1,1],[2,1]]},{source:2,target:3,path:[[2,1],[2,2]]},{source:0,target:3,path:[[0,0],[0,1],[0,2],[1,2],[2,2]]}];
 const original=structuredClone(pairs);
 for(const route of [[0,1,2,3,0],[0,3,2,1,0]]){const {path,stops}=stitchRoute(route,pairs);assert.deepEqual(path[0],path.at(-1));assert.equal(stops.size,4);for(let i=1;i<path.length;i++)assert.equal(Math.abs(path[i][0]-path[i-1][0])+Math.abs(path[i][1]-path[i-1][1]),1);}
 assert.deepEqual(pairs,original);assert.deepEqual(stitchRoute([0,2,0],pairs).path,[]);
});
