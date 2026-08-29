/* ============================================================
   Palamedes — motion.js

   Drives motion.css. No library, no build step, wired the same
   way as app.js: feature-detected, delegated where possible,
   and silent when the visitor prefers reduced motion — in that
   case nothing here touches the DOM and the page stays exactly
   as the server sent it.
   ============================================================ */

(function () {
    "use strict";

    var reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    var fine = window.matchMedia("(hover: hover) and (pointer: fine)");

    /* --------------------------------------------------------
       1. Reveal — staggered entrance for the page's blocks

       Targets are collected, descendants of other targets are
       dropped (so a card inside a revealed column doesn't move
       twice), and each element is delayed by its position among
       its revealed siblings. Elements already on screen at load
       fire immediately, which is what makes the load sequence.
       -------------------------------------------------------- */

    function initReveal() {
        var els = Array.prototype.slice.call(document.querySelectorAll(
            ".hero .stack > *, .grid > *, .bento > *, .stat, .widget, .member-card, .main > .card"
        ));

        els = els.filter(function (el) {
            var p = el.parentElement;
            while (p) {
                if (els.indexOf(p) !== -1) return false;
                p = p.parentElement;
            }
            return true;
        });

        if (!els.length) return;

        // Stagger index within each parent group.
        var groups = new Map();
        els.forEach(function (el) {
            var key = el.parentElement || document.body;
            var i = groups.get(key) || 0;
            groups.set(key, i + 1);
            el.style.setProperty("--rv-delay", Math.min(i * 70, 420) + "ms");
            el.classList.add("rv");
        });

        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                entry.target.classList.add("rv--in");
                io.unobserve(entry.target);
            });
        }, { threshold: 0.1, rootMargin: "0px 0px -32px" });

        els.forEach(function (el) { io.observe(el); });
    }

    /* --------------------------------------------------------
       2. The headline wave

       Display headlines are split into words and characters.
       Words are atomic (white-space: nowrap), so line breaks
       land exactly where they did before the split. The heading
       keeps its text for assistive tech via aria-label; the
       spans are hidden from it.

       On pointer move, each character within reach lifts in
       proportion to its distance from the cursor and the
       closest ones turn gold — type you can run a hand across.
       -------------------------------------------------------- */

    function splitHeadline(el) {
        el.setAttribute("aria-label", el.textContent);

        var wrap = document.createElement("span");
        wrap.setAttribute("aria-hidden", "true");

        function splitNode(node, into) {
            Array.prototype.slice.call(node.childNodes).forEach(function (child) {
                if (child.nodeType === Node.TEXT_NODE) {
                    // Split on regular spaces only; nbsp stays inside its word.
                    child.textContent.split(" ").forEach(function (word, i) {
                        if (i > 0) into.appendChild(document.createTextNode(" "));
                        if (!word) return;
                        var w = document.createElement("span");
                        w.className = "word";
                        Array.prototype.forEach.call(word, function (ch) {
                            var c = document.createElement("span");
                            c.className = "char";
                            c.textContent = ch;
                            w.appendChild(c);
                        });
                        into.appendChild(w);
                    });
                } else if (child.nodeName === "BR") {
                    into.appendChild(child);
                } else {
                    // <strong> etc: recurse, keeping the wrapper.
                    var clone = child.cloneNode(false);
                    splitNode(child, clone);
                    into.appendChild(clone);
                }
            });
        }

        splitNode(el, wrap);
        el.textContent = "";
        el.appendChild(wrap);
        return wrap.querySelectorAll(".char");
    }

    function attachWave(el) {
        var chars = splitHeadline(el);
        var px = 0, py = 0, raf = null;

        function update() {
            raf = null;
            var reach = 110;
            Array.prototype.forEach.call(chars, function (c) {
                var b = c.getBoundingClientRect();
                var dx = px - (b.left + b.width / 2);
                var dy = py - (b.top + b.height / 2);
                var d = Math.sqrt(dx * dx + dy * dy);
                if (d < reach) {
                    var t = 1 - d / reach;
                    t = t * t * (3 - 2 * t); // smoothstep
                    c.style.transform = "translateY(" + (-t * 0.16).toFixed(3) + "em)";
                    c.style.color = t > 0.4 ? "var(--gold-ink, var(--royal))" : "";
                } else {
                    c.style.transform = "";
                    c.style.color = "";
                }
            });
        }

        el.addEventListener("pointermove", function (e) {
            px = e.clientX;
            py = e.clientY;
            if (!raf) raf = window.requestAnimationFrame(update);
        });

        el.addEventListener("pointerleave", function () {
            if (raf) { window.cancelAnimationFrame(raf); raf = null; }
            Array.prototype.forEach.call(chars, function (c) {
                c.style.transform = "";
                c.style.color = "";
            });
        });
    }

    function initWave() {
        if (!fine.matches) return;
        document.querySelectorAll(".display-xl").forEach(attachWave);
    }

    /* --------------------------------------------------------
       3. Numbers count up, meters fill in

       Both wait for their card to scroll into view. The count-up
       preserves whatever surrounds the number — "$", ".00",
       thousands commas — so "$1,240.50" lands as itself.
       -------------------------------------------------------- */

    function countUp(el) {
        var text = el.textContent;
        var m = text.match(/-?\d[\d,]*(?:\.(\d+))?/);
        if (!m) return;

        var raw = m[0];
        var decimals = m[1] ? m[1].length : 0;
        var target = parseFloat(raw.replace(/,/g, ""));
        if (!isFinite(target) || target === 0) return;

        var grouped = raw.indexOf(",") !== -1;
        var prefix = text.slice(0, m.index);
        var suffix = text.slice(m.index + raw.length);
        var dur = 900;
        var start = null;

        function fmt(v) {
            if (grouped) {
                return v.toLocaleString("en-US", {
                    minimumFractionDigits: decimals,
                    maximumFractionDigits: decimals
                });
            }
            return v.toFixed(decimals);
        }

        function step(ts) {
            if (start === null) start = ts;
            var p = Math.min(1, (ts - start) / dur);
            var eased = 1 - Math.pow(1 - p, 3);
            el.textContent = prefix + fmt(target * eased) + suffix;
            if (p < 1) window.requestAnimationFrame(step);
        }

        window.requestAnimationFrame(step);
    }

    function initFigures() {
        var values = document.querySelectorAll(".stat__value, .widget__value");
        var meters = document.querySelectorAll(".meter__fill");

        // Meters start empty; the target width is kept for later.
        meters.forEach(function (m) {
            if (!m.style.width) return;
            m.dataset.w = m.style.width;
            m.style.width = "0%";
        });

        if (!values.length && !meters.length) return;

        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                var el = entry.target;
                io.unobserve(el);

                if (el.dataset.w) {
                    // Reflow so the 0% start is committed before the
                    // transition class lands.
                    void el.offsetWidth;
                    el.classList.add("meter__fill--anim");
                    el.style.width = el.dataset.w;
                } else {
                    countUp(el);
                }
            });
        }, { threshold: 0.4 });

        values.forEach(function (el) { io.observe(el); });
        meters.forEach(function (el) { if (el.dataset.w) io.observe(el); });
    }

    /* --------------------------------------------------------
       4. Magnetic buttons

       Primary and outline buttons lean a few pixels toward the
       pointer and settle back on leave. The existing transform
       transition on .btn smooths both directions.
       -------------------------------------------------------- */

    function initMagnetic() {
        if (!fine.matches) return;

        document.querySelectorAll(".btn--primary, .btn--outline").forEach(function (btn) {
            btn.addEventListener("pointermove", function (e) {
                var b = btn.getBoundingClientRect();
                var dx = (e.clientX - (b.left + b.width / 2)) / (b.width / 2);
                var dy = (e.clientY - (b.top + b.height / 2)) / (b.height / 2);
                btn.style.transform =
                    "translate(" + (dx * 3).toFixed(1) + "px," + (dy * 2).toFixed(1) + "px)";
            });
            btn.addEventListener("pointerleave", function () {
                btn.style.transform = "";
            });
        });
    }

    /* --------------------------------------------------------
       5. Card spotlight

       Feeds --mx/--my to the radial gradient in motion.css.
       Delegated, so cards rendered later still glow.
       -------------------------------------------------------- */

    function initSpotlight() {
        if (!fine.matches) return;

        document.addEventListener("pointermove", function (e) {
            if (!e.target.closest) return;
            var el = e.target.closest(".stat, .widget, .card, .member-card");
            if (!el) return;
            var b = el.getBoundingClientRect();
            el.style.setProperty("--mx", (e.clientX - b.left) + "px");
            el.style.setProperty("--my", (e.clientY - b.top) + "px");
        }, { passive: true });
    }

    /* --------------------------------------------------------
       Boot
       -------------------------------------------------------- */

    function init() {
        if (reduced.matches) return;
        initReveal();
        initWave();
        initFigures();
        initMagnetic();
        initSpotlight();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
