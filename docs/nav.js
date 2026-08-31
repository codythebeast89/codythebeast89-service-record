(() => {
  const PAGES = ["index.html", "decorations.html", "events.html", "osb.html", "jsa.html", "asd.html", "swa.html", "kosovo.html", "afghanistan.html", "iraq.html"];
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function currentFile() {
    const path = window.location.pathname;
    return path.substring(path.lastIndexOf("/") + 1) || "index.html";
  }

  function initEnter() {
    const main = document.querySelector(".page-content");
    if (!main || reduceMotion) return;
    const dir = sessionStorage.getItem("page-transition-dir");
    sessionStorage.removeItem("page-transition-dir");
    if (dir === "forward") main.classList.add("page-enter-forward");
    else if (dir === "back") main.classList.add("page-enter-back");
    else main.classList.add("page-enter");
  }

  function bindNav() {
    document.querySelectorAll(".site-nav a.site-nav__link").forEach((link) => {
      link.addEventListener("click", (event) => {
        const href = link.getAttribute("href");
        if (!href || href.includes("://") || href.startsWith("#")) return;

        const from = currentFile();
        const fromIdx = PAGES.indexOf(from);
        const toIdx = PAGES.indexOf(href);
        if (fromIdx < 0 || toIdx < 0 || fromIdx === toIdx) {
          return;
        }

        sessionStorage.setItem(
          "page-transition-dir",
          toIdx > fromIdx ? "forward" : "back"
        );

        if (reduceMotion) return;

        const main = document.querySelector(".page-content");
        if (!main) return;

        event.preventDefault();
        const exitClass = toIdx > fromIdx ? "page-exit-forward" : "page-exit-back";
        main.classList.add(exitClass);
        window.setTimeout(() => {
          window.location.href = href;
        }, 280);
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      initEnter();
      bindNav();
    });
  } else {
    initEnter();
    bindNav();
  }
})();
