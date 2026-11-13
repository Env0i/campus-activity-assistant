window.__esmOrder.push('l05');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['05'] = { id: 5, name: 'state-05' };
  window.__legacyLayers.view['05'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['05'].id; }
  };
  window.__legacyLayers.controller['05'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['05'].id,
        card: window.__legacyLayers.view['05'].render(),
        label: 'controller-05'
      };
    }
  };
})();
