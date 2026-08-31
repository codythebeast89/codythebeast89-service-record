(() => {
  const PAGES = ["index.html", "decorations.html", "osb.html", "jsa.html", "asd.html", "swa.html", "kosovo.html", "afghanistan.html", "iraq.html"];
  const TRANSITION_MS = 780;
  const TRANSITION_KEY = "page-transition-active";
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function currentFile() {
    const path = window.location.pathname;
    return path.substring(path.lastIndexOf("/") + 1) || "index.html";
  }

  function transitionOverlay() {
    return document.getElementById("page-transition");
  }

  function restartTransitionMedia(overlay) {
    const media = overlay.querySelector("picture") || overlay.querySelector("img");
    if (!media) return;
    media.replaceWith(media.cloneNode(true));
  }

  function showTransitionOverlay() {
    const overlay = transitionOverlay();
    if (!overlay) return;
    restartTransitionMedia(overlay);
    overlay.hidden = false;
    overlay.setAttribute("aria-hidden", "false");
    overlay.classList.add("is-active");
  }

  function hideTransitionOverlay(delay = 0) {
    const overlay = transitionOverlay();
    if (!overlay) return;
    window.setTimeout(() => {
      overlay.classList.remove("is-active");
      window.setTimeout(() => {
        overlay.hidden = true;
        overlay.setAttribute("aria-hidden", "true");
      }, 240);
    }, delay);
  }

  function initEnter() {
    const main = document.querySelector(".page-content");
    const pending = sessionStorage.getItem(TRANSITION_KEY);
    sessionStorage.removeItem(TRANSITION_KEY);

    if (pending && !reduceMotion) {
      showTransitionOverlay();
      hideTransitionOverlay(520);
    }

    if (!main || reduceMotion) return;
    const dir = sessionStorage.getItem("page-transition-dir");
    sessionStorage.removeItem("page-transition-dir");
    if (dir === "forward") main.classList.add("page-enter-forward");
    else if (dir === "back") main.classList.add("page-enter-back");
    else main.classList.add("page-enter");
  }

  function navigateWithTransition(href, toIdx, fromIdx) {
    sessionStorage.setItem(
      "page-transition-dir",
      toIdx > fromIdx ? "forward" : "back"
    );
    sessionStorage.setItem(TRANSITION_KEY, "1");

    if (reduceMotion) {
      window.location.href = href;
      return;
    }

    showTransitionOverlay();
    const main = document.querySelector(".page-content");
    if (main) {
      const exitClass = toIdx > fromIdx ? "page-exit-forward" : "page-exit-back";
      main.classList.add(exitClass);
    }
    window.setTimeout(() => {
      window.location.href = href;
    }, TRANSITION_MS);
  }

  function bindTransitionLink(link) {
    link.addEventListener("click", (event) => {
      const href = link.getAttribute("href");
      if (!href || href.includes("://") || href.startsWith("#")) return;

      const from = currentFile();
      const fromIdx = PAGES.indexOf(from);
      const toIdx = PAGES.indexOf(href);
      if (fromIdx < 0 || toIdx < 0 || fromIdx === toIdx) return;

      event.preventDefault();
      navigateWithTransition(href, toIdx, fromIdx);
    });
  }

  function bindNav() {
    document.querySelectorAll(".site-nav a.site-nav__link").forEach(bindTransitionLink);
    const home = document.querySelector(".site-header__home");
    if (home) bindTransitionLink(home);
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
