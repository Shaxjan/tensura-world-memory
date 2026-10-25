"use strict";
/** Historical 454-root snapshot used only for tests of pre-promotion behavior.
 * These five IDs were promoted on 2026-10-25 and must remain in the live index.
 */
const fs=require("node:fs");
const path=require("node:path");
const PROMOTED_IDS=new Set([
 "18058181561570070","17899242612398487","18152771278539108",
 "18472636933140300","17915165559493626"
]);
const currentIndex=fs.readFileSync(path.join(__dirname,"index/posts.jsonl"),"utf8")
 .trim().split(/\r?\n/).map(JSON.parse);
const r5=JSON.parse(fs.readFileSync(path.join(__dirname,"reserve/ideas-2026-10-25-r5.json"),"utf8"));
const baseIDs=new Set(r5.source_index_post_ids);
if(baseIDs.size!==459||currentIndex.length<459)throw Error("R5 baseline invalid or current corpus shrank");
const r5Index=currentIndex.filter(row=>baseIDs.has(String(row.post_id)));
if(r5Index.length!==459)throw Error("R5 historical roots were discarded");
const found=r5Index.filter(row=>PROMOTED_IDS.has(String(row.post_id)));
if(found.length!==5)throw Error("All five promoted post IDs must remain indexed");
const legacyIndex=r5Index.filter(row=>!PROMOTED_IDS.has(String(row.post_id)));
if(legacyIndex.length!==454)throw Error("Historical test baseline must contain 454 roots");
module.exports={currentIndex,r5Index,legacyIndex,PROMOTED_IDS};
