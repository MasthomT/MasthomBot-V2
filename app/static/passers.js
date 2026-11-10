/* Personnages qui traversent l'écran des titres selon le thème (traîneau, drone, Pac-Man, baleine, soucoupe, bateau pirate, papillons…).
 * Comme la fée Navi : un petit SVG dessiné tourné vers la droite, déplacé par transform seulement (léger pour OBS), retourné quand il va vers la gauche.
 * Usage : Passers.fly(conteneur, 'sleigh') */
(function () {
  var NS = 'http://www.w3.org/2000/svg';
  var css = document.createElement('style');
  css.textContent =
    '.pass{position:absolute;left:0;top:0;pointer-events:none;will-change:transform}' +
    '.pass svg{display:block;width:100%;height:auto;overflow:visible}' +
    '.pass .dir{transform-origin:50% 50%}' +
    '.pass.rtl .dir{transform:scaleX(-1)}' +
    '@keyframes ps-flap{from{transform:scaleX(1)}to{transform:scaleX(.25)}}' +
    '.pass .wing{transform-box:fill-box;transform-origin:50% 50%;animation:ps-flap .22s ease-in-out infinite alternate}' +
    '@keyframes ps-flapy{from{transform:scaleY(1)}to{transform:scaleY(.3)}}' +
    '.pass .wingy{transform-box:fill-box;transform-origin:50% 100%;animation:ps-flapy .3s ease-in-out infinite alternate}' +
    '@keyframes ps-chomp{0%,49%{opacity:1}50%,100%{opacity:0}}' +
    '.pass .mouth-open{animation:ps-chomp .36s steps(1) infinite}' +
    '.pass .mouth-shut{animation:ps-chomp .36s steps(1) infinite reverse}';
  document.head.appendChild(css);

  var svg = function (vb, inner) { return '<svg viewBox="' + vb + '" xmlns="' + NS + '">' + inner + '</svg>'; };

  // ── dessins (tous tournés vers la droite) ──
  var reindeer = function (x, y) {
    return '<g transform="translate(' + x + ' ' + y + ')">' +
      '<g stroke="#5a3a1a" stroke-width="4" stroke-linecap="round"><line x1="14" y1="38" x2="10" y2="56"/><line x1="24" y1="38" x2="26" y2="56"/><line x1="50" y1="38" x2="46" y2="56"/><line x1="60" y1="38" x2="64" y2="56"/></g>' +
      '<ellipse cx="38" cy="30" rx="30" ry="14" fill="#9a6a38"/><circle cx="72" cy="14" r="10" fill="#9a6a38"/>' +
      '<circle cx="80" cy="16" r="3.4" fill="#e63946"/><circle cx="74" cy="11" r="1.6" fill="#1a1a1a"/>' +
      '<path d="M70 6 L66 -8 M66 -8 L60 -12 M66 -8 L70 -14 M75 5 L80 -9 M80 -9 L86 -12 M80 -9 L78 -15" stroke="#5a3a1a" stroke-width="2.6" fill="none" stroke-linecap="round"/></g>';
  };
  var DRAW = {
    sleigh: { w: 24, vb: '0 0 400 130', draw: function () {
      return reindeer(0, 22) + reindeer(78, 22) +
        '<path d="M150 56 C175 50 190 70 214 74" stroke="#d4af37" stroke-width="2.4" fill="none"/>' +
        '<path d="M205 108 H345 Q372 108 374 78" stroke="#d4af37" stroke-width="6" fill="none" stroke-linecap="round"/>' +
        '<path d="M214 104 L222 70 H330 L352 92 Q354 106 336 106 Z" fill="#d62828" stroke="#7a0c14" stroke-width="3"/>' +
        '<path d="M214 104 L220 82 H240" stroke="#ffd54a" stroke-width="3" fill="none"/>' +
        '<circle cx="246" cy="62" r="17" fill="#8a5a2b"/><circle cx="246" cy="62" r="17" fill="none" stroke="#5a3a1a" stroke-width="2"/>' +
        '<circle cx="292" cy="56" r="17" fill="#d62828"/><circle cx="292" cy="36" r="9" fill="#f5cba7"/>' +
        '<path d="M283 33 Q292 40 301 33 L297 46 Q292 50 287 46Z" fill="#fff"/>' +
        '<path d="M282 32 L292 10 L303 32Z" fill="#d62828"/><circle cx="292" cy="9" r="4" fill="#fff"/><rect x="282" y="30" width="22" height="5" rx="2" fill="#fff"/>' +
        '<g fill="#fff3b0"><circle cx="388" cy="40" r="3"/><circle cx="398" cy="60" r="2"/><circle cx="394" cy="84" r="2.6"/></g>';
    } },
    drone: { w: 9, vb: '0 0 200 110', draw: function () {
      return '<path d="M0 36 H62" stroke="#ff2bd6" stroke-width="3" stroke-dasharray="10 8" opacity=".8"/><path d="M6 50 H56" stroke="#00f0ff" stroke-width="2" stroke-dasharray="6 9" opacity=".7"/>' +
        '<path d="M92 56 L72 108 H152 L132 56Z" fill="#00f0ff" opacity=".16"/>' +
        '<line x1="82" y1="18" x2="150" y2="18" stroke="#9fefff" stroke-width="3" stroke-linecap="round"/><line x1="116" y1="18" x2="116" y2="32" stroke="#0c1230" stroke-width="4"/>' +
        '<rect x="62" y="32" width="108" height="26" rx="13" fill="#0c1230" stroke="#00f0ff" stroke-width="3"/>' +
        '<rect x="82" y="42" width="68" height="6" rx="3" fill="#ff2bd6"/><circle cx="160" cy="45" r="4" fill="#00f0ff"/>' +
        '<circle cx="70" cy="62" r="5" fill="#00f0ff"/><circle cx="162" cy="62" r="5" fill="#00f0ff"/>';
    } },
    pacman: { w: 19, vb: '0 0 440 64', draw: function () {
      var ghost = function (x, c) {
        return '<g transform="translate(' + x + ' 6)"><path d="M0 46 V22 a22 22 0 0 1 44 0 V46 l-7.3-7 -7.3 7 -7.3-7 -7.3 7 -7.3-7 -7.3 7z" fill="' + c + '"/>' +
          '<circle cx="14" cy="22" r="6" fill="#fff"/><circle cx="30" cy="22" r="6" fill="#fff"/><circle cx="16.5" cy="22" r="3" fill="#1b3ea8"/><circle cx="32.5" cy="22" r="3" fill="#1b3ea8"/></g>';
      };
      var dots = ''; for (var i = 0; i < 6; i++) dots += '<circle cx="' + (330 + i * 22) + '" cy="32" r="4.5" fill="#ffe9a8"/>';
      return ghost(0, '#ff3b30') + ghost(56, '#ff8fd0') + ghost(112, '#25d9e8') +
        '<g transform="translate(220 0)"><circle class="mouth-shut" cx="32" cy="32" r="30" fill="#ffd400"/>' +
        '<path class="mouth-open" d="M32 32 L62 14 A34 34 0 1 0 62 50Z" fill="#ffd400"/></g>' + dots;
    } },
    whale: { w: 22, vb: '0 0 320 140', draw: function () {
      return '<g stroke="#bdf3ff" stroke-width="5" stroke-linecap="round" fill="none" opacity=".85"><path d="M214 30 Q214 12 200 4 M214 30 Q214 12 228 4"/><path d="M214 30 V6"/></g>' +
        '<path d="M20 86 C20 52 64 36 130 36 C196 36 252 58 270 92 C282 74 296 70 312 74 C306 86 304 98 312 112 C294 114 282 108 272 96 C250 118 190 128 130 128 C64 128 20 118 20 86Z" fill="#2e86c1" stroke="#17527a" stroke-width="4"/>' +
        '<path d="M30 92 C70 118 150 126 240 108 C200 124 100 132 40 112Z" fill="#cdeefb"/>' +
        '<circle cx="62" cy="76" r="5" fill="#0b2a3a"/><path d="M40 98 Q56 106 74 100" stroke="#17527a" stroke-width="3" fill="none" stroke-linecap="round"/>' +
        '<path d="M150 104 Q172 124 196 116 Q184 104 170 98Z" fill="#256f9f" stroke="#17527a" stroke-width="3"/>';
    } },
    fish: { w: 11, vb: '0 0 200 90', draw: function () {
      var f = function (x, y, c, s) {
        return '<g transform="translate(' + x + ' ' + y + ') scale(' + s + ')"><path d="M0 20 Q22 -2 48 12 Q56 4 64 0 Q60 20 64 40 Q56 36 48 28 Q22 42 0 20Z" fill="' + c + '" stroke="#06384d" stroke-width="2.4"/><circle cx="12" cy="17" r="2.6" fill="#06384d"/></g>';
      };
      return f(0, 4, '#ffb703', 1) + f(70, 34, '#fb8500', .85) + f(120, 6, '#ffd166', .75) + f(150, 46, '#ffb703', .6);
    } },
    ufo: { w: 10, vb: '0 0 150 110', draw: function () {
      return '<path d="M52 50 L26 108 H124 L98 50Z" fill="#fff3a0" opacity=".2"/>' +
        '<path d="M48 36 C48 8 102 8 102 36Z" fill="#aef3ff" opacity=".85" stroke="#4aa8c9" stroke-width="3"/><circle cx="75" cy="22" r="6" fill="#5be37d"/>' +
        '<ellipse cx="75" cy="44" rx="68" ry="17" fill="#9aa5b8" stroke="#5a667a" stroke-width="3.5"/>' +
        '<g fill="#ffd54a"><circle cx="24" cy="46" r="4"/><circle cx="50" cy="52" r="4"/><circle cx="75" cy="54" r="4"/><circle cx="100" cy="52" r="4"/><circle cx="126" cy="46" r="4"/></g>';
    } },
    comet: { w: 16, vb: '0 0 300 70', draw: function () {
      return '<defs><linearGradient id="ps-cg" x1="0" x2="1"><stop offset="0" stop-color="#8b5cf6" stop-opacity="0"/><stop offset="1" stop-color="#e9ddff" stop-opacity=".95"/></linearGradient></defs>' +
        '<path d="M0 35 L250 20 Q262 35 250 50Z" fill="url(#ps-cg)"/><circle cx="262" cy="35" r="14" fill="#fff8d6"/><circle cx="262" cy="35" r="24" fill="#ffd166" opacity=".35"/>';
    } },
    ship: { w: 17, vb: '0 0 300 250', draw: function () {
      return '<line x1="150" y1="30" x2="150" y2="190" stroke="#4a2c12" stroke-width="7" stroke-linecap="round"/>' +
        '<path d="M150 44 C198 56 214 100 206 148 L150 148Z" fill="#f4e7c3" stroke="#8b6b3a" stroke-width="3"/>' +
        '<path d="M150 56 C104 66 90 104 96 148 L150 148Z" fill="#efdcae" stroke="#8b6b3a" stroke-width="3"/>' +
        '<path d="M150 28 L196 38 L150 50Z" fill="#161616"/><circle cx="168" cy="38" r="3.4" fill="#fff"/>' +
        '<path d="M28 168 H274 Q262 214 224 226 H80 Q40 214 28 168Z" fill="#7a4a21" stroke="#3b2210" stroke-width="5"/>' +
        '<path d="M44 186 H258" stroke="#c9953d" stroke-width="4"/><g fill="#2a1608"><circle cx="90" cy="204" r="6"/><circle cx="130" cy="206" r="6"/><circle cx="170" cy="206" r="6"/><circle cx="210" cy="204" r="6"/></g>' +
        '<path d="M274 168 L300 150 L286 176Z" fill="#7a4a21"/>';
    } },
    crow: { w: 9, vb: '0 0 170 110', draw: function () {
      return '<path class="wingy" d="M64 56 C48 14 84 -4 116 10 C102 24 96 42 92 58Z" fill="#241d2c"/>' +
        '<path d="M26 56 L2 44 L8 66Z" fill="#14101a"/><ellipse cx="78" cy="62" rx="44" ry="18" fill="#14101a"/>' +
        '<circle cx="122" cy="52" r="13" fill="#14101a"/><path d="M132 48 L158 56 L132 60Z" fill="#4a4a4a"/>' +
        '<circle cx="127" cy="49" r="3" fill="#ff2b2b"/><circle cx="127" cy="49" r="7" fill="#ff2b2b" opacity=".25"/>' +
        '<path class="wingy" d="M88 62 C86 94 112 108 138 98 C122 90 110 78 106 62Z" fill="#1d1824"/>';
    } },
    eyes: { w: 7, vb: '0 0 140 50', draw: function () {
      var e = function (cx) { return '<ellipse cx="' + cx + '" cy="25" rx="26" ry="15" fill="#ff1a1a" opacity=".22"/><path d="M' + (cx - 17) + ' 28 Q' + cx + ' 8 ' + (cx + 17) + ' 28 Q' + cx + ' 36 ' + (cx - 17) + ' 28Z" fill="#ff2020"/><ellipse cx="' + cx + '" cy="24" rx="2.6" ry="8" fill="#150000"/>'; };
      return e(36) + e(104);
    } },
    butterfly: { w: 6, vb: '0 0 100 80', draw: function () {
      return '<g class="wing"><path d="M50 40 C28 6 4 10 10 36 C14 52 34 52 50 44Z" fill="#ff8fb8" stroke="#9c2f63" stroke-width="2"/><path d="M50 44 C36 56 22 70 34 74 C44 76 52 60 50 48Z" fill="#ffb3d1" stroke="#9c2f63" stroke-width="2"/></g>' +
        '<g class="wing"><path d="M50 40 C72 6 96 10 90 36 C86 52 66 52 50 44Z" fill="#ff8fb8" stroke="#9c2f63" stroke-width="2"/><path d="M50 44 C64 56 78 70 66 74 C56 76 48 60 50 48Z" fill="#ffb3d1" stroke="#9c2f63" stroke-width="2"/></g>' +
        '<ellipse cx="50" cy="44" rx="3.4" ry="15" fill="#5a1236"/><path d="M48 30 Q42 18 36 16 M52 30 Q58 18 64 16" stroke="#5a1236" stroke-width="2" fill="none"/>';
    } }
  };

  // Un passage : entre à gauche ou à droite, traverse l'écran avec un léger balancement vertical, puis disparaît
  function fly(container, kind, opts) {
    var d = DRAW[kind]; if (!d || !container) return;
    opts = opts || {};
    if (kind === 'eyes') {                                  // deux yeux qui s'ouvrent dans le noir, clignent, puis se referment (sur place)
      var ey = document.createElement('div'); ey.className = 'pass'; ey.style.width = d.w + 'vw';
      ey.style.transform = 'translate3d(' + (8 + Math.random() * 78) + 'vw,' + (8 + Math.random() * 70) + 'vh,0)';
      ey.innerHTML = svg(d.vb, d.draw()); ey.style.filter = 'drop-shadow(0 0 .8vw #ff1a1a)'; container.appendChild(ey);
      var ea = ey.animate([{ opacity: 0 }, { opacity: 1, offset: .15 }, { opacity: 1, offset: .5 }, { opacity: .1, offset: .54 }, { opacity: 1, offset: .58 }, { opacity: 1, offset: .8 }, { opacity: 0 }], { duration: 5200, fill: 'forwards' });
      ea.onfinish = function () { ey.remove(); }; setTimeout(function () { ey.remove(); }, 6500); return;
    }
    var rtl = Math.random() < 0.5, dur = opts.duration || (kind === 'comet' ? 4200 : kind === 'ship' ? 15000 : 9500);
    var el = document.createElement('div');
    el.className = 'pass' + (rtl ? ' rtl' : '');
    el.style.width = (d.w * (opts.scale || 1)) + 'vw';
    el.innerHTML = '<div class="dir">' + svg(d.vb, d.draw()) + '</div>';
    container.appendChild(el);
    var y0 = (opts.y != null ? opts.y : 8 + Math.random() * 56), amp = kind === 'ship' || kind === 'whale' ? 1.2 : 4;
    var x0 = rtl ? 112 : -(d.w + 6), x1 = rtl ? -(d.w + 6) : 112;
    var frames = [];
    for (var i = 0; i <= 6; i++) {
      var t = i / 6, x = x0 + (x1 - x0) * t, y = y0 + Math.sin(t * Math.PI * (kind === 'butterfly' ? 6 : 2)) * amp + (kind === 'comet' ? t * 26 : 0);
      frames.push({ transform: 'translate3d(' + x + 'vw,' + y + 'vh,0) rotate(' + (kind === 'comet' ? (rtl ? 12 : -12) : 0) + 'deg)', offset: t });
    }
    var a = el.animate(frames, { duration: dur, easing: 'linear', fill: 'forwards' });
    a.onfinish = function () { el.remove(); };
    setTimeout(function () { el.remove(); }, dur + 1500);
  }
  window.Passers = { fly: fly, kinds: Object.keys(DRAW), html: function (k) { var d = DRAW[k]; return svg(d.vb, d.draw()); } };
})();
