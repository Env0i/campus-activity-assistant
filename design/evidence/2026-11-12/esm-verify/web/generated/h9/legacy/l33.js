window.__esmOrder.push('l33');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['33'] = { id: 33, name: 'state-33' };
  window.__legacyLayers.view['33'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['33'].id; }
  };
  window.__legacyLayers.controller['33'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['33'].id,
        card: window.__legacyLayers.view['33'].render(),
        label: 'controller-33'
      };
    }
  };
})();
