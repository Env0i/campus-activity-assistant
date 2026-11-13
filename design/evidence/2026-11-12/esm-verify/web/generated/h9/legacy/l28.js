window.__esmOrder.push('l28');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['28'] = { id: 28, name: 'state-28' };
  window.__legacyLayers.view['28'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['28'].id; }
  };
  window.__legacyLayers.controller['28'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['28'].id,
        card: window.__legacyLayers.view['28'].render(),
        label: 'controller-28'
      };
    }
  };
})();
