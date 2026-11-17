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
    '.pass .flamel{transform-box:fill-box;transform-origin:0 50%;animation:ps-flame .26s linear infinite}.pass .flamer{transform-box:fill-box;transform-origin:100% 50%;animation:ps-flame .24s linear infinite}' +
    '@keyframes ps-flagr{from{transform:skewY(6deg) scaleX(.95)}to{transform:skewY(-5deg) scaleX(1)}}.pass .flagr{transform-box:fill-box;transform-origin:100% 50%;animation:ps-flagr .5s ease-in-out infinite alternate}' +
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
    '@keyframes ps-batw{from{transform:scaleY(1)}to{transform:scaleY(.3)}}.pass .batw{transform-box:fill-box;transform-origin:50% 45%;animation:ps-batw .16s ease-in-out infinite alternate}' +
    '@keyframes ps-trot{0%,100%{transform:translateY(0)}50%{transform:translateY(-3px)}}.pass .trot{animation:ps-trot .3s ease-in-out infinite}' +
    '@keyframes ps-turn{0%,40%{transform:rotate(0)}55%,80%{transform:rotate(-35deg)}95%,100%{transform:rotate(0)}}.pass .turn{transform-box:fill-box;transform-origin:50% 100%;animation:ps-turn 3.2s ease-in-out infinite}' +
    '@keyframes ps-slow{to{transform:rotate(360deg)}}.pass .slowspin{transform-box:fill-box;transform-origin:50% 50%;animation:ps-slow 9s linear infinite}' +
    '@keyframes ps-tent{from{transform:rotate(-10deg)}to{transform:rotate(10deg)}}.pass .tent{transform-box:fill-box;transform-origin:50% 100%;animation:ps-tent 1.3s ease-in-out infinite alternate}' +
    '@keyframes ps-bell{0%,100%{transform:scale(1,1)}50%{transform:scale(1.12,.86)}}.pass .bell{transform-box:fill-box;transform-origin:50% 100%;animation:ps-bell 1.4s ease-in-out infinite}' +
    // sprites pixel art : gros pixels nets, lecture image par image
    '.pass .pxs{width:100%;height:0;background-repeat:no-repeat;image-rendering:pixelated;image-rendering:crisp-edges}' +
    '@keyframes ps-px{from{background-position:0 0}to{background-position:100% 0}}' +
    '@keyframes ps-wave{from{transform:translateX(0)}to{transform:translateX(-28px)}}.pass .waves{animation:ps-wave 1.2s linear infinite}';
  document.head.appendChild(css);

  var svg = function (vb, inner) { return '<svg viewBox="' + vb + '" xmlns="' + NS + '">' + inner + '</svg>'; };

  // Balle Pokémon : moitié haute colorée, décor propre à chaque balle, bouton central, reflet ; roule en rebondissant
  var pokeBall = function (top, deco) {
    return '<g class="hop"><g class="spin"><circle cx="50" cy="50" r="44" fill="#fff" stroke="#222" stroke-width="5"/><path d="M6 50 A44 44 0 0 1 94 50Z" fill="' + top + '" stroke="#222" stroke-width="5"/>' + deco +
      '<line x1="6" y1="50" x2="94" y2="50" stroke="#222" stroke-width="7"/><circle cx="50" cy="50" r="13" fill="#fff" stroke="#222" stroke-width="6"/><circle cx="50" cy="50" r="5" fill="#eee"/>' +
      '<ellipse cx="32" cy="28" rx="10" ry="5" transform="rotate(-35 32 28)" fill="#fff" opacity=".5"/></g></g>';
  };
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
          '<path d="M118 58 C104 40 88 26 70 18 M110 62 C96 48 80 38 64 32" stroke="#6a6088" stroke-width="1.6" fill="none" opacity=".8"/>';
      };
      return '<g class="float"><g class="flap" style="transform-origin:122px 62px;animation-delay:-.1s"><g transform="translate(10 -4)">' + wing('#2e2740', '#7a7098') + '</g></g>' +
        '<path d="M48 66 L8 56 L14 70 L6 84 L48 76Z" fill="#342c48" stroke="#9a90b8" stroke-width="2" stroke-linejoin="round"/>' +
        '<path d="M44 66 C62 54 112 52 142 58 C152 48 166 44 176 48 C184 51 188 56 190 60 L208 66 L188 70 C180 76 164 78 150 76 C122 88 82 88 58 80 C50 78 44 74 44 66Z" fill="#463d5c" stroke="#9a90b8" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<path d="M190 60 L208 66 L190 66Z" fill="#3c3c44"/><path d="M190 66 L208 66 L188 70Z" fill="#2a2a30"/>' +
        '<circle cx="178" cy="56" r="3.4" fill="#ff2b2b"/><circle cx="178" cy="56" r="8" fill="#ff2b2b" opacity=".3"/>' +
        '<path d="M150 62 C130 60 100 62 70 70" stroke="#6a6088" stroke-width="2" fill="none" opacity=".7"/>' +
        '<g stroke="#3c3c44" stroke-width="2.5" stroke-linecap="round"><path d="M112 84 L104 96 M104 96 L98 98 M104 96 L106 102"/><path d="M124 84 L118 94 M118 94 L112 96 M118 94 L120 100"/></g>' +
        '<g class="flap" style="transform-origin:122px 62px">' + wing('#564a70', '#a69cc4') + '</g></g>';
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
// Pokémon : Poké Ball qui roule en rebondissant
    pokeball: { w: 8, vb: '0 0 100 100', draw: function () { return pokeBall('#e3350d', ''); } },
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
    } },
// Zelda : jument alezane à crinière blanche, au galop (deux positions des jambes)
    epona: { w: 17, vb: '0 0 310 190', draw: function () {
      var legs = function (pts, c) { return pts.map(function (p) { return '<polyline points="' + p + '" fill="none" stroke="' + c + '" stroke-width="11" stroke-linecap="round" stroke-linejoin="round"/>'; }).join(''); };
      var hoof = function (pts) { return pts.map(function (p) { var q = p.split(' ').pop().split(','); return '<circle cx="' + q[0] + '" cy="' + q[1] + '" r="6" fill="#2a1a10"/>'; }).join(''); };
      var A1 = ['190,114 206,148 200,176', '112,114 100,148 84,172'], A2 = ['200,112 232,140 248,166', '100,110 78,140 56,158'];
      var B1 = ['190,114 176,144 168,170', '112,114 128,146 150,168'], B2 = ['200,112 196,146 178,168', '100,110 122,140 140,166'];
      return '<defs><linearGradient id="ps-ep" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#b8673a"/><stop offset="1" stop-color="#7a3f1e"/></linearGradient></defs>' +
        '<g class="gallop">' +
        '<g class="mouth-open">' + legs(A1, '#6a3518') + hoof(A1) + '</g><g class="mouth-shut">' + legs(B1, '#6a3518') + hoof(B1) + '</g>' +
        '<path class="billow" d="M86 84 C64 78 44 88 28 108 C44 102 60 100 74 100 C62 112 56 126 54 140 C70 124 84 108 92 96Z" fill="#f5ecd8" stroke="#b8a88a" stroke-width="2" stroke-linejoin="round"/>' +
        '<path d="M80 90 C80 70 110 62 150 62 C180 62 198 64 210 70 C222 52 236 36 250 26 L262 24 C270 30 282 44 292 56 C296 62 294 68 286 70 C276 70 264 64 254 58 C246 68 236 82 228 96 C224 110 210 118 194 118 C170 122 130 122 112 116 C94 116 80 106 80 90Z" fill="url(#ps-ep)" stroke="#3a1a08" stroke-width="3" stroke-linejoin="round"/>' +
        '<path d="M252 26 L255 8 L263 24Z" fill="#7a3f1e" stroke="#3a1a08" stroke-width="2" stroke-linejoin="round"/>' +
        '<path d="M262 30 C270 40 280 50 288 60" stroke="#f5ecd8" stroke-width="5" stroke-linecap="round" fill="none"/>' +
        '<circle cx="262" cy="38" r="3" fill="#1a0a04"/><circle cx="263" cy="37" r="1" fill="#fff"/><circle cx="287" cy="63" r="1.8" fill="#3a1a08"/>' +
        '<path d="M254 50 L272 46 M276 44 L288 60" stroke="#3a2a1a" stroke-width="2" fill="none"/>' +
        '<path class="billow" d="M250 26 C238 30 224 46 212 64 L204 70 C206 60 210 54 214 50 C208 52 202 56 198 62 C206 46 222 32 240 24Z" fill="#f5ecd8" stroke="#b8a88a" stroke-width="2" stroke-linejoin="round"/>' +
        '<path d="M110 70 C140 64 180 64 206 70" stroke="#d48a54" stroke-width="3" fill="none" opacity=".6" stroke-linecap="round"/>' +
        '<g class="mouth-open">' + legs(A2, '#8a4a24') + hoof(A2) + '<path d="M240 158 L250 168 M62 152 L52 160" stroke="#f5ecd8" stroke-width="7" stroke-linecap="round"/></g>' +
        '<g class="mouth-shut">' + legs(B2, '#8a4a24') + hoof(B2) + '<path d="M184 160 L176 168 M134 158 L142 166" stroke="#f5ecd8" stroke-width="7" stroke-linecap="round"/></g>' +
        '</g>';
    } },
// Zelda : Loftwing écarlate (Skyward Sword) — ailes en couches de plumes, huppe, bec crochu, longues plumes de queue
    loftwing: { w: 21, vb: '0 -50 320 240', draw: function () {
      var fea = function (bx, by, ang, len, wd, fill, edge) {
        var a = ang * Math.PI / 180, cx = bx + Math.cos(a) * len / 2, cy = by + Math.sin(a) * len / 2;
        return '<ellipse cx="' + cx.toFixed(1) + '" cy="' + cy.toFixed(1) + '" rx="' + (len / 2) + '" ry="' + (wd / 2) + '" transform="rotate(' + ang + ' ' + cx.toFixed(1) + ' ' + cy.toFixed(1) + ')" fill="' + fill + '" stroke="' + edge + '" stroke-width="2"/>';
      };
      var wing = function (dark) {
        var P1 = dark ? '#4a0a14' : '#7a1224', P2 = dark ? '#5a0e1a' : '#a01a2e', CV = dark ? '#6a1420' : '#d42a3c', ED = '#2a0408', o = '';
        // rémiges primaires en éventail depuis le poignet, pointes claires
        for (var i = 0; i < 6; i++) { var an = 196 + i * 9; o += fea(142 - i * 2, 40 + i * 1.5, an, 78 - i * 4, 15, P1, ED); }
        for (var j = 0; j < 6; j++) { var an2 = 196 + j * 9, a2 = an2 * Math.PI / 180, L = 78 - j * 4; o += '<ellipse cx="' + (142 - j * 2 + Math.cos(a2) * (L - 8)).toFixed(1) + '" cy="' + (40 + j * 1.5 + Math.sin(a2) * (L - 8)).toFixed(1) + '" rx="5" ry="3.5" transform="rotate(' + an2 + ' ' + (142 - j * 2 + Math.cos(a2) * (L - 8)).toFixed(1) + ' ' + (40 + j * 1.5 + Math.sin(a2) * (L - 8)).toFixed(1) + ')" fill="' + (dark ? '#7a4a4a' : '#f2c4b4') + '"/>'; }
        // rémiges secondaires le long du bras
        for (var k = 0; k < 6; k++) o += fea(150 + k * 7, 48 + k * 6, 192 + k * 4, 52 - k * 3, 17, P2, ED);
        // couvertures (dessus de l'aile), bord festonné
        o += '<path d="M190 84 C176 56 158 38 138 30 C130 40 130 54 140 62 C146 58 152 62 152 68 C160 64 166 70 166 76 C174 72 180 78 180 84Z" fill="' + CV + '" stroke="' + ED + '" stroke-width="2.5" stroke-linejoin="round"/>' +
          '<path d="M184 78 C172 58 158 44 142 36" stroke="' + (dark ? '#8a2a34' : '#ff7a84') + '" stroke-width="4" fill="none" stroke-linecap="round" opacity=".8"/>';
        return '<g transform="translate(186 84) scale(1.45) translate(-186 -84)">' + o + '</g>';
      };
      return '<defs><linearGradient id="ps-lb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e83a4a"/><stop offset=".6" stop-color="#c41e30"/><stop offset="1" stop-color="#8a1222"/></linearGradient></defs>' +
        '<g class="float">' +
        '<g class="flap" style="transform-origin:186px 84px;animation-delay:-.12s"><g transform="translate(16 -8)">' + wing(true) + '</g></g>' +
        // longues plumes de queue
        '<path d="M86 94 C60 80 32 70 4 70 C20 78 30 82 40 84 C30 86 20 88 12 92 C40 94 62 98 84 102Z" fill="#f2c94c" stroke="#7a5a10" stroke-width="2" stroke-linejoin="round"/><path d="M84 96 C60 86 34 78 12 76" stroke="#b8860b" stroke-width="1.6" fill="none"/>' +
        '<path d="M86 100 C62 102 36 106 8 114 C26 116 50 114 84 108Z" fill="#f6ead2" stroke="#8a7a5a" stroke-width="2" stroke-linejoin="round"/><path d="M14 113 C10 114 6 114 4 114 L10 118Z" fill="#c41e30"/>' +
        '<path d="M88 104 C66 116 46 128 26 146 C50 140 70 128 90 112Z" fill="#3a6ad8" stroke="#122a6a" stroke-width="2" stroke-linejoin="round"/><path d="M86 108 C68 120 50 132 32 142" stroke="#8ab4ff" stroke-width="1.6" fill="none"/>' +
        // corps
        '<path d="M78 98 C96 74 150 66 196 72 C214 60 236 56 252 62 C266 68 272 78 272 88 L270 98 C262 108 246 112 230 108 C196 122 130 124 98 112 C86 108 78 104 78 98Z" fill="url(#ps-lb)" stroke="#3a0810" stroke-width="3" stroke-linejoin="round"/>' +
        // poitrail crème en écailles
        '<path d="M190 108 C210 116 238 114 254 102 C250 92 236 88 222 90 C206 92 194 98 190 108Z" fill="#f6ead2" stroke="#8a6a4a" stroke-width="1.5"/>' +
        '<path d="M200 104 q5 4 10 0 q5 4 10 0 q5 4 10 0 q5 4 10 0 M206 110 q5 4 10 0 q5 4 10 0 q5 4 10 0" stroke="#c8a888" stroke-width="1.4" fill="none"/>' +
        '<path d="M110 90 C140 80 176 78 200 80" stroke="#ff7a84" stroke-width="3" fill="none" opacity=".6" stroke-linecap="round"/>' +
        // pattes repliées
        '<path d="M150 116 L142 128 M150 128 L138 132 M160 116 L156 130 M156 130 L146 136" stroke="#e8b84a" stroke-width="3.5" stroke-linecap="round"/>' +
        // tête bien détachée : cou plus sombre et crâne arrondi
        '<path d="M228 74 C230 60 242 52 256 54 C270 56 278 68 276 82 C274 94 262 100 248 98 C238 96 230 88 228 74Z" fill="#d42a3c" stroke="#3a0810" stroke-width="3"/>' +
        '<path d="M232 96 C226 88 224 78 228 70" stroke="#8a1222" stroke-width="4" fill="none" stroke-linecap="round"/>' +
        '<path d="M244 58 C252 56 262 58 268 64" stroke="#ff8a94" stroke-width="3" fill="none" stroke-linecap="round" opacity=".8"/>' +
        // huppe
        '<path d="M248 62 C238 54 224 48 208 46 C220 52 228 56 234 60 C222 58 212 60 204 64 C220 64 234 66 246 68Z" fill="#ff6a3a" stroke="#7a1a08" stroke-width="2" stroke-linejoin="round"/>' +
        // tête : marque blanche, œil cerclé, bec crochu
        '<path d="M262 80 C254 86 242 86 232 82" stroke="#f6ead2" stroke-width="4" fill="none" stroke-linecap="round"/>' +
        '<circle cx="256" cy="74" r="7.5" fill="#fff" stroke="#3a0810" stroke-width="1.5"/><circle cx="257.5" cy="74" r="4" fill="#1a1a1a"/><circle cx="259" cy="72.5" r="1.4" fill="#fff"/>' +
        '<path d="M270 78 C284 74 300 80 304 94 C296 90 286 88 272 92Z" fill="#f2c94c" stroke="#7a5a10" stroke-width="2" stroke-linejoin="round"/>' +
        '<path d="M272 92 C282 92 290 94 294 99 C284 102 276 100 270 97Z" fill="#d9a62c" stroke="#7a5a10" stroke-width="2" stroke-linejoin="round"/>' +
        '<g class="flap" style="transform-origin:186px 84px">' + wing(false) + '</g>' +
        '</g>';
    } },
    // Zelda : petite fée rose lumineuse, ailes translucides et traînée d'étincelles
    pinkfairy: { w: 8, vb: '0 0 140 80', draw: function () {
      var sp = ''; [[10, 44, .0], [26, 36, .3], [40, 48, .6], [54, 40, .15], [66, 46, .45]].forEach(function (p, i) {
        sp += '<circle class="tw" style="animation-delay:-' + p[2] + 's" cx="' + p[0] + '" cy="' + p[1] + '" r="' + (1.6 + i * .5) + '" fill="#ffd1ec"/>';
      });
      return '<defs><radialGradient id="ps-pf"><stop offset="0" stop-color="#fff"/><stop offset=".35" stop-color="#ffb8e0"/><stop offset="1" stop-color="#ff5fb4" stop-opacity="0"/></radialGradient></defs>' + sp +
        '<g class="float"><circle class="pulse" cx="104" cy="42" r="16" fill="url(#ps-pf)" opacity=".6"/>' +
        '<g class="hinge" style="transform-origin:104px 42px"><path d="M104 42 C94 20 80 18 78 30 C76 40 92 44 104 42Z M104 42 C114 20 128 18 130 30 C132 40 116 44 104 42Z" fill="#ffe6f6" fill-opacity=".75" stroke="#ff9fd2" stroke-width="1.5"/>' +
        '<path d="M104 44 C96 56 86 60 84 54 C82 48 94 46 104 44Z M104 44 C112 56 122 60 124 54 C126 48 114 46 104 44Z" fill="#ffe6f6" fill-opacity=".6" stroke="#ff9fd2" stroke-width="1.2"/></g>' +
        '<circle cx="104" cy="42" r="8" fill="#fff"/></g>';
    } },
    // Halloween : sorcière sur son balai, cape et cheveux au vent
    witch: { w: 17, vb: '0 0 300 170', draw: function () {
      return '<g class="float">' +
        '<path d="M44 124 L292 98" stroke="#6b4423" stroke-width="7" stroke-linecap="round"/>' +
        '<path d="M64 118 L12 98 L4 118 L10 142 L66 130Z" fill="#d9a441" stroke="#7a5a1a" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<path d="M20 104 L60 120 M10 122 L62 126 M14 136 L62 128" stroke="#a87a2a" stroke-width="2"/><path d="M60 116 L68 132" stroke="#5a2a6a" stroke-width="7" stroke-linecap="round"/>' +
        '<path class="flag" d="M168 70 C140 68 110 74 84 92 C104 94 124 98 140 106 C150 92 160 82 172 78Z" fill="#3a1a52" stroke="#1a0828" stroke-width="2" stroke-linejoin="round"/>' +
        '<path d="M150 112 C148 84 166 66 188 66 C204 68 212 84 210 104 L218 112 L156 118Z" fill="#4a2468" stroke="#1a0828" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<path d="M206 104 L236 110 L240 120 L210 116Z" fill="#2a1a2a"/><g stroke="#e8e0f0" stroke-width="3"><line x1="214" y1="106" x2="214" y2="116"/><line x1="224" y1="108" x2="224" y2="118"/></g>' +
        '<path d="M234 108 L252 108 C256 112 254 118 248 120 L236 120Z" fill="#1a0a1a"/>' +
        '<path d="M196 82 L232 98" stroke="#4a2468" stroke-width="9" stroke-linecap="round"/><circle cx="234" cy="99" r="5.5" fill="#7ac74f"/>' +
        '<path class="billow" d="M186 48 C170 50 156 58 146 70 C160 66 168 66 176 68 C166 74 160 82 158 90 C170 80 180 74 190 70Z" fill="#ff7a18"/>' +
        '<circle cx="196" cy="56" r="13" fill="#8ad15a" stroke="#3a6a20" stroke-width="2"/>' +
        '<path d="M206 52 L222 58 L206 62Z" fill="#8ad15a" stroke="#3a6a20" stroke-width="2" stroke-linejoin="round"/><circle cx="202" cy="52" r="2.4" fill="#1a1a1a"/><path d="M200 63 Q205 66 209 63" stroke="#3a6a20" stroke-width="2" fill="none"/>' +
        '<ellipse cx="194" cy="44" rx="24" ry="5" fill="#1a0a1a"/><path d="M180 44 L210 44 C206 30 196 18 168 6 C178 18 182 30 180 44Z" fill="#2a1438" stroke="#1a0a1a" stroke-width="2" stroke-linejoin="round"/>' +
        '<path d="M181 38 L208 38" stroke="#9b5de5" stroke-width="5"/><rect x="190" y="35" width="7" height="6" fill="#f2c94c"/>' +
        '</g>';
    } },
    // Halloween : nuée de chauves-souris qui battent des ailes
    bats: { w: 16, vb: '0 0 300 120', draw: function () {
      var bat = function (x, y, s, dl) {
        return '<g transform="translate(' + x + ' ' + y + ') scale(' + s + ')"><g class="batw" style="animation-delay:-' + dl + 's">' +
          '<path d="M30 12 C24 2 12 0 0 6 C6 10 6 18 10 20 C14 16 18 18 20 22 C23 18 27 18 30 20 C33 18 37 18 40 22 C42 18 46 16 50 20 C54 18 54 10 60 6 C48 0 36 2 30 12Z" fill="#1a1022" stroke="#4a3a5a" stroke-width="1.2" stroke-linejoin="round"/></g>' +
          '<ellipse cx="30" cy="14" rx="5" ry="7" fill="#241830"/><path d="M26 9 L27 3 L29 8 M34 9 L33 3 L31 8" fill="#241830" stroke="#241830" stroke-width="2"/>' +
          '<circle cx="28" cy="12" r="1.3" fill="#ff3b3b"/><circle cx="32" cy="12" r="1.3" fill="#ff3b3b"/></g>';
      };
      return bat(10, 50, 1.1, 0) + bat(80, 14, .8, .05) + bat(140, 60, 1.3, .1) + bat(220, 24, .9, .03) + bat(250, 74, .7, .08) + bat(60, 86, .6, .12);
    } },
    // Halloween : citrouille sculptée qui bondit, visage éclairé de l'intérieur
    pumpkin: { w: 7, vb: '0 0 120 120', draw: function () {
      return '<defs><radialGradient id="ps-pk" cx=".4" cy=".35" r=".75"><stop offset="0" stop-color="#ffb347"/><stop offset="1" stop-color="#d9580b"/></radialGradient>' +
        '<radialGradient id="ps-pg"><stop offset="0" stop-color="#fff3a0"/><stop offset="1" stop-color="#ff9a00"/></radialGradient></defs>' +
        '<ellipse cx="60" cy="116" rx="34" ry="4" fill="#000" opacity=".35"/>' +
        '<g class="hop">' +
        '<path d="M58 30 C56 20 60 12 70 8 L72 14 C66 16 64 22 66 30Z" fill="#4a7a2a" stroke="#2a4a14" stroke-width="2"/><path d="M68 18 C78 12 88 16 90 24 C82 20 76 22 70 26" fill="#6aaa3a"/>' +
        '<ellipse cx="60" cy="70" rx="50" ry="40" fill="url(#ps-pk)" stroke="#8a3a06" stroke-width="3"/>' +
        '<path d="M60 30 C44 40 42 100 60 110 M60 30 C76 40 78 100 60 110 M36 36 C20 52 22 92 38 106 M84 36 C100 52 98 92 82 106" stroke="#b8480a" stroke-width="2.5" fill="none" opacity=".75"/>' +
        '<g class="pulse"><path d="M50 56 L62 66 L46 68Z M78 54 L86 66 L72 66Z" fill="url(#ps-pg)"/><path d="M80 66 L76 72 L84 70Z" fill="url(#ps-pg)"/>' +
        '<path d="M40 80 C54 94 82 94 98 78 L92 82 L88 76 L82 84 L76 78 L70 86 L64 80 L58 86 L52 80 L46 84Z" fill="url(#ps-pg)"/></g>' +
        '<path d="M30 52 C34 44 40 40 46 38" stroke="#ffd08a" stroke-width="4" fill="none" opacity=".6" stroke-linecap="round"/>' +
        '</g>';
    } },
