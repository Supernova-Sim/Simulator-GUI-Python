// preview-fix.js
// Hefesto C4 Architecture Visualizer
// Intercepta cliques em nós de diagramas Mermaid (tags <a> dentro de <svg>)
// e despacha como cliques HTML padrão reconhecidos pelo roteador do Positron/VS Code.

(function () {
    window.addEventListener('click', function (event) {
        var target = event.target;
        if (!target) return;

        // Trata nós de texto dentro do SVG (nodeType === 3)
        var elem = target.nodeType === 3 ? target.parentElement : target;
        if (!elem) return;

        // Procura a tag <a> mais próxima (HTML ou SVG)
        var anchor = elem.closest ? elem.closest('a') : null;
        if (!anchor) {
            var cur = elem;
            while (cur && cur !== document.body && cur !== document) {
                if (cur.tagName && cur.tagName.toLowerCase() === 'a') {
                    anchor = cur;
                    break;
                }
                cur = cur.parentElement;
            }
        }
        if (!anchor) return;

        // Se for um link HTML normal (não-SVG), deixa o Positron/VS Code tratar nativamente
        var isSvg = anchor.ownerSVGElement || anchor.namespaceURI === 'http://www.w3.org/2000/svg' || (anchor.tagName && anchor.tagName === 'a');
        if (!isSvg) {
            return;
        }

        // Obtém o destino do link (suporta href, xlink:href ou SVGAnimatedString)
        var href = anchor.getAttribute('href') ||
                   anchor.getAttribute('xlink:href') ||
                   (anchor.href && (typeof anchor.href === 'string' ? anchor.href : anchor.href.baseVal));

        if (!href) return;

        // Previne o comportamento padrão e bloqueia a propagação do evento SVG
        event.preventDefault();
        event.stopPropagation();

        // Cria um elemento <a> HTML nativo para acionar o interceptador de links do VS Code
        var htmlAnchor = document.createElement('a');
        htmlAnchor.href = href;
        htmlAnchor.setAttribute('data-href', href);
        htmlAnchor.style.display = 'none';
        document.body.appendChild(htmlAnchor);

        try {
            var evt = new MouseEvent('click', {
                bubbles: true,
                cancelable: true,
                view: window
            });
            htmlAnchor.dispatchEvent(evt);
        } catch (e) {
            htmlAnchor.click();
        }

        setTimeout(function () {
            if (htmlAnchor.parentNode) {
                htmlAnchor.parentNode.removeChild(htmlAnchor);
            }
        }, 100);
    }, true);
})();
