//the Pages dialog: which file is which page, said by hand where lining the comic up cannot settle it. what is
//said is kept in the comic's metadata, and every change lines the comic up again, so what is shown is always
//what the last alignment came to

let fixing = { name: "", pages: [], report: null, fixes: [], settled: true, show: "look", around: null, picture: null };

//an address as the server compares them: scheme, www and a trailing slash say nothing about which page it is
function pfSame(url) {
  return String(url || "").trim().replace(/^https?:\/\//i, "").replace(/^www\./i, "").replace(/\/+$/, "").toLowerCase();
}

function pfBase(src) {
  return String(src || "").split("?")[0].split("/").pop();
}

//the pin or drop said about a page, if any: by its address, and its picture where the address holds several,
//or by its number for a line the site has no address for
function pfFixFor(page) {
  return fixing.fixes.find((f) => (f.what === "pin" || f.what === "drop") && (f.url
    ? pfSame(f.url) === pfSame(page.url) && (!f.src || pfSame(f.src) === pfSame(page.src))
    : f.page === page.n));
}

//why each page wants looking at, by its number, from what the alignment reported
function pfWrongs() {
  const why = new Map();
  const say = (n, text) => why.set(n, (why.has(n) ? why.get(n) + "; " : "") + text);
  const report = fixing.report || {};
  for (const one of report.conflict || []) say(one.n, `the site gives it the size of ${one.sized_as.join(", ")}`);
  for (const one of report.astray || []) say(one.n, "this file is not the picture the site shows here");
  for (const one of report.trouble || []) {
    const span = String(one.where).match(/pages (\d+)-(\d+)/) || String(one.where).match(/after page (\d+)/);
    if (!span) continue;
    for (let n = Number(span[1]); n <= Number(span[2] || span[1]); n++) say(n, one.detail);
  }
  for (const page of fixing.pages) if (!page.file && page.how !== "dropped") say(page.n, "no file here for this page");
  return why;
}

function pfSummary(wrongs) {
  const report = fixing.report || {};
  const lines = [];
  lines.push(fixing.settled
    ? `<span class="good">Settled</span>: every file here is placed.`
    : `<span class="bad">Not settled</span>: it cannot be chaptered until what is below is put right.`);
  const said = [];
  for (const problem of report.fixes || []) said.push(`<span class="bad">A fix that could not be used:</span> ${esc(problem)}`);
  if ((report.spare || []).length) said.push(`${report.spare.length} file(s) here that no page claims, listed under the table.`);
  if ((report.conflict || []).length) said.push(`${report.conflict.length} page(s) whose size, by the site, is another file's.`);
  if ((report.trouble || []).length) said.push(`${report.trouble.length} stretch(es) where the pages walked and the files held do not count out.`);
  if (!fixing.report && fixing.pages.length) said.push("Lined up before alignments kept what stood in their way, so what is wrong cannot be shown yet: press <b>Line it up again</b>.");
  const fixed = fixing.fixes.length;
  if (fixed) said.push(`${fixed} page fix(es) said by hand.`);
  return lines.join("") + (said.length ? `<ul>${said.map((s) => `<li>${s}</li>`).join("")}</ul>` : "");
}

function pfVisible(wrongs) {
  const pages = fixing.pages;
  if (fixing.around) {
    const n = fixing.around;
    return pages.filter((p) => Math.abs(p.n - n) <= 10).map((p) => [p, p.n === n ? "" : "context"]);
  }
  if (fixing.show === "all") return pages.slice(0, 2000).map((p) => [p, ""]);
  const wanted = new Set();
  for (const page of pages) {
    const fixed = pfFixFor(page) || page.how === "hand" || page.how === "dropped";
    if (fixed || (fixing.show === "look" && wrongs.has(page.n))) wanted.add(page.n);
  }
  //a page either side, since a page out of place is told by its neighbours
  const shown = [];
  pages.forEach((page, at) => {
    const near = wanted.has(page.n) || (pages[at - 1] && wanted.has(pages[at - 1].n))
      || (pages[at + 1] && wanted.has(pages[at + 1].n));
    if (near) shown.push([page, wanted.has(page.n) ? "" : "context"]);
  });
  return shown.slice(0, 600);
}

function pfRow(page, kind, wrongs) {
  const fix = pfFixFor(page);
  const why = wrongs.get(page.n);
  const classes = [kind, why && !kind ? "wrong" : "", fix ? "fixed" : ""].filter(Boolean).join(" ");
  const said = fix ? (fix.what === "pin" ? `pinned by hand${fix.note ? ": " + fix.note : ""}`
    : `no page, said by hand${fix.note ? ": " + fix.note : ""}`) : "";
  return `<tr data-n="${page.n}" class="${classes}">
    <td>${page.n}</td>
    <td>${page.url ? `<a href="${esc(page.url)}" target="_blank" rel="noreferrer" title="${esc(page.url)}">${esc(page.short || page.title || page.url)}</a>`
      : `<span class="muted">no address</span>`}
      ${why ? `<span class="why">${esc(why)}</span>` : ""}${said ? `<span class="why" style="color:var(--ok)">${esc(said)}</span>` : ""}</td>
    <td class="file">${page.how === "dropped" ? `<span class="muted">none: not a page</span>`
      : `<input type="text" list="pf-files" spellcheck="false" value="${esc(page.file || "")}" data-pf="file" placeholder="no file">`}</td>
    <td class="muted">${esc(page.how || "-")}</td>
    <td class="site">${page.src ? `<a href="${esc(page.src)}" target="_blank" rel="noreferrer">${esc(pfBase(page.src))}</a>` : `<span class="muted">none</span>`}
      ${page.bytes ? `<span class="muted">${Number(page.bytes).toLocaleString()} bytes</span>` : ""}</td>
    <td>${page.how === "dropped" ? "" : `<button type="button" data-pf-act="pin" title="this page is the file beside it, whatever the site says of its picture">Pin</button>
        <button type="button" data-pf-act="picture" title="save the right picture for this page, from a file or an address">New picture</button>
        <button type="button" data-pf-act="drop" title="this line of the walk is no page at all">Not a page</button>`}
      ${fix ? `<button type="button" data-pf-act="forget">Undo</button>` : ""}</td>
  </tr>`;
}

function pfSpare() {
  const spare = (fixing.report || {}).spare || [];
  const strays = fixing.fixes.filter((f) => f.what === "stray");
  if (!spare.length && !strays.length) return "";
  const after = (f) => f.after ? (fixing.pages.find((p) => pfSame(p.url) === pfSame(f.after)) || {}).n : f.after_page;
  return `<b>Files the walk never saw</b>
    <div class="note">A page found elsewhere that the site has lost. Say which page it reads after and it is packed
      there, wherever its name sorts; left blank, it reads where its name sorts in the folder.</div>
    ${spare.map((name) => `<div class="row" data-pf-stray="${esc(name)}"><code>${esc(name)}</code>
      <span class="muted">reads after page</span><input type="number" min="1" style="width:7em" data-pf="after">
      <button type="button" data-pf-act="place">Place it</button></div>`).join("")}
    ${strays.map((f) => `<div class="row" data-pf-stray="${esc(f.file)}"><code>${esc(f.file)}</code>
      <span class="muted">${after(f) ? `reads after page ${after(f)}` : "reads where it sits"}, said by hand</span>
      <button type="button" data-pf-act="unplace">Undo</button></div>`).join("")}`;
}

function pfDraw() {
  const wrongs = pfWrongs();
  $("pf-said").innerHTML = pfSummary(wrongs);
  const shown = pfVisible(wrongs);
  $("pf-rows").innerHTML = shown.map(([page, kind]) => pfRow(page, kind, wrongs)).join("")
    || `<tr><td colspan="6" class="muted">${fixing.pages.length ? "Nothing here needs looking at." : "This comic has not been lined up against a walk, so there are no pages to show."}</td></tr>`;
  $("pf-count").textContent = fixing.pages.length ? `${shown.length} of ${fixing.pages.length} page(s) shown` : "";
  const files = new Set(fixing.pages.map((p) => p.file).filter(Boolean).concat((fixing.report || {}).spare || []));
  $("pf-files").innerHTML = [...files].map((f) => `<option value="${esc(f)}"></option>`).join("");
  $("pf-spare").innerHTML = pfSpare();
  $("pf-reset").disabled = !fixing.fixes.length;
}

async function pfLoad() {
  const held = await post("/api/pages", { name: fixing.name });
  fixing.pages = held.pages || [];
  fixing.report = held.report || null;
  fixing.fixes = held.fixes || [];
  fixing.settled = !!held.settled;
  $("pf-who").textContent = `${fixing.name} — ${fixing.pages.length} page(s)`;
  pfDraw();
}

async function pfSend(body, doing) {
  const msg = $("pf-msg");
  const keep = $("pf-wrap").scrollTop;
  msg.className = "msg";
  msg.textContent = doing || "Saying so, and lining the comic up again…";
  try {
    const result = await post("/api/pagefix", Object.assign({ name: fixing.name }, body));
    $("pf-out").innerHTML = `<pre>${esc(result.output || "")}</pre>`;
    await pfLoad();
    $("pf-wrap").scrollTop = keep;
    msg.className = result.settled ? "msg good" : "msg";
    msg.textContent = result.settled ? "Saved, and the comic is settled." : "Saved. It is not settled yet: see above.";
    return true;
  } catch (error) {
    msg.className = "msg bad";
    msg.textContent = error.message;
    return false;
  }
}

function pfPicture(n) {
  const page = fixing.pages.find((p) => p.n === n);
  fixing.picture = { n: n, data: null };
  $("pf-pic-what").textContent = `The right picture for page ${n}${page && page.file ? `, saved in place of ${page.file}` : ""}`;
  $("pf-pic-file").value = ""; $("pf-pic-url").value = "";
  $("pf-pic-preview").hidden = true; $("pf-pic-preview").removeAttribute("src");
  $("pf-picture").hidden = false;
  $("pf-picture").scrollIntoView({ block: "nearest" });
}

$("edit-pages").addEventListener("click", async () => {
  fixing = { name: editing.name, pages: [], report: null, fixes: [], settled: true, show: "look", around: null, picture: null };
  $("pf-show").value = "look"; $("pf-go").value = "";
  $("pf-msg").className = "msg"; $("pf-msg").textContent = "Reading which file is which page…";
  $("pf-picture").hidden = true; $("pf-out").innerHTML = ""; $("pf-out-box").open = false;
  $("pf-who").textContent = editing.name;
  pfDraw();
  $("pagefix").showModal();
  try {
    await pfLoad();
    $("pf-msg").textContent = "";
  } catch (error) {
    $("pf-msg").className = "msg bad";
    $("pf-msg").textContent = "Could not read this comic's pages: " + error.message;
  }
});
$("pf-show").addEventListener("change", () => { fixing.show = $("pf-show").value; fixing.around = null; $("pf-go").value = ""; pfDraw(); });
$("pf-go").addEventListener("change", () => {
  const n = Number($("pf-go").value);
  fixing.around = n > 0 ? n : null;
  pfDraw();
});
$("pf-rows").addEventListener("click", (event) => {
  const act = event.target.dataset.pfAct;
  if (!act) return;
  const row = event.target.closest("tr");
  const n = Number(row.dataset.n);
  if (act === "picture") { pfPicture(n); return; }
  if (act === "pin") {
    const file = (row.querySelector('[data-pf="file"]') || {}).value || "";
    if (!file.trim()) { $("pf-msg").className = "msg bad"; $("pf-msg").textContent = `Say which file page ${n} is, or give it a new picture.`; return; }
    pfSend({ at: String(n), file: file.trim() });
  } else if (act === "drop") {
    pfSend({ at: String(n), drop: true });
  } else if (act === "forget") {
    pfSend({ at: String(n), forget: true });
  }
});
$("pf-spare").addEventListener("click", (event) => {
  const act = event.target.dataset.pfAct;
  if (!act) return;
  const row = event.target.closest("[data-pf-stray]");
  const file = row.dataset.pfStray;
  if (act === "unplace") { pfSend({ file: file, forget: true }); return; }
  const after = (row.querySelector('[data-pf="after"]') || {}).value || "";
  pfSend({ file: file, after: after.trim() });
});
$("pf-pic-file").addEventListener("change", () => {
  const chosen = $("pf-pic-file").files[0];
  if (!chosen || !fixing.picture) return;
  $("pf-pic-url").value = "";
  const reader = new FileReader();
  reader.onload = () => {
    fixing.picture.data = reader.result;
    $("pf-pic-preview").src = reader.result;
    $("pf-pic-preview").hidden = false;
  };
  reader.readAsDataURL(chosen);
});
$("pf-pic-url").addEventListener("change", () => {
  const url = $("pf-pic-url").value.trim();
  if (!fixing.picture) return;
  fixing.picture.data = null;
  $("pf-pic-file").value = "";
  //shown from the site itself where it lets it be; one that refuses a picture shown elsewhere is still fetched
  $("pf-pic-preview").hidden = !url;
  if (url) $("pf-pic-preview").src = url;
});
$("pf-pic-go").addEventListener("click", async () => {
  const picked = fixing.picture;
  const url = $("pf-pic-url").value.trim();
  if (!picked || (!picked.data && !url)) {
    $("pf-msg").className = "msg bad"; $("pf-msg").textContent = "Choose a picture, or give its address.";
    return;
  }
  const body = picked.data ? { at: String(picked.n), picture: picked.data } : { at: String(picked.n), picture_url: url };
  if (await pfSend(body, "Saving the picture, and lining the comic up again…")) $("pf-picture").hidden = true;
});
$("pf-pic-cancel").addEventListener("click", () => { $("pf-picture").hidden = true; fixing.picture = null; });
$("pf-reset").addEventListener("click", () => {
  if (fixing.fixes.length && confirm("Undo every page fix said for this comic? The comic is lined up again without them.")) pfSend({ clear: true });
});
$("pf-align").addEventListener("click", () => pfSend({ align: true }, "Lining the comic up again…"));
$("pf-close").addEventListener("click", () => $("pagefix").close());
