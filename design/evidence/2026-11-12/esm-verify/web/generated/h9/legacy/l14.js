window.__esmOrder.push('l14');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['14'] = { id: 14, name: 'state-14' };
  window.__legacyLayers.view['14'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['14'].id; }
  };
  window.__legacyLayers.controller['14'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['14'].id,
        card: window.__legacyLayers.view['14'].render(),
        label: 'controller-14'
      };
    }
  };
})();
