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
if(currentIndex.length!==459)throw Error("Test fixture requires a 459-root index");
const found=currentIndex.filter(row=>PROMOTED_IDS.has(String(row.post_id)));
if(found.length!==5)throw Error("All five promoted post IDs must remain indexed");
const legacyIndex=currentIndex.filter(row=>!PROMOTED_IDS.has(String(row.post_id)));
if(legacyIndex.length!==454)throw Error("Historical test baseline must contain 454 roots");
module.exports={currentIndex,legacyIndex,PROMOTED_IDS};
