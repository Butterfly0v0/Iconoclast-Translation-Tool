/** Drag-resize table columns; persist widths in localStorage. */
function initResizableColumns(table, storageKey, defaultWidths) {
  if (!table || table.dataset.colResizeInit) return;
  table.dataset.colResizeInit = "1";
  table.classList.add("table-resizable");

  let colgroup = table.querySelector("colgroup");
  if (!colgroup) {
    colgroup = document.createElement("colgroup");
    table.querySelectorAll("thead th").forEach((th, i) => {
      const col = document.createElement("col");
      col.dataset.col = th.dataset.col || String(i);
      colgroup.appendChild(col);
    });
    table.insertBefore(colgroup, table.firstChild);
  }

  const cols = [...colgroup.querySelectorAll("col")];
  let saved = {};
  try {
    saved = JSON.parse(localStorage.getItem(storageKey) || "{}") || {};
  } catch {
    saved = {};
  }

  cols.forEach((col) => {
    const key = col.dataset.col;
    const w = saved[key] || defaultWidths[key];
    if (w) col.style.width = typeof w === "number" ? `${w}px` : w;
  });

  function persistWidths() {
    const widths = {};
    cols.forEach((col) => {
      widths[col.dataset.col] = col.style.width || defaultWidths[col.dataset.col];
    });
    localStorage.setItem(storageKey, JSON.stringify(widths));
  }

  table.querySelectorAll("thead th").forEach((th, i) => {
    if (th.querySelector(".col-resize")) return;
    const handle = document.createElement("div");
    handle.className = "col-resize";
    handle.title = "拖动调整列宽";
    th.appendChild(handle);

    handle.addEventListener("mousedown", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const col = cols[i];
      const startX = e.clientX;
      const startW = col.getBoundingClientRect().width;
      document.body.classList.add("col-resizing");
      handle.classList.add("active");

      function onMove(ev) {
        col.style.width = `${Math.max(36, startW + ev.clientX - startX)}px`;
      }

      function onUp() {
        document.body.classList.remove("col-resizing");
        handle.classList.remove("active");
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        persistWidths();
      }

      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
  });
}

function resetColumnWidths(table, storageKey, defaultWidths) {
  localStorage.removeItem(storageKey);
  delete table.dataset.colResizeInit;
  table.querySelectorAll("colgroup col").forEach((col) => {
    const key = col.dataset.col;
    col.style.width = defaultWidths[key]
      ? typeof defaultWidths[key] === "number"
        ? `${defaultWidths[key]}px`
        : defaultWidths[key]
      : "";
  });
  table.querySelectorAll(".col-resize").forEach((el) => el.remove());
  initResizableColumns(table, storageKey, defaultWidths);
}