// Noël : bonhomme de neige qui dévale en luge, écharpe au vent et gerbe de neige derrière
    snowmansled: { w: 12, vb: '0 0 230 180', draw: function () {
      return '<defs><radialGradient id="ps-sn" cx=".35" cy=".3" r=".8"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#c9e2f2"/></radialGradient></defs>' +
        '<g fill="#eaf6ff"><circle class="tw" cx="14" cy="150" r="5"/><circle class="tw" style="animation-delay:-.3s" cx="30" cy="138" r="4"/><circle class="tw" style="animation-delay:-.6s" cx="8" cy="130" r="3"/><circle class="tw" style="animation-delay:-.45s" cx="40" cy="154" r="3.5"/></g>' +
        '<g class="jig">' +
        '<path d="M40 162 H190 C212 162 220 148 212 140 C208 136 202 140 206 146" stroke="#8a5a2b" stroke-width="6" fill="none" stroke-linecap="round"/>' +
        '<path d="M60 150 V162 M160 150 V162" stroke="#8a5a2b" stroke-width="5"/>' +
        '<rect x="46" y="140" width="150" height="12" rx="5" fill="#c9302c" stroke="#7a1410" stroke-width="2.5"/><path d="M56 146 H186" stroke="#ffd54a" stroke-width="2"/>' +
        '<circle cx="104" cy="112" r="36" fill="url(#ps-sn)" stroke="#9bbad0" stroke-width="2.5"/>' +
        '<g fill="#2a2a2a"><circle cx="122" cy="98" r="3"/><circle cx="126" cy="112" r="3"/><circle cx="124" cy="126" r="3"/></g>' +
        '<path d="M128 104 L170 130" stroke="#6b4423" stroke-width="4" stroke-linecap="round"/><path d="M160 124 L170 116 M164 128 L174 126" stroke="#6b4423" stroke-width="3" stroke-linecap="round"/>' +
        '<path d="M186 146 C176 136 170 132 168 130" stroke="#c9a04a" stroke-width="2" fill="none"/>' +
        '<circle cx="114" cy="58" r="24" fill="url(#ps-sn)" stroke="#9bbad0" stroke-width="2.5"/>' +
        '<path class="flag" d="M100 76 C80 74 60 80 40 92 L46 100 C62 92 80 88 98 86Z" fill="#d62828" stroke="#7a0c14" stroke-width="2" stroke-linejoin="round"/>' +
        '<path d="M92 76 C104 84 124 84 136 76 L136 86 C124 92 104 92 92 86Z" fill="#e63946" stroke="#7a0c14" stroke-width="2"/><path d="M98 80 V88 M110 82 V90 M122 82 V90" stroke="#fff" stroke-width="2.5"/>' +
        '<circle cx="118" cy="52" r="3" fill="#1a1a1a"/><circle cx="130" cy="52" r="3" fill="#1a1a1a"/>' +
        '<path d="M132 60 L160 64 L132 66Z" fill="#ff8c1a" stroke="#b85a00" stroke-width="1.5" stroke-linejoin="round"/>' +
        '<path d="M118 68 Q126 72 134 68" stroke="#1a1a1a" stroke-width="2.5" fill="none" stroke-linecap="round"/>' +
        '<g transform="rotate(-12 114 34)"><rect x="92" y="32" width="44" height="6" rx="2" fill="#1a1a1a"/><rect x="100" y="8" width="28" height="26" rx="2" fill="#1a1a1a"/><rect x="100" y="26" width="28" height="5" fill="#c9302c"/></g>' +
        '</g>';
    } },
    // Noël : gros flocons de neige ciselés qui tournent lentement
    snowflakes: { w: 14, vb: '0 0 260 120', draw: function () {
      var flake = function (cx, cy, r, dl) {
        var arm = '<path d="M0 0 V-' + r + ' M0 -' + (r * .55) + ' L-' + (r * .28) + ' -' + (r * .8) + ' M0 -' + (r * .55) + ' L' + (r * .28) + ' -' + (r * .8) + ' M0 -' + (r * .3) + ' L-' + (r * .18) + ' -' + (r * .45) + ' M0 -' + (r * .3) + ' L' + (r * .18) + ' -' + (r * .45) + '"/>';
        var g = ''; for (var i = 0; i < 6; i++) g += '<g transform="rotate(' + (i * 60) + ')">' + arm + '</g>';
        return '<g transform="translate(' + cx + ' ' + cy + ')"><g class="slowspin" style="animation-delay:-' + dl + 's"><g stroke="#eaf6ff" stroke-width="' + (r / 9) + '" stroke-linecap="round" fill="none" style="filter:drop-shadow(0 0 3px #9fd8ff)">' + g + '</g>' +
          '<circle r="' + (r * .14) + '" fill="#ffffff"/></g></g>';
      };
      return flake(50, 60, 42, 0) + flake(150, 40, 28, 3) + flake(220, 78, 34, 6);
    } },
    // Noël : manchot qui glisse sur le ventre, traînée de glace
    penguin: { w: 11, vb: '0 0 220 100', draw: function () {
      return '<g stroke="#bfe6ff" stroke-width="3" stroke-linecap="round" opacity=".8"><path d="M0 84 H50"/><path d="M14 92 H60"/></g>' +
        '<path d="M30 92 H200" stroke="#d8f0ff" stroke-width="4" opacity=".5" stroke-linecap="round"/>' +
        '<g class="jig">' +
        '<path d="M44 64 L22 54 L26 70 L18 80 L46 74Z" fill="#ff9a1a" stroke="#a85a00" stroke-width="2" stroke-linejoin="round"/>' +
        '<path d="M40 70 C40 50 80 38 130 40 C160 42 180 52 182 66 C184 82 160 90 120 90 C80 90 40 86 40 70Z" fill="#1d2433" stroke="#0a0e18" stroke-width="2.5"/>' +
        '<path d="M56 78 C80 88 140 90 172 76 C160 70 140 68 120 70 C96 72 76 76 56 78Z" fill="#ffffff"/>' +
        '<path d="M110 52 C96 56 80 62 66 66 C82 66 98 64 112 60Z" fill="#2c3548" stroke="#0a0e18" stroke-width="2" stroke-linejoin="round"/>' +
        '<circle cx="176" cy="54" r="22" fill="#1d2433" stroke="#0a0e18" stroke-width="2.5"/>' +
        '<path d="M176 42 C188 42 196 50 196 60 C190 66 180 66 172 62 C168 54 170 46 176 42Z" fill="#ffffff"/>' +
        '<circle cx="186" cy="52" r="3" fill="#0a0e18"/><circle cx="187" cy="51" r="1" fill="#fff"/>' +
        '<path d="M194 56 L214 60 L194 64Z" fill="#ff9a1a" stroke="#a85a00" stroke-width="1.5" stroke-linejoin="round"/>' +
        '<path d="M164 70 C174 72 184 70 192 66" stroke="#f2c94c" stroke-width="3" fill="none" stroke-linecap="round"/>' +
        '</g>';
    } },
    // Cyberpunk : voiture volante néon, réacteurs dessous qui crachent une flamme bleue
    flycar: { w: 17, vb: '0 0 320 140', draw: function () {
      return '<defs><linearGradient id="ps-fc" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a2a6a"/><stop offset="1" stop-color="#0a0820"/></linearGradient>' +
        '<linearGradient id="ps-th" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e6fbff"/><stop offset=".4" stop-color="#00f0ff"/><stop offset="1" stop-color="#00f0ff" stop-opacity="0"/></linearGradient></defs>' +
        '<g stroke-linecap="round" opacity=".85"><path d="M0 60 H70" stroke="#ff2bd6" stroke-width="3" stroke-dasharray="14 9"/><path d="M10 76 H80" stroke="#00f0ff" stroke-width="2.4" stroke-dasharray="9 11"/></g>' +
        '<g class="float">' +
        '<g class="flame"><path d="M108 94 L96 132 H128 L118 94Z" fill="url(#ps-th)"/></g><g class="flame" style="animation-delay:-.13s"><path d="M238 94 L226 132 H258 L248 94Z" fill="url(#ps-th)"/></g>' +
        '<path d="M70 82 C70 66 92 58 120 56 L160 36 C180 28 220 28 244 36 L282 54 C302 58 314 66 314 78 L310 92 H74Z" fill="url(#ps-fc)" stroke="#ff2bd6" stroke-width="3" stroke-linejoin="round"/>' +
        '<path d="M168 42 C184 36 214 36 234 42 L262 56 H152Z" fill="#00f0ff" fill-opacity=".35" stroke="#00f0ff" stroke-width="2.5" stroke-linejoin="round"/><path d="M210 38 L208 56" stroke="#00f0ff" stroke-width="2.5"/>' +
        '<path d="M80 74 H306" stroke="#00f0ff" stroke-width="3" opacity=".8"/><path d="M90 84 H200" stroke="#ff2bd6" stroke-width="2" opacity=".6"/>' +
        '<rect x="96" y="88" width="34" height="10" rx="4" fill="#1a1440" stroke="#00f0ff" stroke-width="2"/><rect x="226" y="88" width="34" height="10" rx="4" fill="#1a1440" stroke="#00f0ff" stroke-width="2"/>' +
        '<rect class="pulse" x="302" y="66" width="12" height="6" rx="2" fill="#e6fbff"/><rect class="blink" x="72" y="70" width="8" height="8" rx="2" fill="#ff2b4a"/>' +
        '<ellipse class="pulse" cx="190" cy="104" rx="110" ry="6" fill="#ff2bd6" opacity=".35"/>' +
        '</g>';
    } },
    // Cyberpunk : enseigne holographique qui grésille (sur place)
    hologram: { w: 15, vb: '0 0 240 170', draw: function () {
      var lines = ''; for (var y = 18; y < 118; y += 6) lines += '<line x1="22" y1="' + y + '" x2="218" y2="' + y + '"/>';
      return '<defs><linearGradient id="ps-hg" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#00f0ff" stop-opacity=".45"/><stop offset="1" stop-color="#00f0ff" stop-opacity="0"/></linearGradient></defs>' +
        '<path d="M90 166 L22 118 H218 L150 166Z" fill="url(#ps-hg)"/>' +
        '<rect x="80" y="160" width="80" height="10" rx="3" fill="#1a1440" stroke="#00f0ff" stroke-width="2"/>' +
        '<g class="float"><rect x="20" y="12" width="200" height="108" rx="10" fill="#00f0ff" fill-opacity=".12" stroke="#00f0ff" stroke-width="3"/>' +
        '<g stroke="#00f0ff" stroke-width="1" opacity=".25">' + lines + '</g>' +
        '<text x="120" y="62" text-anchor="middle" font-family="Orbitron,Arial Black,sans-serif" font-weight="900" font-size="34" fill="#ff2bd6" style="filter:drop-shadow(0 0 4px #ff2bd6)">NÉON</text>' +
        '<text class="blink" x="120" y="100" text-anchor="middle" font-family="Orbitron,Arial,sans-serif" font-weight="700" font-size="20" fill="#e6fbff" letter-spacing="4">OUVERT 24/7</text>' +
        '<path d="M30 22 H60 M180 110 H210" stroke="#ff2bd6" stroke-width="3"/></g>';
    } },
    // Arcade : formation d'envahisseurs pixelisés (deux positions) et leur vaisseau mère
    invaders: { w: 17, vb: '0 0 300 130', draw: function () {
      var A = ['0010000100', '0001001000', '0011111100', '0110110110', '1111111111', '1011111101', '1010000101', '0001101100'];
      var B = ['0010000100', '1001001001', '1011111101', '1110110111', '1111111111', '0111111110', '0010000100', '0100000010'];
      var px = function (rows, x, y, c, s) { var o = ''; rows.forEach(function (r, j) { for (var i = 0; i < r.length; i++) if (r[i] === '1') o += '<rect x="' + (x + i * s) + '" y="' + (y + j * s) + '" width="' + s + '" height="' + s + '" fill="' + c + '"/>'; }); return o; };
      var row = function (y, c) { var o = ''; for (var k = 0; k < 4; k++) o += '<g class="mouth-open">' + px(A, 40 + k * 60, y, c, 4) + '</g><g class="mouth-shut">' + px(B, 40 + k * 60, y, c, 4) + '</g>'; return o; };
      return '<g style="filter:drop-shadow(0 0 3px rgba(120,255,120,.6))">' + row(56, '#5bff6b') + row(94, '#ff4fd8') + '</g>' +
        '<g class="float"><path d="M190 22 C190 10 230 10 230 22 L250 26 C252 32 248 36 240 36 H180 C172 36 168 32 170 26Z" fill="#ff3b3b" stroke="#7a0a0a" stroke-width="2"/>' +
        '<g fill="#fff3a0"><circle class="blink" cx="186" cy="30" r="3"/><circle class="blink2" cx="210" cy="30" r="3"/><circle class="blink" cx="234" cy="30" r="3"/></g></g>';
    } },
    // Arcade : champignon à pois qui rebondit
    mushroom: { w: 6, vb: '0 0 110 110', draw: function () {
      return '<ellipse cx="55" cy="106" rx="30" ry="4" fill="#000" opacity=".35"/>' +
        '<g class="hop">' +
        '<path d="M34 58 C30 78 34 98 46 102 H66 C78 98 82 78 76 58Z" fill="#fbe9c8" stroke="#8a6a3a" stroke-width="3"/>' +
        '<ellipse cx="48" cy="78" rx="4" ry="7" fill="#1a1a1a"/><ellipse cx="64" cy="78" rx="4" ry="7" fill="#1a1a1a"/>' +
        '<path d="M8 60 C8 26 30 6 55 6 C80 6 102 26 102 60 C102 66 96 68 90 66 C66 58 44 58 20 66 C14 68 8 66 8 60Z" fill="#e8262b" stroke="#6b0f12" stroke-width="3"/>' +
        '<g fill="#ffffff"><ellipse cx="55" cy="26" rx="14" ry="11"/><ellipse cx="24" cy="44" rx="10" ry="12"/><ellipse cx="88" cy="44" rx="10" ry="12"/></g>' +
        '<path d="M30 20 C36 14 44 10 50 10" stroke="#ff8a8a" stroke-width="4" fill="none" stroke-linecap="round"/>' +
        '</g>';
    } },
    // Océan : tortue de mer qui nage, nageoires avant qui rament
    turtle: { w: 13, vb: '0 0 240 130', draw: function () {
      return '<defs><radialGradient id="ps-ts" cx=".45" cy=".35" r=".7"><stop offset="0" stop-color="#8bbf5a"/><stop offset="1" stop-color="#3f6e2a"/></radialGradient></defs>' +
        '<g class="float">' +
        '<g class="wig" style="transform-origin:100% 0;animation-duration:.9s"><path d="M88 84 C70 98 50 108 32 110 C46 98 60 88 76 80Z" fill="#9ac46a" stroke="#3a5a1e" stroke-width="2.5" stroke-linejoin="round"/></g>' +
        '<path d="M54 66 L26 62 L36 74Z" fill="#9ac46a" stroke="#3a5a1e" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<path d="M50 66 C50 36 90 22 130 22 C168 22 192 40 192 66 C192 84 168 92 130 92 C90 92 50 86 50 66Z" fill="url(#ps-ts)" stroke="#2a4a14" stroke-width="3"/>' +
        '<g stroke="#2a4a14" stroke-width="2" fill="#6a9a40" opacity=".9"><path d="M100 34 L124 30 L140 40 L132 58 L108 58 L96 46Z"/><path d="M140 40 L162 40 L174 56 L160 70 L132 58Z"/><path d="M96 46 L108 58 L100 74 L76 74 L68 58 L80 44Z"/><path d="M108 58 L132 58 L140 76 L118 86 L100 74Z"/></g>' +
        '<path d="M60 82 C100 92 160 92 186 78" stroke="#d8c48a" stroke-width="5" fill="none" stroke-linecap="round"/>' +
        '<path d="M188 56 C200 48 222 48 230 58 C234 66 226 74 212 74 C200 74 192 70 188 66Z" fill="#9ac46a" stroke="#3a5a1e" stroke-width="2.5"/>' +
        '<circle cx="216" cy="58" r="3.4" fill="#1a1a1a"/><circle cx="217" cy="57" r="1.1" fill="#fff"/><path d="M220 68 Q226 68 230 64" stroke="#3a5a1e" stroke-width="2" fill="none"/>' +
        '<g class="wig" style="transform-origin:0 0"><path d="M160 80 C176 98 196 112 216 116 C206 100 192 88 172 76Z" fill="#9ac46a" stroke="#3a5a1e" stroke-width="2.5" stroke-linejoin="round"/></g>' +
        '</g>';
    } },
    // Océan : méduse translucide, cloche qui pulse et tentacules qui ondulent
    jellyfish: { w: 6, vb: '0 0 100 170', draw: function () {
      return '<defs><radialGradient id="ps-jf" cx=".5" cy=".3" r=".8"><stop offset="0" stop-color="#ffd6f4" stop-opacity=".95"/><stop offset="1" stop-color="#b46cff" stop-opacity=".55"/></radialGradient></defs>' +
        '<g class="tent"><path d="M28 60 C22 80 34 96 26 116 C20 132 30 146 24 162" stroke="#e8b8ff" stroke-width="3" fill="none" stroke-linecap="round" opacity=".85"/>' +
        '<path d="M44 62 C40 84 52 100 44 124 C40 138 48 150 44 166" stroke="#ffc8ec" stroke-width="2.5" fill="none" stroke-linecap="round" opacity=".85"/></g>' +
        '<g class="tent" style="animation-delay:-.6s"><path d="M58 62 C62 84 50 102 58 124 C62 138 54 152 58 166" stroke="#ffc8ec" stroke-width="2.5" fill="none" stroke-linecap="round" opacity=".85"/>' +
        '<path d="M72 60 C78 80 66 98 74 116 C80 132 70 146 76 160" stroke="#e8b8ff" stroke-width="3" fill="none" stroke-linecap="round" opacity=".85"/></g>' +
        '<path d="M36 58 C36 76 44 84 40 98 M64 58 C64 76 56 84 60 98" stroke="#ff9ad8" stroke-width="5" fill="none" stroke-linecap="round" opacity=".7"/>' +
        '<g class="bell"><path d="M8 58 C8 26 28 8 50 8 C72 8 92 26 92 58 C84 62 78 56 70 62 C62 56 56 62 50 58 C44 62 38 56 30 62 C22 56 16 62 8 58Z" fill="url(#ps-jf)" stroke="#d48cff" stroke-width="2"/>' +
        '<path d="M24 34 C30 22 40 16 50 16" stroke="#fff" stroke-width="4" fill="none" opacity=".55" stroke-linecap="round"/>' +
        '<g fill="#ffffff" opacity=".7"><circle cx="40" cy="40" r="3"/><circle cx="58" cy="34" r="2.4"/><circle cx="66" cy="46" r="2"/></g></g>';
    } },
