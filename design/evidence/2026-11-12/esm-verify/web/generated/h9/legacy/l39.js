window.__esmOrder.push('l39');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['39'] = { id: 39, name: 'state-39' };
  window.__legacyLayers.view['39'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['39'].id; }
  };
  window.__legacyLayers.controller['39'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['39'].id,
        card: window.__legacyLayers.view['39'].render(),
        label: 'controller-39'
      };
    }
  };
})();
