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
    '@keyframes ps-sway{from{transform:rotate(-7deg)}to{transform:rotate(7deg)}}.pass .sway{transform-box:view-box;animation:ps-sway 1.8s ease-in-out infinite alternate}' +
    '@keyframes ps-spin{to{transform:rotate(360deg)}}.pass .spin{transform-box:fill-box;transform-origin:50% 50%;animation:ps-spin .9s linear infinite}' +
    // mouvements secondaires : flotter, onduler, clignoter, flamme, roulis, drapeau, rotor, roues…
    '.pass .spinf{transform-box:fill-box;transform-origin:50% 50%;animation:ps-spin .32s linear infinite}' +
    '@keyframes ps-float{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}.pass .float{animation:ps-float 1.6s ease-in-out infinite}' +
    '@keyframes ps-jig{0%,100%{transform:translateY(0)}50%{transform:translateY(-1.5px)}}.pass .jig{animation:ps-jig .18s linear infinite}' +
    '@keyframes ps-wig{from{transform:rotate(-14deg)}to{transform:rotate(14deg)}}.pass .wig{transform-box:fill-box;animation:ps-wig .28s ease-in-out infinite alternate}' +
    '@keyframes ps-swim{from{transform:rotate(-2.5deg)}to{transform:rotate(2.5deg)}}.pass .swim{transform-box:view-box;animation:ps-swim 1.4s ease-in-out infinite alternate}' +
    '@keyframes ps-fluke{from{transform:rotate(-9deg)}to{transform:rotate(9deg)}}.pass .fluke{transform-box:view-box;animation:ps-fluke .7s ease-in-out infinite alternate}' +
    '@keyframes ps-blink{0%,45%{opacity:1}50%,95%{opacity:.15}100%{opacity:1}}.pass .blink{animation:ps-blink .6s steps(1) infinite}.pass .blink2{animation:ps-blink .6s steps(1) infinite;animation-delay:-.3s}' +
    '@keyframes ps-flame{0%{transform:scale(1,1)}25%{transform:scale(.85,1.2)}50%{transform:scale(1.1,.85)}75%{transform:scale(.9,1.15)}100%{transform:scale(1,1)}}.pass .flame{transform-box:fill-box;transform-origin:50% 100%;animation:ps-flame .3s linear infinite}' +
    '.pass .flamel{transform-box:fill-box;transform-origin:0 50%;animation:ps-flame .26s linear infinite}' +
    '@keyframes ps-roll{from{transform:rotate(-3deg)}to{transform:rotate(3deg)}}.pass .roll{transform-box:view-box;animation:ps-roll 2.2s ease-in-out infinite alternate}' +
    '@keyframes ps-flag{from{transform:skewY(-8deg) scaleX(.94)}to{transform:skewY(6deg) scaleX(1)}}.pass .flag{transform-box:fill-box;transform-origin:0 50%;animation:ps-flag .45s ease-in-out infinite alternate}' +
    '@keyframes ps-billow{from{transform:scaleX(1)}to{transform:scaleX(1.06)}}.pass .billow{transform-box:fill-box;transform-origin:0 50%;animation:ps-billow 1.1s ease-in-out infinite alternate}' +
    '@keyframes ps-rotor{from{transform:scaleX(1)}to{transform:scaleX(-1)}}.pass .rotor{transform-box:fill-box;transform-origin:50% 50%;animation:ps-rotor .09s linear infinite alternate}' +
    '@keyframes ps-scan{from{transform:rotate(-14deg)}to{transform:rotate(14deg)}}.pass .scan{transform-box:view-box;animation:ps-scan 1.8s ease-in-out infinite alternate}' +
    '@keyframes ps-pulse{0%,100%{opacity:.55}50%{opacity:1}}.pass .pulse{animation:ps-pulse 1.1s ease-in-out infinite}' +
    '@keyframes ps-tw{0%,100%{opacity:.2;transform:scale(.5)}50%{opacity:1;transform:scale(1.15)}}.pass .tw{transform-box:fill-box;transform-origin:50% 50%;animation:ps-tw 1s ease-in-out infinite}' +
    '@keyframes ps-wobble{0%,100%{transform:rotate(-5deg) translateY(0)}50%{transform:rotate(5deg) translateY(-4px)}}.pass .wobble{transform-box:view-box;animation:ps-wobble 2s ease-in-out infinite}' +
    '@keyframes ps-dart{0%,30%{transform:translateX(0)}40%,65%{transform:translateX(3px)}75%,100%{transform:translateX(-2px)}}.pass .dart{animation:ps-dart 2.4s ease-in-out infinite}' +
    '@keyframes ps-hop{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}.pass .hop{animation:ps-hop .6s cubic-bezier(.3,0,.7,1) infinite}' +
    '@keyframes ps-wave{from{transform:translateX(0)}to{transform:translateX(-28px)}}.pass .waves{animation:ps-wave 1.2s linear infinite}';
  document.head.appendChild(css);

  var svg = function (vb, inner) { return '<svg viewBox="' + vb + '" xmlns="' + NS + '">' + inner + '</svg>'; };

  // ── dessins (tous tournés vers la droite) ──
  var DRAW = {
    sleigh: { w: 26, vb: '0 0 430 150', draw: function () {
      var deer = function (x, y, lead) {
        return '<g transform="translate(' + x + ' ' + y + ')">' +
          '<g class="mouth-open"><g stroke="#4a2c12" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" fill="none">' +
            '<polyline points="22,46 12,56 0,58"/><polyline points="28,48 22,60 10,66"/><polyline points="58,46 70,54 84,56"/><polyline points="52,48 62,60 74,66"/></g>' +
            '<g fill="#2a1a0a"><circle cx="0" cy="58" r="2.6"/><circle cx="10" cy="66" r="2.6"/><circle cx="84" cy="56" r="2.6"/><circle cx="74" cy="66" r="2.6"/></g></g>' +
          '<g class="mouth-shut"><g stroke="#4a2c12" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" fill="none">' +
            '<polyline points="22,46 30,58 38,66"/><polyline points="28,48 36,58 46,62"/><polyline points="58,46 52,58 44,66"/><polyline points="52,48 46,60 36,64"/></g>' +
            '<g fill="#2a1a0a"><circle cx="38" cy="66" r="2.6"/><circle cx="46" cy="62" r="2.6"/><circle cx="44" cy="66" r="2.6"/><circle cx="36" cy="64" r="2.6"/></g></g>' +
          '<path d="M12 40 C12 28 30 24 48 26 C62 27 70 32 70 40 C70 50 56 52 40 52 C22 52 12 50 12 40Z" fill="#9a6232" stroke="#4a2c12" stroke-width="2.5"/>' +
          '<path d="M20 48 C34 52 54 52 66 46" stroke="#e8c9a0" stroke-width="4" fill="none" stroke-linecap="round"/>' +
          '<path d="M12 36 L4 30 L10 40Z" fill="#f5efe6"/>' +
          '<path d="M60 32 L72 10 L82 12 L70 38Z" fill="#9a6232" stroke="#4a2c12" stroke-width="2.5" stroke-linejoin="round"/>' +
          '<path d="M70 12 C72 4 80 2 88 6 L96 12 C98 16 94 19 88 18 L78 18 C72 18 68 16 70 12Z" fill="#9a6232" stroke="#4a2c12" stroke-width="2.5" stroke-linejoin="round"/>' +
          '<path d="M74 6 L68 0 L76 2Z" fill="#7a4a22"/><circle cx="84" cy="9" r="1.8" fill="#1a1a1a"/>' +
          '<g stroke="#5a3a1a" stroke-width="2.4" fill="none" stroke-linecap="round"><path d="M76 4 L70 -12 M70 -12 L62 -18 M70 -12 L72 -22 M73 -4 L64 -8"/><path d="M80 3 L84 -12 M84 -12 L92 -18 M84 -12 L82 -22 M82 -4 L90 -8"/></g>' +
          (lead ? '<circle cx="96" cy="13" r="4" fill="#ff2a2a"/><circle cx="96" cy="13" r="8" fill="#ff4a4a" opacity=".35"/>' : '<circle cx="95" cy="13" r="2.4" fill="#2a1a0a"/>') +
          '<rect x="34" y="27" width="6" height="25" rx="2" fill="#c8102e"/><circle cx="37" cy="40" r="3" fill="#ffd54a"/></g>';
      };
      return '<g fill="#fff3b0"><circle class="tw" cx="8" cy="70" r="2.4"/><circle class="tw" style="animation-delay:-.4s" cx="18" cy="88" r="1.8"/><circle class="tw" style="animation-delay:-.7s" cx="4" cy="104" r="2"/><path class="tw" style="animation-delay:-.2s" d="M14 54 l2 5 5 2 -5 2 -2 5 -2 -5 -5 -2 5 -2z"/></g>' +
        '<g class="float">' +
        '<path d="M150 74 C190 66 210 70 236 70 M150 76 C230 80 270 66 326 70" stroke="#d4af37" stroke-width="2" fill="none"/>' +
        '<path d="M30 132 H176 C200 132 204 110 190 104 C184 102 180 108 184 112" stroke="#d4af37" stroke-width="5" fill="none" stroke-linecap="round"/>' +
        '<path d="M30 132 C18 132 16 122 24 118" stroke="#d4af37" stroke-width="5" fill="none" stroke-linecap="round"/>' +
        '<path d="M56 122 V132 M140 122 V132" stroke="#d4af37" stroke-width="4"/>' +
        '<circle cx="66" cy="72" r="22" fill="#8a5a2b" stroke="#4a2c12" stroke-width="2.5"/><path d="M58 52 C62 46 72 46 76 52" stroke="#c9953d" stroke-width="4" fill="none"/>' +
        '<path d="M34 122 L30 86 C28 70 40 64 50 70 C54 72 54 82 60 84 L150 88 C172 90 182 104 176 116 C172 122 164 124 156 124Z" fill="#d62828" stroke="#7a0c14" stroke-width="3" stroke-linejoin="round"/>' +
        '<path d="M44 114 C80 116 130 116 168 110" stroke="#ffd54a" stroke-width="3" fill="none"/><path d="M36 92 C40 78 48 76 52 82" stroke="#ffd54a" stroke-width="3" fill="none"/>' +
        '<path d="M86 88 C86 70 96 62 110 62 C124 62 132 72 132 88Z" fill="#d62828" stroke="#7a0c14" stroke-width="2.5"/><rect x="88" y="78" width="42" height="6" fill="#1a1a1a"/><rect x="105" y="77" width="8" height="8" fill="#ffd54a"/>' +
        '<path d="M126 70 L148 72" stroke="#d62828" stroke-width="7" stroke-linecap="round"/><circle cx="150" cy="72" r="4.5" fill="#fff"/>' +
        '<circle cx="112" cy="48" r="11" fill="#f5cba7"/><path d="M101 50 C102 64 122 64 123 50 C118 54 106 54 101 50Z" fill="#fff"/><circle cx="117" cy="45" r="1.6" fill="#1a1a1a"/><circle cx="121" cy="50" r="2.4" fill="#f08a7a"/>' +
        '<path d="M100 42 C102 30 114 26 122 34 C116 32 108 34 104 40" fill="#fff"/><path d="M102 40 C104 26 112 22 120 30 L96 26 C94 30 96 36 102 40Z" fill="#d62828"/><path d="M100 41 C108 36 118 36 124 40" stroke="#fff" stroke-width="5" stroke-linecap="round"/><circle cx="94" cy="25" r="4.5" fill="#fff"/>' +
        deer(226, 40, false) + deer(324, 40, true) + '</g>';
    } },
    // Cyberpunk : drone furtif, rotors qui tournent, caméra rouge et rayon de scan
    drone: { w: 11, vb: '0 0 230 140', draw: function () {
      return '<defs><linearGradient id="ps-dh" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2a3566"/><stop offset="1" stop-color="#070a1c"/></linearGradient>' +
        '<linearGradient id="ps-db" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ff2bd6" stop-opacity=".5"/><stop offset="1" stop-color="#ff2bd6" stop-opacity="0"/></linearGradient></defs>' +
        '<g opacity=".85" stroke-linecap="round"><path d="M0 52 H58" stroke="#ff2bd6" stroke-width="3" stroke-dasharray="12 9"/><path d="M8 66 H62" stroke="#00f0ff" stroke-width="2.4" stroke-dasharray="7 10"/></g>' +
        '<g class="float">' +
        '<g class="scan" style="transform-origin:170px 78px"><path d="M170 78 L138 140 H202Z" fill="url(#ps-db)"/></g>' +
        '<path d="M86 50 L74 32 M164 46 L178 30" stroke="#5a6aa8" stroke-width="5" stroke-linecap="round"/>' +
        '<ellipse class="rotor" cx="72" cy="30" rx="30" ry="4.5" fill="#9fefff" opacity=".55"/><ellipse class="rotor" cx="180" cy="28" rx="30" ry="4.5" fill="#9fefff" opacity=".55" style="animation-delay:-.04s"/>' +
        '<circle cx="72" cy="30" r="4" fill="#00f0ff"/><circle cx="180" cy="28" r="4" fill="#00f0ff"/>' +
        '<path d="M62 60 L84 42 H160 L190 54 L194 64 L172 78 H86Z" fill="url(#ps-dh)" stroke="#00f0ff" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<path d="M92 50 H158 L176 57" stroke="#ff2bd6" stroke-width="4" fill="none" stroke-linecap="round"/>' +
        '<path d="M100 66 H160" stroke="#00f0ff" stroke-width="2" opacity=".6"/>' +
        '<circle cx="170" cy="76" r="7" fill="#1a0010" stroke="#ff2bd6" stroke-width="2"/><circle class="pulse" cx="170" cy="76" r="3.5" fill="#ff2b4a"/>' +
        '<circle class="blink" cx="66" cy="62" r="3" fill="#00f0ff"/><circle class="blink2" cx="192" cy="60" r="3" fill="#ff2bd6"/>' +
        '<ellipse class="pulse" cx="128" cy="84" rx="44" ry="5" fill="#00f0ff" opacity=".35"/></g>';
    } },
    // Arcade : Pac-Man poursuivi par les fantômes (jupes qui ondulent, yeux qui regardent devant)
    pacman: { w: 20, vb: '0 0 470 72', draw: function () {
      var ghost = function (x, c) {
        var eyes = '<ellipse cx="15" cy="22" rx="6" ry="7" fill="#fff"/><ellipse cx="31" cy="22" rx="6" ry="7" fill="#fff"/><circle class="dart" cx="18" cy="23" r="3.2" fill="#1b3ea8"/><circle class="dart" cx="34" cy="23" r="3.2" fill="#1b3ea8"/>';
        return '<g transform="translate(' + x + ' 8)">' +
          '<path class="mouth-open" d="M0 48 V22 a22 22 0 0 1 44 0 V48 l-5.5 -6 -5.5 6 -5.5 -6 -5.5 6 -5.5 -6 -5.5 6 -5.5 -6 -5.5 6z" fill="' + c + '"/>' +
          '<path class="mouth-shut" d="M0 44 V22 a22 22 0 0 1 44 0 V44 l-5.5 6 -5.5 -6 -5.5 6 -5.5 -6 -5.5 6 -5.5 -6 -5.5 6 -5.5 -6z" fill="' + c + '"/>' +
          '<path d="M8 10 C14 4 24 3 30 6" stroke="#fff" stroke-width="3" fill="none" opacity=".35" stroke-linecap="round"/>' + eyes + '</g>';
      };
      var dots = ''; for (var i = 0; i < 5; i++) dots += '<circle cx="' + (338 + i * 22) + '" cy="36" r="4.5" fill="#ffe9a8"/>';
      return '<defs><radialGradient id="ps-pm" cx=".4" cy=".35" r=".7"><stop offset="0" stop-color="#fff27a"/><stop offset="1" stop-color="#ffb800"/></radialGradient></defs>' +
        ghost(0, '#ff3b30') + ghost(56, '#ff8fd0') + ghost(112, '#25d9e8') + ghost(168, '#ffb347') +
        '<g transform="translate(240 4)"><circle class="mouth-shut" cx="32" cy="32" r="30" fill="url(#ps-pm)"/>' +
        '<path class="mouth-open" d="M32 32 L62 12 A35 35 0 1 0 62 52Z" fill="url(#ps-pm)"/><circle cx="34" cy="16" r="3.6" fill="#1a1a1a"/></g>' + dots +
        '<circle class="pulse" cx="458" cy="36" r="9" fill="#ffe9a8"/>';
    } },
    whale: { w: 22, vb: '0 0 340 150', draw: function () {
      return '<defs><linearGradient id="ps-wh" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2a5fa8"/><stop offset=".6" stop-color="#3b7dd8"/><stop offset="1" stop-color="#4f93e6"/></linearGradient></defs>' +
        '<g class="pulse"><g stroke="#bdf3ff" stroke-width="4" stroke-linecap="round" fill="none" opacity=".85"><path d="M262 38 Q258 18 244 10"/><path d="M262 38 Q266 18 280 10"/><path d="M262 38 V14"/></g>' +
        '<g fill="#dff7ff" opacity=".9"><circle cx="242" cy="8" r="3"/><circle cx="282" cy="8" r="3"/><circle cx="262" cy="10" r="3"/></g></g>' +
        '<g class="swim" style="transform-origin:200px 82px"><path d="M330 80 C328 52 292 38 240 40 C180 42 120 56 74 72 L42 78 C32 70 20 58 6 52 C12 66 20 76 26 82 C20 88 12 98 8 110 C20 104 32 92 42 86 L74 92 C120 112 190 124 250 120 C296 117 330 104 330 80Z" fill="url(#ps-wh)" stroke="#173e6e" stroke-width="3.5" stroke-linejoin="round"/>' +
        '<path d="M84 95 C130 112 200 122 252 118 C292 115 318 104 327 90 C300 100 262 106 222 104 C164 102 122 99 84 95Z" fill="#d4f0fc"/>' +
        '<g stroke="#9cc9e6" stroke-width="2" fill="none" stroke-linecap="round"><path d="M236 110 C262 108 292 102 316 94"/><path d="M228 114 C258 113 290 107 312 99"/><path d="M244 105 C270 103 296 98 318 90"/></g>' +
        '<path d="M330 84 C314 92 292 96 268 95" stroke="#173e6e" stroke-width="3" fill="none" stroke-linecap="round"/>' +
        '<circle cx="290" cy="76" r="4.5" fill="#0b2a3a"/><circle cx="291.5" cy="74.5" r="1.5" fill="#fff"/>' +
        '<path d="M232 104 C228 122 214 136 194 140 C202 128 208 116 212 104Z" fill="#2f6cbf" stroke="#173e6e" stroke-width="3" stroke-linejoin="round"/>' +
        '<path d="M110 60 L122 48 L130 57Z" fill="#2a5fa8" stroke="#173e6e" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<path d="M150 56 C190 46 240 44 282 50" stroke="#7fb4ef" stroke-width="3" fill="none" opacity=".6" stroke-linecap="round"/></g>';
    } },
    fish: { w: 11, vb: '0 0 200 90', draw: function () {
      var f = function (x, y, c, s) {
        return '<g transform="translate(' + x + ' ' + y + ') scale(' + s + ')">' +
          '<path class="wig" style="transform-origin:100% 50%" d="M20 20 L2 4 C6 12 6 28 2 36Z" fill="' + c + '" stroke="#06384d" stroke-width="2.4" stroke-linejoin="round"/>' +
          '<path d="M66 20 C58 4 36 0 18 12 C16 16 16 24 18 28 C36 40 58 36 66 20Z" fill="' + c + '" stroke="#06384d" stroke-width="2.4" stroke-linejoin="round"/>' +
          '<path d="M34 8 C40 2 48 2 52 6" stroke="#06384d" stroke-width="2" fill="none"/><path d="M30 12 C26 18 26 24 30 30" stroke="#06384d" stroke-width="1.8" fill="none" opacity=".6"/>' +
          '<circle cx="54" cy="16" r="3" fill="#06384d"/><circle cx="55" cy="15" r="1" fill="#fff"/></g>';
      };
      return f(0, 6, '#ffb703', 1) + f(76, 34, '#fb8500', .85) + f(122, 4, '#ffd166', .7) + f(150, 50, '#ffb703', .6);
    } },
    ufo: { w: 11, vb: '0 0 180 150', draw: function () {
      return '<defs><linearGradient id="ps-ub" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff6a8" stop-opacity=".55"/><stop offset="1" stop-color="#fff6a8" stop-opacity="0"/></linearGradient>' +
        '<linearGradient id="ps-um" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f4f7fb"/><stop offset=".5" stop-color="#b8c2d2"/><stop offset="1" stop-color="#6b778a"/></linearGradient>' +
        '<radialGradient id="ps-ud" cx=".4" cy=".35" r=".7"><stop offset="0" stop-color="#e8fdff" stop-opacity=".95"/><stop offset="1" stop-color="#6fd3ec" stop-opacity=".55"/></radialGradient></defs>' +
        '<path class="pulse" d="M66 80 H114 L150 150 H30Z" fill="url(#ps-ub)"/>' +
        '<g class="wobble" style="transform-origin:90px 60px">' +
        '<ellipse cx="90" cy="78" rx="34" ry="8" fill="#3a4456"/><ellipse cx="90" cy="78" rx="22" ry="5" fill="#9ff7ff" opacity=".8"/>' +
        '<path d="M54 50 C54 4 126 4 126 50Z" fill="url(#ps-ud)" stroke="#4aa8c9" stroke-width="2.5"/>' +
        '<path d="M80 48 C80 40 100 40 100 48Z" fill="#4fb34f"/><ellipse cx="90" cy="30" rx="11" ry="12" fill="#6bd66b"/><ellipse cx="85" cy="29" rx="3.4" ry="4.6" fill="#111"/><ellipse cx="95" cy="29" rx="3.4" ry="4.6" fill="#111"/>' +
        '<path d="M85 19 L82 12 M95 19 L98 12" stroke="#6bd66b" stroke-width="2"/><circle cx="82" cy="11" r="2.4" fill="#6bd66b"/><circle cx="98" cy="11" r="2.4" fill="#6bd66b"/>' +
        '<path d="M64 26 C68 16 76 12 82 11" stroke="#fff" stroke-width="3" fill="none" opacity=".8" stroke-linecap="round"/>' +
        '<ellipse cx="90" cy="60" rx="84" ry="18" fill="url(#ps-um)" stroke="#4a5568" stroke-width="2.5"/>' +
        '<path d="M8 62 C40 74 140 74 172 62" stroke="#4a5568" stroke-width="2" fill="none"/>' +
        '<path d="M24 54 C50 46 130 46 156 54" stroke="#fff" stroke-width="2.5" fill="none" opacity=".7"/>' +
        '<g class="ufo-lights"><circle class="blink" style="animation-delay:-0.09s" cx="22" cy="64" r="4" fill="#ff5a5a"/><circle class="blink" style="animation-delay:-0.36s" cx="46" cy="69" r="4" fill="#ffd54a"/><circle class="blink" style="animation-delay:-0.00s" cx="70" cy="71.5" r="4" fill="#5be37d"/><circle class="blink" style="animation-delay:-0.54s" cx="90" cy="72" r="4" fill="#5ab8ff"/><circle class="blink" style="animation-delay:-0.45s" cx="110" cy="71.5" r="4" fill="#5be37d"/><circle class="blink" style="animation-delay:-0.09s" cx="134" cy="69" r="4" fill="#ffd54a"/><circle class="blink" style="animation-delay:-0.36s" cx="158" cy="64" r="4" fill="#ff5a5a"/></g></g>';
    } },
    // Espace : comète à longue queue lumineuse, étincelles qui scintillent
    comet: { w: 18, vb: '0 0 330 90', draw: function () {
      var sp = ''; [[60, 40, .1], [110, 30, .4], [150, 56, .7], [200, 36, .2], [230, 52, .55], [95, 58, .85]].forEach(function (p) {
        sp += '<path class="tw" style="animation-delay:-' + p[2] + 's" d="M' + p[0] + ' ' + (p[1] - 5) + ' l1.6 3.4 3.4 1.6 -3.4 1.6 -1.6 3.4 -1.6 -3.4 -3.4 -1.6 3.4 -1.6z" fill="#fff6c8"/>';
      });
      return '<defs><linearGradient id="ps-ct" x1="0" x2="1"><stop offset="0" stop-color="#8b5cf6" stop-opacity="0"/><stop offset=".6" stop-color="#a78bfa" stop-opacity=".55"/><stop offset="1" stop-color="#e9ddff" stop-opacity=".95"/></linearGradient>' +
        '<linearGradient id="ps-ct2" x1="0" x2="1"><stop offset="0" stop-color="#5ab8ff" stop-opacity="0"/><stop offset="1" stop-color="#bfe6ff" stop-opacity=".9"/></linearGradient>' +
        '<radialGradient id="ps-cc"><stop offset="0" stop-color="#fff"/><stop offset=".45" stop-color="#fff3b0"/><stop offset="1" stop-color="#ffd166" stop-opacity="0"/></radialGradient></defs>' +
        '<path d="M0 30 C120 34 220 30 286 38 L288 52 C220 58 120 64 0 66Z" fill="url(#ps-ct)"/>' +
        '<path d="M40 44 C140 44 230 42 288 45" stroke="url(#ps-ct2)" stroke-width="7" fill="none" stroke-linecap="round"/>' + sp +
        '<circle class="pulse" cx="292" cy="45" r="30" fill="url(#ps-cc)"/><circle cx="292" cy="45" r="11" fill="#fffdf2"/><circle cx="288" cy="41" r="4" fill="#fff"/>';
    } },
    ship: { w: 19, vb: '0 0 320 270', draw: function () {
      var sail = function (x1, x2, y1, y2, bulge) {
        return '<path d="M' + x1 + ' ' + y1 + ' Q' + ((x1 + x2) / 2) + ' ' + (y1 - 6) + ' ' + x2 + ' ' + y1 + ' Q' + (x2 + bulge) + ' ' + ((y1 + y2) / 2) + ' ' + x2 + ' ' + y2 + ' Q' + ((x1 + x2) / 2) + ' ' + (y2 + 8) + ' ' + x1 + ' ' + y2 + ' Q' + (x1 + bulge) + ' ' + ((y1 + y2) / 2) + ' ' + x1 + ' ' + y1 + 'Z" fill="#efe2c0" stroke="#8b6b3a" stroke-width="2.5" stroke-linejoin="round"/>' +
          '<line x1="' + (x1 - 6) + '" y1="' + y1 + '" x2="' + (x2 + 6) + '" y2="' + y1 + '" stroke="#4a2c12" stroke-width="4" stroke-linecap="round"/>';
      };
      return '<g class="roll" style="transform-origin:160px 220px"><path d="M232 180 L314 140" stroke="#4a2c12" stroke-width="5" stroke-linecap="round"/><path d="M226 92 L306 142 L232 150Z" fill="#efe2c0" stroke="#8b6b3a" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<g stroke="#4a2c12" stroke-width="7" stroke-linecap="round"><line x1="150" y1="186" x2="150" y2="22"/><line x1="226" y1="182" x2="226" y2="70"/><line x1="66" y1="150" x2="66" y2="64"/></g>' +
        '<g stroke="#6b5030" stroke-width="1.5" opacity=".8"><line x1="150" y1="30" x2="300" y2="140"/><line x1="150" y1="30" x2="26" y2="140"/><line x1="226" y1="76" x2="292" y2="150"/></g>' +
        sail(112, 188, 40, 92, 10) + sail(118, 182, 100, 150, 10) + sail(196, 256, 80, 118, 8) + sail(200, 252, 124, 162, 8) + sail(42, 90, 74, 110, 7) + sail(46, 86, 116, 142, 6) +
        '<g transform="translate(150 124)"><circle cx="0" cy="-4" r="10" fill="#1a1a1a"/><rect x="-6" y="3" width="12" height="7" rx="2" fill="#1a1a1a"/><circle cx="-4" cy="-5" r="3" fill="#efe2c0"/><circle cx="4" cy="-5" r="3" fill="#efe2c0"/>' +
          '<path d="M-14 8 L14 20 M14 8 L-14 20" stroke="#1a1a1a" stroke-width="4" stroke-linecap="round"/></g>' +
        '<g class="flag"><path d="M150 12 L186 8 C180 16 186 22 192 26 L150 30Z" fill="#111"/><circle cx="166" cy="17" r="4" fill="#fff"/><path d="M160 24 L172 24 M161 22 L171 26 M171 22 L161 26" stroke="#fff" stroke-width="1.6"/></g>' +
        '<path d="M14 132 H72 L76 152 H236 L300 136 C292 182 262 214 222 226 H86 C46 214 26 182 14 132Z" fill="#6b3e1f" stroke="#2e1a0a" stroke-width="4" stroke-linejoin="round"/>' +
        '<path d="M14 132 L10 124 H76 L72 132" fill="#5a3218" stroke="#2e1a0a" stroke-width="3" stroke-linejoin="round"/>' +
        '<g fill="#ffd27a" stroke="#2e1a0a" stroke-width="2"><rect x="24" y="140" width="10" height="10" rx="2"/><rect x="40" y="140" width="10" height="10" rx="2"/><rect x="56" y="140" width="10" height="10" rx="2"/></g>' +
        '<path d="M26 170 C90 178 220 176 288 158" stroke="#d9a441" stroke-width="5" fill="none"/>' +
        '<g fill="#1a0d04"><rect x="92" y="184" width="12" height="10" rx="2"/><rect x="124" y="186" width="12" height="10" rx="2"/><rect x="156" y="186" width="12" height="10" rx="2"/><rect x="188" y="184" width="12" height="10" rx="2"/><rect x="220" y="180" width="12" height="10" rx="2"/></g>' +
        '<g stroke="#2a2a2a" stroke-width="4" stroke-linecap="round"><line x1="98" y1="196" x2="98" y2="200"/><line x1="130" y1="198" x2="130" y2="202"/><line x1="162" y1="198" x2="162" y2="202"/><line x1="194" y1="196" x2="194" y2="200"/></g>' +
        '<path d="M76 150 H236" stroke="#2e1a0a" stroke-width="3"/><g stroke="#2e1a0a" stroke-width="2"><line x1="90" y1="142" x2="90" y2="152"/><line x1="120" y1="142" x2="120" y2="152"/><line x1="180" y1="142" x2="180" y2="152"/><line x1="210" y1="142" x2="210" y2="152"/></g><path d="M76 142 H236" stroke="#2e1a0a" stroke-width="2"/>' +
        '</g><g fill="#bfe6ff" opacity=".8" class="waves"><path d="M40 226 q14 -10 28 0 q14 10 28 0 q14 -10 28 0 q14 10 28 0 q14 -10 28 0 q14 10 28 0 q14 -10 28 0 q14 10 28 0 q14 10 28 0 q14 -10 28 0 l0 6 h-252z"/></g>';
    } },
    crow: { w: 10, vb: '0 0 210 130', draw: function () {
      var wing = function (fill, edge) {
        return '<path d="M126 60 C112 34 92 14 62 6 L68 16 L52 14 L62 24 L46 26 L58 34 L42 40 L56 46 C80 56 100 62 114 66Z" fill="' + fill + '" stroke="' + edge + '" stroke-width="2" stroke-linejoin="round"/>' +
          '<path d="M118 58 C104 40 88 26 70 18 M110 62 C96 48 80 38 64 32" stroke="#3a3445" stroke-width="1.6" fill="none" opacity=".8"/>';
      };
      return '<g class="float"><g class="flap" style="transform-origin:122px 62px;animation-delay:-.1s"><g transform="translate(10 -4)">' + wing('#120f16', '#4a4458') + '</g></g>' +
        '<path d="M48 66 L8 56 L14 70 L6 84 L48 76Z" fill="#17131c" stroke="#5a5368" stroke-width="2" stroke-linejoin="round"/>' +
        '<path d="M44 66 C62 54 112 52 142 58 C152 48 166 44 176 48 C184 51 188 56 190 60 L208 66 L188 70 C180 76 164 78 150 76 C122 88 82 88 58 80 C50 78 44 74 44 66Z" fill="#241f2e" stroke="#5a5368" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<path d="M190 60 L208 66 L190 66Z" fill="#3c3c44"/><path d="M190 66 L208 66 L188 70Z" fill="#2a2a30"/>' +
        '<circle cx="178" cy="56" r="3.4" fill="#ff2b2b"/><circle cx="178" cy="56" r="8" fill="#ff2b2b" opacity=".3"/>' +
        '<path d="M150 62 C130 60 100 62 70 70" stroke="#3a3445" stroke-width="2" fill="none" opacity=".7"/>' +
        '<g stroke="#3c3c44" stroke-width="2.5" stroke-linecap="round"><path d="M112 84 L104 96 M104 96 L98 98 M104 96 L106 102"/><path d="M124 84 L118 94 M118 94 L112 96 M118 94 L120 100"/></g>' +
        '<g class="flap" style="transform-origin:122px 62px">' + wing('#2a2433', '#6a6280') + '</g></g>';
    } },
    // Horreur : yeux rouges qui s'ouvrent dans le noir, pupilles fendues qui regardent autour
    eyes: { w: 8, vb: '0 0 150 56', draw: function () {
      var e = function (cx) {
        return '<ellipse cx="' + cx + '" cy="28" rx="30" ry="18" fill="#ff1a1a" opacity=".18"/>' +
          '<path d="M' + (cx - 20) + ' 30 Q' + cx + ' 8 ' + (cx + 20) + ' 30 Q' + cx + ' 40 ' + (cx - 20) + ' 30Z" fill="#c4000a"/>' +
          '<path d="M' + (cx - 14) + ' 28 Q' + cx + ' 14 ' + (cx + 14) + ' 28 Q' + cx + ' 34 ' + (cx - 14) + ' 28Z" fill="#ffb000"/>' +
          '<g class="dart"><ellipse cx="' + cx + '" cy="26" rx="2.6" ry="9" fill="#120000"/><circle cx="' + (cx + 4) + '" cy="21" r="1.6" fill="#fff" opacity=".8"/></g>' +
          '<path d="M' + (cx - 20) + ' 30 Q' + cx + ' 8 ' + (cx + 20) + ' 30" stroke="#300" stroke-width="2.5" fill="none"/>';
      };
      return e(38) + e(112);
    } },
    butterfly: { w: 6, vb: '0 0 100 90', draw: function () {
      // vu de dessus, tête vers l'avant (vers la droite) et légèrement relevée : il vole dans le sens où il avance
      return '<g transform="rotate(72 50 44)"><g class="hinge" style="transform-origin:50px 44px">' +
        '<path d="M50 40 C28 6 4 10 10 36 C14 52 34 52 50 44Z" fill="#ff8fb8" stroke="#9c2f63" stroke-width="2"/><path d="M50 44 C36 56 22 70 34 74 C44 76 52 60 50 48Z" fill="#ffb3d1" stroke="#9c2f63" stroke-width="2"/>' +
        '<path d="M50 40 C72 6 96 10 90 36 C86 52 66 52 50 44Z" fill="#ff8fb8" stroke="#9c2f63" stroke-width="2"/><path d="M50 44 C64 56 78 70 66 74 C56 76 48 60 50 48Z" fill="#ffb3d1" stroke="#9c2f63" stroke-width="2"/>' +
        '<circle cx="28" cy="28" r="5" fill="#fff" opacity=".55"/><circle cx="72" cy="28" r="5" fill="#fff" opacity=".55"/></g>' +
        '<ellipse cx="50" cy="44" rx="3.4" ry="15" fill="#5a1236"/><circle cx="50" cy="28" r="4" fill="#5a1236"/><path d="M48 26 Q42 14 36 12 M52 26 Q58 14 64 12" stroke="#5a1236" stroke-width="2" fill="none"/></g>';
    } },
    // GTA VI : voiture de sport rose néon (traînée de vitesse) et hélico de police avec projecteur
    // GTA VI : voiture de sport néon, roues qui tournent, phares et lueur sous la caisse
    car: { w: 21, vb: '0 0 360 130', draw: function () {
      var wheel = function (cx) {
        return '<g transform="translate(' + cx + ' 96)"><circle r="19" fill="#120a18"/><circle r="12" fill="#c9c3d6"/>' +
          '<g class="spinf"><circle r="12" fill="none"/><path d="M0 -11 L3 -3 L11 -2 L4 3 L6 11 L0 6 L-6 11 L-4 3 L-11 -2 L-3 -3Z" fill="#7a7290"/></g><circle r="3" fill="#ff3fa4"/></g>';
      };
      return '<defs><linearGradient id="ps-cb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ff7ac4"/><stop offset=".55" stop-color="#ff3fa4"/><stop offset="1" stop-color="#a0136a"/></linearGradient>' +
        '<linearGradient id="ps-cg2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#d9fbff"/><stop offset="1" stop-color="#3fb8d8"/></linearGradient>' +
        '<linearGradient id="ps-hl" x1="0" x2="1"><stop offset="0" stop-color="#fff6c8" stop-opacity=".7"/><stop offset="1" stop-color="#fff6c8" stop-opacity="0"/></linearGradient></defs>' +
        '<g stroke-linecap="round" opacity=".8"><path d="M0 60 H66" stroke="#ff3fa4" stroke-width="4" stroke-dasharray="16 10"/><path d="M14 80 H76" stroke="#00e5ff" stroke-width="3" stroke-dasharray="10 12"/></g>' +
        '<ellipse class="pulse" cx="210" cy="116" rx="130" ry="8" fill="#ff3fa4" opacity=".5"/>' +
        '<path d="M330 74 L360 62 V96 L330 86Z" fill="url(#ps-hl)"/>' +
        '<g class="jig">' +
        '<path d="M84 92 C82 78 92 70 112 66 L162 46 C182 38 220 36 246 44 L288 62 C312 65 330 70 332 82 L332 94 H84Z" fill="url(#ps-cb)" stroke="#4a0a30" stroke-width="3.5" stroke-linejoin="round"/>' +
        '<path d="M170 50 C186 43 214 42 236 48 L266 64 H156Z" fill="url(#ps-cg2)" stroke="#4a0a30" stroke-width="3" stroke-linejoin="round"/><path d="M212 44 L210 64" stroke="#4a0a30" stroke-width="3"/>' +
        '<path d="M176 52 C188 48 200 47 206 47 L188 62 H166Z" fill="#fff" opacity=".35"/>' +
        '<path d="M96 78 H320" stroke="#ffd1ea" stroke-width="2.5" opacity=".7"/><path d="M240 82 L268 82 L262 90 H236Z" fill="#4a0a30" opacity=".6"/>' +
        '<path d="M86 62 L78 48 H104 L112 62" fill="#4a0a30"/>' +
        '<rect x="320" y="72" width="12" height="7" rx="2" fill="#fff6b0"/><rect x="86" y="68" width="9" height="9" rx="2" fill="#ff2b4a"/>' +
        '</g>' + wheel(132) + wheel(282);
    } },
    // GTA VI : hélico de police, rotors qui tournent, gyrophares et projecteur qui balaie
    heli: { w: 14, vb: '0 0 270 170', draw: function () {
      return '<defs><linearGradient id="ps-hb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#c9d1e6"/></linearGradient>' +
        '<linearGradient id="ps-sl" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff6c8" stop-opacity=".5"/><stop offset="1" stop-color="#fff6c8" stop-opacity="0"/></linearGradient></defs>' +
        '<g class="scan" style="transform-origin:190px 92px"><path d="M190 92 L150 170 H230Z" fill="url(#ps-sl)"/></g>' +
        '<g class="float">' +
        '<path d="M18 46 H104" stroke="#1d2a5c" stroke-width="10" stroke-linecap="round"/><path d="M16 46 L8 34" stroke="#1d2a5c" stroke-width="6" stroke-linecap="round"/>' +
        '<g transform="translate(14 40)"><ellipse class="rotor" cx="0" cy="0" rx="4" ry="16" fill="#9aa4c0" opacity=".6"/></g>' +
        '<path d="M96 34 H176 C204 34 222 50 222 68 C222 82 206 90 182 90 H110 C100 90 94 82 94 72Z" fill="url(#ps-hb)" stroke="#1d2a5c" stroke-width="3.5"/>' +
        '<path d="M94 58 H222" stroke="#1d2a5c" stroke-width="11"/><text x="120" y="62" font-family="Arial Black,Arial,sans-serif" font-weight="900" font-size="9" fill="#fff" letter-spacing="1">POLICE</text>' +
        '<path d="M178 40 C198 42 212 52 214 64 H178Z" fill="#7ff6ff" stroke="#1d2a5c" stroke-width="2.5"/><path d="M184 44 C194 46 202 52 204 58 H186Z" fill="#fff" opacity=".45"/>' +
        '<rect class="blink" x="128" y="26" width="13" height="8" rx="2" fill="#ff2b4a"/><rect class="blink2" x="143" y="26" width="13" height="8" rx="2" fill="#2b6bff"/>' +
        '<circle cx="190" cy="90" r="5" fill="#fff6c8"/>' +
        '<path d="M106 102 H206 M126 90 V102 M186 90 V102" stroke="#2a2a35" stroke-width="5" stroke-linecap="round"/>' +
        '<rect x="134" y="14" width="8" height="14" fill="#2a2a35"/>' +
        '<g transform="translate(138 14)"><ellipse class="rotor" cx="0" cy="0" rx="112" ry="5" fill="#2a2a35" opacity=".55"/></g><circle cx="138" cy="14" r="4" fill="#2a2a35"/>' +
        '</g>';
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
    // Battle Royale : bus de combat sous sa montgolfière, flamme du brûleur, ballon à fuseaux
    bus: { w: 18, vb: '0 0 300 250', draw: function () {
      return '<defs><linearGradient id="ps-ba" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#2c7fe0"/><stop offset=".5" stop-color="#5fc0ff"/><stop offset="1" stop-color="#2c7fe0"/></linearGradient>' +
        '<linearGradient id="ps-bb" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#7a2fd0"/><stop offset=".5" stop-color="#c06bff"/><stop offset="1" stop-color="#7a2fd0"/></linearGradient>' +
        '<linearGradient id="ps-bv" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5fa8ff"/><stop offset="1" stop-color="#2f6bd6"/></linearGradient>' +
        '<linearGradient id="ps-fl" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#ff7a00"/><stop offset=".6" stop-color="#ffd23f"/><stop offset="1" stop-color="#fff6c8"/></linearGradient></defs>' +
        '<g class="sway" style="transform-origin:150px 10px">' +
        '<path d="M150 8 C96 8 66 46 72 82 C78 108 112 128 128 140 H172 C188 128 222 108 228 82 C234 46 204 8 150 8Z" fill="url(#ps-ba)" stroke="#16084a" stroke-width="4"/>' +
        '<path d="M150 8 C126 10 112 50 116 82 C120 108 130 128 136 140 H150Z M150 8 C174 10 188 50 184 82 C180 108 170 128 164 140 H150Z" fill="url(#ps-bb)" opacity=".9"/>' +
        '<path d="M150 8 C96 8 66 46 72 82 C78 108 112 128 128 140 H172 C188 128 222 108 228 82 C234 46 204 8 150 8Z" fill="none" stroke="#16084a" stroke-width="4"/>' +
        '<path d="M98 40 C108 26 124 18 140 16" stroke="#fff" stroke-width="5" fill="none" opacity=".45" stroke-linecap="round"/>' +
        '<path d="M80 78 C120 92 180 92 220 78" stroke="#ffe14d" stroke-width="6" fill="none"/>' +
        '<rect x="136" y="140" width="28" height="10" rx="2" fill="#4a4a5a"/>' +
        '<g class="flame"><path d="M150 142 C134 132 138 114 150 98 C162 114 166 132 150 142Z" fill="url(#ps-fl)"/><path d="M150 140 C144 134 145 124 150 116 C155 124 156 134 150 140Z" fill="#fff6c8"/></g>' +
        '<g stroke="#16084a" stroke-width="2.5"><line x1="130" y1="142" x2="92" y2="176"/><line x1="170" y1="142" x2="208" y2="176"/><line x1="150" y1="150" x2="150" y2="176"/></g>' +
        '<rect x="56" y="176" width="190" height="56" rx="14" fill="url(#ps-bv)" stroke="#16084a" stroke-width="4"/>' +
        '<g fill="#bfe6ff" stroke="#16084a" stroke-width="2.5"><rect x="70" y="186" width="30" height="22" rx="4"/><rect x="108" y="186" width="30" height="22" rx="4"/><rect x="146" y="186" width="30" height="22" rx="4"/><rect x="186" y="186" width="46" height="22" rx="4"/></g>' +
        '<g fill="#fff" opacity=".5"><path d="M74 189 h10 l-8 16 h-2z"/><path d="M190 189 h12 l-10 16 h-2z"/></g>' +
        '<path d="M56 216 H246" stroke="#ffe14d" stroke-width="5"/><rect x="236" y="196" width="10" height="8" rx="2" fill="#fff6b0"/>' +
        '<g fill="#16084a"><circle cx="92" cy="234" r="12"/><circle cx="212" cy="234" r="12"/></g><g fill="#8a8aa0"><circle cx="92" cy="234" r="5"/><circle cx="212" cy="234" r="5"/></g>' +
        '</g>';
    } },
    // Dark fantasy : dragon qui bat des ailes
    dragon: { w: 22, vb: '0 0 360 200', draw: function () {
      var wing = function (fill, rib) {
        return '<path d="M185 95 L205 55 L175 22 L115 2 Q118 28 82 24 Q102 46 70 60 Q104 74 132 96Z" fill="' + fill + '" stroke="#120c04" stroke-width="3" stroke-linejoin="round"/>' +
          '<path d="M175 22 L115 2 M175 22 L82 24 M175 22 L70 60" stroke="' + rib + '" stroke-width="3" stroke-linecap="round"/>' +
          '<path d="M185 95 L205 55 L175 22" stroke="' + rib + '" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" fill="none"/><path d="M175 22 L180 12" stroke="#d4b06a" stroke-width="3" stroke-linecap="round"/>';
      };
      return '<g class="float"><g class="flap" style="transform-origin:180px 98px;opacity:.75">' + '<g transform="translate(22 -4)">' + wing('#3a1610', '#1e0c06') + '</g></g>' +
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
        '<g class="flamel"><path d="M344 74 C356 66 372 72 380 78 C370 80 360 84 344 80Z" fill="#ff7a1a" opacity=".9"/><path d="M346 76 C354 72 364 75 368 78 C362 79 354 80 346 79Z" fill="#ffd23f"/></g>' +
        '<g class="flap" style="transform-origin:180px 98px">' + wing('#6b2a1a', '#2a1008') + '</g></g>';
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
    supply: { w: 9, vb: '0 0 160 200', draw: function () {
      var drop = '<defs><linearGradient id="ps-cv" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffc24a"/><stop offset="1" stop-color="#d9861a"/></linearGradient>' +
        '<linearGradient id="ps-cv2" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7d8f4e"/><stop offset="1" stop-color="#4f5f2c"/></linearGradient></defs>' +
        '<g stroke="#d8e8c8" stroke-width="1.3" opacity=".9"><line x1="10" y1="70" x2="80" y2="122"/><line x1="38" y1="70" x2="80" y2="122"/><line x1="66" y1="70" x2="80" y2="122"/><line x1="94" y1="70" x2="80" y2="122"/><line x1="122" y1="70" x2="80" y2="122"/><line x1="150" y1="70" x2="80" y2="122"/></g>' +
        '<path d="M10 70 C10 22 50 6 80 6 C110 6 150 22 150 70 Q136 60 122 70 Q108 60 94 70 Q80 60 66 70 Q52 60 38 70 Q24 60 10 70Z" fill="url(#ps-cv)"/>' +
        '<path d="M80 6 C60 18 44 40 38 70 Q52 60 66 70 C68 40 72 20 80 6Z" fill="url(#ps-cv2)"/><path d="M80 6 C88 20 92 40 94 70 Q108 60 122 70 C116 40 100 18 80 6Z" fill="url(#ps-cv2)"/>' +
        '<path d="M10 70 C10 22 50 6 80 6 C110 6 150 22 150 70 Q136 60 122 70 Q108 60 94 70 Q80 60 66 70 Q52 60 38 70 Q24 60 10 70Z" fill="none" stroke="#3a2a00" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<g stroke="#3a2a00" stroke-width="1.5" fill="none" opacity=".7"><path d="M80 6 C60 18 44 40 38 70"/><path d="M80 6 C72 20 68 40 66 70"/><path d="M80 6 C88 20 92 40 94 70"/><path d="M80 6 C100 18 116 40 122 70"/></g>' +
        '<path d="M26 30 C40 16 60 10 76 10" stroke="#fff3c4" stroke-width="3" fill="none" opacity=".6" stroke-linecap="round"/>' +
        '<g stroke="#9aa88a" stroke-width="2.2"><line x1="80" y1="122" x2="56" y2="137"/><line x1="80" y1="122" x2="104" y2="137"/><line x1="80" y1="122" x2="114" y2="130"/></g><circle cx="80" cy="122" r="2.6" fill="#555"/>' +
        '<path d="M54 138 L64 130 H116 L106 138Z" fill="#6c7d40" stroke="#1e2610" stroke-width="2" stroke-linejoin="round"/>' +
        '<path d="M106 138 L116 130 V178 L106 186Z" fill="#343f1c" stroke="#1e2610" stroke-width="2" stroke-linejoin="round"/>' +
        '<rect x="54" y="138" width="52" height="48" fill="#4b5a2e" stroke="#1e2610" stroke-width="2"/>' +
        '<g stroke="#3a4622" stroke-width="1.5"><line x1="54" y1="150" x2="106" y2="150"/><line x1="54" y1="174" x2="106" y2="174"/></g>' +
        '<g fill="#8a8f80"><path d="M54 138 h8 v4 h-4 v4 h-4z"/><path d="M106 138 h-8 v4 h4 v4 h4z"/><path d="M54 186 h8 v-4 h-4 v-4 h-4z"/><path d="M106 186 h-8 v-4 h4 v-4 h4z"/></g>' +
        '<circle cx="80" cy="162" r="10" fill="#ffd400" stroke="#1a1a1a" stroke-width="1.8"/>' +
        '<g fill="#1a1a1a" transform="rotate(180 80 162)"><circle cx="80" cy="162" r="2.2"/><path d="M80 162 L75 153.5 A10 10 0 0 1 85 153.5Z"/><path d="M80 162 L89.5 165 A10 10 0 0 1 84.5 170.5Z"/><path d="M80 162 L75.5 170.5 A10 10 0 0 1 70.5 165Z"/></g>';
      return '<g class="sway" style="transform-origin:80px 6px">' + drop + '</g>';
    } },
    // Pokémon : Poké Ball qui roule
    pokeball: { w: 6, vb: '0 0 100 100', draw: function () {
      return '<g class="hop"><g class="spin"><circle cx="50" cy="50" r="44" fill="#fff" stroke="#222" stroke-width="5"/><path d="M6 50 A44 44 0 0 1 94 50Z" fill="#e3350d" stroke="#222" stroke-width="5"/>' +
        '<line x1="6" y1="50" x2="94" y2="50" stroke="#222" stroke-width="7"/><circle cx="50" cy="50" r="13" fill="#fff" stroke="#222" stroke-width="6"/><circle cx="50" cy="50" r="5" fill="#eee"/>' +
        '<ellipse cx="32" cy="28" rx="10" ry="5" transform="rotate(-35 32 28)" fill="#fff" opacity=".5"/></g></g>';
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