// Océan : deux dauphins qui bondissent — melon arrondi, rostre, aileron recourbé, nageoire caudale à deux lobes
    dolphins: { w: 18, vb: '0 0 345 130', draw: function () {
      var dol = function (x, y, s, dl) {
        return '<g transform="translate(' + x + ' ' + y + ') scale(' + s + ')"><g class="swim" style="transform-origin:80px 40px;animation-delay:-' + dl + 's">' +
          '<defs><linearGradient id="ps-dlg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3f6f9f"/><stop offset="1" stop-color="#7aa8d4"/></linearGradient></defs>' +
          '<path d="M92 17 C88 9 82 3 72 1 C78 8 80 14 80 20Z" fill="#355f8a" stroke="#14304e" stroke-width="2" stroke-linejoin="round"/>' +
          '<path d="M156 34 C150 30 140 28 132 26 C124 18 108 14 90 16 C66 18 44 28 30 40 C24 45 18 48 12 50 C6 44 0 38 -10 33 C-4 42 -2 48 2 52 C-2 56 -4 62 -10 71 C0 66 6 60 12 56 C26 58 44 56 64 52 C90 48 116 46 134 42 C142 40 150 38 156 36Z" fill="url(#ps-dlg)" stroke="#14304e" stroke-width="2.5" stroke-linejoin="round"/>' +
          '<path d="M36 54 C64 52 104 46 134 41 C140 41 146 39 152 37 C140 41 120 46 96 50 C76 53 54 56 36 54Z" fill="#e3eef8"/>' +
          '<path d="M112 46 C108 54 100 60 90 62 C96 56 100 50 102 46Z" fill="#355f8a" stroke="#14304e" stroke-width="2" stroke-linejoin="round"/>' +
          '<path d="M60 24 C80 18 104 16 122 20" stroke="#a8c8e8" stroke-width="3" fill="none" opacity=".6" stroke-linecap="round"/>' +
          '<circle cx="137" cy="31" r="2.4" fill="#0a1a2a"/><circle cx="137.8" cy="30.3" r=".8" fill="#fff"/>' +
          '<path d="M142 36 C147 37 152 36.5 156 35.5" stroke="#14304e" stroke-width="1.6" fill="none" stroke-linecap="round"/>' +
          '</g></g>';
      };
      return '<g fill="#bfe6ff" opacity=".85"><circle class="tw" cx="14" cy="108" r="4"/><circle class="tw" style="animation-delay:-.4s" cx="30" cy="118" r="3"/><circle class="tw" style="animation-delay:-.7s" cx="6" cy="120" r="2.5"/></g>' +
        dol(22, 46, 1, 0) + dol(192, 8, .92, .7);
    } },
