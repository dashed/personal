// ==UserScript==
// @name         Readable http://www.randomservices.org/
// @namespace    http://tampermonkey.net/
// @version      0.1
// @description  try to take over the world!
// @author       You
// @match        *.randomservices.org/*
// @grant        none
// ==/UserScript==

(function () {
  "use strict";

  document.body.style.margin = "auto";
  document.body.style.width = "700px";
  document.body.style.fontSize = "1.2rem";

  // https://github.com/vincentdoerig/latex-css
  const head = document.getElementsByTagName("head")[0];
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.type = "text/css";
  link.href = "https://latex.now.sh/style.css";
  link.media = "all";
  head.appendChild(link);

  const styles = `
dfn {
  font-weight: bold;
}

img {
  margin: auto;
}

div.exercise {
  padding: 16px;
}

p.proof {
  margin: unset;
}
`;

  // https://stackoverflow.com/questions/707565/how-do-you-add-css-with-javascript
  const styleSheet = document.createElement("style");
  styleSheet.type = "text/css";
  styleSheet.innerText = styles;
  document.head.appendChild(styleSheet);

  const headers = document
    .querySelector("body")
    .querySelectorAll("h1[id],h2[id],h3[id],h4[id],h5[id],h6[id]");

  Array.prototype.forEach.call(headers, function (element) {
    const anchor = document.createElement("a");
    anchor.textContent = "¶";
    anchor.style.display = "none";
    anchor.style.cursor = "pointer";

    anchor.addEventListener("click", function (e) {
      e.preventDefault();

      window.location.hash = this.parentNode.getAttribute("id");
    });

    element.appendChild(document.createTextNode(" "));
    element.appendChild(anchor);

    element.parentNode.addEventListener("mouseover", function () {
      anchor.style.display = "inline";
    });

    element.parentNode.addEventListener("mouseout", function () {
      anchor.style.display = "none";
    });
  });
})();
