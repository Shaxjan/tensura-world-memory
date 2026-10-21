#!/usr/bin/env node
"use strict";
/**
 * Read-only Threads editorial idea check.
 * Usage: node threads/radar/semantic_cli.js path/to/idea.json --as-of 2026-10-21
 * idea.json: {"text":"...","event":"...","characters":["..."],
 *             "viewpoint":"...","conflict":"...","conclusion":"..."}
 */
const fs = require("node:fs");
const path = require("node:path");
const {compare,krasnoyarskToday} = require("./semantic.js");

function lines(p) {
  return fs.readFileSync(p, "utf8").trim().split(/\r?\n/).filter(Boolean).map(JSON.parse);
}
function flags(argv, name, defaultValue) {
  const index = argv.indexOf(name);
  if(index < 0) return defaultValue;
  if(index + 1 >= argv.length) throw new Error("Missing value after " + name);
  return argv[index+1];
}
function main(argv=process.argv.slice(2)) {
  if(!argv.length || argv[0]==="--help") {
    console.log("node threads/radar/semantic_cli.js idea.json [--as-of YYYY-MM-DD] [--last-synced YYYY-MM-DD]");
    console.log("Checks published and editorial indexes. Nothing is posted or changed.");
    return;
  }
  if(argv[0].startsWith("--"))throw new Error("First argument must be the idea.json path");
  const input=JSON.parse(fs.readFileSync(argv[0], "utf8"));
  if(!input || typeof input!=="object" || Array.isArray(input))throw new Error("Idea must be a JSON object");
  const dir=path.join(__dirname,"index");
  const manifest=JSON.parse(fs.readFileSync(path.join(dir,"manifest.json"),"utf8"));
  const posts=lines(path.join(dir,"posts.jsonl")),journal=lines(path.join(dir,"editorial.jsonl"));
  const day=flags(argv,"--as-of",krasnoyarskToday());
  const sync=flags(argv,"--last-synced",manifest.generated_date_utc || null);
  const out=compare(input,posts,journal,{as_of:day,last_synced_at:sync,max_age_days:1});
  console.log(JSON.stringify({idea:input,checked_posts:posts.length,checked_editorial_cards:journal.length,...out},null,2));
}
try { main(); }catch(e) { console.error("Radar error:",e.message);process.exitCode=1; }