// Espace : astronaute qui flotte en tournant lentement sur lui-même
    astronaut: { w: 8, vb: '0 0 150 160', draw: function () {
      return '<defs><linearGradient id="ps-av" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffe9a8"/><stop offset=".5" stop-color="#f2a93b"/><stop offset="1" stop-color="#7a4a10"/></linearGradient>' +
        '<linearGradient id="ps-as" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#c9d1e0"/></linearGradient></defs>' +
        '<g class="slowspin">' +
        '<rect x="44" y="50" width="62" height="56" rx="12" fill="#b8c2d2" stroke="#4a5568" stroke-width="3"/>' +
        '<path d="M50 76 C30 70 18 56 14 40" stroke="url(#ps-as)" stroke-width="18" stroke-linecap="round" fill="none"/><path d="M50 76 C30 70 18 56 14 40" stroke="#4a5568" stroke-width="2" fill="none" opacity=".4"/>' +
        '<path d="M100 78 C120 82 132 96 136 112" stroke="url(#ps-as)" stroke-width="18" stroke-linecap="round" fill="none"/>' +
        '<circle cx="14" cy="38" r="9" fill="#e8ecf4" stroke="#4a5568" stroke-width="2.5"/><circle cx="136" cy="114" r="9" fill="#e8ecf4" stroke="#4a5568" stroke-width="2.5"/>' +
        '<path d="M60 104 C56 120 50 132 44 144 M90 104 C96 120 104 130 112 140" stroke="url(#ps-as)" stroke-width="20" stroke-linecap="round" fill="none"/>' +
        '<path d="M34 146 H56 M104 144 L124 136" stroke="#6b778a" stroke-width="12" stroke-linecap="round"/>' +
        '<rect x="50" y="58" width="50" height="50" rx="14" fill="url(#ps-as)" stroke="#4a5568" stroke-width="3"/>' +
        '<rect x="62" y="74" width="26" height="16" rx="4" fill="#4a5568"/><circle cx="68" cy="82" r="3" fill="#ff5a5a"/><circle cx="76" cy="82" r="3" fill="#5be37d"/><circle cx="84" cy="82" r="3" fill="#5ab8ff"/>' +
        '<circle cx="75" cy="38" r="30" fill="url(#ps-as)" stroke="#4a5568" stroke-width="3"/>' +
        '<path d="M52 36 C52 22 64 16 76 16 C90 16 100 24 100 36 C100 50 90 56 76 56 C62 56 52 50 52 36Z" fill="url(#ps-av)" stroke="#4a5568" stroke-width="2.5"/>' +
        '<path d="M60 30 C64 22 72 20 80 21" stroke="#fff" stroke-width="4" fill="none" opacity=".8" stroke-linecap="round"/>' +
        '</g>';
    } },
    // Espace : fusée rouge et blanche, flamme qui vacille et fumée derrière
    rocket: { w: 14, vb: '0 0 280 120', draw: function () {
      return '<defs><linearGradient id="ps-rb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset=".6" stop-color="#e3e8f0"/><stop offset="1" stop-color="#9aa5b8"/></linearGradient>' +
        '<linearGradient id="ps-rf" x1="1" y1="0" x2="0" y2="0"><stop offset="0" stop-color="#fff6c8"/><stop offset=".4" stop-color="#ffb347"/><stop offset="1" stop-color="#ff3b1a" stop-opacity="0"/></linearGradient></defs>' +
        '<g fill="#d8dde6" opacity=".55"><circle class="tw" cx="14" cy="60" r="12"/><circle class="tw" style="animation-delay:-.4s" cx="34" cy="48" r="9"/><circle class="tw" style="animation-delay:-.7s" cx="30" cy="72" r="8"/></g>' +
        '<g class="flamer"><path d="M86 44 C60 46 40 54 24 60 C40 66 60 74 86 76Z" fill="url(#ps-rf)"/><path d="M86 52 C72 54 62 57 54 60 C62 63 72 66 86 68Z" fill="#fff6c8"/></g>' +
        '<g class="jig">' +
        '<path d="M88 42 L70 10 L128 42Z M88 78 L70 110 L128 78Z" fill="#d62828" stroke="#7a0c14" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<path d="M86 40 H200 C236 40 262 50 276 60 C262 70 236 80 200 80 H86 C82 74 82 46 86 40Z" fill="url(#ps-rb)" stroke="#4a5568" stroke-width="3" stroke-linejoin="round"/>' +
        '<path d="M232 44 C254 48 268 54 276 60 C268 66 254 72 232 76 C238 66 238 54 232 44Z" fill="#d62828" stroke="#7a0c14" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<path d="M120 40 V80 M134 40 V80" stroke="#d62828" stroke-width="5"/>' +
        '<circle cx="184" cy="60" r="13" fill="#5ab8ff" stroke="#4a5568" stroke-width="4"/><path d="M178 54 C182 50 188 50 190 52" stroke="#fff" stroke-width="3" fill="none" stroke-linecap="round"/>' +
        '<path d="M96 46 H220" stroke="#fff" stroke-width="3" opacity=".8"/>' +
        '</g>';
    } },
    // Espace : satellite aux panneaux solaires, antenne parabolique et feu qui clignote
    satellite: { w: 14, vb: '0 0 280 130', draw: function () {
      var panel = function (x) { var o = '<rect x="' + x + '" y="44" width="90" height="42" rx="3" fill="#1e4fa8" stroke="#c9d1e0" stroke-width="3"/>';
        for (var i = 1; i < 5; i++) o += '<line x1="' + (x + i * 18) + '" y1="44" x2="' + (x + i * 18) + '" y2="86" stroke="#7fb4ef" stroke-width="1.5"/>';
        return o + '<line x1="' + x + '" y1="65" x2="' + (x + 90) + '" y2="65" stroke="#7fb4ef" stroke-width="1.5"/><path d="M' + (x + 6) + ' 50 L' + (x + 30) + ' 50" stroke="#fff" stroke-width="2" opacity=".6"/>'; };
      return '<g class="float"><g class="roll" style="transform-origin:140px 65px">' +
        '<path d="M100 65 H180" stroke="#c9d1e0" stroke-width="5"/>' + panel(6) + panel(184) +
        '<rect x="112" y="40" width="56" height="50" rx="6" fill="#d9a441" stroke="#7a5a1a" stroke-width="3"/>' +
        '<path d="M112 52 H168 M112 66 H168 M112 80 H168" stroke="#f2c94c" stroke-width="2" opacity=".8"/>' +
        '<path d="M140 40 V24" stroke="#c9d1e0" stroke-width="3"/><path d="M124 22 C130 6 150 6 156 22Z" fill="#e8ecf4" stroke="#6b778a" stroke-width="2.5"/><circle cx="140" cy="16" r="3" fill="#6b778a"/>' +
        '<circle class="blink" cx="160" cy="96" r="4" fill="#ff3b3b"/><path d="M140 90 V102" stroke="#c9d1e0" stroke-width="3"/>' +
        '</g></g>';
    } },
    // Pirate : perroquet ara rouge, bleu et jaune qui bat des ailes
    parrot: { w: 11, vb: '0 0 230 130', draw: function () {
      var wing = function (top, mid, tip) {
        return '<path d="M128 56 C116 30 92 12 60 6 L68 16 L52 16 L62 26 L48 30 L60 38 L50 44 C80 54 100 60 116 64Z" fill="' + top + '" stroke="#3a0a10" stroke-width="2" stroke-linejoin="round"/>' +
          '<path d="M112 54 C98 38 82 26 64 18 L66 26 C84 36 98 48 106 60Z" fill="' + mid + '"/><path d="M60 6 L68 16 L52 16 L62 26 L48 30 L60 38 L50 44 C56 30 60 18 60 6Z" fill="' + tip + '"/>';
      };
      return '<g class="float">' +
        '<g class="flap" style="transform-origin:124px 60px;animation-delay:-.1s"><g transform="translate(10 -4)">' + wing('#a0141e', '#1e5fc8', '#123a8a') + '</g></g>' +
        '<path d="M70 66 L10 74 L16 82 L4 92 L68 80Z" fill="#d62828" stroke="#3a0a10" stroke-width="2" stroke-linejoin="round"/><path d="M60 74 L14 86" stroke="#1e5fc8" stroke-width="5" stroke-linecap="round"/>' +
        '<path d="M64 68 C80 54 120 50 150 54 C160 42 176 38 188 44 C198 50 200 60 196 68 C190 78 176 80 164 78 C140 90 100 90 76 82 C68 80 62 74 64 68Z" fill="#e8262b" stroke="#3a0a10" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<path d="M100 80 C120 84 146 84 160 78" stroke="#f2c94c" stroke-width="6" fill="none" stroke-linecap="round"/>' +
        '<path d="M176 50 C184 50 190 56 190 62 C186 64 180 62 176 58Z" fill="#fff"/><circle cx="182" cy="56" r="3" fill="#1a1a1a"/>' +
        '<path d="M194 54 C206 52 214 60 210 72 C206 66 200 64 194 66Z" fill="#2a2a2a" stroke="#000" stroke-width="1.5"/><path d="M196 66 C200 70 202 74 200 78 C196 74 194 70 194 66Z" fill="#4a4a4a"/>' +
        '<g class="flap" style="transform-origin:124px 60px">' + wing('#e8262b', '#2a7ae0', '#1e5fc8') + '<path d="M112 54 C104 46 96 40 86 34" stroke="#f2c94c" stroke-width="5" stroke-linecap="round"/></g>' +
        '</g>';
    } },
    // Pirate : tentacules de kraken qui sortent de l'eau et ondulent (sort du bas de l'écran)
    kraken: { w: 22, vb: '0 0 340 220', draw: function () {
      var t = function (x, h, lean, dl, s) {
        var d = 'M' + (x - 16 * s) + ' 220 C' + (x - 18 * s) + ' ' + (220 - h * .4) + ' ' + (x + lean - 10 * s) + ' ' + (220 - h * .7) + ' ' + (x + lean) + ' ' + (220 - h) +
          ' C' + (x + lean + 18 * s) + ' ' + (220 - h - 14) + ' ' + (x + lean + 26 * s) + ' ' + (220 - h + 8) + ' ' + (x + lean + 12 * s) + ' ' + (220 - h + 16) +
          ' C' + (x + lean + 4 * s) + ' ' + (220 - h + 8) + ' ' + (x + 2 * s) + ' ' + (220 - h * .6) + ' ' + (x + 16 * s) + ' 220Z';
        var su = ''; for (var i = 1; i < 6; i++) { var yy = 220 - h * i / 6, xx = x + lean * i / 6 + 6 * s; su += '<circle cx="' + xx + '" cy="' + yy + '" r="' + (5 - i * .6) * s + '" fill="#f7b2c4" stroke="#7a1a3a" stroke-width="1.2"/>'; }
        return '<g class="tent" style="animation-delay:-' + dl + 's"><path d="' + d + '" fill="#9c2a5a" stroke="#4a0a24" stroke-width="3" stroke-linejoin="round"/>' + su + '</g>';
      };
      return t(70, 170, -30, 0, 1.1) + t(170, 200, 26, .5, 1.3) + t(270, 150, 30, .9, 1) +
        '<g class="waves"><path d="M-30 200 q14 -12 28 0 q14 12 28 0 q14 -12 28 0 q14 12 28 0 q14 -12 28 0 q14 12 28 0 q14 -12 28 0 q14 12 28 0 q14 -12 28 0 q14 12 28 0 q14 -12 28 0 q14 12 28 0 q14 -12 28 0 q14 12 28 0 V220 H-30Z" fill="#1e6fa8" opacity=".9"/></g>' +
        '<path d="M0 206 H340" stroke="#bfe6ff" stroke-width="3" opacity=".6" stroke-dasharray="20 14"/>';
    } },
    // Pirate : bouteille à la mer avec son message, qui flotte sur les vagues
    bottle: { w: 9, vb: '0 0 180 110', draw: function () {
      return '<defs><linearGradient id="ps-bt" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#9fe8c0" stop-opacity=".9"/><stop offset="1" stop-color="#2f8a5a" stop-opacity=".85"/></linearGradient></defs>' +
        '<g class="float"><g class="roll" style="transform-origin:90px 70px">' +
        '<path d="M30 52 C30 40 40 36 54 36 H110 C120 36 126 40 132 46 L150 48 V64 L132 66 C126 72 120 76 110 76 H54 C40 76 30 72 30 60Z" fill="url(#ps-bt)" stroke="#1e5a3a" stroke-width="3" stroke-linejoin="round"/>' +
        '<rect x="150" y="46" width="16" height="20" rx="3" fill="#b8864a" stroke="#6b4a1a" stroke-width="2"/>' +
        '<g transform="rotate(-6 84 56)"><rect x="52" y="46" width="64" height="20" rx="6" fill="#f3e3b8" stroke="#a8864a" stroke-width="2"/><path d="M62 52 H104 M62 58 H96" stroke="#8a6a3a" stroke-width="1.6"/><path d="M84 46 V66" stroke="#c8302c" stroke-width="3"/></g>' +
        '<path d="M42 44 C60 40 90 40 120 42" stroke="#fff" stroke-width="4" fill="none" opacity=".6" stroke-linecap="round"/>' +
        '</g></g>' +
        '<g class="waves" opacity=".9"><path d="M-30 84 q14 -10 28 0 q14 10 28 0 q14 -10 28 0 q14 10 28 0 q14 -10 28 0 q14 10 28 0 q14 -10 28 0 q14 10 28 0 V110 H-30Z" fill="#2c7fd0" opacity=".75"/></g>';
    } },
    // Sakura : branche de cerisier en fleurs qui dérive, pétales qui s'en détachent
    branch: { w: 17, vb: '0 0 300 130', draw: function () {
      var fl = function (x, y, s) {
        var p = ''; for (var i = 0; i < 5; i++) p += '<ellipse cx="0" cy="-9" rx="6" ry="9" fill="#ffc1d9" stroke="#e87aa4" stroke-width="1.2" transform="rotate(' + (i * 72) + ')"/>';
        return '<g transform="translate(' + x + ' ' + y + ') scale(' + s + ')">' + p + '<circle r="4" fill="#ff7aa8"/><circle r="1.6" fill="#ffe08a"/></g>';
      };
      return '<g class="sway" style="transform-origin:150px 70px">' +
        '<path d="M10 90 C60 80 110 70 160 64 C200 60 240 50 290 30" stroke="#5a3424" stroke-width="9" fill="none" stroke-linecap="round"/>' +
        '<path d="M120 70 C130 50 150 40 170 34 M200 56 C210 70 230 80 250 82 M70 80 C76 96 90 106 108 110" stroke="#5a3424" stroke-width="5" fill="none" stroke-linecap="round"/>' +
        '<g fill="#7fbf6a"><path d="M60 82 C52 70 40 68 34 74 C42 82 52 84 60 82Z"/><path d="M230 46 C238 34 250 32 256 38 C248 46 238 48 230 46Z"/></g>' +
        fl(40, 80, 1) + fl(96, 68, 1.2) + fl(150, 46, 1) + fl(172, 30, .9) + fl(212, 58, 1.1) + fl(250, 80, .9) + fl(262, 36, 1.2) + fl(108, 106, .9) + fl(180, 70, .8) +
        '</g>' +
        '<g fill="#ffc1d9"><ellipse class="tw" cx="120" cy="118" rx="4" ry="6"/><ellipse class="tw" style="animation-delay:-.5s" cx="200" cy="110" rx="3.5" ry="5"/><ellipse class="tw" style="animation-delay:-.8s" cx="60" cy="116" rx="3" ry="4.5"/></g>';
    } },
    // Sakura : lanterne japonaise en papier qui se balance et rayonne
    lantern: { w: 6, vb: '0 0 100 170', draw: function () {
      return '<defs><radialGradient id="ps-ln" cx=".5" cy=".45" r=".6"><stop offset="0" stop-color="#fff0c8"/><stop offset=".55" stop-color="#ff6b4a"/><stop offset="1" stop-color="#c8202a"/></radialGradient>' +
        '<radialGradient id="ps-lg"><stop offset="0" stop-color="#ffb070" stop-opacity=".55"/><stop offset="1" stop-color="#ff6b4a" stop-opacity="0"/></radialGradient></defs>' +
        '<g class="sway" style="transform-origin:50px 0px">' +
        '<path d="M50 0 V18" stroke="#3a2a1a" stroke-width="2.5"/>' +
        '<circle class="pulse" cx="50" cy="80" r="50" fill="url(#ps-lg)"/>' +
        '<rect x="32" y="18" width="36" height="10" rx="3" fill="#2a1a10"/>' +
        '<path d="M50 28 C22 30 12 52 12 80 C12 108 22 128 50 132 C78 128 88 108 88 80 C88 52 78 30 50 28Z" fill="url(#ps-ln)" stroke="#7a1010" stroke-width="2.5"/>' +
        '<g stroke="#9a1a1a" stroke-width="1.6" fill="none" opacity=".7"><path d="M16 50 C36 46 64 46 84 50"/><path d="M12 70 C36 66 64 66 88 70"/><path d="M12 90 C36 94 64 94 88 90"/><path d="M16 110 C36 114 64 114 84 110"/></g>' +
        '<g transform="translate(50 80)" opacity=".85">' + [0, 72, 144, 216, 288].map(function (a) { return '<ellipse cx="0" cy="-9" rx="6" ry="9" fill="#ffe3ec" stroke="#7a1010" stroke-width="1.5" transform="rotate(' + a + ')"/>'; }).join('') + '<circle r="3.5" fill="#7a1010"/></g>' +
        '<rect x="34" y="130" width="32" height="9" rx="3" fill="#2a1a10"/>' +
        '<path class="flag" d="M50 139 V166 M44 139 L42 164 M56 139 L58 164" stroke="#d4a017" stroke-width="2.5" stroke-linecap="round"/>' +
        '</g>';
    } },
    // Sakura : grue en papier (origami) qui bat des ailes
    crane: { w: 11, vb: '0 0 220 130', draw: function () {
      var wing = function (a, b) { return '<path d="M110 70 L60 8 L130 58Z" fill="' + a + '" stroke="#b8406a" stroke-width="2" stroke-linejoin="round"/><path d="M110 70 L60 8 L96 64Z" fill="' + b + '"/>'; };
      return '<g class="float">' +
        '<g class="flap" style="transform-origin:116px 66px;animation-duration:.7s;animation-delay:-.15s"><g transform="translate(10 -2)">' + wing('#e88fb0', '#d06a92') + '</g></g>' +
        '<path d="M40 70 L110 62 L150 76 L100 90Z" fill="#ffd1e3" stroke="#b8406a" stroke-width="2" stroke-linejoin="round"/>' +
        '<path d="M100 90 L150 76 L120 96Z" fill="#f2a8c6" stroke="#b8406a" stroke-width="2" stroke-linejoin="round"/>' +
        '<path d="M40 70 L6 48 L48 78Z" fill="#ffc1d9" stroke="#b8406a" stroke-width="2" stroke-linejoin="round"/>' +
        '<path d="M146 76 L186 30 L176 50 L156 82Z" fill="#ffc1d9" stroke="#b8406a" stroke-width="2" stroke-linejoin="round"/><path d="M186 30 L206 36 L180 40Z" fill="#ff8fb8" stroke="#b8406a" stroke-width="2" stroke-linejoin="round"/>' +
        '<g class="flap" style="transform-origin:116px 66px;animation-duration:.7s">' + wing('#ffd1e3', '#f2a8c6') + '</g>' +
        '</g>';
    } },
    // Horreur : silhouette qui avance en titubant, bras tendus (deux positions des jambes)
    shambler: { w: 6.5, vb: '0 0 120 220', draw: function () {
      return '<defs><linearGradient id="ps-zb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a4a3a"/><stop offset="1" stop-color="#141a14"/></linearGradient></defs>' +
        '<g class="trot" style="animation-duration:.9s">' +
        '<g class="mouth-open" style="animation-duration:1.4s"><path d="M54 132 L46 172 L38 208 M66 132 L80 168 L90 204" stroke="#141a14" stroke-width="13" stroke-linecap="round" stroke-linejoin="round" fill="none"/></g>' +
        '<g class="mouth-shut" style="animation-duration:1.4s"><path d="M54 132 L58 172 L54 208 M66 132 L64 170 L70 206" stroke="#141a14" stroke-width="13" stroke-linecap="round" stroke-linejoin="round" fill="none"/></g>' +
        '<path d="M40 72 C38 100 42 120 46 138 H76 C80 118 80 96 76 72 C68 64 50 64 40 72Z" fill="url(#ps-zb)" stroke="#000" stroke-width="2"/>' +
        '<path d="M46 138 L52 128 L58 140 L66 126 L72 140 L76 130 V138Z" fill="#141a14"/>' +
        '<path d="M70 80 C86 82 100 84 114 82 M64 92 C80 96 94 100 110 100" stroke="#2a342a" stroke-width="11" stroke-linecap="round" fill="none"/>' +
        '<g stroke="#2a342a" stroke-width="3" stroke-linecap="round"><path d="M114 82 L120 78 M114 82 L120 84 M110 100 L118 98 M110 100 L116 104"/></g>' +
        '<g transform="rotate(14 60 50)"><ellipse cx="60" cy="46" rx="17" ry="20" fill="#2a342a" stroke="#000" stroke-width="2"/>' +
        '<circle cx="68" cy="42" r="3.2" fill="#c8ff6a"/><circle cx="68" cy="42" r="7" fill="#c8ff6a" opacity=".25"/><path d="M62 58 L74 56" stroke="#000" stroke-width="2.5"/></g>' +
        '</g>';
    } },
    // Horreur : main décharnée qui sort de terre et remue les doigts (sort du bas de l'écran)
    hand: { w: 7, vb: '0 0 120 190', draw: function () {
      return '<g class="tent" style="animation-duration:2.2s">' +
        '<path d="M44 190 L46 120 C40 110 36 96 34 80 L30 46 C29 40 37 38 39 44 L44 74 L44 30 C44 22 54 22 54 30 L56 70 L60 24 C61 16 71 17 70 25 L68 72 L76 36 C78 28 87 30 85 38 L78 82 L90 64 C94 58 101 63 98 70 L84 104 C80 114 76 120 74 128 L76 190Z" fill="#8a9a7a" stroke="#2a3020" stroke-width="3" stroke-linejoin="round"/>' +
        '<path d="M50 120 C56 112 66 112 72 120 M52 140 L70 144 M50 160 L72 158" stroke="#5a6a4a" stroke-width="2" fill="none"/>' +
        '<path d="M40 48 L36 50 M50 30 L46 32 M65 26 L61 28 M80 38 L76 40" stroke="#3a2a20" stroke-width="3" stroke-linecap="round"/>' +
        '<path d="M44 150 L54 146 L52 156Z" fill="#6a1010"/>' +
        '</g>' +
        '<path d="M0 190 C10 176 26 172 40 176 C50 168 70 168 82 176 C96 172 110 178 120 190Z" fill="#3a2a1a"/>' +
        '<g fill="#5a4030"><circle cx="20" cy="178" r="5"/><circle cx="100" cy="180" r="4"/><circle cx="34" cy="170" r="3"/></g>';
    } },
    // Horreur : poupée de porcelaine fêlée qui tourne lentement la tête (sur place)
    doll: { w: 7, vb: '0 0 120 170', draw: function () {
      return '<defs><radialGradient id="ps-dl" cx=".45" cy=".4" r=".7"><stop offset="0" stop-color="#fff8f0"/><stop offset="1" stop-color="#d8c8b8"/></radialGradient></defs>' +
        '<path d="M22 170 C24 130 36 110 60 106 C84 110 96 130 98 170Z" fill="#6a1a2a" stroke="#2a0810" stroke-width="2.5"/>' +
        '<path d="M44 108 L60 124 L76 108 L70 104 H50Z" fill="#f3e3d0" stroke="#8a6a5a" stroke-width="2"/>' +
        '<g class="turn" style="animation-duration:4s">' +
        '<path d="M22 50 C20 20 40 6 60 6 C80 6 100 20 98 50 C100 70 96 92 90 100 L84 60 H36 L30 100 C24 92 20 70 22 50Z" fill="#2a1a10"/>' +
        '<ellipse cx="60" cy="62" rx="30" ry="36" fill="url(#ps-dl)" stroke="#8a6a5a" stroke-width="2.5"/>' +
        '<ellipse cx="48" cy="58" rx="8" ry="9" fill="#0a0a0a"/><ellipse cx="72" cy="58" rx="8" ry="9" fill="#0a0a0a"/>' +
        '<circle class="pulse" cx="48" cy="58" r="2.4" fill="#ff2b2b"/><circle class="pulse" cx="72" cy="58" r="2.4" fill="#ff2b2b"/>' +
        '<ellipse cx="44" cy="76" rx="6" ry="3.5" fill="#f2a0a0" opacity=".6"/><ellipse cx="76" cy="76" rx="6" ry="3.5" fill="#f2a0a0" opacity=".6"/>' +
        '<path d="M54 84 Q60 88 66 84" stroke="#8a1a1a" stroke-width="2.5" fill="none" stroke-linecap="round"/>' +
        '<path d="M74 30 L68 46 L76 52 L70 70" stroke="#5a4a3a" stroke-width="1.6" fill="none"/>' +
        '<path d="M30 28 C40 16 50 14 60 14 C50 22 40 26 30 28Z M90 28 C80 16 70 14 60 14 C70 22 80 26 90 28Z" fill="#3a2414"/>' +
        '<path d="M36 22 C30 14 30 6 40 4 C42 12 40 18 36 22Z M84 22 C90 14 90 6 80 4 C78 12 80 18 84 22Z" fill="#6a1a2a"/>' +
        '</g>';
    } },
// GTA VI : hors-bord qui rebondit sur l'eau, sillage d'écume derrière
    boat: { w: 18, vb: '0 0 330 130', draw: function () {
      return '<defs><linearGradient id="ps-bh" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset=".55" stop-color="#ffd1ea"/><stop offset="1" stop-color="#ff3fa4"/></linearGradient></defs>' +
        '<path d="M0 112 C40 100 80 104 120 108 L130 118 C90 118 40 120 0 124Z" fill="#e8fbff" opacity=".7"/>' +
        '<g fill="#e8fbff"><circle class="tw" cx="40" cy="98" r="6"/><circle class="tw" style="animation-delay:-.3s" cx="66" cy="90" r="5"/><circle class="tw" style="animation-delay:-.6s" cx="20" cy="104" r="4"/><circle class="tw" style="animation-delay:-.45s" cx="90" cy="96" r="4"/></g>' +
        '<g class="jig" style="animation-duration:.35s">' +
        '<path d="M96 72 H300 C316 72 326 78 328 84 C300 104 250 116 200 116 H118 C104 116 96 104 96 92Z" fill="url(#ps-bh)" stroke="#5a0b38" stroke-width="3" stroke-linejoin="round"/>' +
        '<path d="M100 96 H320" stroke="#00e5ff" stroke-width="4"/><path d="M106 104 C160 108 230 106 300 92" stroke="#5a0b38" stroke-width="2" fill="none" opacity=".5"/>' +
        '<path d="M190 72 L216 46 H240 L232 72Z" fill="#7ff6ff" fill-opacity=".7" stroke="#5a0b38" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<circle cx="172" cy="52" r="10" fill="#3a2a2a"/><path d="M160 72 C160 60 166 56 172 56 C180 56 186 62 186 72Z" fill="#ff7a18"/><path d="M164 48 H182" stroke="#1a1a1a" stroke-width="4" stroke-linecap="round"/>' +
        '<rect x="96" y="66" width="20" height="14" rx="3" fill="#2a2a35"/><path d="M98 80 L92 98" stroke="#2a2a35" stroke-width="5"/>' +
        '</g>' +
        '<path d="M80 120 H330" stroke="#2c9fd0" stroke-width="5" opacity=".6"/>';
    } },
    // GTA VI : flamant rose en vol, cou tendu en avant, pattes à l'arrière
    flamingo: { w: 17, vb: '0 0 320 120', draw: function () {
      var wing = function (a, b) {
        return '<path d="M160 58 C150 30 126 10 92 4 L100 14 L84 14 L94 24 L80 28 L92 36 L82 42 C110 52 132 58 150 64Z" fill="' + a + '" stroke="#8a2a4a" stroke-width="2" stroke-linejoin="round"/>' +
          '<path d="M92 4 L100 14 L84 14 L94 24 L80 28 L92 36 L82 42 C88 28 92 16 92 4Z" fill="' + b + '"/>';
      };
      return '<g class="float">' +
        '<g class="flap" style="transform-origin:156px 62px;animation-duration:.6s;animation-delay:-.1s"><g transform="translate(10 -4)">' + wing('#e8668e', '#1a1a1a') + '</g></g>' +
        '<path d="M110 66 L20 74 M108 70 L18 82" stroke="#e8668e" stroke-width="4" stroke-linecap="round"/><path d="M20 74 L8 70 M18 82 L6 82" stroke="#e8668e" stroke-width="3" stroke-linecap="round"/>' +
        '<path d="M100 66 C110 52 150 48 180 54 C192 56 196 64 190 70 C170 80 130 82 108 76 C100 74 96 70 100 66Z" fill="#ff8fb2" stroke="#8a2a4a" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<path d="M110 70 L96 74 L108 78Z" fill="#ff8fb2" stroke="#8a2a4a" stroke-width="2" stroke-linejoin="round"/>' +
        '<path d="M186 60 C214 58 240 56 266 58" stroke="#ff8fb2" stroke-width="9" stroke-linecap="round" fill="none"/>' +
        '<ellipse cx="274" cy="58" rx="12" ry="9" fill="#ff8fb2" stroke="#8a2a4a" stroke-width="2"/>' +
        '<path d="M282 54 C296 54 306 60 308 68 C300 66 292 66 284 64Z" fill="#fff4e0" stroke="#8a2a4a" stroke-width="1.5"/><path d="M300 62 C304 64 308 68 308 72 C302 70 298 68 296 64Z" fill="#1a1a1a"/>' +
        '<circle cx="276" cy="55" r="2" fill="#1a1a1a"/>' +
        '<g class="flap" style="transform-origin:156px 62px;animation-duration:.6s">' + wing('#ff8fb2', '#1a1a1a') + '</g>' +
        '</g>';
    } },
