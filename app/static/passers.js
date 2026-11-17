/* Personnages qui traversent l'écran des titres selon le thème (traîneau, drone, Pac-Man, baleine, soucoupe, bateau pirate, papillons, voiture et hélico GTA VI…).
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
    '@keyframes ps-hinge{from{transform:scaleX(1)}to{transform:scaleX(.18)}}' +
    '.pass .hinge{transform-box:view-box;animation:ps-hinge .2s ease-in-out infinite alternate}' +
    '@keyframes ps-beat{from{transform:scaleY(1)}to{transform:scaleY(.25)}}' +
    '.pass .beat{transform-box:view-box;animation:ps-beat .07s linear infinite alternate}' +
    '@keyframes ps-flapy{from{transform:scaleY(1)}to{transform:scaleY(.3)}}' +
    '.pass .wingy{transform-box:fill-box;transform-origin:50% 100%;animation:ps-flapy .3s ease-in-out infinite alternate}' +
    '@keyframes ps-chomp{0%,49%{opacity:1}50%,100%{opacity:0}}' +
    '.pass .mouth-open{animation:ps-chomp .36s steps(1) infinite}' +
    '.pass .mouth-shut{animation:ps-chomp .36s steps(1) infinite reverse}' +
    '@keyframes ps-legA{from{transform:rotate(-16deg)}to{transform:rotate(16deg)}}@keyframes ps-legB{from{transform:rotate(16deg)}to{transform:rotate(-16deg)}}' +
    '.pass .leg-a,.pass .leg-b{transform-box:fill-box;transform-origin:50% 0}.pass .leg-a,.pass .leg-b{animation-duration:.32s!important}.pass .leg-a{animation:ps-legA .25s ease-in-out infinite alternate}.pass .leg-b{animation:ps-legB .25s ease-in-out infinite alternate}' +
    '@keyframes ps-bob{from{transform:translateY(0)}to{transform:translateY(-3px)}}.pass .bob{animation:ps-bob .25s ease-in-out infinite alternate}' +
    '@keyframes ps-gal{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}.pass .gallop{animation:ps-gal .36s ease-in-out infinite}' +
    '@keyframes ps-flapd{from{transform:scaleY(1)}to{transform:scaleY(-.35)}}.pass .flap{transform-box:view-box;animation:ps-flapd .55s ease-in-out infinite alternate}' +
    '@keyframes ps-spin{to{transform:rotate(360deg)}}.pass .spin{transform-box:fill-box;transform-origin:50% 50%;animation:ps-spin .9s linear infinite}';
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
      return '<g class="hinge" style="transform-origin:50px 44px">' +
        '<path d="M50 40 C28 6 4 10 10 36 C14 52 34 52 50 44Z" fill="#ff8fb8" stroke="#9c2f63" stroke-width="2"/><path d="M50 44 C36 56 22 70 34 74 C44 76 52 60 50 48Z" fill="#ffb3d1" stroke="#9c2f63" stroke-width="2"/>' +
        '<path d="M50 40 C72 6 96 10 90 36 C86 52 66 52 50 44Z" fill="#ff8fb8" stroke="#9c2f63" stroke-width="2"/><path d="M50 44 C64 56 78 70 66 74 C56 76 48 60 50 48Z" fill="#ffb3d1" stroke="#9c2f63" stroke-width="2"/>' +
        '<circle cx="28" cy="28" r="5" fill="#fff" opacity=".55"/><circle cx="72" cy="28" r="5" fill="#fff" opacity=".55"/></g>' +
        '<ellipse cx="50" cy="44" rx="3.4" ry="15" fill="#5a1236"/><circle cx="50" cy="28" r="4" fill="#5a1236"/><path d="M48 26 Q42 14 36 12 M52 26 Q58 14 64 12" stroke="#5a1236" stroke-width="2" fill="none"/>';
    } },
    // GTA VI : voiture de sport rose néon (traînée de vitesse) et hélico de police avec projecteur
    car: { w: 20, vb: '0 0 330 110', draw: function () {
      return '<g stroke-linecap="round" opacity=".8"><path d="M0 52 H60" stroke="#ff3fa4" stroke-width="4" stroke-dasharray="14 10"/><path d="M10 70 H70" stroke="#00e5ff" stroke-width="3" stroke-dasharray="10 12"/></g>' +
        '<ellipse cx="200" cy="100" rx="120" ry="7" fill="#ff3fa4" opacity=".35"/>' +
        '<path d="M78 82 C78 66 92 60 112 58 L160 40 C178 33 214 32 238 40 L276 56 C298 59 316 64 318 76 L318 86 H78Z" fill="#ff3fa4" stroke="#5a0b38" stroke-width="4" stroke-linejoin="round"/>' +
        '<path d="M166 46 C182 40 210 39 230 44 L258 58 H150Z" fill="#7ff6ff" stroke="#5a0b38" stroke-width="3" stroke-linejoin="round"/><line x1="204" y1="41" x2="204" y2="58" stroke="#5a0b38" stroke-width="3"/>' +
        '<path d="M90 70 H310" stroke="#ffd1ea" stroke-width="3" opacity=".7"/><rect x="304" y="66" width="12" height="7" rx="2" fill="#fff6b0"/><rect x="80" y="64" width="9" height="8" rx="2" fill="#ff2b4a"/>' +
        '<path d="M80 58 L74 46 H96 L104 58" fill="#5a0b38"/>' +
        '<g><circle cx="128" cy="86" r="17" fill="#1a1022"/><circle cx="128" cy="86" r="8" fill="#c9c3d6"/><circle cx="272" cy="86" r="17" fill="#1a1022"/><circle cx="272" cy="86" r="8" fill="#c9c3d6"/></g>';
    } },
    heli: { w: 13, vb: '0 0 240 150', draw: function () {
      return '<path d="M120 64 L60 150 H210 L160 64Z" fill="#fff6c8" opacity=".14"/>' +
        '<line x1="20" y1="10" x2="210" y2="10" stroke="#2a2a35" stroke-width="5" stroke-linecap="round" class="wing"/><rect x="112" y="10" width="8" height="16" fill="#2a2a35"/>' +
        '<path d="M14 40 H96" stroke="#1d2a5c" stroke-width="10" stroke-linecap="round"/><path d="M6 26 L18 52" stroke="#2a2a35" stroke-width="5" stroke-linecap="round"/>' +
        '<path d="M90 30 H170 C196 30 214 46 214 62 C214 76 198 84 176 84 H104 C94 84 88 76 88 66Z" fill="#f2f4fa" stroke="#1d2a5c" stroke-width="4"/>' +
        '<path d="M88 52 H214" stroke="#1d2a5c" stroke-width="10"/><path d="M172 36 C192 38 206 48 208 60 H172Z" fill="#7ff6ff" stroke="#1d2a5c" stroke-width="3"/>' +
        '<rect x="122" y="22" width="12" height="8" rx="2" fill="#ff2b4a"/><rect x="136" y="22" width="12" height="8" rx="2" fill="#2b6bff"/>' +
        '<path d="M100 96 H200 M120 84 V96 M180 84 V96" stroke="#2a2a35" stroke-width="5" stroke-linecap="round"/>';
    } },
    // R.E.P.O. : petit robot qui trottine en portant un sac de butin
    robot: { w: 8, vb: '0 0 150 160', draw: function () {
      var leg = function (cls, x) {
        return '<g class="' + cls + '"><rect x="' + (x - 4) + '" y="104" width="8" height="30" rx="4" fill="#3a3a3a"/>' +
          '<path d="M' + (x - 9) + ' 132 H' + (x + 13) + ' Q' + (x + 16) + ' 140 ' + (x + 10) + ' 141 H' + (x - 9) + 'Z" fill="#1a1400"/></g>';
      };
      return leg('leg-b', 60) +
        '<g class="bob">' +
        '<path d="M50 74 L38 92" stroke="#3a3a3a" stroke-width="6" stroke-linecap="round" class="arm"/><circle cx="37" cy="94" r="5" fill="#1a1400"/>' +
        '<path d="M108 40 C98 36 98 24 108 22 C110 16 120 16 124 22 C134 24 134 36 124 40 C146 50 150 86 128 96 C112 102 90 96 90 76 C90 60 98 48 108 40Z" fill="#c99a3c" stroke="#5a3a10" stroke-width="3.5" stroke-linejoin="round"/>' +
        '<rect x="104" y="36" width="24" height="7" rx="3" fill="#8a5a1a" stroke="#5a3a10" stroke-width="2"/>' +
        '<path d="M112 46 C102 56 100 76 106 88" stroke="#e8c070" stroke-width="3" fill="none" opacity=".7" stroke-linecap="round"/>' +
        '<text x="118" y="80" text-anchor="middle" font-family="Arial Black,Arial,sans-serif" font-weight="900" font-size="24" fill="#5a3a10">$</text>' +
        '<rect x="48" y="64" width="40" height="42" rx="10" fill="#ffd400" stroke="#1a1400" stroke-width="3.5"/>' +
        '<path d="M52 92 L60 84 M60 100 L76 84 M72 102 L86 88" stroke="#1a1400" stroke-width="4" stroke-linecap="round"/>' +
        '<path d="M84 72 L100 52" stroke="#3a3a3a" stroke-width="6" stroke-linecap="round"/><circle cx="102" cy="48" r="5.5" fill="#1a1400"/>' +
        '<rect x="62" y="56" width="12" height="10" fill="#3a3a3a"/>' +
        '<rect x="36" y="8" width="64" height="50" rx="22" fill="#ffd400" stroke="#1a1400" stroke-width="3.5"/>' +
        '<rect x="50" y="20" width="44" height="26" rx="13" fill="#1a1400"/>' +
        '<ellipse cx="66" cy="33" rx="5" ry="7" fill="#6bf0ff"/><ellipse cx="82" cy="33" rx="5" ry="7" fill="#6bf0ff"/><circle cx="67.5" cy="30" r="1.8" fill="#fff"/><circle cx="83.5" cy="30" r="1.8" fill="#fff"/>' +
        '<ellipse cx="50" cy="16" rx="8" ry="4" fill="#fff6a0" opacity=".7"/>' +
        '<line x1="68" y1="8" x2="68" y2="-2" stroke="#1a1400" stroke-width="3"/><circle cx="68" cy="-4" r="4" fill="#ff5a1f"/>' +
        '</g>' + leg('leg-a', 76);
    } },
    // Battle Royale : bus volant suspendu à son ballon
    bus: { w: 18, vb: '0 0 300 200', draw: function () {
      return '<ellipse cx="150" cy="44" rx="78" ry="40" fill="#3fa9ff" stroke="#16084a" stroke-width="4"/><path d="M80 44 H220" stroke="#b14bff" stroke-width="10"/>' +
        '<g stroke="#16084a" stroke-width="3"><line x1="98" y1="78" x2="90" y2="112"/><line x1="202" y1="78" x2="210" y2="112"/><line x1="150" y1="84" x2="150" y2="112"/></g>' +
        '<rect x="56" y="112" width="190" height="62" rx="14" fill="#3f8cff" stroke="#16084a" stroke-width="4"/>' +
        '<g fill="#bfe6ff" stroke="#16084a" stroke-width="2.5"><rect x="70" y="122" width="32" height="24" rx="4"/><rect x="110" y="122" width="32" height="24" rx="4"/><rect x="150" y="122" width="32" height="24" rx="4"/><rect x="190" y="122" width="44" height="24" rx="4"/></g>' +
        '<path d="M56 154 H246" stroke="#ffe14d" stroke-width="5"/><g fill="#16084a"><circle cx="92" cy="176" r="12"/><circle cx="212" cy="176" r="12"/></g>' +
        '<g stroke="#9fdcff" stroke-width="3" stroke-linecap="round" opacity=".7"><line x1="10" y1="130" x2="44" y2="130"/><line x1="2" y1="150" x2="40" y2="150"/></g>';
    } },
    // Dark fantasy : dragon qui bat des ailes
    dragon: { w: 22, vb: '0 0 360 200', draw: function () {
      var wing = function (fill, rib) {
        return '<path d="M185 95 L205 55 L175 22 L115 2 Q118 28 82 24 Q102 46 70 60 Q104 74 132 96Z" fill="' + fill + '" stroke="#120c04" stroke-width="3" stroke-linejoin="round"/>' +
          '<path d="M175 22 L115 2 M175 22 L82 24 M175 22 L70 60" stroke="' + rib + '" stroke-width="3" stroke-linecap="round"/>' +
          '<path d="M185 95 L205 55 L175 22" stroke="' + rib + '" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" fill="none"/><path d="M175 22 L180 12" stroke="#d4b06a" stroke-width="3" stroke-linecap="round"/>';
      };
      return '<g class="flap" style="transform-origin:180px 98px;opacity:.75">' + '<g transform="translate(22 -4)">' + wing('#3a1610', '#1e0c06') + '</g></g>' +
        '<path d="M130 100 C98 96 66 104 36 116 L30 126 C64 118 98 114 132 118Z" fill="#4a2a1c" stroke="#120c04" stroke-width="3" stroke-linejoin="round"/>' +
        '<path d="M36 110 L8 104 L22 120 L6 134 L38 124Z" fill="#7a2a14" stroke="#120c04" stroke-width="3" stroke-linejoin="round"/>' +
        '<path d="M150 116 L138 140 L154 144 L164 120Z M212 116 L222 136 L236 134 L226 114Z" fill="#3a2016" stroke="#120c04" stroke-width="3" stroke-linejoin="round"/>' +
        '<path d="M120 100 C140 84 190 82 222 92 C242 98 252 108 246 118 C232 130 170 130 130 120 C116 116 112 106 120 100Z" fill="#4a2a1c" stroke="#120c04" stroke-width="3.5"/>' +
        '<path d="M134 118 C170 126 220 126 240 114" stroke="#b8692e" stroke-width="5" fill="none" stroke-linecap="round"/>' +
        '<path d="M226 94 C250 82 266 72 284 66 L294 80 C278 86 262 98 246 114Z" fill="#4a2a1c" stroke="#120c04" stroke-width="3.5" stroke-linejoin="round"/>' +
        '<path d="M240 108 C256 96 270 88 288 80" stroke="#b8692e" stroke-width="4" fill="none"/>' +
        '<path d="M150 92 L156 82 L162 92 L170 80 L176 90 L186 80 L190 90 L202 82 L206 92" fill="#7a2a14" stroke="#120c04" stroke-width="2" stroke-linejoin="round"/>' +
        '<path d="M282 62 C296 54 312 56 326 62 L346 68 L330 74 L342 80 L322 84 C308 86 294 84 284 80Z" fill="#4a2a1c" stroke="#120c04" stroke-width="3.5" stroke-linejoin="round"/>' +
        '<path d="M292 60 L280 36 L302 58 Z M302 58 L300 32 L312 58Z" fill="#d4b06a" stroke="#120c04" stroke-width="2" stroke-linejoin="round"/>' +
        '<circle cx="310" cy="66" r="3.4" fill="#ffb347"/><circle cx="310" cy="66" r="8" fill="#ff7a1a" opacity=".3"/>' +
        '<path d="M344 74 C352 70 358 76 356 82 C352 78 348 80 344 78Z" fill="#ff7a1a" opacity=".85"/>' +
        '<g class="flap" style="transform-origin:180px 98px">' + wing('#6b2a1a', '#2a1008') + '</g>';
    } },
    // Clair Obscur : pinceau qui trace un coup de peinture dorée
    brush: { w: 24, vb: '0 0 360 120', draw: function () {
      return '<path d="M0 92 C60 70 120 108 190 88 C215 81 235 88 250 96 C236 102 214 98 190 102 C120 120 60 92 0 100Z" fill="#e8c27a" opacity=".9"/>' +
        '<path d="M10 95 C70 80 130 108 200 92 C222 87 238 92 248 97" stroke="#fff3d6" stroke-width="2" fill="none" opacity=".6"/>' +
        '<path d="M20 99 C80 94 140 112 210 98" stroke="#c8102e" stroke-width="3" fill="none" opacity=".75" stroke-linecap="round"/>' +
        '<path d="M248 100 C246 86 256 72 268 66 L286 84 C280 96 264 102 248 100Z" fill="#3a2414"/><path d="M254 94 C256 84 262 76 270 72" stroke="#6b4a2a" stroke-width="2" fill="none"/>' +
        '<path d="M248 100 C248 94 251 88 256 84 L262 91 C258 96 253 99 248 100Z" fill="#c8102e"/>' +
        '<polygon points="268,66 286,84 302,68 286,52" fill="#d9b25a" stroke="#6b4a14" stroke-width="2" stroke-linejoin="round"/>' +
        '<path d="M276 60 L294 78" stroke="#fff1c4" stroke-width="1.6" opacity=".7"/>' +
        '<path d="M286 52 L302 68 L354 16 Q356 8 348 6 Z" fill="#1a1008" stroke="#e8c27a" stroke-width="1.5" stroke-linejoin="round"/>' +
        '<path d="M318 40 L324 46" stroke="#e8c27a" stroke-width="3"/>';
    } },
    // Pleine lune : loup qui court
    wolf: { w: 16.5, vb: '0 0 312 140', draw: function () {
      var body = '<path d="M100 60 C80 48 54 46 30 54 C20 58 14 56 8 52 C16 68 38 76 62 72 C78 70 92 72 106 76Z" fill="#56628f" stroke="#0a1030" stroke-width="3" stroke-linejoin="round"/>' +
        '<path d="M306 57 C298 61 280 63 266 62 C258 66 250 72 244 80 C238 92 230 102 216 104 C196 104 178 92 160 88 C146 86 136 92 124 98 C110 102 98 96 94 84 C92 72 96 62 104 58 C130 50 170 50 200 46 C214 44 226 38 234 32 L243 26 L247 9 L255 25 L262 11 L266 29 C276 34 286 42 296 46 C302 49 306 53 306 57Z" fill="#56628f" stroke="#0a1030" stroke-width="3" stroke-linejoin="round"/>' +
        '<path d="M244 82 L236 90 L242 92 L232 100" stroke="#7a86b8" stroke-width="2.5" fill="none" stroke-linejoin="round" stroke-linecap="round"/>' +
        '<path d="M255 25 L258 32 M248 14 L250 26" stroke="#2a3150" stroke-width="2" stroke-linecap="round"/>' +
        '<path d="M110 60 C150 52 190 52 228 38" stroke="#9aa6d6" stroke-width="2.5" fill="none" opacity=".7"/>' +
        '<circle cx="270" cy="42" r="3.2" fill="#ffd54a"/><circle cx="270" cy="42" r="8" fill="#ffd54a" opacity=".25"/><circle cx="304" cy="55" r="3" fill="#0a1030"/>';
      var leg = function (pts, c) { return '<polygon points="' + pts + '" fill="' + c + '" stroke="#0a1030" stroke-width="2.5" stroke-linejoin="round"/>'; };
      var A = leg('206,88 218,90 236,114 254,124 252,130 230,122 204,100', '#3c4670') + leg('112,80 138,88 124,110 98,128 80,132 80,126 96,118 108,100', '#3c4670') +
              leg('214,86 228,86 250,110 272,118 272,124 246,120 220,100', '#56628f') + leg('104,74 132,84 112,106 82,124 62,128 62,122 80,114 96,98', '#56628f');
      var B = leg('204,88 218,90 210,112 192,124 182,126 182,120 196,114 202,102', '#3c4670') + leg('116,80 140,88 150,110 172,122 180,126 178,132 160,128 140,114 120,96', '#3c4670') +
              leg('214,86 230,88 226,108 210,124 196,128 194,122 206,116 214,102', '#56628f') + leg('106,74 134,84 140,104 158,120 170,124 168,130 150,126 132,110 112,94', '#56628f');
      return '<g class="gallop">' + '<g class="mouth-open">' + A + '</g><g class="mouth-shut">' + B + '</g>' + body + '</g>';
    } },
    // Brouillard : nappe de brume qui dérive lentement
    fog: { w: 70, vb: '0 0 600 160', draw: function () {
      return '<defs><filter id="ps-fogb" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="18"/></filter></defs>' +
        '<g filter="url(#ps-fogb)" fill="#d8d4cc" opacity=".55"><ellipse cx="140" cy="90" rx="140" ry="40"/><ellipse cx="320" cy="70" rx="170" ry="50"/><ellipse cx="480" cy="95" rx="120" ry="36"/></g>';
    } },
    // Post-apo : caisse de ravitaillement sous parachute
    supply: { w: 9, vb: '0 0 140 180', draw: function () {
      return '<path d="M10 56 C10 10 130 10 130 56 C110 46 90 50 70 56 C50 50 30 46 10 56Z" fill="#ffb000" stroke="#3a2a00" stroke-width="3"/>' +
        '<path d="M50 52 C56 30 84 30 90 52" fill="#3cff6a" opacity=".35"/>' +
        '<g stroke="#c8ffd2" stroke-width="2"><line x1="12" y1="56" x2="46" y2="120"/><line x1="128" y1="56" x2="94" y2="120"/><line x1="70" y1="56" x2="70" y2="120"/></g>' +
        '<rect x="40" y="120" width="60" height="48" rx="4" fill="#3d4a2c" stroke="#0b1a06" stroke-width="3"/><path d="M40 120 L100 168 M100 120 L40 168" stroke="#2a3420" stroke-width="3"/>' +
        '<circle cx="70" cy="144" r="11" fill="#ffd400" stroke="#0b1a06" stroke-width="2"/><path d="M70 144 L64 135 A11 11 0 0 1 76 135Z M70 144 L80 148 A11 11 0 0 1 74 154Z M70 144 L60 148 A11 11 0 0 0 66 154Z" fill="#0b1a06"/>';
    } },
    // Pokémon : Poké Ball qui roule
    pokeball: { w: 6, vb: '0 0 100 100', draw: function () {
      return '<g class="spin"><circle cx="50" cy="50" r="44" fill="#fff" stroke="#222" stroke-width="5"/><path d="M6 50 A44 44 0 0 1 94 50Z" fill="#e3350d" stroke="#222" stroke-width="5"/>' +
        '<line x1="6" y1="50" x2="94" y2="50" stroke="#222" stroke-width="7"/><circle cx="50" cy="50" r="13" fill="#fff" stroke="#222" stroke-width="6"/><circle cx="50" cy="50" r="5" fill="#eee"/>' +
        '<ellipse cx="32" cy="28" rx="10" ry="5" transform="rotate(-35 32 28)" fill="#fff" opacity=".5"/></g>';
    } },
    // Cosy : abeille
    bee: { w: 5.5, vb: '0 0 120 90', draw: function () {
      return '<defs><clipPath id="ps-beeb"><ellipse cx="52" cy="54" rx="30" ry="22"/></clipPath></defs>' +
        '<path d="M22 58 L8 62 L22 50Z" fill="#3a2a10"/>' +
        '<g stroke="#3a2a10" stroke-width="2.5" stroke-linecap="round" fill="none"><path d="M46 74 L42 84 M58 75 L58 85 M70 72 L74 82"/></g>' +
        '<ellipse cx="52" cy="54" rx="30" ry="22" fill="#ffcf33"/>' +
        '<g clip-path="url(#ps-beeb)" fill="#3a2a10"><rect x="34" y="28" width="9" height="52"/><rect x="52" y="28" width="9" height="52"/><rect x="18" y="28" width="7" height="52"/></g>' +
        '<ellipse cx="52" cy="54" rx="30" ry="22" fill="none" stroke="#3a2a10" stroke-width="3"/>' +
        '<ellipse cx="58" cy="46" rx="10" ry="5" fill="#fff" opacity=".35"/>' +
        '<circle cx="88" cy="50" r="15" fill="#3a2a10"/><circle cx="94" cy="46" r="5" fill="#fff"/><circle cx="95.5" cy="46" r="2.6" fill="#111"/><circle cx="96.5" cy="44.8" r="1" fill="#fff"/>' +
        '<path d="M92 57 Q97 60 101 56" stroke="#ffcf33" stroke-width="2" fill="none" stroke-linecap="round"/>' +
        '<g stroke="#3a2a10" stroke-width="2.4" fill="none" stroke-linecap="round"><path d="M86 36 Q84 20 76 16"/><path d="M92 37 Q96 22 104 18"/></g><circle cx="76" cy="16" r="3" fill="#3a2a10"/><circle cx="104" cy="18" r="3" fill="#3a2a10"/>' +
        '<g class="beat" style="transform-origin:58px 34px"><path d="M58 34 C40 4 18 8 22 24 C26 34 44 36 58 34Z" fill="#e6f6ff" fill-opacity=".8" stroke="#7fa9bd" stroke-width="2"/>' +
        '<path d="M60 34 C58 10 76 2 82 14 C86 24 72 32 60 34Z" fill="#e6f6ff" fill-opacity=".8" stroke="#7fa9bd" stroke-width="2"/></g>';
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
    var rtl = Math.random() < 0.5, dur = opts.duration || ({ comet: 4200, car: 4800, wolf: 5200, pokeball: 6000, robot: 11000, ship: 15000, fog: 26000, supply: 14000 }[kind] || 9500);
    var el = document.createElement('div');
    el.className = 'pass' + (rtl ? ' rtl' : '');
    el.style.width = (d.w * (opts.scale || 1)) + 'vw';
    el.innerHTML = '<div class="dir">' + svg(d.vb, d.draw()) + '</div>';
    container.appendChild(el);
    var GROUND = { car: 1, wolf: 1, robot: 1, pokeball: 1 };   // ceux-là roulent / marchent en bas de l'écran, sans tanguer
    var y0 = (opts.y != null ? opts.y : GROUND[kind] ? 76 + Math.random() * 8 : kind === 'fog' ? 50 + Math.random() * 30 : kind === 'supply' ? 2 + Math.random() * 12 : 8 + Math.random() * 56),
        amp = GROUND[kind] ? 0.3 : kind === 'ship' || kind === 'whale' || kind === 'fog' ? 1.2 : 4;
    var x0 = rtl ? 112 : -(d.w + 6), x1 = rtl ? -(d.w + 6) : 112;
    var frames = [];
    for (var i = 0; i <= 6; i++) {
      var t = i / 6, x = x0 + (x1 - x0) * t, y = y0 + Math.sin(t * Math.PI * (kind === 'butterfly' ? 6 : 2)) * amp + (kind === 'comet' ? t * 26 : kind === 'supply' ? t * 30 : 0);
      frames.push({ transform: 'translate3d(' + x + 'vw,' + y + 'vh,0) rotate(' + (kind === 'comet' ? (rtl ? 12 : -12) : 0) + 'deg)', offset: t });
    }
    var a = el.animate(frames, { duration: dur, easing: 'linear', fill: 'forwards' });
    a.onfinish = function () { el.remove(); };
    setTimeout(function () { el.remove(); }, dur + 1500);
  }
  window.Passers = { fly: fly, kinds: Object.keys(DRAW), html: function (k) { var d = DRAW[k]; return svg(d.vb, d.draw()); } };
})();
