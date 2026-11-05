/* Navi : la fée qui passe (thème Zelda). Utilisée par les écrans de titre et les alertes.
 *   NaviFairy.fly(conteneur, { duration: 6500 })  → fait traverser l'écran à une fée lumineuse (ailes qui battent, traînée d'étincelles)
 * La fée entre d'un côté au hasard, ondule en route et ressort de l'autre côté. Ne bloque rien (pointer-events: none). */
(function () {
    if (window.NaviFairy) return;
    var css = [
        '.navi{position:fixed;left:0;top:0;width:3.4vw;height:3.4vw;pointer-events:none;z-index:6;will-change:transform}',
        '.navi .in{position:absolute;inset:0}',
        '.navi.ltr .in{transform:scaleX(-1)}',
        '.navi .orb{position:absolute;left:30%;top:30%;width:40%;height:40%;border-radius:50%;',
        'background:radial-gradient(circle,#fff 0,#fff 30%,#bdf3ff 55%,#7fd8ff 100%);',
        'box-shadow:0 0 .9vw .35vw rgba(170,235,255,.95),0 0 2.6vw .9vw rgba(110,200,255,.55)}',
        '.navi .wing{position:absolute;top:8%;width:46%;height:52%;opacity:.9;',
        'background:radial-gradient(ellipse at 90% 90%,rgba(255,255,255,.95),rgba(190,238,255,.6) 55%,rgba(150,220,255,0) 78%);',
        'border-radius:100% 0 100% 0;animation:navi-flap .12s ease-in-out infinite alternate}',
        '.navi .wing.r{left:52%;transform-origin:0 100%;transform:rotate(-24deg)}',
        '.navi .wing.l{left:2%;transform-origin:100% 100%;transform:scaleX(-1) rotate(-24deg);animation-name:navi-flap-l}',
        '@keyframes navi-flap{from{transform:rotate(-34deg) scaleY(.62)}to{transform:rotate(-8deg) scaleY(1.08)}}',
        '@keyframes navi-flap-l{from{transform:scaleX(-1) rotate(-34deg) scaleY(.62)}to{transform:scaleX(-1) rotate(-8deg) scaleY(1.08)}}',
        '.navi-spark{position:fixed;width:.55vw;height:.55vw;margin:-.275vw 0 0 -.275vw;border-radius:50%;pointer-events:none;z-index:5;',
        'background:#f2fcff;box-shadow:0 0 .7vw .25vw rgba(160,230,255,.9);animation:navi-spark var(--sd,1.1s) ease-out forwards}',
        '@keyframes navi-spark{0%{opacity:1;transform:translate(0,0) scale(1)}100%{opacity:0;transform:translate(var(--sx,0),var(--sy,2vw)) scale(.1)}}'
    ].join('');
    function ensureStyle() {
        if (document.getElementById('navi-css')) return;
        var st = document.createElement('style'); st.id = 'navi-css'; st.textContent = css; document.head.appendChild(st);
    }
    function rnd(a, b) { return a + Math.random() * (b - a); }

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
        el.innerHTML = '<div class="in"><div class="wing l"></div><div class="wing r"></div><div class="orb"></div></div>';
        host.appendChild(el);
        var y0 = rnd(18, 70), amp = rnd(9, 20), waves = rnd(1.4, 2.6), phase = rnd(0, Math.PI * 2), drift = rnd(-12, 12);
        var N = 28, frames = [];
        for (var i = 0; i <= N; i++) {
            var t = i / N;
            var x = -6 + 112 * (ltr ? t : 1 - t);
            var y = y0 + drift * t + amp * Math.sin(phase + t * waves * Math.PI * 2) * (0.6 + 0.4 * Math.sin(t * Math.PI));
            frames.push({ transform: 'translate(' + x.toFixed(2) + 'vw,' + y.toFixed(2) + 'vh)', offset: t });
        }
        var anim = el.animate(frames, { duration: dur, easing: 'linear', fill: 'forwards' });

        // traînée d'étincelles : une toutes les ~70 ms à l'endroit où se trouve la fée
        var trail = setInterval(function () {
            if (!el.isConnected) return clearInterval(trail);
            var r = el.getBoundingClientRect();
            if (r.right < 0 || r.left > innerWidth) return;
            var s = document.createElement('div'); s.className = 'navi-spark';
            s.style.left = (r.left + r.width / 2 + rnd(-6, 6)) + 'px'; s.style.top = (r.top + r.height / 2 + rnd(-6, 6)) + 'px';
            s.style.setProperty('--sx', rnd(-2, 2) + 'vw'); s.style.setProperty('--sy', rnd(1.2, 3.4) + 'vw'); s.style.setProperty('--sd', rnd(0.8, 1.5) + 's');
            host.appendChild(s); setTimeout(function () { s.remove(); }, 1700);
        }, 70);
        return new Promise(function (resolve) {
            anim.onfinish = function () { clearInterval(trail); el.remove(); resolve(); };
            anim.oncancel = function () { clearInterval(trail); el.remove(); resolve(); };
        });
    }
    window.NaviFairy = { fly: fly };
})();