// GTA VI : avion de tourisme à aile haute qui tire une banderole « VICE CITY » au vent
    plane: { w: 30, vb: '0 0 560 130', draw: function () {
      return '<path d="M222 60 C236 62 248 64 262 64" stroke="#c9c3d6" stroke-width="2" fill="none"/>' +
        '<g class="flagr"><path d="M10 34 H222 V86 H10 L22 60Z" fill="#fff1f8" stroke="#ff3fa4" stroke-width="3" stroke-linejoin="round"/>' +
        '<text x="120" y="72" text-anchor="middle" font-family="Bebas Neue,Arial Black,sans-serif" font-weight="900" font-size="34" fill="#ff3fa4" letter-spacing="3">VICE CITY</text></g>' +
        '<g class="float">' +
        '<path d="M264 60 L250 20 H274 L306 56Z" fill="#ff7a18" stroke="#5a2a00" stroke-width="2.5" stroke-linejoin="round"/><path d="M258 30 H274 L290 50" stroke="#fff" stroke-width="3" fill="none"/>' +
        '<path d="M262 60 L304 53 L470 49 C500 49 522 55 536 63 C541 67 539 74 530 76 L470 82 L304 79 L262 70Z" fill="#ffffff" stroke="#2a2a35" stroke-width="3" stroke-linejoin="round"/>' +
        '<path d="M268 66 L470 66 L532 66" stroke="#ff7a18" stroke-width="5"/><path d="M300 74 L470 76" stroke="#ff3fa4" stroke-width="2.5"/>' +
        '<ellipse cx="282" cy="64" rx="26" ry="4.5" fill="#ff7a18" stroke="#5a2a00" stroke-width="2"/>' +
        '<path d="M436 51 L470 50 C486 50 498 54 508 61 H436Z" fill="#7ff6ff" stroke="#2a2a35" stroke-width="2.5" stroke-linejoin="round"/><path d="M462 51 V61" stroke="#2a2a35" stroke-width="2.5"/>' +
        '<g fill="#7ff6ff" stroke="#2a2a35" stroke-width="2"><rect x="380" y="54" width="18" height="9" rx="2"/><rect x="404" y="54" width="18" height="9" rx="2"/></g>' +
        '<path d="M372 44 H486 C492 44 494 50 488 52 H372 C366 52 366 44 372 44Z" fill="#ff7a18" stroke="#5a2a00" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<path d="M420 52 L442 80" stroke="#6a6a7a" stroke-width="3"/>' +
        '<path d="M528 60 C538 61 546 65 547 70 C546 75 538 78 528 77Z" fill="#9aa0aa" stroke="#2a2a35" stroke-width="2"/><circle cx="548" cy="69" r="4" fill="#2a2a35"/>' +
        '<g transform="translate(550 69)"><ellipse class="rotor" cx="0" cy="0" rx="3" ry="26" fill="#9aa4c0" opacity=".65"/></g>' +
        '<path d="M452 82 L446 98 M470 82 L476 98" stroke="#2a2a35" stroke-width="3.5"/><circle cx="446" cy="100" r="6" fill="#2a2a35"/><circle cx="476" cy="100" r="6" fill="#2a2a35"/>' +
        '<path d="M276 70 L272 78" stroke="#2a2a35" stroke-width="2.5"/><circle cx="272" cy="80" r="3.5" fill="#2a2a35"/>' +
        '</g>';
    } },
    // R.E.P.O. : deux petits robots qui portent ensemble un grand vase en or
    carry: { w: 16, vb: '0 0 280 190', draw: function () {
      var bot = function (x, cls) {
        return '<g transform="translate(' + x + ' 0)">' +
          '<g class="leg-b"><rect x="26" y="146" width="8" height="28" rx="4" fill="#3a3a3a"/><rect x="20" y="170" width="20" height="7" rx="3" fill="#1a1400"/></g>' +
          '<g class="bob"><rect x="14" y="112" width="44" height="38" rx="9" fill="#ffd400" stroke="#1a1400" stroke-width="3"/><path d="M20 140 L28 132 M30 146 L46 130" stroke="#1a1400" stroke-width="3.5" stroke-linecap="round"/>' +
          '<rect x="10" y="74" width="52" height="40" rx="18" fill="#ffd400" stroke="#1a1400" stroke-width="3"/><rect x="24" y="84" width="34" height="20" rx="10" fill="#1a1400"/>' +
          '<ellipse cx="36" cy="94" rx="4" ry="5.5" fill="#6bf0ff"/><ellipse cx="49" cy="94" rx="4" ry="5.5" fill="#6bf0ff"/>' +
          '<path d="M18 116 L12 70 M54 116 L60 70" stroke="#3a3a3a" stroke-width="5" stroke-linecap="round"/></g>' +
          '<g class="leg-a"><rect x="42" y="146" width="8" height="28" rx="4" fill="#3a3a3a"/><rect x="38" y="170" width="20" height="7" rx="3" fill="#1a1400"/></g></g>';
      };
      return bot(20) + bot(196) +
        '<g class="bob"><defs><linearGradient id="ps-gv" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#b8860b"/><stop offset=".45" stop-color="#ffe9a0"/><stop offset="1" stop-color="#9a6a08"/></linearGradient></defs>' +
        '<rect x="30" y="62" width="240" height="10" rx="4" fill="#6b4a2a" stroke="#2a1a0a" stroke-width="2"/>' +
        '<path d="M126 62 C112 54 108 40 118 30 C110 22 112 10 122 8 H178 C188 10 190 22 182 30 C192 40 188 54 174 62Z" fill="url(#ps-gv)" stroke="#5a3a00" stroke-width="3" stroke-linejoin="round"/>' +
        '<path d="M120 30 H180" stroke="#5a3a00" stroke-width="2.5"/><path d="M132 14 C134 26 134 44 136 54" stroke="#fff6c8" stroke-width="4" opacity=".7" stroke-linecap="round"/>' +
        '<path class="tw" d="M190 14 l2 5 5 2 -5 2 -2 5 -2 -5 -5 -2 5 -2z" fill="#fff6c8"/><path class="tw" style="animation-delay:-.5s" d="M108 40 l2 5 5 2 -5 2 -2 5 -2 -5 -5 -2 5 -2z" fill="#fff6c8"/></g>';
    } },
    // R.E.P.O. : chariot plein de butin (or, gemmes, vase) qui roule
    cart: { w: 12, vb: '0 0 220 150', draw: function () {
      var wheel = function (cx) { return '<g transform="translate(' + cx + ' 128)"><circle r="16" fill="#2a2a2a"/><g class="spinf"><circle r="10" fill="#8a8a8a"/><path d="M0 -10 V10 M-10 0 H10" stroke="#2a2a2a" stroke-width="3"/></g><circle r="3" fill="#ffd400"/></g>'; };
      return '<g class="jig">' +
        '<path d="M20 70 C40 40 80 30 110 40 C140 26 180 36 196 62Z" fill="#ffd23f" stroke="#8a5a00" stroke-width="2.5"/>' +
        '<g fill="#ffe680" stroke="#8a5a00" stroke-width="1.5"><circle cx="50" cy="56" r="9"/><circle cx="74" cy="48" r="9"/><circle cx="150" cy="50" r="9"/><circle cx="170" cy="58" r="8"/></g>' +
        '<path d="M98 30 L110 14 L122 30 L110 46Z" fill="#5ad1ff" stroke="#1a5a8a" stroke-width="2"/><path d="M130 40 L138 28 L146 40 L138 50Z" fill="#ff5a8a" stroke="#8a1a3a" stroke-width="2"/>' +
        '<path d="M60 36 C56 26 58 18 66 16 H86 C94 18 96 26 92 36Z" fill="#c9a04a" stroke="#5a3a00" stroke-width="2"/>' +
        '<path d="M14 64 H206 L192 112 H28Z" fill="#6b778a" stroke="#2a2f3a" stroke-width="3" stroke-linejoin="round"/>' +
        '<path d="M20 78 H202 M24 94 H198" stroke="#9aa5b8" stroke-width="2.5"/><path d="M60 64 L52 112 M110 64 V112 M160 64 L168 112" stroke="#4a5568" stroke-width="2"/>' +
        '<path d="M206 64 L218 46" stroke="#2a2f3a" stroke-width="5" stroke-linecap="round"/>' +
        '</g>' + wheel(54) + wheel(166);
    } },
// R.E.P.O. : monstre bossu qui court sur ses longs bras, cornes, pics sur le dos et gueule ouverte (deux positions)
// R.E.P.O. : spectre en robe déchirée qui flotte au ras du sol, capuche vide, yeux luisants, longs bras griffus tendus en avant
    monster: { w: 9, vb: '0 0 180 230', draw: function () {
      return '<defs><linearGradient id="ps-rb2" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a2a52"/><stop offset=".6" stop-color="#22183a"/><stop offset="1" stop-color="#120c22"/></linearGradient>' +
        '<radialGradient id="ps-eye"><stop offset="0" stop-color="#ffffff"/><stop offset=".4" stop-color="#bff6ff"/><stop offset="1" stop-color="#5ad8ff" stop-opacity="0"/></radialGradient></defs>' +
        '<g class="float" style="animation-duration:1.4s">' +
        '<g opacity=".45"><path class="tent" d="M30 120 C10 126 0 140 -4 158 C10 150 22 146 34 146Z" fill="#22183a"/><path class="tent" style="animation-delay:-.6s" d="M34 160 C16 170 8 184 6 202 C18 192 28 186 40 184Z" fill="#22183a"/></g>' +
        '<path d="M110 74 C126 84 140 92 160 96" stroke="#1a1228" stroke-width="10" stroke-linecap="round" fill="none"/>' +
        '<g stroke="#cfc6dc" stroke-width="3" stroke-linecap="round"><path d="M160 96 L176 92 M160 96 L178 100 M158 98 L172 108"/></g>' +
        '<path d="M64 42 C44 62 38 120 34 190 L118 190 C116 120 110 62 98 42Z" fill="url(#ps-rb2)" stroke="#6a4a8a" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<g class="tent" style="animation-duration:1.1s"><path d="M34 188 L42 214 L52 192 L62 222 L72 194 L84 218 L94 194 L104 216 L112 192 L118 188Z" fill="#120c22" stroke="#6a4a8a" stroke-width="2" stroke-linejoin="round"/></g>' +
        '<path d="M60 70 C58 110 56 150 54 186 M92 70 C96 110 98 150 100 186" stroke="#4a3664" stroke-width="2.5" fill="none" opacity=".8"/>' +
        '<path d="M50 56 C46 24 64 4 86 6 C108 8 120 28 114 54 C106 46 92 42 80 42 C68 42 58 48 50 56Z" fill="#2e2244" stroke="#6a4a8a" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<ellipse cx="90" cy="42" rx="18" ry="20" fill="#05030a"/>' +
        '<circle class="pulse" cx="86" cy="40" r="9" fill="url(#ps-eye)"/><circle class="pulse" cx="100" cy="40" r="8" fill="url(#ps-eye)"/>' +
        '<circle cx="86" cy="40" r="4.2" fill="#ffffff"/><circle cx="100" cy="40" r="3.8" fill="#ffffff"/>' +
        '<path d="M100 66 C120 76 140 82 162 82" stroke="#2e2244" stroke-width="12" stroke-linecap="round" fill="none"/><path d="M100 66 C120 76 140 82 162 82" stroke="#6a4a8a" stroke-width="2" fill="none" opacity=".7"/>' +
        '<g stroke="#e4ddee" stroke-width="3" stroke-linecap="round"><path d="M162 82 L178 76 M162 82 L180 84 M161 84 L176 94"/></g>' +
        '</g>';
    } },
    // Battle Royale : lama piñata à franges colorées, long cou, museau allongé et grandes oreilles, qui bondit
    llama: { w: 10, vb: '0 -20 210 220', draw: function () {
      var fr = function (x, y, w, c) { var d = 'M' + x + ' ' + y; for (var i = 0; i < w / 10; i++) d += ' q5 6 10 0'; return '<path d="' + d + ' V' + (y - 9) + ' H' + x + 'Z" fill="' + c + '"/>'; };
      var cols = ['#ff4fd8', '#ffd23f', '#3fd1ff', '#5bff6b'];
      var body = ''; cols.forEach(function (c, i) { body += fr(36, 96 + i * 13, 110, c); });
      return '<ellipse cx="96" cy="194" rx="56" ry="5" fill="#000" opacity=".3"/>' +
        '<g class="hop" style="animation-duration:.7s">' +
        '<g fill="#4a2490" stroke="#2a0a5a" stroke-width="2.5"><rect x="62" y="136" width="12" height="44" rx="5"/><rect x="138" y="136" width="12" height="44" rx="5"/></g><g fill="#6a34c0" stroke="#2a0a5a" stroke-width="2.5"><rect x="44" y="136" width="13" height="46" rx="5"/><rect x="120" y="136" width="13" height="46" rx="5"/></g>' +
        '<path d="M30 92 C20 88 12 96 16 106 C22 102 28 100 36 100" fill="#8a4ae0" stroke="#2a0a5a" stroke-width="2.5"/>' +
        '<path d="M34 96 C34 80 54 74 96 74 C130 74 150 80 150 96 V142 H34Z" fill="#8a4ae0" stroke="#2a0a5a" stroke-width="3"/>' + body +
        '<path d="M34 96 C34 80 54 74 96 74 C130 74 150 80 150 96 V142 H34Z" fill="none" stroke="#2a0a5a" stroke-width="3"/>' +
        '<clipPath id="ps-lneck"><path d="M112 92 C116 70 124 50 132 34 L166 30 C166 52 162 74 152 96Z"/></clipPath>' +
        '<path d="M112 92 C116 70 124 50 132 34 L166 30 C166 52 162 74 152 96Z" fill="#8a4ae0"/>' +
        '<g clip-path="url(#ps-lneck)">' + [0, 1, 2, 3, 4].map(function (i) { return fr(108, 48 + i * 11, 64, cols[i % 4]); }).join('') + '</g>' +
        '<path d="M112 92 C116 70 124 50 132 34 L166 30 C166 52 162 74 152 96" fill="none" stroke="#2a0a5a" stroke-width="3" stroke-linejoin="round"/>' +
        '<path d="M140 2 C134 -10 136 -20 144 -22 C150 -14 150 -4 148 4Z M156 2 C156 -12 162 -20 170 -18 C172 -8 168 0 162 6Z" fill="#8a4ae0" stroke="#2a0a5a" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<path d="M142 -2 C140 -10 141 -16 144 -18 M160 0 C162 -8 165 -14 168 -15" stroke="#ff4fd8" stroke-width="3" fill="none" stroke-linecap="round"/>' +
        '<path d="M128 26 C126 10 138 0 154 2 C166 4 176 10 190 18 C200 24 202 34 194 38 C182 42 166 42 150 42 C136 42 128 36 128 26Z" fill="#8a4ae0" stroke="#2a0a5a" stroke-width="3" stroke-linejoin="round"/>' +
        '<path d="M178 22 C190 24 198 28 200 34 C192 38 184 38 176 36Z" fill="#b47aff"/><circle cx="196" cy="30" r="2.4" fill="#2a0a5a"/><path d="M186 38 Q192 40 198 37" stroke="#2a0a5a" stroke-width="2" fill="none"/>' +
        '<circle cx="158" cy="18" r="7" fill="#fff" stroke="#2a0a5a" stroke-width="2"/><circle cx="160" cy="18" r="4" fill="#1a1a1a"/><circle cx="161.5" cy="16.5" r="1.4" fill="#fff"/>' +
        '<path d="M134 8 C140 4 148 4 154 6" stroke="#ff4fd8" stroke-width="4" fill="none" stroke-linecap="round"/>' +
        '</g>';
    } },
