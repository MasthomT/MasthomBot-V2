/* Thème du bot pour une page HTML LOCALE d'OBS (fichier sur le PC, ex. overlay_scenes.html).
 *
 * Dans la page, ajouter dans <head> (adapter l'IP du serveur du bot) :
 *   <script src="http://192.168.1.110:8000/static/theme-vars.js"></script>
 * puis utiliser les variables dans le CSS :
 *   color: var(--theme-accent, #6366f1);   font-family: var(--theme-font, 'Inter'), sans-serif;
 *
 * Variables posées sur <html> (vides si le thème n'en définit pas) :
 *   --theme-accent, --theme-accent2, --theme-font (polices des titres), --theme-label-font,
 *   --theme-color, --theme-glow, --theme-icon-color
 * + attribut data-theme="halloween" | "classique" | "perso" sur <html>.
 * Le thème est relu toutes les 15 s : un changement dans /admin/labels est repris sans recharger OBS,
 * et il repasse tout seul au style classique à la date de fin du thème (31/10 pour Halloween).
 */
(function () {
    var host = 'localhost';
    try { host = new URL(document.currentScript.src).hostname; } catch (e) {}
    var API = 'http://' + host + ':8001/api/labels/style';      // port 8001 : CORS ouvert aux pages locales
    var root = document.documentElement, fontLinks = {};

    function loadFont(name) {
        if (!name || fontLinks[name]) return;
        var l = document.createElement('link');
        l.rel = 'stylesheet';
        l.href = 'https://fonts.googleapis.com/css2?family=' + encodeURIComponent(name).replace(/%20/g, '+') + '&display=swap';
        document.head.appendChild(l);
        fontLinks[name] = l;
    }
    function q(n) { return n ? "'" + String(n).replace(/'/g, '') + "'" : ''; }
    function set(k, v) { root.style.setProperty(k, v || ''); }

    function apply(s) {
        set('--theme-accent', s.w_accent); set('--theme-accent2', s.w_accent2);
        set('--theme-font', q(s.w_font)); set('--theme-label-font', q(s.font));
        set('--theme-color', s.color); set('--theme-glow', s.glow); set('--theme-icon-color', s.icon_color);
        root.setAttribute('data-theme', s.preset || 'classique');
        loadFont(s.w_font); loadFont(s.font);
    }
    function refresh() {
        fetch(API + '?t=' + Date.now(), { cache: 'no-store' }).then(function (r) { return r.json(); }).then(apply).catch(function () {});
    }
    refresh();
    setInterval(refresh, 15000);
})();
