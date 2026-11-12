/* Thème des widgets de la scène (couleur d'accent + police), réglé dans /admin/labels.
   Chargé par chaque overlay ; lit /api/labels/style et ajoute des règles CSS spécifiques à la page. */
(function () {
    var base = '';
    try { base = new URL(document.currentScript.src).origin; } catch (e) {}
    var path = location.pathname.replace(/\/+$/, '');
    var page = null;
    else if (path === '/overlay/twitch_poll') page = 'twitch_poll';
    else if (path === '/overlay/trophies') page = 'trophies';
    else if (path === '/overlay/time') page = 'time';
    else if (path === '/overlay/credits') page = 'credits';
    else if (/^\/overlay\/wheels?(\/\d+)?$/.test(path)) page = 'wheel';
    else if (path === '/shoutout') page = 'shoutout';
    else if (path === '/brb') page = 'brb';
    if (!page) return;

    function rgb(hex) {
        hex = hex.replace('#', '');
        if (hex.length === 3) hex = hex.split('').map(function (c) { return c + c; }).join('');
        return [parseInt(hex.substr(0, 2), 16), parseInt(hex.substr(2, 2), 16), parseInt(hex.substr(4, 2), 16)];
    }
    function rgba(hex, a) { var c = rgb(hex); return 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + a + ')'; }
    function light(hex, t) {  // éclaircit vers le blanc
        var c = rgb(hex);
        return 'rgb(' + c.map(function (v) { return Math.round(v + (255 - v) * t); }).join(',') + ')';
    }
    function dark(hex, t) {
        var c = rgb(hex);
        return 'rgb(' + c.map(function (v) { return Math.round(v * (1 - t)); }).join(',') + ')';
    }

    var RULES = {
        poll: function (a, a2, F) {
            return (a ? ':root{--border-color:' + rgba(a, 0.7) + ' !important;--accent:' + light(a, 0.35) + ' !important}'
                + '#poll-widget{box-shadow:0 25px 50px rgba(0,0,0,.8),0 0 30px ' + rgba(a, 0.4) + ' !important}'
                + '.opt-bar{background:' + rgba(a, 0.8) + ' !important}'
                + '.footer-note{border-color:' + rgba(a, 0.5) + ' !important;background:' + rgba(a2 || dark(a, 0.6), 0.25) + ' !important}' : '')
                + (F ? '.header-title,.question,.opt-pct{font-family:' + F + ' !important}' : '');
        },
        twitch_poll: function (a, a2, F) {
            return (a ? ':root{--twitch:' + a + ' !important}.timer{border-color:' + rgba(a, 0.4) + ' !important}' : '')
                + (F ? '.title,.timer{font-family:' + F + ' !important}' : '');
        },
        trophies: function (a, a2, F) {
            return (a ? '#trophy-container{border-color:' + a + ' !important;box-shadow:0 10px 30px rgba(0,0,0,.5),0 0 28px ' + rgba(a, 0.4) + ' !important}' : '')
                + (F ? '.text-box{font-family:' + F + ' !important}' : '');
        },
        time: function (a, a2, F) {
            return (a ? '.timer-widget{border-left-color:' + a + ' !important}'
                + '.display{color:' + a + ' !important;animation:none !important;filter:none !important;text-shadow:0 0 12px ' + rgba(a, 0.7) + ' !important}' : '')
                + (F ? '.label,.display{font-family:' + F + ' !important}' : '');
        },
        wheel: function (a, a2, F) {
            return (a ? '#wheel-disc{border-color:' + a + ' !important;box-shadow:0 0 0 4px rgba(15,23,42,.95),0 30px 70px rgba(0,0,0,.75),0 0 50px ' + rgba(a, 0.55) + ' !important}'
                + '#hub{background:radial-gradient(circle at 35% 30%,' + light(a2 || a, 0.45) + ',' + dark(a2 || a, 0.35) + ' 70%) !important}'
                + '#result-banner{border-color:' + a + ' !important;box-shadow:0 20px 45px rgba(0,0,0,.6),0 0 30px ' + rgba(a, 0.35) + ' !important}'
                + '#result-banner .label{color:' + a + ' !important}' : '')
                + (F ? '#result-banner .value,.segment-label{font-family:' + F + ' !important}' : '');
        },
        shoutout: function (a, a2, F) {
            return (a ? '.video-box,.card{border-color:' + a + ' !important}'
                + '#avatar{border-color:' + a + ' !important}'
                + '.meta{color:' + light(a, 0.35) + ' !important}'
                + '#progress{background:' + light(a, 0.35) + ' !important;box-shadow:0 0 15px ' + a + ' !important}'
                + '.twitch-logo{color:' + a + ' !important}'
                + '#tiktok{border-color:' + a + ' !important;box-shadow:0 25px 50px rgba(0,0,0,.8),0 0 30px ' + rgba(a, 0.4) + ' !important}'
                + '.tt-badge{background:' + a + ' !important}' : '')
                + (F ? '#name,.tt-badge{font-family:' + F + ' !important}' : '');
        },
        credits: function (a, a2, F, s) {
            var spooky = s && (s.icon_set === 'halloween' || s.preset === 'halloween');
            var second = a2 ? light(a2, 0.45) : (a ? light(a, 0.5) : '');
            return (a ? '.main-title{color:' + light(a, 0.25) + ' !important;text-shadow:0 0 18px ' + rgba(a, 0.9) + ',0 8px 40px ' + rgba(a, 0.6) + ' !important}'
                + '.sub-title{color:' + second + ' !important;text-shadow:0 0 16px ' + rgba(a2 || a, 0.7) + ' !important}'
                + '.section:nth-of-type(odd) .section-title{color:' + a + ' !important;text-shadow:0 0 14px ' + rgba(a, 0.55) + ' !important}'
                + '.section:nth-of-type(even) .section-title{color:' + second + ' !important;text-shadow:0 0 14px ' + rgba(a2 || a, 0.5) + ' !important}'
                + '.section-title{border-bottom:2px solid ' + rgba(a, 0.35) + ' !important}'
                + '.name-item{background:rgba(18,10,28,.88) !important;border:1px solid ' + rgba(a, 0.4) + ' !important;box-shadow:0 0 14px ' + rgba(a, 0.15) + ' !important}'
                + '.user-label{background:' + rgba(a, 0.16) + ' !important;color:' + light(a, 0.4) + ' !important}'
                + '.user-label .fa-star,.user-label .fa-clock{color:' + a + ' !important}' : '')
                + (F ? '.main-title,.sub-title,.section-title,.user-name{font-family:' + F + ' !important}.main-title,.section-title{letter-spacing:.06em !important}' : '')
                + (spooky ? '.main-title::before{content:"🎃 "}.main-title::after{content:" 🎃"}'
                          + '.section-title::before{content:"🦇 "}.section-title::after{content:" 🦇"}'
                          + '.sub-title::before{content:"👻 "}.sub-title::after{content:" 👻"}' : '');
        },
        brb: function (a, a2, F) {
            return (a ? '#container{border-color:' + a + ' !important}.bottom-bar{border-top-color:' + a + ' !important}'
                + '#progress{background:' + light(a, 0.35) + ' !important;box-shadow:0 0 15px ' + a + ' !important}' : '')
                + (F ? '#title{font-family:' + F + ' !important}' : '');
        }
    };

    var styleEl = document.createElement('style');
    styleEl.id = 'widget-theme';
    document.head.appendChild(styleEl);
    var fontLink = null, lastSig = null;

    function apply(s) {
        var sig = [s.w_accent, s.w_accent2, s.w_font, s.icon_set, s.preset].join('|');
        if (sig === lastSig) return;
        lastSig = sig;
        var F = s.w_font ? "'" + s.w_font.replace(/'/g, '') + "',cursive" : '';
        styleEl.textContent = RULES[page](s.w_accent || '', s.w_accent2 || '', F, s);
        if (fontLink) { fontLink.remove(); fontLink = null; }
        if (s.w_font) {
            fontLink = document.createElement('link');
            fontLink.rel = 'stylesheet';
            fontLink.href = 'https://fonts.googleapis.com/css2?family=' + encodeURIComponent(s.w_font).replace(/%20/g, '+') + '&display=swap';
            document.head.appendChild(fontLink);
        }
    }

    function refresh() {
        // Pages servies par Node (autre origine, pas de CORS côté bot) : on passe par le relais /api/theme-style
        var url = (base && base !== location.origin) ? location.origin + '/api/theme-style' : base + '/api/labels/style';
        fetch(url + '?t=' + Date.now(), { cache: 'no-store' })
            .then(function (r) { return r.json(); }).then(apply).catch(function () {});
    }
    refresh();
    setInterval(refresh, 15000);
})();