// Battle Royale : joueur qui descend sous un parachute à panneaux colorés
    glider: { w: 10, vb: '0 0 180 230', draw: function () {
      var cols = ['#3fd1ff', '#ff3fa4', '#ffd23f', '#5bff6b', '#b14bff', '#ff8a1a'];
      var gores = ''; for (var i = 0; i < 6; i++) {
        var x0 = 14 + i * 25.3, x1 = x0 + 25.3, mx = (x0 + x1) / 2;
        gores += '<path d="M90 10 C' + (90 + (x0 - 90) * .7) + ' 12 ' + x0 + ' 40 ' + x0 + ' 80 Q' + mx + ' 70 ' + x1 + ' 80 C' + x1 + ' 40 ' + (90 + (x1 - 90) * .7) + ' 12 90 10Z" fill="' + cols[i] + '" stroke="#16084a" stroke-width="2.5" stroke-linejoin="round"/>';
      }
      return '<g class="sway" style="transform-origin:90px 10px">' + gores +
        '<path d="M30 30 C44 18 62 12 80 11" stroke="#fff" stroke-width="5" fill="none" opacity=".5" stroke-linecap="round"/>' +
        '<g stroke="#e6e1f0" stroke-width="1.6"><line x1="14" y1="80" x2="82" y2="150"/><line x1="40" y1="80" x2="84" y2="148"/><line x1="65" y1="80" x2="86" y2="146"/><line x1="115" y1="80" x2="94" y2="146"/><line x1="140" y1="80" x2="96" y2="148"/><line x1="166" y1="80" x2="98" y2="150"/></g>' +
        '<path d="M80 150 L84 158 M100 150 L96 158" stroke="#3a3a4a" stroke-width="3"/>' +
        '<path d="M80 156 L74 172 M100 156 L106 172" stroke="#f5cba7" stroke-width="7" stroke-linecap="round"/>' +
        '<rect x="78" y="166" width="24" height="30" rx="6" fill="#3a8a5a" stroke="#1a3a2a" stroke-width="2"/><path d="M80 176 H100" stroke="#ffd23f" stroke-width="3"/>' +
        '<circle cx="90" cy="158" r="11" fill="#f5cba7" stroke="#5a3a2a" stroke-width="2"/><path d="M79 155 C80 144 100 144 101 155 C96 151 86 151 79 155Z" fill="#3a2a1a"/><circle cx="94" cy="158" r="1.8" fill="#1a1a1a"/>' +
        '<path d="M84 196 L78 218 M96 196 L104 216" stroke="#2a3a6a" stroke-width="8" stroke-linecap="round"/><path d="M74 220 H84 M102 218 H112" stroke="#1a1a1a" stroke-width="5" stroke-linecap="round"/>' +
        '</g>';
    } },
    // Battle Royale : coffre doré vu de face, couvercle grand ouvert, intérieur qui rayonne (sur place)
    chest: { w: 9, vb: '0 0 170 170', draw: function () {
      return '<defs><linearGradient id="ps-cg3" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffe680"/><stop offset="1" stop-color="#d4930f"/></linearGradient>' +
        '<linearGradient id="ps-ray" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#fff6c8" stop-opacity=".9"/><stop offset="1" stop-color="#fff6c8" stop-opacity="0"/></linearGradient></defs>' +
        '<g class="pulse"><path d="M60 80 L34 4 H58Z M80 78 L74 0 H98Z M104 80 L118 4 H142Z" fill="url(#ps-ray)"/></g>' +
        '<path d="M28 82 L40 40 H130 L142 82Z" fill="#7a4a0a" stroke="#4a2a00" stroke-width="3" stroke-linejoin="round"/>' +
        '<path d="M40 40 C40 28 130 28 130 40" fill="url(#ps-cg3)" stroke="#4a2a00" stroke-width="3"/>' +
        '<path d="M46 76 L54 46 H116 L124 76Z" fill="#fff3b0" opacity=".85"/><path d="M58 72 L64 52 H106 L112 72Z" fill="#ffffff" opacity=".7"/>' +
        '<path d="M70 40 L66 82 M100 40 L104 82" stroke="#b8860b" stroke-width="5"/>' +
        '<rect x="24" y="82" width="122" height="68" rx="6" fill="url(#ps-cg3)" stroke="#4a2a00" stroke-width="3"/>' +
        '<path d="M24 96 H146" stroke="#b8860b" stroke-width="4"/><path d="M58 82 V150 M112 82 V150" stroke="#b8860b" stroke-width="6"/>' +
        '<path d="M24 150 H146" stroke="#4a2a00" stroke-width="3"/>' +
        '<rect x="74" y="96" width="22" height="26" rx="5" fill="#ffd23f" stroke="#4a2a00" stroke-width="2.5"/><path d="M85 104 V114" stroke="#4a2a00" stroke-width="3" stroke-linecap="round"/><circle cx="85" cy="104" r="3" fill="#4a2a00"/>' +
        '<path d="M32 88 H50" stroke="#fffbe0" stroke-width="3" opacity=".8" stroke-linecap="round"/>' +
        '<g fill="#fff6c8"><path class="tw" d="M30 30 l3 7 7 3 -7 3 -3 7 -3 -7 -7 -3 7 -3z"/><path class="tw" style="animation-delay:-.4s" d="M140 22 l3 7 7 3 -7 3 -3 7 -3 -7 -7 -3 7 -3z"/><path class="tw" style="animation-delay:-.7s" d="M86 12 l2 5 5 2 -5 2 -2 5 -2 -5 -5 -2 5 -2z"/></g>';
    } },
    // Dark fantasy : chevalier en armure au galop, bannière au vent
    knight: { w: 18, vb: '0 -80 310 270', draw: function () {
      return DRAW.epona.draw().replace(/#b8673a/g, '#9aa0aa').replace(/#7a3f1e/g, '#5a606a').replace(/#f5ecd8/g, '#2a2a30').replace(/#6a3518/g, '#4a4e58').replace(/#8a4a24/g, '#6a707a').replace(/ps-ep/g, 'ps-kn') +
        '<g class="gallop">' +
        '<path d="M110 66 C120 54 190 54 206 66 L212 112 C190 120 130 120 104 112Z" fill="#8a1a2a" stroke="#3a0810" stroke-width="2.5"/><path d="M110 112 L118 104 L126 114 L134 104 L142 114 L150 104 L158 114 L166 104 L174 114 L182 104 L190 114 L198 104 L206 112" stroke="#d4b06a" stroke-width="3" fill="none"/>' +
                '<path d="M136 -2 C136 -18 168 -18 168 -2 L172 60 H134Z" fill="#c9cfd8" stroke="#3a3f4a" stroke-width="2.5"/><path d="M140 10 H166 M138 30 H170" stroke="#8a8f9a" stroke-width="2"/>' +
        // jambe en armure : cuisse, genouillère, tibia le long du flanc, soleret dans l'étrier
        '<path d="M164 72 L170 104" stroke="#5a3a1a" stroke-width="2.5"/>' +
        '<path d="M142 54 L168 74 L164 104" stroke="#2a2f3a" stroke-width="24" stroke-linecap="round" stroke-linejoin="round" fill="none"/>' +
        '<path d="M142 54 L168 74" stroke="#a8b0bc" stroke-width="19" stroke-linecap="round"/>' +
        '<path d="M168 74 L164 104" stroke="#98a0ac" stroke-width="15" stroke-linecap="round"/>' +
        '<path d="M140 52 L170 70 M138 62 L164 80 M162 78 L158 104 M172 76 L170 104" stroke="#3a3f4a" stroke-width="2" fill="none" opacity=".7"/>' +
        '<circle cx="169" cy="74" r="9" fill="#dfe4ec" stroke="#3a3f4a" stroke-width="2"/>' +
        '<path d="M158 102 H176 C182 102 184 108 178 110 H158Z" fill="#9aa0aa" stroke="#3a3f4a" stroke-width="2" stroke-linejoin="round"/>' +
        '<path d="M156 112 H180" stroke="#5a5a62" stroke-width="3" stroke-linecap="round"/>' +
        '<path d="M160 6 L190 20" stroke="#c9cfd8" stroke-width="10" stroke-linecap="round"/>' +
        '<path d="M140 -24 C140 -46 166 -46 166 -24 V-8 H140Z" fill="#c9cfd8" stroke="#3a3f4a" stroke-width="2.5"/><path d="M152 -28 H166" stroke="#1a1a1a" stroke-width="4"/><path d="M148 -44 C152 -60 170 -62 176 -52 C166 -50 158 -46 152 -40" fill="#d62828"/>' +
        '<path d="M192 22 V-76" stroke="#5a3a1a" stroke-width="5" stroke-linecap="round"/>' +
        '<g class="flagr"><path d="M190 -74 H130 L142 -60 L130 -46 H190Z" fill="#8a1a2a" stroke="#3a0810" stroke-width="2"/><path d="M168 -66 L172 -56 L162 -60 H174 L164 -56Z" fill="#d4b06a"/></g>' +
        '</g>';
    } },
// Dark fantasy : chauve-souris géante de profil — ailes membraneuses à doigts qui battent depuis l'épaule, grandes oreilles, crocs
    giantbat: { w: 14, vb: '0 -20 260 170', draw: function () {
      var wing = function (mem, bone, edge) {
        return '<path d="M150 66 L130 30 L100 14 L40 6 Q58 28 32 40 Q60 50 48 70 Q82 72 92 86 Q118 80 142 78Z" fill="' + mem + '" stroke="' + edge + '" stroke-width="2.5" stroke-linejoin="round"/>' +
          '<path d="M150 66 L130 30 L100 14" stroke="' + bone + '" stroke-width="5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>' +
          '<path d="M100 14 L40 6 M100 14 L32 40 M100 14 L48 70 M100 14 L92 86" stroke="' + bone + '" stroke-width="2.6" stroke-linecap="round"/>' +
          '<path d="M100 14 L104 4 L108 14" fill="' + bone + '"/>';
      };
      return '<g class="float" style="animation-duration:1.2s">' +
        '<g class="flap" style="transform-origin:150px 66px;animation-duration:.42s;animation-delay:-.1s"><g transform="translate(14 -6)">' + wing('#3a2236', '#24121f', '#120810') + '</g></g>' +
        '<path d="M118 86 L104 96 M124 88 L112 100" stroke="#3a2a34" stroke-width="3.5" stroke-linecap="round"/><path d="M104 96 l-5 1 M104 96 l-2 5 M112 100 l-5 1 M112 100 l-2 5" stroke="#d8ccd8" stroke-width="2" stroke-linecap="round"/>' +
        '<path d="M120 70 C130 58 156 56 170 62 C182 68 184 78 178 84 C166 94 138 94 124 88 C114 84 112 76 120 70Z" fill="#5a3a50" stroke="#1a0c16" stroke-width="2.5"/>' +
        '<path d="M128 84 C140 90 160 90 172 84" stroke="#8a6a80" stroke-width="3" fill="none" opacity=".7"/>' +
        '<path d="M174 54 L168 30 L184 50Z M186 52 L194 28 L198 54Z" fill="#5a3a50" stroke="#1a0c16" stroke-width="2.5" stroke-linejoin="round"/><path d="M174 48 L171 36 L180 48Z M188 48 L193 36 L195 50Z" fill="#c88aa8"/>' +
        '<path d="M170 66 C170 54 180 48 190 52 C198 56 204 64 208 70 C202 76 192 80 182 78 C174 76 170 72 170 66Z" fill="#5a3a50" stroke="#1a0c16" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<circle cx="207" cy="70" r="2" fill="#1a0c16"/><circle cx="188" cy="62" r="3.4" fill="#ff4a4a"/><circle cx="189" cy="61" r="1.1" fill="#fff"/>' +
        '<path d="M194 76 L196 84 L199 76 M200 75 L202 82 L204 74" fill="#fff" stroke="#fff" stroke-width="1"/>' +
        '<g class="flap" style="transform-origin:150px 66px;animation-duration:.42s">' + wing('#6a4462', '#2a1424', '#120810') + '</g>' +
        '</g>';
    } },
    // Dark fantasy : esprits lumineux (feux follets) qui ondulent en traînée
    wisps: { w: 14, vb: '0 0 280 100', draw: function () {
      var w = function (x, y, r, dl, c) {
        return '<g class="float" style="animation-delay:-' + dl + 's;animation-duration:1.3s"><path d="M' + (x - r * 4) + ' ' + y + ' C' + (x - r * 2) + ' ' + (y - r) + ' ' + (x - r) + ' ' + (y - r) + ' ' + x + ' ' + (y - r * .8) + ' V' + (y + r * .8) + ' C' + (x - r) + ' ' + (y + r) + ' ' + (x - r * 2) + ' ' + (y + r) + ' ' + (x - r * 4) + ' ' + y + 'Z" fill="' + c + '" opacity=".35"/>' +
          '<circle class="pulse" cx="' + x + '" cy="' + y + '" r="' + (r * 2.2) + '" fill="' + c + '" opacity=".25"/><circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="#f4fbff"/></g>';
      };
      return w(60, 40, 8, 0, '#7fd8ff') + w(130, 62, 10, .4, '#a8f0ff') + w(200, 34, 7, .8, '#7fd8ff') + w(256, 58, 9, .2, '#c8f6ff');
    } },
// Pleine lune : grosse lune qui se lève derrière un loup qui hurle sur son rocher (sort du bas de l'écran)
    moon: { w: 16, vb: '0 0 260 250', draw: function () {
      return '<defs><radialGradient id="ps-mn" cx=".42" cy=".38" r=".7"><stop offset="0" stop-color="#ffffff"/><stop offset=".6" stop-color="#e6ecff"/><stop offset="1" stop-color="#aeb9e0"/></radialGradient>' +
        '<radialGradient id="ps-mg"><stop offset="0" stop-color="#dfe6ff" stop-opacity=".5"/><stop offset="1" stop-color="#9db4ff" stop-opacity="0"/></radialGradient></defs>' +
        '<circle class="pulse" cx="130" cy="110" r="125" fill="url(#ps-mg)"/>' +
        '<circle cx="130" cy="110" r="88" fill="url(#ps-mn)"/>' +
        '<g fill="#c4cdea" opacity=".8"><circle cx="100" cy="80" r="14"/><circle cx="160" cy="130" r="18"/><circle cx="150" cy="70" r="8"/><circle cx="96" cy="140" r="9"/><circle cx="178" cy="96" r="6"/></g>' +
        '<path d="M20 250 L60 196 L92 188 L120 160 L150 170 L176 150 L206 176 L240 200 L260 250Z" fill="#0d1230"/>' +
        '<g class="trot" style="animation-duration:2.4s"><path d="M106 166 C104 150 110 138 120 132 L124 112 L130 102 L134 112 L146 94 C150 88 156 88 156 94 L150 110 C156 118 158 130 154 142 L164 160 C168 166 162 170 156 166 L146 158 L142 168 H134 L130 158 L122 168 H114 Z" fill="#0d1230"/>' +
        '<path d="M108 168 C94 164 84 170 80 180 C90 176 100 176 110 178Z" fill="#0d1230"/></g>';
    } },
    // Pleine lune : chouette qui plane, grands yeux ronds, ailes qui battent
    owl: { w: 12, vb: '0 0 230 140', draw: function () {
      var wing = function (a, b) {
        return '<path d="M120 62 C108 34 84 14 48 8 L56 18 L42 20 L52 30 L38 34 L50 42 L40 48 C70 56 92 64 108 70Z" fill="' + a + '" stroke="#3a2412" stroke-width="2" stroke-linejoin="round"/>' +
          '<path d="M56 18 L72 32 M52 30 L70 40 M50 42 L68 48" stroke="' + b + '" stroke-width="2.4" stroke-linecap="round"/>';
      };
      return '<g class="float">' +
        '<g class="flap" style="transform-origin:118px 66px;animation-duration:.7s;animation-delay:-.12s"><g transform="translate(10 -4)">' + wing('#6b4a2a', '#4a3018') + '</g></g>' +
        '<path d="M60 74 L26 70 L32 80 L22 88 L60 86Z" fill="#8a6a42" stroke="#3a2412" stroke-width="2" stroke-linejoin="round"/>' +
        '<path d="M56 78 C70 58 120 52 150 58 C164 60 170 72 166 84 C160 98 130 104 100 100 C78 98 60 92 56 78Z" fill="#a07a4a" stroke="#3a2412" stroke-width="2.5"/>' +
        '<g fill="#5a3a1a" opacity=".6"><path d="M90 88 l4 4 4 -4"/><path d="M106 90 l4 4 4 -4"/><path d="M122 88 l4 4 4 -4"/></g>' +
        '<circle cx="172" cy="62" r="28" fill="#b08a5a" stroke="#3a2412" stroke-width="2.5"/>' +
        '<path d="M150 44 L146 26 L162 38Z M192 40 L200 22 L204 42Z" fill="#8a6a42" stroke="#3a2412" stroke-width="2" stroke-linejoin="round"/>' +
        '<circle cx="164" cy="60" r="12" fill="#f3e6c8"/><circle cx="188" cy="60" r="12" fill="#f3e6c8"/>' +
        '<circle cx="166" cy="60" r="7" fill="#ffb000"/><circle cx="190" cy="60" r="7" fill="#ffb000"/><circle cx="167" cy="60" r="3.6" fill="#1a1a1a"/><circle cx="191" cy="60" r="3.6" fill="#1a1a1a"/>' +
        '<circle cx="168.5" cy="58.5" r="1.2" fill="#fff"/><circle cx="192.5" cy="58.5" r="1.2" fill="#fff"/>' +
        '<path d="M176 68 L182 80 L188 68Z" fill="#e8b84a" stroke="#6a4a10" stroke-width="1.5" stroke-linejoin="round"/>' +
        '<g class="flap" style="transform-origin:118px 66px;animation-duration:.7s">' + wing('#8a6a42', '#5a3a1a') + '</g>' +
        '</g>';
    } },
    // Pleine lune : chasseur en manteau, chapeau et fusil, lanterne qui se balance (deux positions des jambes)
    hunter: { w: 7, vb: '0 0 140 220', draw: function () {
      return '<defs><radialGradient id="ps-hl2"><stop offset="0" stop-color="#ffe9a0" stop-opacity=".8"/><stop offset="1" stop-color="#ffb347" stop-opacity="0"/></radialGradient></defs>' +
        '<g class="trot" style="animation-duration:.8s">' +
        '<g class="mouth-open" style="animation-duration:1.2s"><path d="M56 140 L46 176 L40 208 M70 140 L84 172 L92 204" stroke="#2a1e14" stroke-width="12" stroke-linecap="round" stroke-linejoin="round" fill="none"/></g>' +
        '<g class="mouth-shut" style="animation-duration:1.2s"><path d="M56 140 L60 176 L56 208 M70 140 L66 174 L72 206" stroke="#2a1e14" stroke-width="12" stroke-linecap="round" stroke-linejoin="round" fill="none"/></g>' +
        '<path d="M40 52 L28 14" stroke="#4a3a2a" stroke-width="5" stroke-linecap="round"/><path d="M26 10 L30 22" stroke="#2a2a2a" stroke-width="7" stroke-linecap="round"/>' +
        '<path d="M44 66 C40 90 38 120 36 150 H88 C86 120 84 90 80 66 C72 58 52 58 44 66Z" fill="#5a3a24" stroke="#1e140a" stroke-width="2.5"/>' +
        '<path d="M60 64 V150" stroke="#3a2414" stroke-width="2"/><path d="M42 100 H84" stroke="#2a1a0a" stroke-width="5"/>' +
        '<circle cx="64" cy="46" r="14" fill="#e8c09a" stroke="#5a3a24" stroke-width="2"/><circle cx="70" cy="44" r="2" fill="#1a1a1a"/><path d="M58 54 C62 60 70 60 74 56" fill="#6a4a2a"/>' +
        '<ellipse cx="62" cy="34" rx="24" ry="5" fill="#2a1e14"/><path d="M48 34 C48 18 56 12 64 12 C72 12 78 18 78 34Z" fill="#3a2a1a"/>' +
        '<path d="M78 74 L100 98" stroke="#5a3a24" stroke-width="9" stroke-linecap="round"/>' +
        '<g class="sway" style="transform-origin:102px 100px;animation-duration:1.1s">' +
        '<circle class="pulse" cx="104" cy="130" r="30" fill="url(#ps-hl2)"/>' +
        '<path d="M102 100 V112" stroke="#2a2a2a" stroke-width="2.5"/><path d="M94 112 H112 L110 118 H96Z" fill="#2a2a2a"/>' +
        '<rect x="96" y="118" width="16" height="22" rx="3" fill="#ffd36a" stroke="#2a2a2a" stroke-width="2.5"/><path d="M104 122 C100 128 100 134 104 136 C108 134 108 128 104 122Z" fill="#ff8a1a"/>' +
        '<path d="M94 140 H114" stroke="#2a2a2a" stroke-width="4"/></g>' +
        '</g>';
    } },
    // Brouillard : silhouette qui avance lentement dans la brume, lampe torche qui éclaire devant (deux positions des jambes)
    figure: { w: 13, vb: '0 0 260 220', draw: function () {
      return '<defs><linearGradient id="ps-tb" x1="0" x2="1"><stop offset="0" stop-color="#fff6d8" stop-opacity=".55"/><stop offset="1" stop-color="#fff6d8" stop-opacity="0"/></linearGradient>' +
        '<linearGradient id="ps-fg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a3a40"/><stop offset="1" stop-color="#1a1a1e"/></linearGradient></defs>' +
        '<path class="pulse" d="M110 92 L260 50 V150Z" fill="url(#ps-tb)"/>' +
        '<g class="trot" style="animation-duration:1.1s">' +
        '<g class="mouth-open" style="animation-duration:1.6s"><path d="M56 140 L46 176 L40 208 M70 140 L84 172 L92 204" stroke="#1a1a1e" stroke-width="12" stroke-linecap="round" stroke-linejoin="round" fill="none"/></g>' +
        '<g class="mouth-shut" style="animation-duration:1.6s"><path d="M56 140 L60 176 L56 208 M70 140 L66 174 L72 206" stroke="#1a1a1e" stroke-width="12" stroke-linecap="round" stroke-linejoin="round" fill="none"/></g>' +
        '<path d="M42 62 C38 90 38 120 40 148 H86 C88 120 88 90 82 62 C72 54 52 54 42 62Z" fill="url(#ps-fg)"/>' +
        '<path d="M78 72 C90 80 100 86 108 90" stroke="#2a2a30" stroke-width="10" stroke-linecap="round"/>' +
        '<rect x="102" y="84" width="16" height="10" rx="3" fill="#3a3a40" transform="rotate(-16 110 89)"/><circle cx="118" cy="86" r="4" fill="#fff6d8"/>' +
        '<circle cx="62" cy="42" r="15" fill="#2a2a30"/><path d="M46 40 C46 24 56 20 64 20 C74 20 80 26 80 40 C76 34 70 32 62 32 C54 32 50 36 46 40Z" fill="#1a1a1e"/>' +
        '</g>';
    } },
    // Brouillard : sirène d'alerte sur son poteau, gyrophare qui tourne et ondes sonores (sur place)
    siren: { w: 9, vb: '0 0 170 230', draw: function () {
      var arc = function (r, dl) { return '<path class="tw" style="animation-delay:-' + dl + 's" d="M' + (110 + r * .5) + ' ' + (60 - r) + ' C' + (110 + r) + ' ' + (60 - r * .4) + ' ' + (110 + r) + ' ' + (60 + r * .4) + ' ' + (110 + r * .5) + ' ' + (60 + r) + '" stroke="#e6e1d8" stroke-width="3" fill="none" stroke-linecap="round"/>'; };
      return '<path d="M70 90 V230" stroke="#5a4a3a" stroke-width="10"/><path d="M50 230 H90" stroke="#3a2a1a" stroke-width="8"/>' +
        '<path d="M40 50 H100 L120 34 V86 L100 70 H40Z" fill="#8a8f9a" stroke="#2a2f3a" stroke-width="3" stroke-linejoin="round"/>' +
        '<path d="M48 56 H96 M48 64 H96" stroke="#5a606a" stroke-width="2"/>' +
        '<rect x="36" y="44" width="14" height="32" rx="3" fill="#5a606a" stroke="#2a2f3a" stroke-width="2.5"/>' +
        '<path d="M58 50 V34 H84 V50" fill="#3a3f4a"/><path d="M60 34 C60 18 82 18 82 34Z" fill="#ff2b2b" stroke="#6a0a0a" stroke-width="2"/>' +
        '<g class="blink"><path d="M71 26 L20 4 L24 30Z M71 26 L122 4 L118 30Z" fill="#ff2b2b" opacity=".35"/><circle cx="71" cy="26" r="14" fill="#ff4a4a" opacity=".5"/></g>' +
        arc(26, 0) + arc(42, .3) + arc(58, .6);
    } },
    // Brouillard : talkie-walkie qui grésille, voyant rouge et ondes de parasites (sur place)
    radio: { w: 8, vb: '0 0 150 190', draw: function () {
      var st = ''; for (var i = 0; i < 9; i++) st += '<rect class="blink' + (i % 2 ? '2' : '') + '" x="' + (36 + (i * 37) % 70) + '" y="' + (78 + (i * 23) % 40) + '" width="' + (6 + i % 3 * 4) + '" height="2.5" fill="#e6e1d8" opacity=".7"/>';
      return '<path d="M48 40 V2" stroke="#2a2a2a" stroke-width="6" stroke-linecap="round"/><circle cx="48" cy="2" r="4" fill="#2a2a2a"/>' +
        '<rect x="24" y="36" width="92" height="150" rx="16" fill="#3a3f2a" stroke="#14180a" stroke-width="3"/>' +
        '<rect x="34" y="70" width="72" height="56" rx="6" fill="#2a2a22" stroke="#14180a" stroke-width="2"/>' + st +
        '<g fill="#14180a">' + [0, 1, 2, 3, 4].map(function (r) { return [0, 1, 2, 3, 4, 5].map(function (c) { return '<circle cx="' + (44 + c * 10) + '" cy="' + (140 + r * 8) + '" r="2.4"/>'; }).join(''); }).join('') + '</g>' +
        '<circle class="blink" cx="100" cy="52" r="5" fill="#ff2b2b"/><rect x="36" y="46" width="40" height="12" rx="3" fill="#7ac74f" opacity=".8"/>' +
        '<path d="M44 52 l4 -3 4 6 4 -6 4 6 4 -3" stroke="#14180a" stroke-width="1.6" fill="none"/>' +
        '<path class="tw" d="M126 70 C136 80 136 100 126 110" stroke="#e6e1d8" stroke-width="3" fill="none" stroke-linecap="round"/><path class="tw" style="animation-delay:-.5s" d="M134 58 C150 76 150 104 134 122" stroke="#e6e1d8" stroke-width="3" fill="none" stroke-linecap="round"/>';
    } },
    // Post-apo : buggy des terres désolées — grosses roues crantées, châssis rouillé, arceau, pare-chocs à pointes, pot qui fume, pilote à lunettes
    buggy: { w: 18, vb: '0 0 330 175', draw: function () {
      var wheel = function (cx) {
        return '<g transform="translate(' + cx + ' 138)"><circle r="31" fill="#1a1a18"/><circle r="31" fill="none" stroke="#3a3a34" stroke-width="7" stroke-dasharray="7 6"/>' +
          '<g class="spinf"><circle r="16" fill="#8a5a2a" stroke="#3a2410" stroke-width="2.5"/><g fill="#3a2410"><circle cx="0" cy="-9" r="2.6"/><circle cx="8.5" cy="-2.8" r="2.6"/><circle cx="5.3" cy="7.3" r="2.6"/><circle cx="-5.3" cy="7.3" r="2.6"/><circle cx="-8.5" cy="-2.8" r="2.6"/></g></g>' +
          '<circle r="4.5" fill="#c8a070"/></g>';
      };
      return '<g fill="#a89a80" opacity=".6"><circle class="tw" cx="96" cy="34" r="9"/><circle class="tw" style="animation-delay:-.4s" cx="84" cy="20" r="7"/><circle class="tw" style="animation-delay:-.7s" cx="72" cy="10" r="5"/></g>' +
        '<g fill="#b8a07a" opacity=".5"><circle class="tw" cx="22" cy="150" r="14"/><circle class="tw" style="animation-delay:-.5s" cx="40" cy="136" r="10"/></g>' +
        '<g class="jig">' +
        '<circle cx="58" cy="98" r="22" fill="#1a1a18" stroke="#3a3a34" stroke-width="5" stroke-dasharray="6 5"/><circle cx="58" cy="98" r="10" fill="#6b4a24"/>' +
        '<path d="M102 88 L98 46" stroke="#4a4e48" stroke-width="7" stroke-linecap="round"/><path d="M94 44 H104" stroke="#2a2a28" stroke-width="5" stroke-linecap="round"/>' +
        '<path d="M64 114 L76 92 H142 L158 76 H218 L236 92 H290 L306 104 V120 H64Z" fill="#a8642a" stroke="#2a1608" stroke-width="3" stroke-linejoin="round"/>' +
        '<path d="M160 92 H214 V118 H160Z" fill="#5a6a3a" stroke="#2a1608" stroke-width="2.5"/><path d="M168 100 H206" stroke="#3a4624" stroke-width="2"/>' +
        '<path d="M70 120 C70 100 112 100 112 120 M228 120 C228 100 272 100 272 120" stroke="#2a1608" stroke-width="7" fill="none"/>' +
        '<g fill="#6b3a14" opacity=".7"><circle cx="134" cy="104" r="5"/><path d="M246 98 l12 3 -8 7z"/><circle cx="290" cy="112" r="3"/></g>' +
        '<g fill="#2a1608"><circle cx="150" cy="96" r="2"/><circle cx="150" cy="112" r="2"/><circle cx="222" cy="96" r="2"/><circle cx="222" cy="112" r="2"/></g>' +
        '<text x="120" y="114" font-family="Arial Black,Arial,sans-serif" font-weight="900" font-size="15" fill="#f2e2c0" opacity=".85">77</text>' +
        '<path d="M126 92 L140 40 H200 L218 76 M140 40 L156 76 M200 40 L188 76" stroke="#3a3f44" stroke-width="7" fill="none" stroke-linejoin="round" stroke-linecap="round"/>' +
        '<path class="flag" d="M160 62 C146 60 134 62 120 68 L124 74 C136 70 148 68 162 68Z" fill="#c8302c"/>' +
        '<circle cx="172" cy="56" r="13" fill="#c8a07a" stroke="#3a2a1a" stroke-width="2"/><path d="M160 50 C162 40 182 38 186 50Z" fill="#5a4a3a"/>' +
        '<rect x="164" y="50" width="26" height="9" rx="4" fill="#3cff6a" stroke="#1a1a1a" stroke-width="2.5"/><path d="M162 66 C168 72 178 72 184 66" fill="#c8302c"/>' +
        '<path d="M184 70 L204 84" stroke="#c8a07a" stroke-width="6" stroke-linecap="round"/>' +
        '<rect x="294" y="94" width="12" height="9" rx="2" fill="#ffd36a" stroke="#2a1608" stroke-width="1.5"/>' +
        '<path d="M306 104 L322 108 L306 112Z M306 112 L322 116 L306 120Z" fill="#c9cfd8" stroke="#3a3f44" stroke-width="1.5" stroke-linejoin="round"/>' +
        '</g>' + wheel(92) + wheel(250);
    } },
// Post-apo : robot sphérique d'après-guerre qui flotte — coque kaki rouillée, rivets, grand objectif, antenne, ailerons, petits réacteurs
    assistbot: { w: 7, vb: '0 0 150 170', draw: function () {
      var rv = ''; [[46, 52], [104, 52], [36, 84], [114, 84], [50, 112], [100, 112]].forEach(function (p) { rv += '<circle cx="' + p[0] + '" cy="' + p[1] + '" r="2.4" fill="#2a3018"/>'; });
      return '<defs><radialGradient id="ps-ab2" cx=".36" cy=".3" r=".8"><stop offset="0" stop-color="#9aa86a"/><stop offset=".6" stop-color="#5f6c38"/><stop offset="1" stop-color="#2f3818"/></radialGradient>' +
        '<radialGradient id="ps-lens" cx=".4" cy=".35" r=".7"><stop offset="0" stop-color="#eaffef"/><stop offset=".35" stop-color="#3cff6a"/><stop offset="1" stop-color="#0a4a1a"/></radialGradient></defs>' +
        '<g class="float">' +
        '<g class="flame"><path d="M54 126 C50 136 52 146 58 152 C64 146 66 136 62 126Z" fill="#ff8a1a"/><path d="M56 128 C55 134 56 140 58 144 C60 140 61 134 60 128Z" fill="#fff3a0"/></g>' +
        '<g class="flame" style="animation-delay:-.13s"><path d="M88 126 C84 136 86 146 92 152 C98 146 100 136 96 126Z" fill="#ff8a1a"/><path d="M90 128 C89 134 90 140 92 144 C94 140 95 134 94 128Z" fill="#fff3a0"/></g>' +
        '<path d="M50 116 H66 L62 128 H54Z M84 116 H100 L96 128 H88Z" fill="#3a3f2a" stroke="#14180a" stroke-width="2"/>' +
        '<path d="M28 70 L8 60 L12 84 L30 88Z M122 70 L142 60 L138 84 L120 88Z" fill="#4a5628" stroke="#14180a" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<circle cx="75" cy="78" r="48" fill="url(#ps-ab2)" stroke="#14180a" stroke-width="3"/>' +
        '<path d="M30 70 C50 64 100 64 120 70 M28 92 C50 98 100 98 122 92" stroke="#2f3818" stroke-width="2.5" fill="none"/>' + rv +
        '<g fill="#8a4a1a" opacity=".55"><path d="M40 100 l8 2 -2 6z"/><path d="M106 44 l6 4 -6 2z"/><circle cx="58" cy="104" r="3"/></g>' +
        '<circle cx="84" cy="74" r="20" fill="#2a2f1a" stroke="#14180a" stroke-width="3"/><circle cx="84" cy="74" r="14" fill="url(#ps-lens)"/><circle class="pulse" cx="84" cy="74" r="6" fill="#bfffcf"/><circle cx="79" cy="69" r="3" fill="#fff"/>' +
        '<g fill="#14180a"><rect x="44" y="70" width="18" height="3" rx="1.5"/><rect x="44" y="76" width="18" height="3" rx="1.5"/><rect x="44" y="82" width="18" height="3" rx="1.5"/></g>' +
        '<circle cx="62" cy="104" r="7" fill="#ffd400" stroke="#14180a" stroke-width="1.5"/><path d="M62 104 L58 98 A7 7 0 0 1 66 98Z M62 104 L69 106 A7 7 0 0 1 65 110Z M62 104 L59 110 A7 7 0 0 1 55 106Z" fill="#14180a"/>' +
        '<path d="M50 44 C58 36 68 32 78 32" stroke="#c8d49a" stroke-width="4" fill="none" opacity=".7" stroke-linecap="round"/>' +
        '<path d="M92 32 L100 8" stroke="#3a3f2a" stroke-width="3"/><circle class="blink" cx="100" cy="7" r="4" fill="#ff3b3b"/>' +
        '</g>';
    } },
    // Pokémon : trois balles différentes qui roulent en rebondissant
    balls: { w: 14, vb: '0 0 280 90', draw: function () {
      var ball = function (x, top, band, extra, dl) {
        return '<g transform="translate(' + x + ' 46)"><g class="hop" style="animation-delay:-' + dl + 's"><g class="spin">' +
          '<circle r="30" fill="#fff" stroke="#222" stroke-width="4"/><path d="M-30 0 A30 30 0 0 1 30 0Z" fill="' + top + '" stroke="#222" stroke-width="4"/>' + extra +
          '<line x1="-30" y1="0" x2="30" y2="0" stroke="#222" stroke-width="5"/><circle r="9" fill="#fff" stroke="#222" stroke-width="4"/><circle r="3.5" fill="#ddd"/>' +
          '<ellipse cx="-12" cy="-16" rx="7" ry="3.5" transform="rotate(-35 -12 -16)" fill="#fff" opacity=".55"/></g></g></g>';
      };
      return ball(40, '#2a6ad8', '', '<path d="M-22 -18 L-12 -8 M22 -18 L12 -8" stroke="#e3350d" stroke-width="6" stroke-linecap="round"/>', 0) +
        ball(140, '#222', '', '<path d="M-14 -28 V-6 M14 -28 V-6" stroke="#ffcb05" stroke-width="7" stroke-linecap="round"/>', .2) +
        ball(240, '#7a3fd0', '', '<circle cx="-14" cy="-14" r="5" fill="#ff7ad8"/><circle cx="14" cy="-14" r="5" fill="#ff7ad8"/><text x="0" y="-9" text-anchor="middle" font-family="Arial Black,Arial,sans-serif" font-weight="900" font-size="12" fill="#fff">M</text>', .4);
    } },
    // Pokémon : jeune dresseur à vélo, casquette rouge, roues qui tournent (deux positions des jambes)
    cyclist: { w: 12, vb: '0 0 230 180', draw: function () {
      var wheel = function (cx) { return '<g transform="translate(' + cx + ' 140)"><circle r="32" fill="none" stroke="#1a1a1a" stroke-width="6"/><g class="spinf"><circle r="30" fill="none"/><path d="M0 -30 V30 M-30 0 H30 M-21 -21 L21 21 M21 -21 L-21 21" stroke="#9aa0aa" stroke-width="1.6"/></g><circle r="4" fill="#5a5a5a"/></g>'; };
      return '<g class="jig">' + wheel(50) + wheel(180) +
        '<path d="M50 140 L100 140 L130 92 H84 Z M100 140 L84 92 M130 92 L180 140 M126 84 L138 70" stroke="#e3350d" stroke-width="6" fill="none" stroke-linejoin="round" stroke-linecap="round"/>' +
        '<path d="M76 88 H96" stroke="#1a1a1a" stroke-width="6" stroke-linecap="round"/><path d="M132 70 H148" stroke="#1a1a1a" stroke-width="5" stroke-linecap="round"/>' +
        '<g class="mouth-open" style="animation-duration:.5s"><path d="M88 82 L112 112 L104 140 M88 82 L96 118 L120 128" stroke="#2a4a8a" stroke-width="10" stroke-linecap="round" stroke-linejoin="round" fill="none"/></g>' +
        '<g class="mouth-shut" style="animation-duration:.5s"><path d="M88 82 L114 104 L118 130 M88 82 L92 116 L96 140" stroke="#2a4a8a" stroke-width="10" stroke-linecap="round" stroke-linejoin="round" fill="none"/></g>' +
        '<path d="M86 84 C84 64 96 48 112 46 L120 52 C110 60 104 72 102 86Z" fill="#2aa8d8" stroke="#145a7a" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<path d="M108 54 L140 70" stroke="#f5cba7" stroke-width="8" stroke-linecap="round"/>' +
        '<circle cx="120" cy="36" r="14" fill="#f5cba7" stroke="#8a5a3a" stroke-width="2"/><circle cx="127" cy="34" r="2" fill="#1a1a1a"/>' +
        '<path d="M106 32 C106 18 132 16 136 28 L148 30 C146 34 140 34 134 32 Z" fill="#e3350d" stroke="#7a1a05" stroke-width="2" stroke-linejoin="round"/><path d="M110 26 C116 22 124 22 128 24" stroke="#fff" stroke-width="3"/>' +
        '<path d="M104 36 C100 40 100 46 104 48" stroke="#3a2a1a" stroke-width="4" fill="none" stroke-linecap="round"/>' +
        '<rect x="74" y="56" width="20" height="26" rx="6" fill="#ffcb05" stroke="#8a6a00" stroke-width="2"/>' +
        '</g>';
    } },
    // Pokémon : nuée de petits oiseaux qui battent des ailes
    birds: { w: 15, vb: '0 0 290 110', draw: function () {
      var bird = function (x, y, s, dl) {
        return '<g transform="translate(' + x + ' ' + y + ') scale(' + s + ')">' +
          '<path d="M6 26 L-8 22 L-4 30 L-10 36 L8 32Z" fill="#8a5a2a" stroke="#3a2412" stroke-width="1.5" stroke-linejoin="round"/>' +
          '<path d="M4 28 C10 18 30 16 42 20 C50 22 54 28 50 34 C44 40 24 40 12 36 C6 34 2 32 4 28Z" fill="#c8964a" stroke="#3a2412" stroke-width="1.8"/>' +
          '<path d="M14 34 C24 38 38 38 46 32" stroke="#f3e0b8" stroke-width="4" fill="none" stroke-linecap="round"/>' +
          '<circle cx="48" cy="18" r="9" fill="#c8964a" stroke="#3a2412" stroke-width="1.8"/><path d="M44 10 L42 2 L48 8 L50 0 L52 9" fill="#c8964a" stroke="#3a2412" stroke-width="1.2"/>' +
          '<circle cx="51" cy="16" r="2" fill="#1a1a1a"/><path d="M56 18 L64 20 L56 22Z" fill="#e8b84a" stroke="#6a4a10" stroke-width="1"/>' +
          '<g class="batw" style="animation-duration:.2s;animation-delay:-' + dl + 's;transform-origin:50% 100%"><path d="M32 24 C26 10 16 2 4 0 L8 6 L2 8 L8 12 L4 16 C14 20 22 24 28 28Z" fill="#a8763a" stroke="#3a2412" stroke-width="1.5" stroke-linejoin="round"/></g>' +
          '</g>';
      };
      return bird(10, 30, 1, 0) + bird(90, 8, .8, .07) + bird(140, 54, 1.1, .03) + bird(220, 22, .9, .12) + bird(70, 70, .7, .1);
    } },
    // Cosy : petit renard roux qui trotte, queue touffue à bout blanc (deux positions des pattes)
    fox: { w: 12, vb: '0 0 250 140', draw: function () {
      var legs = function (pts, c) { return pts.map(function (p) { return '<polyline points="' + p + '" fill="none" stroke="' + c + '" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>'; }).join(''); };
      var paws = function (pts) { return pts.map(function (p) { var q = p.split(' ').pop().split(','); return '<circle cx="' + q[0] + '" cy="' + q[1] + '" r="5" fill="#2a1a10"/>'; }).join(''); };
      var A1 = ['170,92 180,112 190,128', '92,94 82,112 70,126'], A2 = ['160,94 152,114 146,130', '102,96 110,114 118,128'];
      return '<defs><linearGradient id="ps-fx" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ff9a3c"/><stop offset="1" stop-color="#d9650f"/></linearGradient></defs>' +
        '<g class="trot">' +
        '<g class="mouth-open" style="animation-duration:.4s">' + legs(A1, '#a84a0a') + paws(A1) + '</g><g class="mouth-shut" style="animation-duration:.4s">' + legs(A2, '#a84a0a') + paws(A2) + '</g>' +
        '<g class="sway" style="transform-origin:86px 80px;animation-duration:.8s"><path d="M88 78 C60 62 30 66 8 84 C24 96 52 98 80 90Z" fill="url(#ps-fx)" stroke="#6a2a04" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<path d="M28 74 C18 76 10 80 8 84 C16 92 26 94 34 94 C30 86 28 80 28 74Z" fill="#fffaf0"/></g>' +
        '<path d="M84 84 C84 66 110 58 150 58 C176 58 190 66 192 80 C194 94 176 102 146 102 C110 102 84 98 84 84Z" fill="url(#ps-fx)" stroke="#6a2a04" stroke-width="2.5"/>' +
        '<path d="M150 98 C166 100 182 96 190 86 C180 84 168 86 160 90Z" fill="#fffaf0"/>' +
        '<path d="M184 70 C190 54 206 46 222 50 L244 64 C240 70 232 72 224 72 C214 78 196 80 186 78Z" fill="url(#ps-fx)" stroke="#6a2a04" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<path d="M216 66 L244 64 C240 70 232 72 224 72 C220 72 216 70 216 66Z" fill="#fffaf0"/><circle cx="244" cy="64" r="3" fill="#1a1a1a"/>' +
        '<path d="M196 52 L196 30 L210 48Z M208 48 L214 28 L222 50Z" fill="#d9650f" stroke="#6a2a04" stroke-width="2" stroke-linejoin="round"/><path d="M200 46 L199 36 L206 46Z" fill="#2a1a10"/>' +
        '<circle cx="216" cy="58" r="3" fill="#1a1a1a"/><circle cx="217" cy="57" r="1" fill="#fff"/>' +
        '<g class="mouth-open" style="animation-duration:.4s">' + legs(['176,90 196,108 210,118', '96,92 74,106 58,114'], '#d9650f') + paws(['176,90 196,108 210,118', '96,92 74,106 58,114']) + '</g>' +
        '<g class="mouth-shut" style="animation-duration:.4s">' + legs(['176,90 172,112 162,128', '96,92 104,112 98,128'], '#d9650f') + paws(['176,90 172,112 162,128', '96,92 104,112 98,128']) + '</g>' +
        '</g>';
    } },
    // Cosy : coccinelle qui vole, élytres ouverts et ailes fines qui vibrent
    ladybug: { w: 6, vb: '0 0 130 100', draw: function () {
      return '<g class="float" style="animation-duration:.9s">' +
        '<g class="beat" style="transform-origin:66px 40px"><path d="M66 40 C50 10 26 4 18 16 C12 28 40 40 66 44Z" fill="#e6f6ff" fill-opacity=".7" stroke="#8ab0c8" stroke-width="1.5"/>' +
        '<path d="M66 40 C82 10 106 4 114 16 C120 28 92 40 66 44Z" fill="#e6f6ff" fill-opacity=".6" stroke="#8ab0c8" stroke-width="1.5"/></g>' +
        '<g stroke="#1a1a1a" stroke-width="2.5" stroke-linecap="round"><path d="M50 76 L42 88 M64 80 L62 94 M78 76 L84 88"/></g>' +
        '<ellipse cx="64" cy="62" rx="38" ry="24" fill="#1a1a1a"/>' +
        '<g transform="rotate(-24 50 54)"><path d="M28 60 C26 40 40 30 60 30 C64 44 64 60 58 76 C42 76 30 70 28 60Z" fill="#e8262b" stroke="#6b0f12" stroke-width="2"/><circle cx="42" cy="50" r="5" fill="#1a1a1a"/><circle cx="50" cy="66" r="4" fill="#1a1a1a"/></g>' +
        '<g transform="rotate(18 82 54)"><path d="M100 60 C102 40 88 30 68 30 C64 44 64 60 70 76 C86 76 98 70 100 60Z" fill="#e8262b" stroke="#6b0f12" stroke-width="2"/><circle cx="86" cy="48" r="5" fill="#1a1a1a"/><circle cx="80" cy="64" r="4" fill="#1a1a1a"/></g>' +
        '<circle cx="104" cy="60" r="13" fill="#1a1a1a"/><circle cx="108" cy="56" r="3.5" fill="#fff"/><circle cx="109" cy="56" r="1.8" fill="#1a1a1a"/>' +
        '<path d="M110 50 C116 40 122 38 126 40 M104 48 C108 36 112 32 118 32" stroke="#1a1a1a" stroke-width="2" fill="none" stroke-linecap="round"/>' +
        '<ellipse cx="44" cy="40" rx="6" ry="3" fill="#fff" opacity=".5" transform="rotate(-24 44 40)"/>' +
        '</g>';
    } },
    // Cosy : montgolfière en tissu patchwork avec coutures, panier en osier
    patchballoon: { w: 9, vb: '0 0 170 230', draw: function () {
      var cols = ['#ffb4a2', '#7cc68d', '#ffd166', '#8ecae6', '#e5989b', '#b5e48c'];
      var gores = ''; for (var i = 0; i < 6; i++) {
        var x0 = 15 + i * 23.3, x1 = x0 + 23.3;
        gores += '<path d="M85 8 C' + (85 + (x0 - 85) * 1.25) + ' 20 ' + x0 + ' 70 ' + (85 + (x0 - 85) * .9) + ' 110 L' + (85 + (x0 - 85) * .35) + ' 160 H' + (85 + (x1 - 85) * .35) + ' L' + (85 + (x1 - 85) * .9) + ' 110 C' + x1 + ' 70 ' + (85 + (x1 - 85) * 1.25) + ' 20 85 8Z" fill="' + cols[i] + '"/>';
      }
      return '<g class="sway" style="transform-origin:85px 10px;animation-duration:2.6s">' +
        '<clipPath id="ps-pb"><path d="M85 8 C30 8 10 50 14 90 C18 120 50 146 62 160 H108 C120 146 152 120 156 90 C160 50 140 8 85 8Z"/></clipPath>' +
        '<g clip-path="url(#ps-pb)">' + gores + '<path d="M10 60 H160 M12 100 H158" stroke="#fffaf0" stroke-width="2.5" stroke-dasharray="6 5"/></g>' +
        '<path d="M85 8 C30 8 10 50 14 90 C18 120 50 146 62 160 H108 C120 146 152 120 156 90 C160 50 140 8 85 8Z" fill="none" stroke="#5a3a2a" stroke-width="3"/>' +
        '<path d="M40 40 C50 24 64 18 76 16" stroke="#fff" stroke-width="5" fill="none" opacity=".5" stroke-linecap="round"/>' +
        '<g stroke="#5a3a2a" stroke-width="2"><line x1="64" y1="160" x2="68" y2="196"/><line x1="106" y1="160" x2="102" y2="196"/></g>' +
        '<path d="M62 196 H108 L104 224 H66Z" fill="#c8964a" stroke="#5a3a1a" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<path d="M64 204 H106 M65 212 H105 M75 196 V224 M85 196 V224 M95 196 V224" stroke="#8a5a2a" stroke-width="1.6"/>' +
        '<circle cx="78" cy="190" r="6" fill="#f5cba7"/><circle cx="94" cy="191" r="5.5" fill="#d9a07a"/>' +
        '</g>';
    } },
    // Pokémon : Super Ball (bleue à bandes rouges)
    superball: { w: 8, vb: '0 0 100 100', draw: function () { return pokeBall('#2a6ad8', '<path d="M22 22 L36 38 M78 22 L64 38" stroke="#e3350d" stroke-width="9" stroke-linecap="round"/>'); } },
    // Pokémon : Hyper Ball (noire à bandes jaunes)
    hyperball: { w: 8, vb: '0 0 100 100', draw: function () { return pokeBall('#2a2a2e', '<path d="M34 9 V40 M66 9 V40" stroke="#ffcb05" stroke-width="10" stroke-linecap="round"/>'); } },
    // Pokémon : Master Ball (violette, pastilles roses et « M »)
    masterball: { w: 8, vb: '0 0 100 100', draw: function () { return pokeBall('#7a3fd0', '<circle cx="28" cy="30" r="7" fill="#ff7ad8"/><circle cx="72" cy="30" r="7" fill="#ff7ad8"/><text x="50" y="36" text-anchor="middle" font-family="Arial Black,Arial,sans-serif" font-weight="900" font-size="18" fill="#fff">M</text>'); } }
  };

  // ── Sprites pixel art : chaque élément est capturé image par image depuis son dessin animé (12 images par cycle),
  // pixellisé (palette commune, contour sombre) et rangé en planche dans /static/passers_px/<nom>.png.
  // Un pixel d'art fait ART_VW vw (≈ 3,5 px sur un écran de 1920 px). Données : [images, durée du cycle ms, largeur, hauteur].
  var BASEPX = '/static/passers_px/';
  try { BASEPX = new URL('passers_px/', document.currentScript.src).href; } catch (e) {}
  var ART_VW = 3.5 / 19.2;
  var PX = {"epona":[12,1200,84,57],"loftwing":[12,1200,100,47],"pinkfairy":[12,1200,41,20],"witch":[12,1200,94,48],"bats":[12,1200,86,28],"pumpkin":[12,1200,36,41],"sleigh":[12,1200,145,43],"snowmansled":[12,1200,65,49],"snowflakes":[12,1200,77,34],"penguin":[12,1200,62,20],"drone":[12,1200,57,31],"flycar":[12,1200,95,33],"hologram":[12,1200,72,60],"pacman":[12,1200,112,20],"invaders":[12,1200,72,41],"mushroom":[12,1200,32,37],"whale":[12,1200,120,51],"turtle":[12,1200,64,36],"fish":[12,1200,61,24],"jellyfish":[12,1200,35,56],"dolphins":[12,1200,84,36],"ufo":[12,1200,60,44],"astronaut":[12,1200,53,53],"comet":[12,1200,85,20],"rocket":[12,1200,79,32],"satellite":[12,1200,78,30],"ship":[12,1200,106,78],"parrot":[12,1200,58,27],"kraken":[12,1200,151,80],"bottle":[12,1200,71,25],"butterfly":[12,1200,27,29],"lantern":[12,1200,36,58],"crane":[12,1200,58,28],"crow":[12,1200,56,29],"shambler":[12,1200,30,61],"eyes":[12,1200,42,14],"hand":[12,1200,41,59],"doll":[12,1200,39,57],"car":[12,1200,116,31],"heli":[12,1200,68,45],"boat":[12,1200,102,28],"flamingo":[12,1200,91,28],"plane":[12,1200,158,32],"robot":[12,1200,36,48],"carry":[12,1200,79,58],"cart":[12,1200,65,43],"monster":[12,1200,68,46],"bus":[12,1200,83,84],"llama":[12,1200,51,63],"glider":[12,1200,66,47],"dragon":[12,1200,131,53],"knight":[12,1200,88,88],"giantbat":[12,1200,57,31],"wisps":[12,1200,71,22],"wolf":[12,1200,91,41],"moon":[12,1200,84,80],"owl":[12,1200,56,32],"hunter":[12,1200,31,61],"figure":[12,1200,52,57],"siren":[12,1200,45,73],"radio":[12,1200,40,58],"supply":[12,1200,51,59],"buggy":[12,1200,89,42],"assistbot":[12,1200,47,51],"pokeball":[12,1200,34,37],"cyclist":[12,1200,61,48],"birds":[12,1200,82,28],"bee":[12,1200,28,23],"fox":[12,1200,66,33],"ladybug":[12,1200,32,25],"patchballoon":[12,1200,51,67]};
  function buildPx(k) {
    var p = PX[k];
    return '<div class="pxs" style="padding-bottom:' + (p[3] / p[2] * 100) + '%;background-image:url(' + BASEPX + k + '.png);background-size:' + (p[0] * 100) + '% 100%;' +
      'animation:ps-px ' + p[1] + 'ms steps(' + p[0] + ', jump-none) infinite"></div>';
  }

  // Un passage : entre à gauche ou à droite, traverse l'écran avec un léger balancement vertical, puis disparaît
  // Façon de se déplacer de chaque élément :
  //   ground : roule / marche en bas de l'écran (bas du dessin posé vers 96 % de la hauteur), sans tanguer
  //   spot   : apparaît sur place puis disparaît ('fade') ; 'rise' : sort du bas de l'écran puis y retourne
  //   dur (ms), amp (tangage vertical en vh), waves (nombre d'ondulations), y : [min, max] de la hauteur (vh), drift : descente en vh
  var META = {
    comet: { dur: 4200, drift: 26, tilt: 12 }, car: { ground: 1, dur: 4800 }, wolf: { ground: 1, dur: 5200 }, pokeball: { ground: 1, dur: 6000 },
    superball: { ground: 1, dur: 5600 }, hyperball: { ground: 1, dur: 5200 }, masterball: { ground: 1, dur: 6400 },
    robot: { ground: 1, dur: 11000 }, ship: { dur: 15000, amp: 1.2, y: [40, 58] }, fog: { dur: 26000, amp: 1.2, y: [50, 80] }, supply: { dur: 14000, drift: 30, y: [2, 14] },
    whale: { amp: 1.2, dur: 13000 }, butterfly: { waves: 6 }, eyes: { spot: 'fade', dur: 5200, glow: '#ff1a1a', blink: 1 },
    epona: { ground: 1, dur: 6500 }, pumpkin: { ground: 1, dur: 9000 }, snowmansled: { ground: 1, dur: 7000 }, penguin: { ground: 1, dur: 8000 },
    mushroom: { ground: 1, dur: 7000 }, bottle: { ground: 1, dur: 16000 }, shambler: { ground: 1, dur: 17000 }, boat: { ground: 1, dur: 6000 },
    carry: { ground: 1, dur: 14000 }, cart: { ground: 1, dur: 9000 }, monster: { ground: 1, dur: 13000 }, llama: { ground: 1, dur: 8000 },
    knight: { ground: 1, dur: 7000 }, hunter: { ground: 1, dur: 16000 }, figure: { ground: 1, dur: 20000 }, buggy: { ground: 1, dur: 6000 },
    balls: { ground: 1, dur: 7000 }, cyclist: { ground: 1, dur: 8000 }, fox: { ground: 1, dur: 7000 },
    hologram: { spot: 'fade', dur: 6000, glitch: 1 }, doll: { spot: 'fade', dur: 6500 }, chest: { spot: 'fade', dur: 6000 },
    siren: { spot: 'fade', dur: 6000 }, radio: { spot: 'fade', dur: 6000 },
    kraken: { spot: 'rise', dur: 7000 }, hand: { spot: 'rise', dur: 6000 }, moon: { spot: 'rise', dur: 9000 },
    dolphins: { amp: 7, waves: 4, dur: 9000, y: [30, 55] }, jellyfish: { amp: 3, dur: 16000 }, astronaut: { dur: 16000, amp: 3 },
    satellite: { dur: 15000, amp: 1 }, lantern: { dur: 15000, amp: 2 }, branch: { dur: 13000, amp: 3 }, snowflakes: { dur: 14000, amp: 3 },
    wisps: { dur: 11000, amp: 5, waves: 3 }, turtle: { dur: 13000, amp: 2 }, patchballoon: { dur: 16000, amp: 2, y: [6, 30] },
    plane: { dur: 12000, amp: 1.5, y: [12, 26] }, glider: { dur: 11000, drift: 18, y: [4, 20] }, assistbot: { dur: 11000, amp: 3 },
    bats: { dur: 7000, amp: 5, waves: 3 }, birds: { dur: 9000, amp: 3, waves: 2, y: [4, 30] }
  };
  function sizeVh(d, scale) { var p = d.vb.split(' '); return d.w * (scale || 1) * (+p[3] / +p[2]) * 16 / 9; }

  function fly(container, kind, opts) {
    var px = PX[kind], d = px ? { w: px[2] * ART_VW, vb: '0 0 ' + px[2] + ' ' + px[3] } : DRAW[kind]; if (!d || !container) return;
    opts = opts || {};
    var m = META[kind] || {}, scale = opts.scale || 1, wv = d.w * scale, hv = sizeVh(d, scale);
    var body = px ? buildPx(kind) : svg(DRAW[kind].vb, DRAW[kind].draw());
    // tous les dessins regardent vers la droite : retournés quand ils vont vers la gauche
    var flipFor = function (goingLeft) { return goingLeft; };
    var el = document.createElement('div'), dur = opts.duration || m.dur || 9500;
    el.style.width = wv + 'vw';
    if (m.spot) {                                            // sur place
      var rtlS = false;   // sur place : jamais retourné (textes, visages de face)
      el.className = 'pass' + (rtlS ? ' rtl' : '');
      el.innerHTML = '<div class="dir">' + body + '</div>';
      if (m.glow) el.style.filter = 'drop-shadow(0 0 .8vw ' + m.glow + ')';
      container.appendChild(el);
      var sx = 4 + Math.random() * Math.max(1, 92 - wv), an;
      if (m.spot === 'drop') {                              // descend du haut au bout de son fil, puis remonte
        var low = 10 + Math.random() * 30;
        el.innerHTML = '<div style="position:absolute;left:50%;bottom:90%;width:2px;height:120vh;background:rgba(220,220,230,.6)"></div>' + el.innerHTML;
        an = el.animate([{ transform: 'translate3d(' + sx + 'vw,-' + (hv + 4) + 'vh,0)' }, { transform: 'translate3d(' + sx + 'vw,' + low + 'vh,0)', offset: .3 },
          { transform: 'translate3d(' + sx + 'vw,' + low + 'vh,0)', offset: .7 }, { transform: 'translate3d(' + sx + 'vw,-' + (hv + 4) + 'vh,0)' }], { duration: dur, easing: 'ease-in-out', fill: 'forwards' });
      } else if (m.spot === 'rise') {
        var top = 100 - hv + 3;
        an = el.animate([{ transform: 'translate3d(' + sx + 'vw,101vh,0)' }, { transform: 'translate3d(' + sx + 'vw,' + top + 'vh,0)', offset: .25 },
          { transform: 'translate3d(' + sx + 'vw,' + top + 'vh,0)', offset: .75 }, { transform: 'translate3d(' + sx + 'vw,101vh,0)' }], { duration: dur, easing: 'ease-in-out', fill: 'forwards' });
      } else {
        var sy = 6 + Math.random() * Math.max(1, 86 - hv);
        el.style.transform = 'translate3d(' + sx + 'vw,' + sy + 'vh,0)';
        var fr = m.blink ? [{ opacity: 0 }, { opacity: 1, offset: .15 }, { opacity: 1, offset: .5 }, { opacity: .1, offset: .54 }, { opacity: 1, offset: .58 }, { opacity: 1, offset: .8 }, { opacity: 0 }]
               : m.glitch ? [{ opacity: 0 }, { opacity: .9, offset: .08 }, { opacity: .3, offset: .1 }, { opacity: 1, offset: .14 }, { opacity: 1, offset: .55 }, { opacity: .2, offset: .57 }, { opacity: 1, offset: .6 }, { opacity: 1, offset: .85 }, { opacity: 0 }]
               : [{ opacity: 0, transform: el.style.transform + ' scale(.85)' }, { opacity: 1, transform: el.style.transform + ' scale(1)', offset: .15 }, { opacity: 1, transform: el.style.transform + ' scale(1)', offset: .82 }, { opacity: 0, transform: el.style.transform + ' scale(.9)' }];
        an = el.animate(fr, { duration: dur, fill: 'forwards' });
      }
      an.onfinish = function () { el.remove(); }; setTimeout(function () { el.remove(); }, dur + 1500); return;
    }
    var rtl = Math.random() < 0.5;
    el.className = 'pass' + (flipFor(rtl) ? ' rtl' : '');
    el.innerHTML = '<div class="dir">' + body + '</div>';
    container.appendChild(el);
    var y0 = opts.y != null ? opts.y : m.ground ? 96 - hv - Math.random() * 3 : m.y ? m.y[0] + Math.random() * (m.y[1] - m.y[0]) : 6 + Math.random() * Math.max(4, 64 - hv);
    var amp = m.ground ? 0.2 : (m.amp != null ? m.amp : 4), waves = m.waves || 2;
    var x0 = rtl ? 104 : -(wv + 4), x1 = rtl ? -(wv + 4) : 104;
    var frames = [], N = 12;
    for (var i = 0; i <= N; i++) {
      var t = i / N, x = x0 + (x1 - x0) * t, y = y0 + Math.sin(t * Math.PI * waves) * amp + (m.drift ? t * m.drift : 0);
      frames.push({ transform: 'translate3d(' + x + 'vw,' + y + 'vh,0) rotate(' + (m.tilt ? (rtl ? m.tilt : -m.tilt) : 0) + 'deg)', offset: t });
    }
    if (m.fade) { frames[0].opacity = 0; frames[2].opacity = 1; frames[N - 2].opacity = 1; frames[N].opacity = 0; }
    var a = el.animate(frames, { duration: dur, easing: 'linear', fill: 'forwards' });
    a.onfinish = function () { el.remove(); };
    setTimeout(function () { el.remove(); }, dur + 1500);
  }
  window.Passers = { fly: fly, kinds: Object.keys(DRAW), sprite: function (k) { return PX[k] ? buildPx(k) : null; }, html: function (k) { var d = DRAW[k]; return svg(d.vb, d.draw()); } };
})();
