/* Navi : la fée qui passe (thème Zelda). Utilisée par les écrans de titre et les alertes.
 *   NaviFairy.fly(conteneur, { duration: 6500 })  → fait traverser l'écran à une fée lumineuse (ailes qui battent, traînée d'étincelles)
 * La fée entre d'un côté au hasard, ondule en route et ressort de l'autre côté. Ne bloque rien (pointer-events: none).
 * Pensé pour le navigateur d'OBS (rendu logiciel) : uniquement des transformations / opacités (pas de flou animé, pas de lecture de
 * mise en page), halo en dégradé radial, nombre d'étincelles plafonné. */
(function () {
    if (window.NaviFairy) return;
    var css = [
        '.navi{position:fixed;left:0;top:0;width:3.4vw;height:3.4vw;pointer-events:none;z-index:6;will-change:transform}',
        '.navi .in{position:absolute;inset:0}',
        '.navi.ltr .in{transform:scaleX(-1)}',
        '.navi .halo{position:absolute;left:-60%;top:-60%;width:220%;height:220%;border-radius:50%;',
        'background:radial-gradient(circle,rgba(190,240,255,.85) 0,rgba(130,210,255,.45) 22%,rgba(110,200,255,.14) 48%,rgba(110,200,255,0) 70%)}',
        '.navi .orb{position:absolute;left:30%;top:30%;width:40%;height:40%;border-radius:50%;',
        'background:radial-gradient(circle,#fff 0,#fff 35%,#c4f4ff 65%,#8fdcff 100%)}',
        '.navi .wing{position:absolute;top:8%;width:46%;height:52%;opacity:.9;',
        'background:radial-gradient(ellipse at 90% 90%,rgba(255,255,255,.95),rgba(190,238,255,.6) 55%,rgba(150,220,255,0) 78%);',
        'border-radius:100% 0 100% 0;animation:navi-flap .16s ease-in-out infinite alternate}',
        '.navi .wing.r{left:52%;transform-origin:0 100%;transform:rotate(-24deg)}',
        '.navi .wing.l{left:2%;transform-origin:100% 100%;transform:scaleX(-1) rotate(-24deg);animation-name:navi-flap-l}',
        '@keyframes navi-flap{from{transform:rotate(-34deg) scaleY(.62)}to{transform:rotate(-8deg) scaleY(1.08)}}',
        '@keyframes navi-flap-l{from{transform:scaleX(-1) rotate(-34deg) scaleY(.62)}to{transform:scaleX(-1) rotate(-8deg) scaleY(1.08)}}',
        '.navi-spark{position:fixed;left:0;top:0;width:1.1vw;height:1.1vw;margin:-.55vw 0 0 -.55vw;border-radius:50%;pointer-events:none;z-index:5;opacity:0;',
        'background:radial-gradient(circle,#fff 0,#e2f8ff 30%,rgba(150,225,255,.55) 55%,rgba(150,225,255,0) 75%)}'
    ].join('');
    function ensureStyle() {
        if (document.getElementById('navi-css')) return;
        var st = document.createElement('style'); st.id = 'navi-css'; st.textContent = css; document.head.appendChild(st);
    }
    function rnd(a, b) { return a + Math.random() * (b - a); }
    var MAX_SPARKS = 14, sparks = 0;

    function fly(container, opts) {
        ensureStyle();
        opts = opts || {};
        var host = container || document.body;
        var dur = opts.duration || 6500;
        var el = document.createElement('div');
        // trajet : de gauche à droite (ou l'inverse), en ondulant ; positions en vw / vh pour suivre la taille de l'écran
        var ltr = opts.ltr != null ? opts.ltr : Math.random() < 0.5;
        // les ailes sont dessinées derrière la fée quand elle va vers la GAUCHE ; vers la droite on retourne le dessin (ailes toujours derrière)
        el.className = 'navi' + (ltr ? ' ltr' : '');
        el.innerHTML = '<div class="in"><div class="halo"></div><div class="wing l"></div><div class="wing r"></div><div class="orb"></div></div>';
        host.appendChild(el);

        var y0 = rnd(18, 70), amp = rnd(9, 20), waves = rnd(1.4, 2.6), phase = rnd(0, Math.PI * 2), drift = rnd(-12, 12);
        function point(t) {            // position (vw, vh) de la fée à l'instant t (0..1)
            var x = -6 + 112 * (ltr ? t : 1 - t);
            var y = y0 + drift * t + amp * Math.sin(phase + t * waves * Math.PI * 2) * (0.6 + 0.4 * Math.sin(t * Math.PI));
            return [x, y];
        }
        var N = 28, frames = [];
        for (var i = 0; i <= N; i++) {
            var p = point(i / N);
            frames.push({ transform: 'translate(' + p[0].toFixed(2) + 'vw,' + p[1].toFixed(2) + 'vh)', offset: i / N });
        }
        var anim = el.animate(frames, { duration: dur, easing: 'linear', fill: 'forwards' });

        // traînée d'étincelles : position calculée (aucune lecture de mise en page), une toutes les ~110 ms, 14 au maximum à l'écran
        var trail = setInterval(function () {
            if (!el.isConnected) return clearInterval(trail);
            if (sparks >= MAX_SPARKS) return;
            var t = Math.min(1, (anim.currentTime || 0) / dur), p = point(t);
            if (p[0] < -3 || p[0] > 103) return;
            var cx = p[0] / 100 * innerWidth + innerWidth * 0.017, cy = p[1] / 100 * innerHeight + innerWidth * 0.017;
            var s = document.createElement('div'); s.className = 'navi-spark';
            var life = rnd(0.9, 1.5) * 1000, dx = rnd(-2, 2) * innerWidth / 100, dy = rnd(1.2, 3.4) * innerWidth / 100;
            host.appendChild(s); sparks++;
            var a = s.animate([
                { opacity: 1, transform: 'translate(' + (cx + rnd(-5, 5)) + 'px,' + (cy + rnd(-5, 5)) + 'px) scale(1)' },
                { opacity: 0, transform: 'translate(' + (cx + dx) + 'px,' + (cy + dy) + 'px) scale(.15)' }
            ], { duration: life, easing: 'ease-out', fill: 'forwards' });
            a.onfinish = function () { s.remove(); sparks--; };
        }, 110);
        return new Promise(function (resolve) {
            anim.onfinish = function () { clearInterval(trail); el.remove(); resolve(); };
            anim.oncancel = function () { clearInterval(trail); el.remove(); resolve(); };
        });
    }
    window.NaviFairy = { fly: fly };
})();
